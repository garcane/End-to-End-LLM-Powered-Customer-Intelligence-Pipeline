"""Generate the member dimension and the latent traits that drive every other table.

The latent traits (engagement, affinities, satisfaction, trajectory) are *not* exported.
They exist so that the observable activity tables are generated from a coherent
underlying person, which is what makes the churn label learnable rather than random.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .ibm_seed import TENURE_SCALE, IbmCalibration
from .utils import clip01, from_ordinal, pick, to_ordinal

MEMBER_COLUMNS = [
    "member_id",
    "join_date",
    "membership_status",
    "membership_type",
    "region",
    "age_band",
    "organisation_type",
    "career_stage",
    "acquisition_channel",
    "renewal_date",
    "annual_fee",
    "auto_renewal",
    "communication_consent",
    "churn_date",
    "churn_flag",
]

#: Share of members whose tenure is drawn from beyond the seed's censoring point.
#: IBM observes tenure only up to 72 months, so the long tail has to be extrapolated.
CENSORED_TAIL_SHARE = 0.05
CENSORED_TAIL_MEAN_MONTHS = 30.0

#: Base rate for being an advocate at all.  Tuned so that the share of members making at
#: least one referral matches the IBM seed (45.8%).
ADVOCATE_BASE = 0.25

#: P(career stage | age band).  Columns follow config.CAREER_STAGES.
_CAREER_BY_AGE = {
    "18-24": [0.62, 0.34, 0.03, 0.01, 0.00, 0.00],
    "25-34": [0.10, 0.55, 0.30, 0.04, 0.01, 0.00],
    "35-44": [0.02, 0.18, 0.52, 0.25, 0.03, 0.00],
    "45-54": [0.01, 0.06, 0.38, 0.45, 0.10, 0.00],
    "55-64": [0.01, 0.03, 0.26, 0.51, 0.14, 0.05],
    "65+": [0.00, 0.01, 0.08, 0.27, 0.09, 0.55],
}

#: P(membership type | career stage).  Columns follow config.MEMBERSHIP_TYPES.
_TYPE_BY_CAREER = {
    "Student": [0.86, 0.12, 0.02, 0.00, 0.00, 0.00, 0.00],
    "Early career": [0.14, 0.52, 0.30, 0.02, 0.00, 0.00, 0.02],
    "Mid career": [0.01, 0.20, 0.56, 0.17, 0.01, 0.00, 0.05],
    "Senior": [0.00, 0.05, 0.40, 0.41, 0.08, 0.01, 0.05],
    "Executive": [0.00, 0.02, 0.22, 0.44, 0.24, 0.02, 0.06],
    "Retired": [0.00, 0.04, 0.08, 0.10, 0.06, 0.70, 0.02],
}


def _sample_conditional(rng: np.random.Generator, parent: np.ndarray, table: dict, child_values: list[str]) -> np.ndarray:
    """Vectorised sampling of a child category given a parent category."""
    out = np.empty(len(parent), dtype=object)
    child = np.array(child_values, dtype=object)
    for key, probs in table.items():
        mask = parent == key
        n = int(mask.sum())
        if n:
            p = np.array(probs, dtype=float)
            out[mask] = rng.choice(child, size=n, p=p / p.sum())
    return out


def generate_members(rng: np.random.Generator, n: int, cal: IbmCalibration) -> pd.DataFrame:
    """Return one row per member with exported fields plus latent behavioural traits."""
    as_of = to_ordinal(config.AS_OF_DATE)
    earliest = to_ordinal(config.EARLIEST_JOIN)

    df = pd.DataFrame({"member_id": [f"M{i:07d}" for i in range(1, n + 1)]})

    # --- Demographics -----------------------------------------------------------------
    df["region"] = pick(rng, config.REGIONS, n)
    df["organisation_type"] = pick(rng, config.ORGANISATION_TYPES, n)
    df["acquisition_channel"] = pick(rng, config.ACQUISITION_CHANNELS, n)

    # IBM records exact age, so the band shares are measured rather than assumed. The
    # calibration applies a documented professional-body re-weighting on top; see
    # docs/ibm-telco-calibration.md section 3.
    if cal.age_shares_adjusted:
        age_bands = list(cal.age_shares_adjusted)
        age_probs = np.array(list(cal.age_shares_adjusted.values()), dtype=float)
    else:
        age_bands = [b for b, _ in config.AGE_BANDS]
        age_probs = np.array([p for _, p in config.AGE_BANDS], dtype=float)
    df["age_band"] = rng.choice(age_bands, size=n, p=age_probs / age_probs.sum())

    df["career_stage"] = _sample_conditional(rng, df["age_band"].to_numpy(), _CAREER_BY_AGE, [c for c, _ in config.CAREER_STAGES])
    df["membership_type"] = _sample_conditional(
        rng, df["career_stage"].to_numpy(), _TYPE_BY_CAREER, [t for t, _, _ in config.MEMBERSHIP_TYPES]
    )

    # --- Tenure and join date ---------------------------------------------------------
    # Bootstrapped from the seed's empirical tenure distribution rather than a fitted
    # parametric curve, then stretched because annual membership terms are not
    # month-to-month telco contracts. IBM censors tenure at 72 months, so the top of the
    # distribution is extrapolated with an exponential tail for long-standing members.
    deciles = np.asarray(cal.tenure_deciles, dtype=float)
    u = rng.random(n)
    tenure_months = np.interp(u, np.linspace(0.0, 1.0, len(deciles)), deciles)
    censored = u > (1.0 - CENSORED_TAIL_SHARE)
    tenure_months[censored] = deciles[-1] + rng.exponential(CENSORED_TAIL_MEAN_MONTHS, int(censored.sum()))
    tenure_days = tenure_months * TENURE_SCALE * 30.44
    # Students and early-career members skew newer; fellows skew much older.
    tenure_days *= np.select(
        [
            df["membership_type"].isin(["Student", "Associate"]).to_numpy(),
            df["membership_type"].isin(["Fellow", "Chartered"]).to_numpy(),
        ],
        [0.55, 1.75],
        default=1.0,
    )
    join_ord = np.clip(as_of - tenure_days.astype(int), earliest, as_of - 30)
    df["join_ord"] = join_ord
    df["tenure_years_as_of"] = (as_of - join_ord) / 365.25

    # --- Latent behavioural traits ----------------------------------------------------
    base = rng.beta(2.2, 2.8, size=n)
    type_uplift = df["membership_type"].map(config.TYPE_ENGAGEMENT_UPLIFT).to_numpy(dtype=float)
    channel_quality = df["acquisition_channel"].map(config.CHANNEL_QUALITY).to_numpy(dtype=float)
    engagement = clip01(base * type_uplift + channel_quality + rng.normal(0, 0.07, n))
    # Members who are still present after many years are, on average, more engaged.
    engagement = clip01(engagement + 0.035 * np.log1p(df["tenure_years_as_of"].to_numpy()))
    df["engagement"] = engagement

    df["event_affinity"] = clip01(engagement + rng.normal(0, 0.20, n))
    df["learning_affinity"] = clip01(
        engagement
        + rng.normal(0, 0.20, n)
        + np.where(df["career_stage"].isin(["Student", "Early career"]), 0.12, -0.02)
    )
    df["email_affinity"] = clip01(engagement + rng.normal(0, 0.22, n))
    df["web_affinity"] = clip01(engagement + rng.normal(0, 0.15, n))
    df["satisfaction"] = clip01(0.45 + 0.45 * engagement + rng.normal(0, 0.16, n))
    # Advocacy drives the member_referrals stream. IBM shows this is one of the
    # strongest retention signals in the seed: retained customers referred 4.8x as many
    # people as churned ones.
    #
    # It is modelled as zero-inflated, because the seed is: 54.2% of customers referred
    # nobody at all, while those who did referred 4.27 on average. A single rate
    # parameter cannot reproduce both facts, so members are first split into advocates
    # and non-advocates, and only advocates generate referrals.
    sat = df["satisfaction"].to_numpy()
    advocate_p = clip01(ADVOCATE_BASE + 0.55 * engagement + 0.30 * (sat - 0.5))
    is_advocate = rng.random(n) < advocate_p
    df["is_advocate"] = is_advocate
    df["advocacy"] = np.where(
        is_advocate,
        clip01(0.70 * engagement + 0.40 * sat - 0.10 + rng.normal(0, 0.14, n)),
        0.0,
    )

    # Year-on-year multiplicative drift in activity.  Slightly negative on average:
    # a minority of members quietly disengage before they ever cancel.
    df["drift"] = rng.normal(-0.04, 0.30, n)
    df["price_sensitivity"] = clip01(
        rng.beta(2.0, 3.0, n)
        + np.where(df["membership_type"].isin(["Student", "Retired"]), 0.18, 0.0)
        + np.where(df["organisation_type"] == "Self-employed or consultant", 0.10, 0.0)
        - np.where(df["organisation_type"].isin(["Private sector - large", "Public sector"]), 0.12, 0.0)
    )

    # --- Commercial attributes --------------------------------------------------------
    auto_p = clip01(
        (1.0 - cal.month_to_month_share) * 0.9
        + 0.30 * engagement
        - 0.25 * df["price_sensitivity"].to_numpy()
        + np.where(df["organisation_type"] == "Private sector - large", 0.10, 0.0)
    )
    df["auto_renewal"] = rng.random(n) < auto_p
    # Paperless billing is the seed's closest analogue to opting in to digital
    # communications, measured at 59.2% of customers.
    consent_base = cal.paperless_billing_share if cal.paperless_billing_share else 0.62
    df["communication_consent"] = rng.random(n) < clip01(consent_base + 0.30 * engagement)

    fee_lookup = {t: f for t, f, _ in config.MEMBERSHIP_TYPES}
    df["base_fee"] = df["membership_type"].map(fee_lookup).astype(float)
    # Regional fee bands: overseas members pay a reduced rate.
    df["base_fee"] *= np.where(df["region"].isin(["Europe (non-UK)", "Rest of World"]), 0.82, 1.0)

    # Renewal anniversary is the join anniversary.
    df["renewal_month_day"] = [from_ordinal(o).strftime("%m-%d") for o in join_ord]

    df["join_date"] = [from_ordinal(o).isoformat() for o in join_ord]
    return df
