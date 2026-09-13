"""Per-member behavioural simulation, churn assignment and row emission.

One member is simulated end to end:

1.  Behaviour is generated across the member's whole active window from their latent
    traits, a year-on-year drift and a seasonal factor.
2.  At each renewal anniversary, features are measured from the behaviour that has
    already happened, the published logistic model is applied, and the renewal outcome
    is sampled.
3.  Once a renewal lapses, every activity row after that date is discarded.  This is the
    step that makes the dataset causally coherent: activity leads churn, never the
    reverse.

Members are processed in chunks and rows are streamed straight to CSV, so peak memory
stays in the tens of megabytes even at full scale.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from . import config
from .features import (
    MemberTimeline,
    churn_log_odds,
    compute_features,
    engagement_score,
    risk_category,
    top_protective_factors,
    top_risk_factors,
)
from .templates import feedback_text, insight_text
from .utils import add_years, from_ordinal, iso, iso_ts, sigmoid, to_ordinal, week_start

# --------------------------------------------------------------------------------------
# Table schemas
# --------------------------------------------------------------------------------------

SCHEMAS = {
    "membership_history": [
        "membership_history_id",
        "member_id",
        "effective_from",
        "effective_to",
        "membership_type",
        "membership_status",
        "annual_fee",
        "renewal_outcome",
        "cancellation_reason",
    ],
    "website_activity": [
        "activity_id",
        "member_id",
        "activity_date",
        "session_count",
        "page_views",
        "content_downloads",
        "searches",
        "average_session_minutes",
        "device_type",
    ],
    "login_history": [
        "login_id",
        "member_id",
        "login_timestamp",
        "platform",
        "session_duration_minutes",
        "successful_login",
    ],
    "event_attendance": [
        "attendance_id",
        "event_id",
        "member_id",
        "registration_date",
        "attendance_status",
        "booking_channel",
        "feedback_score",
        "continuing_development_hours",
    ],
    "learning_activity": [
        "learning_activity_id",
        "member_id",
        "course_id",
        "activity_date",
        "completion_status",
        "completion_percentage",
        "assessment_score",
        "learning_minutes",
    ],
    "marketing_engagement": [
        "engagement_id",
        "member_id",
        "campaign_id",
        "sent_date",
        "delivered",
        "opened",
        "clicked",
        "converted",
        "unsubscribed",
    ],
    "member_feedback": [
        "feedback_id",
        "member_id",
        "submitted_date",
        "feedback_channel",
        "feedback_category",
        "rating",
        "feedback_text",
        "sentiment_label",
    ],
    "model_predictions": [
        "prediction_id",
        "prediction_run_id",
        "member_id",
        "prediction_date",
        "churn_probability",
        "risk_category",
        "predicted_churn",
        "engagement_score",
        "segment_id",
        "model_name",
        "model_version",
        "top_risk_factor_1",
        "top_risk_factor_2",
        "top_risk_factor_3",
    ],
    "ai_insights": [
        "insight_id",
        "prediction_run_id",
        "member_id",
        "insight_type",
        "executive_summary",
        "risk_explanation",
        "recommended_action",
        "llm_provider",
        "llm_model",
        "prompt_version",
        "generated_at",
        "validation_status",
    ],
    "member_training_features": [
        "member_id",
        "observation_date",
        "tenure_years",
        "logins_90d",
        "logins_prior_90d",
        "days_since_last_login",
        "web_sessions_90d",
        "web_sessions_prior_90d",
        "events_attended_365d",
        "learning_completions_365d",
        "campaigns_sent_180d",
        "campaign_open_rate_180d",
        "services_used",
        "min_rating_365d",
        "inactive_90_days",
        "negative_feedback",
        "failed_payment",
        "no_event_attendance",
        "declining_logins",
        "completed_learning",
        "attended_first_90_days",
        "auto_renewal",
        "long_tenure",
        "low_campaign_engagement",
        "fee_increase",
        "student_to_full_transition",
        "multi_service_user",
        "true_churn_probability",
        "churn_flag",
    ],
}

# --------------------------------------------------------------------------------------
# Rate parameters (per week unless stated otherwise)
# --------------------------------------------------------------------------------------

LOGIN_RATE = 1.05  # expected logins per week at affinity 1.0 and level 1.0
BROWSE_RATE = 0.30  # additional non-login web sessions per week
EVENT_RATE_YEAR = 7.5  # expected event registrations per year at affinity 1.0
LEARNING_RATE_YEAR = 3.5  # expected learning activities per year at affinity 1.0
SUPPORT_TICKET_RATE_YEAR = 0.15

#: Membership progression probabilities applied at a renewal.
UPGRADE_PATHS = {
    "Student": ("Associate", 1.00),  # forced at the student-to-full transition
    "Associate": ("Professional", 0.12),
    "Professional": ("Chartered", 0.06),
    "Chartered": ("Fellow", 0.02),
}

WEEKDAY_WEIGHTS = np.array([0.19, 0.19, 0.19, 0.17, 0.15, 0.06, 0.05])


@dataclass
class RunContext:
    """Everything the per-member simulation needs that is shared across members."""

    rng: np.random.Generator
    events: pd.DataFrame
    campaigns: pd.DataFrame
    courses: pd.DataFrame
    prediction_runs: list[int]
    insight_run: int
    as_of: int
    window_start: int

    def __post_init__(self):
        base = to_ordinal(config.EARLIEST_JOIN)
        span = self.as_of - base + 8
        days = np.arange(base, base + span)
        from .utils import seasonality

        self._season_base = base
        self.season = seasonality(days)

        # Event pools: online events are available to everyone, in-person events are
        # drawn from the member's own region.
        self.event_pools: dict[str, dict[str, np.ndarray]] = {}
        ev = self.events
        online = ev[ev["event_format"].isin(["Online", "Hybrid"])]
        self.event_pools["__online__"] = _pool(online)
        for region, grp in ev[~ev["event_format"].isin(["Online"])].groupby("region"):
            self.event_pools[region] = _pool(grp)

        self.campaign_start = self.campaigns["start_ord"].to_numpy()
        self.campaign_id = self.campaigns["campaign_id"].to_numpy()
        self.campaign_type = self.campaigns["campaign_type"].to_numpy()
        self.campaign_segment = self.campaigns["target_segment"].to_numpy()

        order = np.argsort(self.courses["launch_ord"].to_numpy())
        self.course_launch = self.courses["launch_ord"].to_numpy()[order]
        self.course_id = self.courses["course_id"].to_numpy()[order]
        self.course_minutes = self.courses["expected_minutes"].to_numpy()[order]

    def season_at(self, ords: np.ndarray) -> np.ndarray:
        idx = np.clip(np.asarray(ords) - self._season_base, 0, len(self.season) - 1)
        return self.season[idx]


def _pool(df: pd.DataFrame) -> dict[str, np.ndarray]:
    order = np.argsort(df["event_ord"].to_numpy())
    return {
        "ord": df["event_ord"].to_numpy()[order],
        "id": df["event_id"].to_numpy()[order],
        "category": df["event_category"].to_numpy()[order],
        "format": df["event_format"].to_numpy()[order],
    }


_CPD_HOURS = {
    "Conference": (6.0, 14.0),
    "Technical workshop": (3.0, 6.5),
    "Career development": (1.5, 3.5),
    "Webinar": (0.75, 1.5),
    "Regional branch meeting": (1.5, 3.0),
    "Networking": (0.0, 1.0),
    "Awards and celebration": (0.0, 0.0),
}


# --------------------------------------------------------------------------------------
# Per-member simulation
# --------------------------------------------------------------------------------------


def simulate_member(m, ctx: RunContext, ids: dict[str, int], writers) -> dict:
    """Simulate one member and write their rows.  Returns a summary dict for the
    member dimension (final status, fee, churn outcome)."""
    rng = ctx.rng
    join_ord = int(m.join_ord)
    sim_start = max(join_ord, ctx.window_start)
    sim_end = ctx.as_of
    if sim_start > sim_end:  # should not happen, but keeps the loop total
        sim_start = sim_end

    weeks = np.arange(week_start(sim_start), sim_end + 1, 7)
    if weeks.size == 0:
        weeks = np.array([week_start(sim_start)])
    years_since_join = (weeks - join_ord) / 365.25
    level = np.exp(m.drift * years_since_join) * ctx.season_at(weeks)
    level = np.clip(level, 0.02, 3.0)

    # --- Logins -----------------------------------------------------------------------
    login_lam = LOGIN_RATE * m.web_affinity * level
    login_counts = rng.poisson(login_lam)
    n_logins = int(login_counts.sum())
    if n_logins:
        offsets = rng.choice(7, size=n_logins, p=WEEKDAY_WEIGHTS)
        login_ords = np.repeat(weeks, login_counts) + offsets
        keep = (login_ords >= sim_start) & (login_ords <= sim_end)
        login_ords = np.sort(login_ords[keep])
    else:
        login_ords = np.empty(0, dtype=int)

    # --- Weekly website activity ------------------------------------------------------
    browse = rng.poisson(BROWSE_RATE * m.web_affinity * level)
    sessions = login_counts + browse
    web_mask = sessions > 0
    web_week_ords = weeks[web_mask]
    web_sessions = sessions[web_mask]

    # --- Event registrations ----------------------------------------------------------
    ev_lam = EVENT_RATE_YEAR * m.event_affinity * level / 52.0
    ev_counts = rng.poisson(ev_lam)
    ev_weeks = np.repeat(weeks, ev_counts)
    ev_rows, attended_ords = _draw_events(rng, ctx, m, ev_weeks, sim_start, sim_end)

    # --- Learning ---------------------------------------------------------------------
    lr_lam = LEARNING_RATE_YEAR * m.learning_affinity * level / 52.0
    lr_counts = rng.poisson(lr_lam)
    lr_days = np.repeat(weeks, lr_counts) + rng.integers(0, 7, int(lr_counts.sum()))
    lr_days = np.sort(lr_days[(lr_days >= sim_start) & (lr_days <= sim_end)])
    lr_rows, learning_completed_ords = _draw_learning(rng, ctx, m, lr_days)

    # --- Marketing --------------------------------------------------------------------
    mk_rows, sent_ords, opened_flags, survey_ords = _draw_marketing(rng, ctx, m, sim_start, sim_end)

    # --- Feedback ---------------------------------------------------------------------
    fb_rows = _draw_feedback(rng, m, attended_ords, survey_ords, sim_start, sim_end, level, weeks)
    fb_ords = np.array([r[0] for r in fb_rows], dtype=int) if fb_rows else np.empty(0, dtype=int)
    fb_ratings = np.array([r[3] for r in fb_rows], dtype=float) if fb_rows else np.empty(0, dtype=float)
    order = np.argsort(fb_ords)
    fb_ords, fb_ratings = fb_ords[order], fb_ratings[order]
    fb_rows = [fb_rows[i] for i in order]

    timeline = MemberTimeline(
        join_ord=join_ord,
        login_ords=login_ords,
        web_week_ords=web_week_ords,
        web_sessions=web_sessions,
        attended_ords=attended_ords,
        learning_ords=lr_days,
        learning_completed_ords=learning_completed_ords,
        campaign_sent_ords=sent_ords,
        campaign_opened=opened_flags,
        feedback_ords=fb_ords,
        feedback_ratings=fb_ratings,
    )

    # --- Renewals and churn -----------------------------------------------------------
    outcome = _run_renewals(rng, ctx, m, timeline, ids, writers)
    churn_ord = outcome["churn_ord"]

    # --- Truncate activity after churn ------------------------------------------------
    if churn_ord is not None:
        login_ords = login_ords[login_ords < churn_ord]
        keep_web = web_week_ords < churn_ord
        web_week_ords, web_sessions = web_week_ords[keep_web], web_sessions[keep_web]
        ev_rows = [r for r in ev_rows if r[0] < churn_ord]
        lr_rows = [r for r in lr_rows if r[0] < churn_ord]
        mk_rows = [r for r in mk_rows if r[0] < churn_ord]
        fb_rows = [r for r in fb_rows if r[0] < churn_ord]
        # Exit survey: the most informative free text in the dataset.
        if rng.random() < 0.55:
            fb_rows.append(_exit_feedback(rng, m, outcome, churn_ord))

    _emit(m, ids, writers, login_ords, web_week_ords, web_sessions, ev_rows, lr_rows, mk_rows, fb_rows, rng)

    # --- Scoring runs -----------------------------------------------------------------
    _emit_predictions(rng, ctx, m, timeline, outcome, ids, writers)

    return outcome


# --------------------------------------------------------------------------------------
# Component draws
# --------------------------------------------------------------------------------------


def _draw_events(rng, ctx: RunContext, m, ev_weeks, sim_start, sim_end):
    rows, attended = [], []
    if ev_weeks.size == 0:
        return rows, np.empty(0, dtype=int)

    regional = ctx.event_pools.get(m.region)
    online = ctx.event_pools["__online__"]
    prefer_online = rng.random(ev_weeks.size) < 0.62

    for i, wk in enumerate(ev_weeks):
        pool = online if (prefer_online[i] or regional is None) else regional
        lo = np.searchsorted(pool["ord"], wk, "left")
        hi = np.searchsorted(pool["ord"], wk + 75, "right")
        if hi <= lo:
            continue
        j = int(rng.integers(lo, hi))
        ev_ord = int(pool["ord"][j])
        lead = int(rng.integers(1, 46))
        reg_ord = max(ev_ord - lead, sim_start)
        if reg_ord > sim_end:
            continue

        if ev_ord > ctx.as_of:
            status = "Registered"
        elif rng.random() < 0.03:
            status = "Waitlisted"
        else:
            p_attend = float(np.clip(0.50 + 0.35 * m.engagement - (0.10 if pool["format"][j] == "Online" else 0.0), 0.05, 0.95))
            r = rng.random()
            status = "Attended" if r < p_attend else ("No-show" if r < p_attend + (1 - p_attend) * 0.45 else "Cancelled")

        score = ""
        cpd = 0.0
        if status == "Attended":
            attended.append(ev_ord)
            lo_h, hi_h = _CPD_HOURS[pool["category"][j]]
            cpd = round(float(rng.uniform(lo_h, hi_h)), 2)
            if rng.random() < 0.62:
                score = int(np.clip(round(1 + 4 * min(max(m.satisfaction + rng.normal(0, 0.13), 0.0), 1.0)), 1, 5))

        rows.append(
            (
                reg_ord,
                pool["id"][j],
                str(rng.choice([c for c, _ in config.BOOKING_CHANNELS], p=[p for _, p in config.BOOKING_CHANNELS])),
                status,
                score,
                cpd if status == "Attended" else "",
            )
        )

    return rows, np.sort(np.array(attended, dtype=int))


def _draw_learning(rng, ctx: RunContext, m, days):
    rows, completed = [], []
    if days.size == 0:
        return rows, np.empty(0, dtype=int)

    p_complete = float(np.clip(0.22 + 0.58 * m.learning_affinity, 0.05, 0.95))
    for day in days:
        hi = np.searchsorted(ctx.course_launch, day, "right")
        if hi == 0:
            continue
        j = int(rng.integers(0, hi))
        expected = float(ctx.course_minutes[j])

        r = rng.random()
        if r < p_complete:
            status, pct_done = "Completed", 100.0
        elif r < p_complete + 0.22:
            status, pct_done = "In progress", round(float(rng.uniform(15, 85)), 1)
        elif r < p_complete + 0.32:
            status, pct_done = "Abandoned", round(float(rng.uniform(3, 40)), 1)
        else:
            status, pct_done = "Not started", 0.0

        minutes = round(expected * (pct_done / 100.0) * float(rng.uniform(0.7, 1.45)), 1)
        if status == "Completed":
            completed.append(int(day))
            score = int(np.clip(rng.normal(68 + 22 * m.learning_affinity, 9), 35, 100))
        else:
            score = ""
        rows.append((int(day), ctx.course_id[j], status, pct_done, score, minutes))

    return rows, np.sort(np.array(completed, dtype=int))


_SEGMENT_ELIGIBILITY = {
    "All members": lambda m, tenure: True,
    "Highly engaged": lambda m, tenure: m.engagement > 0.60,
    "Learning audience": lambda m, tenure: m.learning_affinity > 0.50,
    "Student and early career": lambda m, tenure: m.career_stage in ("Student", "Early career"),
    "New joiners": lambda m, tenure: tenure < 1.0,
    "Lapsing risk": lambda m, tenure: m.engagement < 0.40,
    "Regional audience": lambda m, tenure: True,  # narrowed by a random draw below
}


def _draw_marketing(rng, ctx: RunContext, m, sim_start, sim_end):
    if not m.communication_consent:
        return [], np.empty(0, dtype=int), np.empty(0, dtype=bool), np.empty(0, dtype=int)

    in_window = (ctx.campaign_start >= sim_start) & (ctx.campaign_start <= sim_end)
    idx = np.flatnonzero(in_window)
    if idx.size == 0:
        return [], np.empty(0, dtype=int), np.empty(0, dtype=bool), np.empty(0, dtype=int)

    tenure = (ctx.campaign_start[idx] - m.join_ord) / 365.25
    keep = []
    for k, i in enumerate(idx):
        seg = ctx.campaign_segment[i]
        if not _SEGMENT_ELIGIBILITY.get(seg, lambda *_: True)(m, tenure[k]):
            continue
        if seg == "Regional audience" and rng.random() > 0.28:
            continue
        keep.append(i)
    if not keep:
        return [], np.empty(0, dtype=int), np.empty(0, dtype=bool), np.empty(0, dtype=int)

    idx = np.array(keep)
    n = idx.size
    sent = ctx.campaign_start[idx] + rng.integers(0, 3, n)
    ctype = ctx.campaign_type[idx]

    level = np.clip(np.exp(m.drift * (sent - m.join_ord) / 365.25), 0.05, 2.0)
    delivered = rng.random(n) < 0.965
    open_p = np.clip(
        0.10 + 0.55 * m.email_affinity * level + np.where(ctype == "Renewal reminder", 0.18, 0.0) + np.where(ctype == "Member survey", -0.05, 0.0),
        0.01,
        0.95,
    )
    opened = delivered & (rng.random(n) < open_p)
    clicked = opened & (rng.random(n) < np.clip(0.16 + 0.42 * m.email_affinity, 0.02, 0.9))
    converted = clicked & (rng.random(n) < np.clip(0.10 + 0.28 * m.engagement, 0.01, 0.7))
    unsub = delivered & (rng.random(n) < (0.003 + 0.018 * (1.0 - m.satisfaction)))

    # Stop sending after the first unsubscribe.
    prior_unsub = np.concatenate([[0], np.cumsum(unsub)[:-1]])
    alive = prior_unsub == 0
    idx, sent, delivered, opened, clicked, converted, unsub, ctype = (
        idx[alive],
        sent[alive],
        delivered[alive],
        opened[alive],
        clicked[alive],
        converted[alive],
        unsub[alive],
        ctype[alive],
    )

    rows = [
        (int(sent[k]), ctx.campaign_id[idx[k]], bool(delivered[k]), bool(opened[k]), bool(clicked[k]), bool(converted[k]), bool(unsub[k]))
        for k in range(idx.size)
    ]
    survey_ords = sent[(ctype == "Member survey") & opened]
    return rows, np.sort(sent), opened[np.argsort(sent)], survey_ords


def _rating_from(rng, m, at_level: float) -> int:
    base = m.satisfaction * 0.75 + 0.25 * float(np.clip(at_level, 0, 1.2)) / 1.2
    return int(np.clip(round(1 + 4 * float(np.clip(base + rng.normal(0, 0.14), 0, 1))), 1, 5))


def _draw_feedback(rng, m, attended_ords, survey_ords, sim_start, sim_end, level, weeks):
    rows = []

    def level_at(day: int) -> float:
        i = int(np.clip(np.searchsorted(weeks, day, "right") - 1, 0, len(level) - 1))
        return float(level[i])

    # Post-event feedback
    for ev_ord in attended_ords:
        if rng.random() < 0.11:
            day = int(ev_ord + rng.integers(0, 5))
            if day > sim_end:
                continue
            rating = _rating_from(rng, m, level_at(day))
            text, sentiment = feedback_text(rng, "Events and content", rating)
            rows.append((day, "Event feedback form", "Events and content", rating, text, sentiment))

    # Annual survey responses
    for s_ord in survey_ords:
        if rng.random() < 0.33:
            day = int(s_ord + rng.integers(0, 12))
            if day > sim_end:
                continue
            category = str(rng.choice(config.FEEDBACK_CATEGORIES))
            rating = _rating_from(rng, m, level_at(day))
            text, sentiment = feedback_text(rng, category, rating)
            rows.append((day, "Annual member survey", category, rating, text, sentiment))

    # Support tickets and unsolicited website feedback
    years = max((sim_end - sim_start) / 365.25, 0.0)
    n_tickets = rng.poisson(SUPPORT_TICKET_RATE_YEAR * years * (1.6 - m.satisfaction))
    for _ in range(int(n_tickets)):
        day = int(rng.integers(sim_start, sim_end + 1))
        channel = str(rng.choice(["Support ticket", "Website feedback widget"], p=[0.62, 0.38]))
        category = str(rng.choice(["Customer service", "Website and digital services", "Fees and billing", "Communications"], p=[0.31, 0.29, 0.22, 0.18]))
        rating = int(np.clip(_rating_from(rng, m, level_at(day)) - 1, 1, 5))
        text, sentiment = feedback_text(rng, category, rating)
        rows.append((day, channel, category, rating, text, sentiment))

    return rows


def _exit_feedback(rng, m, outcome, churn_ord):
    reason = outcome["cancellation_reason"] or "Membership value"
    category = {
        "Cost or affordability": "Fees and billing",
        "Lack of relevance to my role": "Events and content",
        "Not enough time to use benefits": "Membership value",
        "Employer no longer funding": "Fees and billing",
        "Joined an alternative body": "Membership value",
        "Career change or retirement": "Membership value",
        "Service dissatisfaction": "Customer service",
    }.get(reason, "Membership value")
    rating = int(np.clip(round(1 + 4 * float(np.clip(m.satisfaction - 0.30 + rng.normal(0, 0.12), 0, 1))), 1, 5))
    text, sentiment = feedback_text(rng, category, rating)
    return (int(churn_ord), "Cancellation survey", category, rating, text, sentiment)


# --------------------------------------------------------------------------------------
# Renewals, churn and membership history
# --------------------------------------------------------------------------------------


def _run_renewals(rng, ctx: RunContext, m, tl: MemberTimeline, ids, writers) -> dict:
    join_ord = int(m.join_ord)
    fee = float(m.base_fee)
    mtype = m.membership_type
    auto = bool(m.auto_renewal)

    term_start = join_ord
    history: list[tuple] = []
    churn_ord = None
    cancellation_reason = ""
    last_failed_payment = False
    last_renewal = join_ord

    k = 1
    while True:
        r = add_years(join_ord, k)
        if r > ctx.as_of:
            break
        last_renewal = r

        # Pricing: a standard uplift most years, a larger repricing occasionally.
        big_uplift = rng.random() < 0.20
        uplift = 0.09 if big_uplift else config.ANNUAL_FEE_UPLIFT
        new_fee = round(fee * (1 + uplift), 2)
        fee_increase = bool(big_uplift and m.price_sensitivity > 0.60)

        student_transition = mtype == "Student" and (r - join_ord) / 365.25 >= 3.0

        if r < ctx.window_start:
            # Pre-window renewals are assumed successful: the member is still here.
            outcome_label = "Renewed"
            failed_payment = False
        else:
            failed_payment = rng.random() < config.FAILED_PAYMENT_RATE["auto" if auto else "manual"]
            feats = compute_features(
                tl,
                r,
                auto_renewal=auto,
                failed_payment=failed_payment,
                fee_increase=fee_increase,
                student_transition=student_transition,
            )
            p = sigmoid(churn_log_odds(feats))
            churned = rng.random() < p

            writers["member_training_features"].write_rows(
                [
                    [
                        m.member_id,
                        iso(r),
                        feats["tenure_years"],
                        feats["logins_90d"],
                        feats["logins_prior_90d"],
                        feats["days_since_last_login"],
                        round(feats["web_sessions_90d"], 1),
                        round(feats["web_sessions_prior_90d"], 1),
                        feats["events_attended_365d"],
                        feats["learning_completions_365d"],
                        feats["campaigns_sent_180d"],
                        feats["campaign_open_rate_180d"],
                        feats["services_used"],
                        "" if feats["min_rating_365d"] is None else feats["min_rating_365d"],
                        feats["inactive_90_days"],
                        feats["negative_feedback"],
                        feats["failed_payment"],
                        feats["no_event_attendance"],
                        feats["declining_logins"],
                        feats["completed_learning"],
                        feats["attended_first_90_days"],
                        feats["auto_renewal"],
                        feats["long_tenure"],
                        feats["low_campaign_engagement"],
                        feats["fee_increase"],
                        feats["student_to_full_transition"],
                        feats["multi_service_user"],
                        round(float(p), 4),
                        int(churned),
                    ]
                ]
            )

            if churned:
                voluntary = rng.random() < 0.55
                outcome_label = "Cancelled" if voluntary else "Lapsed"
                cancellation_reason = _pick_reason(rng, m, feats)
                history.append((term_start, r, mtype, outcome_label, fee, outcome_label, cancellation_reason))
                churn_ord = r
                break
            outcome_label = "Renewed"

        # Membership progression.
        new_type = mtype
        if student_transition:
            new_type = "Associate" if m.career_stage in ("Student", "Early career") else "Professional"
            outcome_label = "Upgraded"
        elif mtype in UPGRADE_PATHS and rng.random() < UPGRADE_PATHS[mtype][1] * (1.5 if tl.learning_completed_ords.size > 2 else 1.0):
            new_type = UPGRADE_PATHS[mtype][0]
            outcome_label = "Upgraded"
        elif m.age_band == "65+" and mtype != "Retired" and rng.random() < 0.12:
            new_type = "Retired"
            outcome_label = "Downgraded"

        history.append((term_start, r, mtype, "Active", fee, outcome_label, ""))
        if new_type != mtype:
            mtype = new_type
            fee = float({t: f for t, f, _ in config.MEMBERSHIP_TYPES}[mtype]) * (fee / max(float(m.base_fee), 1.0))
            fee = round(fee, 2)
        else:
            fee = new_fee
        last_failed_payment = failed_payment
        term_start = r
        k += 1

    # Current open term.
    if churn_ord is None:
        history.append((term_start, None, mtype, "Active", fee, "", ""))
        renewal_date = add_years(join_ord, k)
        status = "Suspended" if (last_failed_payment and ctx.as_of - last_renewal < 45) else "Active"
    else:
        renewal_date = None
        status = history[-1][5] if history[-1][5] in ("Lapsed", "Cancelled") else "Lapsed"

    for term in history:
        if term[1] is not None and term[1] < ctx.window_start:
            continue  # terms that ended before the activity window are out of scope
        ids["membership_history"] += 1
        writers["membership_history"].write_rows(
            [
                [
                    f"MH{ids['membership_history']:08d}",
                    m.member_id,
                    iso(term[0]),
                    "" if term[1] is None else iso(term[1] - 1),
                    term[2],
                    term[3],
                    round(term[4], 2),
                    term[5],
                    term[6],
                ]
            ]
        )

    return {
        "member_id": m.member_id,
        "churn_ord": churn_ord,
        "churn_flag": int(churn_ord is not None),
        "membership_status": status,
        "membership_type": mtype,
        "annual_fee": round(fee, 2),
        "renewal_ord": renewal_date,
        "cancellation_reason": cancellation_reason,
    }


def _pick_reason(rng, m, feats) -> str:
    weights = {name: w for name, w in config.CANCELLATION_REASONS}
    if feats["fee_increase"] or m.price_sensitivity > 0.7:
        weights["Cost or affordability"] *= 2.4
    if feats["no_event_attendance"]:
        weights["Lack of relevance to my role"] *= 1.9
    if feats["inactive_90_days"]:
        weights["Not enough time to use benefits"] *= 1.8
    if feats["negative_feedback"]:
        weights["Service dissatisfaction"] *= 3.0
    if m.age_band == "65+":
        weights["Career change or retirement"] *= 3.5
    if m.organisation_type in ("Private sector - large", "Public sector"):
        weights["Employer no longer funding"] *= 1.6
    names = list(weights)
    p = np.array([weights[n] for n in names], dtype=float)
    return str(rng.choice(names, p=p / p.sum()))


# --------------------------------------------------------------------------------------
# Row emission
# --------------------------------------------------------------------------------------


def _emit(m, ids, writers, login_ords, web_weeks, web_sessions, ev_rows, lr_rows, mk_rows, fb_rows, rng):
    mid = m.member_id

    # Logins
    n = login_ords.size
    if n:
        minute = np.where(
            rng.random(n) < 0.68,
            rng.normal(10 * 60 + 30, 110, n),
            rng.normal(20 * 60 + 15, 95, n),
        )
        minute = np.clip(minute, 5, 23 * 60 + 55).astype(int)
        platform = rng.choice([p for p, _ in config.LOGIN_PLATFORMS], size=n, p=[p for _, p in config.LOGIN_PLATFORMS])
        duration = np.round(np.clip(rng.lognormal(2.05, 0.75, n), 0.5, 180), 1)
        success = rng.random(n) > 0.038
        start = ids["login_history"]
        writers["login_history"].write_rows(
            [
                [f"LG{start + i + 1:09d}", mid, iso_ts(int(login_ords[i]), int(minute[i])), platform[i], float(duration[i]), bool(success[i])]
                for i in range(n)
            ]
        )
        ids["login_history"] += n

    # Weekly website activity
    n = web_weeks.size
    if n:
        s = web_sessions.astype(float)
        page_views = np.round(s * (2.1 + rng.gamma(2.0, 1.5, n))).astype(int)
        downloads = rng.poisson(np.clip(0.30 * s * m.learning_affinity, 0, None))
        searches = rng.poisson(np.clip(0.55 * s, 0, None))
        avg_minutes = np.round(np.clip(rng.lognormal(1.75, 0.6, n), 0.4, 120), 1)
        device = rng.choice([d for d, _ in config.DEVICE_TYPES], size=n, p=[p for _, p in config.DEVICE_TYPES])
        start = ids["website_activity"]
        writers["website_activity"].write_rows(
            [
                [
                    f"WA{start + i + 1:09d}",
                    mid,
                    iso(int(web_weeks[i])),
                    int(web_sessions[i]),
                    int(page_views[i]),
                    int(downloads[i]),
                    int(searches[i]),
                    float(avg_minutes[i]),
                    device[i],
                ]
                for i in range(n)
            ]
        )
        ids["website_activity"] += n

    if ev_rows:
        start = ids["event_attendance"]
        writers["event_attendance"].write_rows(
            [[f"AT{start + i + 1:09d}", r[1], mid, iso(r[0]), r[3], r[2], r[4], r[5]] for i, r in enumerate(ev_rows)]
        )
        ids["event_attendance"] += len(ev_rows)

    if lr_rows:
        start = ids["learning_activity"]
        writers["learning_activity"].write_rows(
            [[f"LA{start + i + 1:09d}", mid, r[1], iso(r[0]), r[2], r[3], r[4], r[5]] for i, r in enumerate(lr_rows)]
        )
        ids["learning_activity"] += len(lr_rows)

    if mk_rows:
        start = ids["marketing_engagement"]
        writers["marketing_engagement"].write_rows(
            [[f"ME{start + i + 1:09d}", mid, r[1], iso(r[0]), r[2], r[3], r[4], r[5], r[6]] for i, r in enumerate(mk_rows)]
        )
        ids["marketing_engagement"] += len(mk_rows)

    if fb_rows:
        start = ids["member_feedback"]
        writers["member_feedback"].write_rows(
            [[f"FB{start + i + 1:08d}", mid, iso(r[0]), r[1], r[2], r[3], r[4], r[5]] for i, r in enumerate(fb_rows)]
        )
        ids["member_feedback"] += len(fb_rows)


# --------------------------------------------------------------------------------------
# Scoring runs and AI insights
# --------------------------------------------------------------------------------------


def _segment_id(feats: dict, prob: float, score: float) -> int:
    if feats["tenure_years"] < 1.0:
        return 7
    if prob >= config.RISK_THRESHOLDS["medium_max"] or score < 12:
        return 6
    if score >= 60 and feats["events_attended_365d"] >= 2 and feats["learning_completions_365d"] >= 1:
        return 1
    if feats["learning_completions_365d"] >= 2:
        return 3
    if feats["events_attended_365d"] >= 2:
        return 4
    if feats["auto_renewal"] and score < 30:
        return 5
    return 2


def _emit_predictions(rng, ctx: RunContext, m, tl: MemberTimeline, outcome, ids, writers):
    churn_ord = outcome["churn_ord"]
    for run_ord in ctx.prediction_runs:
        if m.join_ord > run_ord - 30:
            continue
        if churn_ord is not None and churn_ord <= run_ord:
            continue

        feats = compute_features(tl, run_ord, auto_renewal=bool(m.auto_renewal))
        true_lo = churn_log_odds(feats)
        # The "model" sees a noisy version of the truth, which is what gives the
        # prediction table realistic (rather than perfect) discrimination.
        # Round before banding, so that risk_category always agrees with the probability
        # as it appears in the exported file.
        prob = round(float(sigmoid(true_lo + rng.normal(0, config.PREDICTION_NOISE_SD))), 4)
        cat = risk_category(prob)
        score = engagement_score(feats)
        factors = top_risk_factors(feats, 3)
        factors += [""] * (3 - len(factors))

        ids["model_predictions"] += 1
        writers["model_predictions"].write_rows(
            [
                [
                    f"PR{ids['model_predictions']:09d}",
                    f"RUN-{iso(run_ord)}",
                    m.member_id,
                    iso(run_ord),
                    prob,
                    cat,
                    int(prob >= config.PREDICTION_THRESHOLD),
                    score,
                    _segment_id(feats, prob, score),
                    config.MODEL_NAME,
                    config.MODEL_VERSION,
                    factors[0],
                    factors[1],
                    factors[2],
                ]
            ]
        )

        # Insights are generated for the latest run only, for everyone above low risk
        # plus a sample of low-risk members so the report has comparison cases.
        if run_ord == ctx.insight_run and (cat != "Low" or rng.random() < 0.06):
            summary, explanation, action = insight_text(
                rng,
                member_id=m.member_id,
                probability=prob,
                risk_level=cat,
                factors=[f for f in factors if f],
                protective=top_protective_factors(feats, 2),
                features=feats,
            )
            ids["ai_insights"] += 1
            writers["ai_insights"].write_rows(
                [
                    [
                        f"IN{ids['ai_insights']:08d}",
                        f"RUN-{iso(run_ord)}",
                        m.member_id,
                        "Member retention brief",
                        summary,
                        explanation,
                        action,
                        config.LLM_PROVIDER,
                        config.LLM_MODEL,
                        config.PROMPT_VERSION,
                        iso_ts(run_ord, int(rng.integers(60, 400))),
                        "Template",
                    ]
                ]
            )


def prediction_run_dates(n_runs: int, as_of: int) -> list[int]:
    """Month-end scoring dates, oldest first, ending on the as-of date."""
    runs = []
    d = from_ordinal(as_of)
    for i in range(n_runs):
        year, month = d.year, d.month - i
        while month <= 0:
            month += 12
            year -= 1
        nxt = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(1)
        runs.append(min(to_ordinal(nxt.date()), as_of))
    return sorted(set(runs))
