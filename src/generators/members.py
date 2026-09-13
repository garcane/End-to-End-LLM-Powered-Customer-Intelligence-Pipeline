"""Generate the member dimension and the latent traits that drive every other table.

The latent traits (engagement, affinities, satisfaction, trajectory) are *not* exported.
They exist so that the observable activity tables are generated from a coherent
underlying person, which is what makes the churn label learnable rather than random.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .seed import SeedCalibration
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

#: Annual membership terms run for a year, whereas the telco seed measures month-to-month
#: contracts.  Tenure drawn from the seed is stretched by this factor before use.
TENURE_SCALE = 1.6

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


def generate_members(rng: np.random.Generator, n: int, cal: SeedCalibration) -> pd.DataFrame:
    """Return one row per member with exported fields plus latent behavioural traits."""
    as_of = to_ordinal(config.AS_OF_DATE)
    earliest = to_ordinal(config.EARLIEST_JOIN)

    df = pd.DataFrame({"member_id": [f"M{i:07d}" for i in range(1, n + 1)]})

    # --- Demographics -----------------------------------------------------------------
    df["region"] = pick(rng, config.REGIONS, n)
    df["organisation_type"] = pick(rng, config.ORGANISATION_TYPES, n)
    df["acquisition_channel"] = pick(rng, config.ACQUISITION_CHANNELS, n)

    age_bands = [b for b, _ in config.AGE_BANDS]
    age_probs = np.array([p for _, p in config.AGE_BANDS], dtype=float)
    # Nudge the oldest band towards the seed's "senior citizen" share.
    age_probs[-1] = max(age_probs[-1], cal.senior_share * 0.45)
    df["age_band"] = rng.choice(age_bands, size=n, p=age_probs / age_probs.sum())

    df["career_stage"] = _sample_conditional(rng, df["age_band"].to_numpy(), _CAREER_BY_AGE, [c for c, _ in config.CAREER_STAGES])
    df["membership_type"] = _sample_conditional(
        rng, df["career_stage"].to_numpy(), _TYPE_BY_CAREER, [t for t, _, _ in config.MEMBERSHIP_TYPES]
    )

    # --- Tenure and join date ---------------------------------------------------------
    # Gamma matched to the seed's tenure mean/sd, stretched from monthly contracts to
    # annual membership terms.
    mean_m = cal.tenure_mean_months * TENURE_SCALE
    sd_m = max(cal.tenure_sd_months * TENURE_SCALE, 1.0)
    shape = (mean_m / sd_m) ** 2
    scale = sd_m**2 / mean_m
    tenure_days = rng.gamma(shape, scale, size=n) * 30.44
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
    df["communication_consent"] = rng.random(n) < clip01(0.62 + 0.30 * engagement)

    fee_lookup = {t: f for t, f, _ in config.MEMBERSHIP_TYPES}
    df["base_fee"] = df["membership_type"].map(fee_lookup).astype(float)
    # Regional fee bands: overseas members pay a reduced rate.
    df["base_fee"] *= np.where(df["region"].isin(["Europe (non-UK)", "Rest of World"]), 0.82, 1.0)

    # Renewal anniversary is the join anniversary.
    df["renewal_month_day"] = [from_ordinal(o).strftime("%m-%d") for o in join_ord]

    df["join_date"] = [from_ordinal(o).isoformat() for o in join_ord]
    return df
