"""Calibration of the member dimension against the IBM Telco Customer Churn dataset.

The recommendation in ``Data Recomendations.md`` is to use IBM Telco as the *foundation*
for the member dimension and then extend it with membership-specific activity.  This
module implements that as a calibration step rather than a hard dependency:

* If ``data/seed/ibm_telco_churn.csv`` is present, the marginal distributions that carry
  over to a membership organisation are measured from it directly.
* If it is absent, the same quantities fall back to constants taken from the published
  summary statistics of the dataset, so the generator still runs offline.

Only structural marginals are carried over.  Telco-specific columns (phone service,
streaming TV, and so on) are deliberately dropped: they have no membership analogue and
copying them is what makes a project look like a re-skinned churn exercise.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from . import config


@dataclass
class SeedCalibration:
    """Marginals carried over from IBM Telco into the member dimension."""

    source: str
    #: Mean and dispersion of tenure in months, used to shape the join-date distribution.
    tenure_mean_months: float = 32.4
    tenure_sd_months: float = 24.6
    #: Share of customers on a month-to-month contract.  Mapped to members who pay
    #: annually without a continuous-payment mandate, i.e. auto_renewal = False.
    month_to_month_share: float = 0.550
    #: Share on automatic payment methods (bank transfer / credit card automatic).
    automatic_payment_share: float = 0.433
    #: Overall churn rate, used as the target for the calibrated churn intercept.
    churn_rate: float = 0.265
    #: Ratio of mean monthly charge for churned vs retained customers.  Churners pay
    #: more, which is where the fee-sensitivity term in the churn model comes from.
    churn_charge_ratio: float = 1.166
    #: Share aged 65+ ("senior citizen" flag in the source).
    senior_share: float = 0.162
    notes: list[str] = field(default_factory=list)


_FALLBACK_NOTE = (
    "IBM Telco seed file not found; using published marginals from the IBM sample "
    "dataset. Place the CSV at data/seed/ibm_telco_churn.csv to calibrate directly."
)


def load_calibration(verbose: bool = True) -> SeedCalibration:
    """Measure the seed marginals from the IBM file, or fall back to published values."""
    path = config.IBM_SEED_FILE
    if not path.exists():
        cal = SeedCalibration(source="published-marginals")
        cal.notes.append(_FALLBACK_NOTE)
        if verbose:
            print(f"  seed: {_FALLBACK_NOTE}")
        return cal

    df = pd.read_csv(path)
    df.columns = [c.strip().lower().replace(" ", "") for c in df.columns]
    cal = SeedCalibration(source=str(path))

    if "tenure" in df:
        tenure = pd.to_numeric(df["tenure"], errors="coerce").dropna()
        cal.tenure_mean_months = float(tenure.mean())
        cal.tenure_sd_months = float(tenure.std())
    if "contract" in df:
        cal.month_to_month_share = float((df["contract"] == "Month-to-month").mean())
    if "paymentmethod" in df:
        cal.automatic_payment_share = float(df["paymentmethod"].str.contains("automatic", case=False).mean())
    if "churn" in df:
        churn = df["churn"].astype(str).str.strip().str.lower().isin(["yes", "1", "true"])
        cal.churn_rate = float(churn.mean())
        if "monthlycharges" in df:
            charges = pd.to_numeric(df["monthlycharges"], errors="coerce")
            retained = charges[~churn].mean()
            if retained and np.isfinite(retained) and retained > 0:
                cal.churn_charge_ratio = float(charges[churn].mean() / retained)
    if "seniorcitizen" in df:
        cal.senior_share = float(pd.to_numeric(df["seniorcitizen"], errors="coerce").fillna(0).mean())

    cal.notes.append(f"Calibrated from {path.name} ({len(df):,} source rows).")
    if verbose:
        print(f"  seed: calibrated from {path.name} ({len(df):,} rows)")
    return cal
