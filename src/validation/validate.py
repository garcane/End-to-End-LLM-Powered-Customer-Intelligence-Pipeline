"""Validate a generated dataset.

Four kinds of check are run:

* **Structural** - primary keys unique, foreign keys resolve, values inside their
  declared domains, no activity recorded after a member lapsed.
* **Volume** - row counts against the ranges recommended in ``Data Recomendations.md``.
* **Signal** - a logistic regression is fitted to ``member_training_features`` from
  scratch (scipy only) to confirm that the churn label is genuinely learnable, that the
  fitted coefficients recover the ones used to generate it, and that the ceiling AUC is
  high enough to be interesting but well short of 1.0.
* **IBM seed fidelity** - the parts of the dataset taken from the seed are compared back
  against ``data/seed/ibm_calibration.json``: referral behaviour, the age distribution,
  the survey rating distribution, and whether the IBM-estimated coefficients have drifted
  away from the calibration that produced them.

Usage::

    python -m src.validation.validate [--data data/synthetic]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.generators import config  # noqa: E402
from src.generators.features import PROTECTIVE_FEATURES, RISK_FEATURES  # noqa: E402

#: Row-count ranges recommended in "Data Recomendations.md", expressed per member so
#: they can be checked at any scale.
VOLUME_TARGETS_PER_MEMBER = {
    "membership_history": (1.6, 3.4),
    "website_activity": (40, 90),
    "login_history": (40, 130),
    "event_attendance": (6.0, 13.0),
    "learning_activity": (4.0, 10.0),
    "marketing_engagement": (40, 130),
    "member_feedback": (0.8, 2.2),
    "member_referrals": (1.2, 3.0),
    "model_predictions": (4.0, 8.0),
    "ai_insights": (0.20, 1.00),
}

DOMAINS = {
    ("event_attendance", "attendance_status"): set(config.ATTENDANCE_STATUSES),
    ("member_feedback", "sentiment_label"): {"Positive", "Neutral", "Negative"},
    ("member_feedback", "feedback_channel"): {c for c, _ in config.FEEDBACK_CHANNELS},
    ("member_referrals", "referral_channel"): {"Word of mouth", "Referral link", "Event introduction", "Employer scheme"},
    ("members", "membership_type"): {t for t, _, _ in config.MEMBERSHIP_TYPES},
    ("members", "career_stage"): {c for c, _ in config.CAREER_STAGES},
    ("model_predictions", "risk_category"): {"Low", "Medium", "High"},
    ("learning_activity", "completion_status"): {"Completed", "In progress", "Abandoned", "Not started"},
    ("membership_history", "membership_status"): {"Active", "Lapsed", "Cancelled"},
    ("membership_history", "churn_category"): set(config.CHURN_CATEGORIES),
    ("member_referrals", "referral_status"): {"Invited", "Joined", "Declined", "Expired"},
    ("members", "membership_status"): {"Active", "Lapsed", "Cancelled", "Suspended"},
}


class Report:
    def __init__(self):
        self.rows: list[tuple[str, str, bool, str, bool]] = []

    def check(self, group: str, name: str, passed: bool, detail: str = "", advisory: bool = False) -> None:
        """Record a check.  ``advisory`` checks are reported but do not fail the run."""
        self.rows.append((group, name, bool(passed), detail, advisory))

    @property
    def failures(self) -> list[tuple]:
        return [r for r in self.rows if not r[2] and not r[4]]

    def render(self) -> str:
        lines, group = [], None
        passed_count = 0
        for g, name, passed, detail, advisory in self.rows:
            if g != group:
                lines.append(f"\n{g}")
                lines.append("-" * len(g))
                group = g
            mark = "PASS" if passed else ("WARN" if advisory else "FAIL")
            passed_count += int(passed)
            lines.append(f"  [{mark}] {name}" + (f"  -- {detail}" if detail else ""))
        lines.append(f"\n{passed_count}/{len(self.rows)} checks passed, {len(self.failures)} failed.")
        return "\n".join(lines)


# --------------------------------------------------------------------------------------
# Minimal logistic regression (scipy only) so the suite has no sklearn dependency
# --------------------------------------------------------------------------------------


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-3) -> np.ndarray:
    X1 = np.column_stack([np.ones(len(X)), X])

    def nll(w):
        z = X1 @ w
        # log(1 + exp(z)) computed stably
        ll = np.sum(y * z - np.logaddexp(0.0, z))
        return -ll / len(y) + l2 * np.sum(w[1:] ** 2)

    def grad(w):
        p = 1.0 / (1.0 + np.exp(-(X1 @ w)))
        g = X1.T @ (p - y) / len(y)
        g[1:] += 2 * l2 * w[1:]
        return g

    res = minimize(nll, np.zeros(X1.shape[1]), jac=grad, method="L-BFGS-B")
    return res.x


def auc(y: np.ndarray, score: np.ndarray) -> float:
    order = np.argsort(score)
    ranks = np.empty(len(score), dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    # Average ranks within ties.
    s = score[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        if j > i:
            ranks[order[i : j + 1]] = (i + j + 2) / 2.0
        i = j + 1
    n1, n0 = float(y.sum()), float((1 - y).sum())
    if n1 == 0 or n0 == 0:
        return float("nan")
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


def validate(data_dir: Path) -> Report:
    rep = Report()
    read = lambda name, **kw: pd.read_csv(data_dir / f"{name}.csv", **kw)  # noqa: E731

    members = read("members")
    n_members = len(members)
    member_ids = set(members["member_id"])

    # --- Structural -------------------------------------------------------------------
    g = "Structure"
    for table, key in [
        ("members", "member_id"),
        ("events", "event_id"),
        ("campaigns", "campaign_id"),
        ("courses", "course_id"),
        ("segments", "segment_id"),
        ("membership_history", "membership_history_id"),
        ("event_attendance", "attendance_id"),
        ("learning_activity", "learning_activity_id"),
        ("member_feedback", "feedback_id"),
        ("member_referrals", "referral_id"),
        ("model_predictions", "prediction_id"),
        ("ai_insights", "insight_id"),
        ("data_quality_results", "check_id"),
    ]:
        col = read(table, usecols=[key])[key]
        rep.check(g, f"{table}.{key} unique", col.is_unique, f"{len(col):,} rows")

    event_ids = set(read("events", usecols=["event_id"])["event_id"])
    course_ids = set(read("courses", usecols=["course_id"])["course_id"])
    campaign_ids = set(read("campaigns", usecols=["campaign_id"])["campaign_id"])

    g = "Referential integrity"
    for table in [
        "membership_history",
        "website_activity",
        "login_history",
        "event_attendance",
        "learning_activity",
        "marketing_engagement",
        "member_feedback",
        "model_predictions",
        "ai_insights",
    ]:
        ids = read(table, usecols=["member_id"])["member_id"]
        missing = len(set(ids) - member_ids)
        rep.check(g, f"{table}.member_id resolves", missing == 0, f"{missing} orphans")

    rep.check(g, "event_attendance.event_id resolves", not (set(read("event_attendance", usecols=["event_id"])["event_id"]) - event_ids))
    rep.check(g, "learning_activity.course_id resolves", not (set(read("learning_activity", usecols=["course_id"])["course_id"]) - course_ids))
    refs = read("member_referrals", usecols=["referring_member_id", "referred_member_id"])
    rep.check(g, "member_referrals.referring_member_id resolves",
              not (set(refs["referring_member_id"]) - member_ids))
    joined = refs["referred_member_id"].dropna()
    rep.check(g, "member_referrals.referred_member_id resolves", not (set(joined) - member_ids),
              f"{len(joined):,} converted referrals")
    segment_ids = set(read("segments", usecols=["segment_id"])["segment_id"])
    rep.check(g, "model_predictions.segment_id resolves",
              not (set(preds_segment_ids := set(read("model_predictions", usecols=["segment_id"])["segment_id"])) - segment_ids),
              f"{len(preds_segment_ids)} distinct segments in use")
    rep.check(g, "marketing_engagement.campaign_id resolves", not (set(read("marketing_engagement", usecols=["campaign_id"])["campaign_id"]) - campaign_ids))

    # --- Domains ----------------------------------------------------------------------
    g = "Domains"
    for (table, col), allowed in DOMAINS.items():
        values = set(read(table, usecols=[col])[col].dropna())
        bad = values - allowed
        rep.check(g, f"{table}.{col} in reference list", not bad, f"unexpected: {sorted(bad)}" if bad else "")

    preds = read("model_predictions")
    rep.check(g, "churn_probability in [0, 1]", preds["churn_probability"].between(0, 1).all())
    band = np.where(
        preds["churn_probability"] < config.RISK_THRESHOLDS["low_max"],
        "Low",
        np.where(preds["churn_probability"] < config.RISK_THRESHOLDS["medium_max"], "Medium", "High"),
    )
    rep.check(g, "risk_category matches probability band", bool((band == preds["risk_category"]).all()))

    mk = read("marketing_engagement")
    rep.check(g, "opened implies delivered", bool((~mk["opened"] | mk["delivered"]).all()))
    rep.check(g, "clicked implies opened", bool((~mk["clicked"] | mk["opened"]).all()))
    rep.check(g, "converted implies clicked", bool((~mk["converted"] | mk["clicked"]).all()))

    la = read("learning_activity")
    rep.check(g, "completed implies 100%", bool((la.loc[la["completion_status"] == "Completed", "completion_percentage"] == 100).all()))
    rep.check(g, "assessment_score only when completed", bool(la.loc[la["completion_status"] != "Completed", "assessment_score"].isna().all()))

    # --- Causal consistency -----------------------------------------------------------
    g = "Causal consistency"
    churned = members.loc[members["churn_flag"] == 1, ["member_id", "churn_date", "join_date"]]
    churn_map = dict(zip(churned["member_id"], pd.to_datetime(churned["churn_date"])))
    rep.check(g, "churn_date after join_date", bool((pd.to_datetime(churned["churn_date"]) > pd.to_datetime(churned["join_date"])).all()))
    rep.check(
        g,
        "churned members have no renewal_date",
        bool(members.loc[members["churn_flag"] == 1, "renewal_date"].isna().all()),
    )
    rep.check(
        g,
        "active members have a renewal_date",
        bool(members.loc[members["churn_flag"] == 0, "renewal_date"].notna().all()),
    )

    for table, date_col in [
        ("login_history", "login_timestamp"),
        ("website_activity", "activity_date"),
        ("event_attendance", "registration_date"),
        ("learning_activity", "activity_date"),
        ("marketing_engagement", "sent_date"),
    ]:
        df = read(table, usecols=["member_id", date_col])
        df = df[df["member_id"].isin(churn_map)]
        if df.empty:
            rep.check(g, f"no {table} rows after churn", True, "no churned-member rows")
            continue
        cut = df["member_id"].map(churn_map)
        after = int((pd.to_datetime(df[date_col]) >= cut).sum())
        rep.check(g, f"no {table} rows after churn", after == 0, f"{after} rows after churn date")

    rf = read("member_referrals", usecols=["referring_member_id", "referral_date"])
    rf = rf[rf["referring_member_id"].isin(churn_map)]
    after = int((pd.to_datetime(rf["referral_date"]) >= rf["referring_member_id"].map(churn_map)).sum())
    rep.check(g, "no member_referrals rows after churn", after == 0, f"{after} rows")

    fb = read("member_feedback", usecols=["member_id", "submitted_date", "feedback_channel"])
    fb = fb[fb["member_id"].isin(churn_map) & (fb["feedback_channel"] != "Cancellation survey")]
    after = int((pd.to_datetime(fb["submitted_date"]) >= fb["member_id"].map(churn_map)).sum())
    rep.check(g, "no member_feedback after churn (exit surveys excepted)", after == 0, f"{after} rows")

    preds_churned = preds[preds["member_id"].isin(churn_map)]
    after = int((pd.to_datetime(preds_churned["prediction_date"]) >= preds_churned["member_id"].map(churn_map)).sum())
    rep.check(g, "no predictions scored after churn", after == 0, f"{after} rows")

    # --- Volume -----------------------------------------------------------------------
    # The recommended volumes assume the full profile: the smaller profiles deliberately
    # cut the campaign catalogue and the number of scoring runs, so their per-member
    # ratios are reported but not enforced.
    manifest_path = data_dir / "generation_manifest.json"
    profile = json.loads(manifest_path.read_text(encoding="utf-8"))["scale_profile"] if manifest_path.exists() else "full"
    advisory = profile != "full"

    g = f"Volume (per member, profile '{profile}')"
    for table, (lo, hi) in VOLUME_TARGETS_PER_MEMBER.items():
        n = sum(1 for _ in open(data_dir / f"{table}.csv", encoding="utf-8")) - 1
        per = n / n_members
        rep.check(g, f"{table}", lo <= per <= hi, f"{n:,} rows = {per:.2f}/member (target {lo}-{hi})", advisory=advisory)

    fb_all = read("member_feedback")

    # --- Signal -----------------------------------------------------------------------
    g = "Churn signal"
    feats = read("member_training_features")
    model_cols = RISK_FEATURES + PROTECTIVE_FEATURES
    X = feats[model_cols].to_numpy(dtype=float)
    y = feats["churn_flag"].to_numpy(dtype=float)

    rate = y.mean()
    rep.check(g, "annual lapse rate is plausible", 0.05 <= rate <= 0.22, f"{rate:.1%} per renewal decision")

    ceiling = auc(y, feats["true_churn_probability"].to_numpy())
    rep.check(g, "ceiling AUC (true propensity)", 0.72 <= ceiling <= 0.95, f"AUC = {ceiling:.3f}")

    # Hold out the most recent third of observations, as a real pipeline would.
    order = np.argsort(pd.to_datetime(feats["observation_date"]).to_numpy())
    split = int(len(order) * 0.67)
    tr, te = order[:split], order[split:]
    w = fit_logistic(X[tr], y[tr])
    test_auc = auc(y[te], X[te] @ w[1:] + w[0])
    rep.check(g, "out-of-time AUC of a refitted model", 0.68 <= test_auc <= 0.95, f"AUC = {test_auc:.3f}")

    # Coefficient recovery: signs must match the generating model, and the magnitudes
    # should be in the same neighbourhood.
    fitted = dict(zip(model_cols, w[1:]))
    wrong_sign = [c for c in model_cols if np.sign(fitted[c]) != np.sign(config.CHURN_COEFFICIENTS[c]) and abs(fitted[c]) > 0.08]
    rep.check(g, "fitted coefficient signs match the generating model", not wrong_sign, f"mismatched: {wrong_sign}" if wrong_sign else "")

    corr = np.corrcoef([fitted[c] for c in model_cols], [config.CHURN_COEFFICIENTS[c] for c in model_cols])[0, 1]
    rep.check(g, "fitted vs true coefficients correlate", corr >= 0.85, f"r = {corr:.3f}")

    print("\n  Recovered coefficients (fitted vs generating):")
    for c in model_cols:
        print(f"    {c:<28} {fitted[c]:+.3f}   vs {config.CHURN_COEFFICIENTS[c]:+.2f}")
    print(f"    {'intercept':<28} {w[0]:+.3f}   vs {config.CHURN_COEFFICIENTS['intercept']:+.2f}")

    # --- Sanity of headline business metrics ------------------------------------------
    g = "Business plausibility"
    mk_rate = mk.loc[mk["delivered"], "opened"].mean()
    rep.check(g, "email open rate is realistic", 0.20 <= mk_rate <= 0.55, f"{mk_rate:.1%}")
    click_rate = mk.loc[mk["opened"], "clicked"].mean()
    rep.check(g, "click-through rate is realistic", 0.15 <= click_rate <= 0.55, f"{click_rate:.1%} of opens")

    ea = read("event_attendance")
    attended = (ea["attendance_status"] == "Attended").mean()
    rep.check(g, "event attendance rate is realistic", 0.45 <= attended <= 0.80, f"{attended:.1%} of registrations")

    neg = (fb_all["sentiment_label"] == "Negative").mean()
    rep.check(g, "negative feedback share is realistic", 0.08 <= neg <= 0.40, f"{neg:.1%}")

    # Engaged members should renew more often than disengaged ones.
    lapsed = feats.groupby("churn_flag")["logins_90d"].mean()
    rep.check(
        g,
        "lapsing members log in less before renewal",
        lapsed.get(1, 0) < lapsed.get(0, 1),
        f"{lapsed.get(1, float('nan')):.1f} vs {lapsed.get(0, float('nan')):.1f} logins in the prior 90 days",
    )

    # --- Fidelity to the IBM seed -----------------------------------------------------
    # The point of a hybrid dataset is that the parts taken from the seed still look like
    # the seed. These checks close that loop.
    cal_path = config.SEED_DIR / "ibm_calibration.json"
    if cal_path.exists():
        cal = json.loads(cal_path.read_text(encoding="utf-8"))
        g = f"IBM seed fidelity (source: {cal.get('source', 'unknown')})"

        refs_all = read("member_referrals", usecols=["referring_member_id"])
        per_referrer = refs_all.groupby("referring_member_id").size()
        share = len(per_referrer) / n_members
        target = cal["referrer_share"]
        rep.check(g, "share of members who refer someone", abs(share - target) <= 0.05,
                  f"{share:.1%} vs IBM {target:.1%}")

        mean_refs = float(per_referrer.mean())
        target = cal["referrals_mean_among_referrers"]
        rep.check(g, "mean referrals among referrers", abs(mean_refs - target) <= 0.8,
                  f"{mean_refs:.2f} vs IBM {target:.2f}")

        used = cal.get("age_shares_adjusted") or {}
        if used:
            observed = members["age_band"].value_counts(normalize=True)
            worst = max(abs(observed.get(b, 0.0) - v) for b, v in used.items())
            rep.check(g, "age band distribution matches the calibration", worst <= 0.02,
                      f"largest deviation {worst:.1%}")

        survey = fb_all[fb_all["feedback_channel"] == "Annual member survey"]
        observed = survey["rating"].value_counts(normalize=True)
        sat = {int(k): v for k, v in cal["satisfaction_shares"].items()}
        # Total variation distance, rather than the single worst band: one band being a
        # few points out says much less than the whole distribution being the wrong shape,
        # and a worst-band threshold sits on a knife edge between runs.
        tvd = sum(abs(float(observed.get(k, 0.0)) - v) for k, v in sat.items()) / 2
        rep.check(g, "survey rating distribution matches IBM satisfaction", tvd <= 0.06,
                  f"total variation distance {tvd:.3f}")

        obs_mean = float(survey["rating"].mean())
        ibm_mean = sum(k * v for k, v in sat.items())
        rep.check(g, "mean survey rating matches IBM", abs(obs_mean - ibm_mean) <= 0.20,
                  f"{obs_mean:.2f} vs IBM {ibm_mean:.2f}")

        # Advisory: the seed's advocacy effect is stronger than the generated one.
        life = members[["member_id", "churn_flag"]].merge(
            per_referrer.rename("n"), left_on="member_id", right_index=True, how="left"
        ).fillna({"n": 0})
        by_churn = life.groupby("churn_flag")["n"].mean()
        ratio = float(by_churn.get(1, 0.0) / max(by_churn.get(0, 1.0), 1e-9))
        rep.check(g, "lapsed members refer less than retained members", ratio < 0.85,
                  f"ratio {ratio:.2f} vs IBM {cal['referrals_churn_ratio']:.2f} "
                  "(IBM counts lifetime referrals at one cross-section; not directly comparable)",
                  advisory=True)

        # The extension coefficients should still be the ones the seed produced.
        analogue = cal.get("analogue_coefficients", {})
        pairs = [("fee_increase", "high_charge"), ("multi_service_user", "multi_service"),
                 ("no_recent_advocacy", "referred")]
        drift = []
        for feature, source_name in pairs:
            if source_name not in analogue:
                continue
            expected = abs(analogue[source_name])
            actual = abs(config.CHURN_COEFFICIENTS[feature])
            if abs(actual - expected) > 0.05:
                drift.append(f"{feature} {actual:+.2f} vs IBM {analogue[source_name]:+.3f}")
        rep.check(g, "IBM-estimated coefficients still match the calibration", not drift,
                  "; ".join(drift) if drift else "fee_increase, multi_service_user, no_recent_advocacy")
    else:
        rep.check("IBM seed fidelity", "calibration file present", False,
                  "run python -m src.generators.calibrate", advisory=True)

    return rep


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Validate the generated synthetic dataset.")
    p.add_argument("--data", type=Path, default=config.SYNTHETIC_DIR)
    args = p.parse_args(argv)

    if not (args.data / "members.csv").exists():
        print(f"No dataset found in {args.data}. Run: python -m src.generators.run --scale full")
        return 2

    print(f"Validating {args.data}")
    rep = validate(args.data)
    print(rep.render())
    return 1 if rep.failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
