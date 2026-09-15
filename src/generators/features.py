"""Behavioural feature extraction and the churn data-generating process.

This module is the heart of the dataset.  Churn is never drawn at random: it is sampled
from a logistic model whose inputs are features measured from activity that was
generated *before* the renewal decision.  The coefficients are the ones published in
``Data Recomendations.md``, plus four documented extensions.

The same feature extractor is used at renewal dates (to decide churn) and at monthly
scoring dates (to populate ``model_predictions``), so the features a downstream
model sees are exactly the features that generated the label.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import ADVOCACY_WINDOW_DAYS, CHURN_COEFFICIENTS, RISK_THRESHOLDS

#: Human-readable labels used for top_risk_factor_* and LLM prompts.
RISK_FACTOR_LABELS = {
    "inactive_90_days": "No logins in the last 90 days",
    "negative_feedback": "Negative feedback submitted in the last year",
    "failed_payment": "Failed renewal payment",
    "no_event_attendance": "No event attendance in the last year",
    "declining_logins": "Login frequency down sharply on the previous quarter",
    "low_campaign_engagement": "Rarely opens member communications",
    "fee_increase": "Fee increase for a price-sensitive member",
    "student_to_full_transition": "Moving off the student rate to a full subscription",
    "completed_learning": "Completed learning in the last year",
    "attended_first_90_days": "Attended an event within 90 days of joining",
    "auto_renewal": "Continuous payment mandate in place",
    "long_tenure": "Long-standing member (5+ years)",
    "multi_service_user": "Uses three or more member services",
    "no_recent_advocacy": "Has not referred anyone in the last year",
}

#: Features that raise churn risk, ordered for tie-breaking in explanations.
RISK_FEATURES = [
    "inactive_90_days",
    "failed_payment",
    "negative_feedback",
    "no_event_attendance",
    "declining_logins",
    "student_to_full_transition",
    "low_campaign_engagement",
    "fee_increase",
    "no_recent_advocacy",
]

PROTECTIVE_FEATURES = [
    "completed_learning",
    "attended_first_90_days",
    "auto_renewal",
    "long_tenure",
    "multi_service_user",
]


@dataclass
class MemberTimeline:
    """All behaviour generated for one member, as day-ordinal arrays."""

    join_ord: int
    login_ords: np.ndarray
    web_week_ords: np.ndarray
    web_sessions: np.ndarray
    attended_ords: np.ndarray
    learning_ords: np.ndarray
    learning_completed_ords: np.ndarray
    campaign_sent_ords: np.ndarray
    campaign_opened: np.ndarray
    feedback_ords: np.ndarray
    feedback_ratings: np.ndarray
    referral_ords: np.ndarray


def _count_between(sorted_ords: np.ndarray, lo: int, hi: int) -> int:
    """Number of entries in ``[lo, hi)``."""
    if sorted_ords.size == 0:
        return 0
    return int(np.searchsorted(sorted_ords, hi, "left") - np.searchsorted(sorted_ords, lo, "left"))


def compute_features(
    tl: MemberTimeline,
    at: int,
    *,
    auto_renewal: bool,
    failed_payment: bool = False,
    fee_increase: bool = False,
    student_transition: bool = False,
) -> dict:
    """Measure the churn model's inputs as they stood on day ``at``."""
    logins_90 = _count_between(tl.login_ords, at - 90, at)
    logins_prior_90 = _count_between(tl.login_ords, at - 180, at - 90)
    events_365 = _count_between(tl.attended_ords, at - 365, at)
    learning_365 = _count_between(tl.learning_completed_ords, at - 365, at)
    learning_any_365 = _count_between(tl.learning_ords, at - 365, at)

    sent_180 = _count_between(tl.campaign_sent_ords, at - 180, at)
    if sent_180:
        lo = np.searchsorted(tl.campaign_sent_ords, at - 180, "left")
        hi = np.searchsorted(tl.campaign_sent_ords, at, "left")
        open_rate = float(tl.campaign_opened[lo:hi].mean())
    else:
        open_rate = 0.0

    if tl.feedback_ords.size:
        lo = np.searchsorted(tl.feedback_ords, at - 365, "left")
        hi = np.searchsorted(tl.feedback_ords, at, "left")
        recent_ratings = tl.feedback_ratings[lo:hi]
    else:
        recent_ratings = np.empty(0)
    negative_feedback = bool(recent_ratings.size and recent_ratings.min() <= 2)

    web_lo = np.searchsorted(tl.web_week_ords, at - 90, "left")
    web_mid = np.searchsorted(tl.web_week_ords, at - 180, "left")
    web_hi = np.searchsorted(tl.web_week_ords, at, "left")
    sessions_90 = float(tl.web_sessions[web_lo:web_hi].sum()) if tl.web_sessions.size else 0.0
    sessions_prior_90 = float(tl.web_sessions[web_mid:web_lo].sum()) if tl.web_sessions.size else 0.0

    days_since_login = int(at - tl.login_ords[-1]) if tl.login_ords.size and tl.login_ords[0] < at else 999
    if tl.login_ords.size:
        before = tl.login_ords[tl.login_ords < at]
        days_since_login = int(at - before[-1]) if before.size else 999

    tenure_years = (at - tl.join_ord) / 365.25
    services_used = int(logins_90 > 0) + int(events_365 > 0) + int(learning_any_365 > 0) + int(open_rate > 0.2)

    return {
        # --- binary model inputs ------------------------------------------------------
        "inactive_90_days": int(logins_90 == 0),
        "negative_feedback": int(negative_feedback),
        "failed_payment": int(failed_payment),
        "no_event_attendance": int(events_365 == 0),
        "declining_logins": int(logins_prior_90 >= 3 and logins_90 < 0.6 * logins_prior_90),
        "completed_learning": int(learning_365 >= 1),
        "attended_first_90_days": int(_count_between(tl.attended_ords, tl.join_ord, tl.join_ord + 90) >= 1),
        "auto_renewal": int(auto_renewal),
        "long_tenure": int(tenure_years >= 5.0),
        "low_campaign_engagement": int(sent_180 >= 4 and open_rate < 0.15),
        "fee_increase": int(fee_increase),
        "student_to_full_transition": int(student_transition),
        "multi_service_user": int(services_used >= 3),
        # IBM's strongest leak-free protective signal: customers who referred someone
        # churned at a fraction of the rate of those who did not.
        "no_recent_advocacy": int(_count_between(tl.referral_ords, at - ADVOCACY_WINDOW_DAYS, at) == 0),
        # --- descriptive features (exported, not used by the churn model) -------------
        "logins_90d": logins_90,
        "logins_prior_90d": logins_prior_90,
        "days_since_last_login": days_since_login,
        "events_attended_365d": events_365,
        "learning_completions_365d": learning_365,
        "web_sessions_90d": sessions_90,
        "web_sessions_prior_90d": sessions_prior_90,
        "campaign_open_rate_180d": round(open_rate, 4),
        "campaigns_sent_180d": sent_180,
        "tenure_years": round(tenure_years, 3),
        "services_used": services_used,
        "referrals_365d": _count_between(tl.referral_ords, at - 365, at),
        "min_rating_365d": float(recent_ratings.min()) if recent_ratings.size else None,
    }


def churn_log_odds(features: dict) -> float:
    """Apply the published coefficient set to a feature dictionary."""
    total = CHURN_COEFFICIENTS["intercept"]
    for name, coef in CHURN_COEFFICIENTS.items():
        if name == "intercept":
            continue
        total += coef * features[name]
    return float(total)


def contributions(features: dict) -> dict[str, float]:
    """Per-feature contribution to the log-odds, for explanation and risk factors."""
    return {
        name: CHURN_COEFFICIENTS[name] * features[name]
        for name in CHURN_COEFFICIENTS
        if name != "intercept" and features.get(name)
    }


def top_risk_factors(features: dict, k: int = 3) -> list[str]:
    """The ``k`` largest risk-increasing contributions, most important first."""
    contrib = {n: v for n, v in contributions(features).items() if v > 0}
    ranked = sorted(contrib.items(), key=lambda kv: (-kv[1], RISK_FEATURES.index(kv[0]) if kv[0] in RISK_FEATURES else 99))
    return [RISK_FACTOR_LABELS[name] for name, _ in ranked[:k]]


def top_protective_factors(features: dict, k: int = 2) -> list[str]:
    contrib = {n: v for n, v in contributions(features).items() if v < 0}
    ranked = sorted(contrib.items(), key=lambda kv: kv[1])
    return [RISK_FACTOR_LABELS[name] for name, _ in ranked[:k]]


def engagement_score(features: dict) -> float:
    """A 0-100 composite engagement score derived from observed behaviour."""
    score = (
        20 * np.tanh(features["logins_90d"] / 8.0)
        + 18 * np.tanh(features["web_sessions_90d"] / 12.0)
        + 20 * np.tanh(features["events_attended_365d"] / 2.5)
        + 18 * np.tanh(features["learning_completions_365d"] / 2.0)
        + 12 * features["campaign_open_rate_180d"]
        + 8 * (features["services_used"] / 4.0)
        + 8 * np.tanh(features["referrals_365d"] / 1.5)
    )
    return float(np.round(np.clip(score, 0, 100), 1))


def risk_category(probability: float) -> str:
    if probability < RISK_THRESHOLDS["low_max"]:
        return "Low"
    if probability < RISK_THRESHOLDS["medium_max"]:
        return "Medium"
    return "High"
