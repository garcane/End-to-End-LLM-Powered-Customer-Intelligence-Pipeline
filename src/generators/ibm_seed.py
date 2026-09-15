"""Calibration of the synthetic dataset against the IBM Telco Customer Churn sample.

`Data Recomendations.md` proposes using IBM Telco as the *foundation* for the member
dimension. This module implements that properly: it reads the extended IBM Cognos
sample (six workbooks, 7,043 customers), measures the quantities that transfer to a
membership organisation, and fits a leak-free logistic model on mapped analogue
predictors so that several coefficients in the churn model are **estimated from data**
rather than asserted.

Two columns in the IBM extended sample are post-hoc and must never be used as
predictors:

* ``Satisfaction Score`` -- scores of 1-2 churn at 100% and 4-5 at 0%. It was assigned
  after the outcome was known.
* ``Churn Score`` -- IBM's own model output, near-separable against the label.

Both are detected and reported by :func:`detect_leakage`, and both are excluded from the
analogue model. Their marginal distributions are still useful and are retained.

The output is an :class:`IbmCalibration`, cached to ``data/seed/ibm_calibration.json``
so that dataset generation never needs Excel or the source workbooks.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from . import config

#: Directories searched for the IBM workbooks, in order.
SOURCE_DIRS = [
    config.PROJECT_ROOT / "IBM Source Files",
    config.SEED_DIR / "ibm",
    config.SEED_DIR,
]

WORKBOOKS = {
    "demographics": "Telco_customer_churn_demographics.xlsx",
    "services": "Telco_customer_churn_services.xlsx",
    "status": "Telco_customer_churn_status.xlsx",
    "location": "Telco_customer_churn_location.xlsx",
    "population": "Telco_customer_churn_population.xlsx",
    "churn": "Telco_customer_churn.xlsx",
}

CACHE_FILE = config.SEED_DIR / "ibm_calibration.json"

#: Add-on services counted towards "breadth of use".
ADDON_SERVICES = [
    "Online Security",
    "Online Backup",
    "Device Protection Plan",
    "Premium Tech Support",
    "Streaming TV",
    "Streaming Movies",
    "Streaming Music",
    "Unlimited Data",
]

#: Membership-relevant age bands. IBM records exact age, so these are measured.
AGE_BAND_EDGES = [0, 24, 34, 44, 54, 64, 200]
AGE_BAND_LABELS = ["18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

#: Membership of a professional body concentrates in working years, whereas the IBM
#: sample is a general consumer base. These multipliers are applied to the measured age
#: distribution and then renormalised. This is the one demographic judgement in the
#: calibration, and both the raw and adjusted shares are reported so it stays auditable.
PROFESSIONAL_AGE_WEIGHTING = {
    "18-24": 0.85,
    "25-34": 1.35,
    "35-44": 1.35,
    "45-54": 1.20,
    "55-64": 0.85,
    "65+": 0.35,
}

#: Annual membership terms run for a year, whereas the seed measures month-to-month
#: telco contracts. Tenure drawn from the seed is stretched by this factor.
TENURE_SCALE = 1.6


@dataclass
class IbmCalibration:
    """Everything measured from the IBM sample that the generator consumes."""

    source: str = "published-marginals"
    n_source_rows: int = 0

    # --- tenure -----------------------------------------------------------------------
    tenure_mean_months: float = 32.39
    tenure_sd_months: float = 24.54
    tenure_max_months: int = 72
    #: Deciles of the empirical tenure distribution, bootstrapped when generating.
    tenure_deciles: list = field(default_factory=lambda: [1, 4, 9, 16, 24, 29, 38, 48, 57, 66, 72])

    # --- commercial -------------------------------------------------------------------
    month_to_month_share: float = 0.5126
    automatic_payment_share: float = 0.4353
    payment_method_source: str = "published-marginals"
    paperless_billing_share: float = 0.592
    churn_rate: float = 0.2654
    joined_share: float = 0.0645
    churn_charge_ratio: float = 1.2151
    cltv_mean: float = 4400.3
    cltv_cv: float = 0.2689
    cltv_churn_ratio: float = 0.9238

    # --- demographics -----------------------------------------------------------------
    age_shares_raw: dict = field(default_factory=dict)
    age_shares_adjusted: dict = field(default_factory=dict)

    # --- advocacy ---------------------------------------------------------------------
    referrer_share: float = 0.4575
    referrals_mean_among_referrers: float = 4.27
    referrals_max: int = 11
    referrals_churn_ratio: float = 0.2105

    # --- satisfaction -----------------------------------------------------------------
    satisfaction_shares: dict = field(
        default_factory=lambda: {1: 0.1309, 2: 0.0735, 3: 0.3784, 4: 0.2540, 5: 0.1631}
    )

    # --- churn reasons ----------------------------------------------------------------
    churn_category_shares: dict = field(default_factory=dict)
    churn_reason_shares: dict = field(default_factory=dict)
    #: Whether churn reason varies materially with tenure in the source.
    reason_tenure_spread_months: float = 2.2

    # --- analogue model ---------------------------------------------------------------
    analogue_coefficients: dict = field(default_factory=dict)
    analogue_auc: float = 0.0
    analogue_n: int = 0
    analogue_churn_rate: float = 0.0

    leakage: dict = field(default_factory=dict)
    notes: list = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, default=float)


# --------------------------------------------------------------------------------------
# Loading
# --------------------------------------------------------------------------------------


def find_source_dir():
    for d in SOURCE_DIRS:
        if (d / WORKBOOKS["status"]).exists():
            return d
    return None


def load_source(source_dir: Path) -> pd.DataFrame:
    """Join the demographics, services and status workbooks on Customer ID.

    The original single-table workbook is joined in as well, purely for its
    ``Payment Method`` column. This is not redundancy -- see :func:`_automatic_payment`.
    """
    demo = pd.read_excel(source_dir / WORKBOOKS["demographics"])
    serv = pd.read_excel(source_dir / WORKBOOKS["services"])
    stat = pd.read_excel(source_dir / WORKBOOKS["status"])
    df = demo.merge(serv, on="Customer ID", suffixes=("", "_svc")).merge(
        stat, on="Customer ID", suffixes=("", "_sts")
    )

    original = source_dir / WORKBOOKS["churn"]
    if original.exists():
        legacy = pd.read_excel(original, usecols=["CustomerID", "Payment Method"]).rename(
            columns={"CustomerID": "Customer ID", "Payment Method": "payment_method_original"}
        )
        df = df.merge(legacy, on="Customer ID", how="left")

    def yes(col):
        return df[col].astype(str).str.strip().str.lower().eq("yes").astype(int)

    df["n_addon_services"] = sum(yes(c) for c in ADDON_SERVICES)
    df["has_internet"] = yes("Internet Service")
    df["auto_payment"] = _automatic_payment(df)
    return df


def _automatic_payment(df: pd.DataFrame) -> pd.Series:
    """Whether the customer pays by a standing automatic mandate.

    The extended workbook's ``Payment Method`` column **cannot answer this**. It relabels
    the original four categories into three, and the relabelling is lossy: every
    "Electronic check" customer (33.6% of the sample, and manual) is folded into
    "Bank Withdrawal" alongside genuine "Bank transfer (automatic)" customers. Taking the
    extended labels at face value puts the automatic share at 95.6% when the true figure
    is 43.6%, and it mis-specifies the predictor that maps onto ``auto_renewal``.

    So the original workbook, whose labels still carry the "(automatic)" marker, is the
    authority here. If it is unavailable the flag falls back to the extended labels and
    the calibration records that the figure is unreliable.
    """
    if "payment_method_original" in df:
        return df["payment_method_original"].astype(str).str.contains("automatic", case=False).astype(int)
    return df["Payment Method"].isin(["Bank Withdrawal", "Credit Card"]).astype(int)


# --------------------------------------------------------------------------------------
# Leakage detection
# --------------------------------------------------------------------------------------


def detect_leakage(df: pd.DataFrame) -> dict:
    """Identify columns that cannot have been known before the outcome.

    A predictor is flagged when some of its values map to a churn rate of exactly 0 or
    exactly 1 across a non-trivial number of rows. Real predictors do not behave that
    way; post-hoc annotations do.
    """
    findings: dict = {}
    y = df["Churn Value"]

    for col in ["Satisfaction Score", "Churn Score"]:
        if col not in df:
            continue
        values = df[col]
        if values.nunique() > 20:  # bin continuous scores
            values = pd.qcut(values, 10, duplicates="drop")
        rates = df.groupby(values, observed=True)["Churn Value"].agg(["mean", "size"])
        degenerate = rates[((rates["mean"] <= 0.001) | (rates["mean"] >= 0.999)) & (rates["size"] >= 50)]
        if len(degenerate):
            findings[col] = {
                "verdict": "leaked",
                "degenerate_groups": int(len(degenerate)),
                "rows_affected": int(degenerate["size"].sum()),
                "share_of_rows": round(float(degenerate["size"].sum() / len(df)), 4),
                "detail": (
                    f"{len(degenerate)} value groups covering {int(degenerate['size'].sum()):,} rows "
                    "have a churn rate of exactly 0 or exactly 1"
                ),
            }

    if "Churn Score" in df:
        # Negative overlap means the two classes are fully separated by the score.
        overlap = float(df.loc[y == 0, "Churn Score"].max() - df.loc[y == 1, "Churn Score"].min())
        findings.setdefault("Churn Score", {})["class_overlap_points"] = overlap
    return findings


# --------------------------------------------------------------------------------------
# Analogue model
# --------------------------------------------------------------------------------------

#: How each IBM predictor maps onto a membership feature.
ANALOGUE_MAP = {
    "auto_payment": ("auto_renewal", "Automatic payment method -> continuous payment mandate"),
    "long_tenure": ("long_tenure", "Tenure >= 60 months -> member of 5+ years"),
    "multi_service": ("multi_service_user", "3+ add-on services -> uses 3+ member services"),
    "high_charge": ("fee_increase", "Monthly charge in the top quartile -> fee pressure on a price-sensitive member"),
    "referred": ("no_recent_advocacy", "Has referred another customer -> has referred a member"),
    "month_to_month": (None, "No membership analogue: annual terms have no contract-length equivalent"),
}


def fit_logistic(X: np.ndarray, y: np.ndarray, l2: float = 1e-3) -> np.ndarray:
    X1 = np.column_stack([np.ones(len(X)), X])

    def nll(w):
        z = X1 @ w
        return -np.sum(y * z - np.logaddexp(0.0, z)) / len(y) + l2 * np.sum(w[1:] ** 2)

    def grad(w):
        p = 1.0 / (1.0 + np.exp(-(X1 @ w)))
        g = X1.T @ (p - y) / len(y)
        g[1:] += 2 * l2 * w[1:]
        return g

    return minimize(nll, np.zeros(X1.shape[1]), jac=grad, method="L-BFGS-B").x


def _auc(y: np.ndarray, score: np.ndarray) -> float:
    order = np.argsort(score)
    ranks = np.empty(len(score), dtype=float)
    ranks[order] = np.arange(1, len(score) + 1)
    n1, n0 = float(y.sum()), float((1 - y).sum())
    return float((ranks[y == 1].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def fit_analogue_model(df: pd.DataFrame):
    """Fit the leak-free analogue model on the comparable sub-population.

    Customers with no internet service are excluded: they hold a structurally different
    product (phone only), and including them inverts the sign on service breadth,
    because a cheap single-product customer is not the same thing as a disengaged one.
    """
    sub = df[df["has_internet"] == 1].copy()
    charge_q75 = sub["Monthly Charge"].quantile(0.75)

    X = pd.DataFrame(
        {
            "auto_payment": sub["auto_payment"],
            "long_tenure": (sub["Tenure in Months"] >= 60).astype(int),
            "multi_service": (sub["n_addon_services"] >= 3).astype(int),
            "high_charge": (sub["Monthly Charge"] >= charge_q75).astype(int),
            "referred": (sub["Number of Referrals"] > 0).astype(int),
            "month_to_month": (sub["Contract"] == "Month-to-Month").astype(int),
        }
    )
    y = sub["Churn Value"].to_numpy(dtype=float)
    w = fit_logistic(X.to_numpy(dtype=float), y)
    coefficients = {"intercept": float(w[0])}
    coefficients.update({c: float(v) for c, v in zip(X.columns, w[1:])})
    score = np.column_stack([np.ones(len(X)), X.to_numpy(dtype=float)]) @ w
    return coefficients, _auc(y, score), int(len(sub)), float(y.mean())


# --------------------------------------------------------------------------------------
# Calibration
# --------------------------------------------------------------------------------------


def measure(df: pd.DataFrame, source: str) -> IbmCalibration:
    cal = IbmCalibration(source=source, n_source_rows=int(len(df)))
    y = df["Churn Value"]

    tenure = df["Tenure in Months"].astype(float)
    cal.tenure_mean_months = round(float(tenure.mean()), 3)
    cal.tenure_sd_months = round(float(tenure.std()), 3)
    cal.tenure_max_months = int(tenure.max())
    cal.tenure_deciles = [round(float(v), 2) for v in np.quantile(tenure, np.linspace(0, 1, 11))]

    cal.month_to_month_share = round(float((df["Contract"] == "Month-to-Month").mean()), 4)
    cal.automatic_payment_share = round(float(df["auto_payment"].mean()), 4)
    cal.payment_method_source = (
        "original workbook (labels carry the automatic marker)"
        if "payment_method_original" in df
        else "extended workbook (UNRELIABLE: relabelling is lossy)"
    )
    cal.paperless_billing_share = round(
        float(df["Paperless Billing"].astype(str).str.lower().eq("yes").mean()), 4
    )
    cal.churn_rate = round(float(y.mean()), 4)
    cal.joined_share = round(float((df["Customer Status"] == "Joined").mean()), 4)

    charge = df["Monthly Charge"].astype(float)
    cal.churn_charge_ratio = round(float(charge[y == 1].mean() / charge[y == 0].mean()), 4)

    cltv = df["CLTV"].astype(float)
    cal.cltv_mean = round(float(cltv.mean()), 1)
    cal.cltv_cv = round(float(cltv.std() / cltv.mean()), 4)
    cal.cltv_churn_ratio = round(float(cltv[y == 1].mean() / cltv[y == 0].mean()), 4)

    bands = pd.cut(df["Age"], AGE_BAND_EDGES, labels=AGE_BAND_LABELS)
    raw = bands.value_counts(normalize=True).sort_index()
    cal.age_shares_raw = {str(k): round(float(v), 4) for k, v in raw.items()}
    adjusted = raw * pd.Series(PROFESSIONAL_AGE_WEIGHTING)
    adjusted = adjusted / adjusted.sum()
    cal.age_shares_adjusted = {str(k): round(float(v), 4) for k, v in adjusted.items()}

    refs = df["Number of Referrals"].astype(float)
    cal.referrer_share = round(float((refs > 0).mean()), 4)
    cal.referrals_mean_among_referrers = round(float(refs[refs > 0].mean()), 3)
    cal.referrals_max = int(refs.max())
    cal.referrals_churn_ratio = round(float(refs[y == 1].mean() / refs[y == 0].mean()), 4)

    sat = df["Satisfaction Score"].value_counts(normalize=True).sort_index()
    cal.satisfaction_shares = {int(k): round(float(v), 4) for k, v in sat.items()}

    churned = df[y == 1]
    cat = churned["Churn Category"].value_counts(normalize=True)
    cal.churn_category_shares = {str(k): round(float(v), 4) for k, v in cat.items()}
    reason = churned["Churn Reason"].value_counts(normalize=True)
    cal.churn_reason_shares = {str(k): round(float(v), 4) for k, v in reason.head(20).items()}
    by_cat_tenure = churned.groupby("Churn Category")["Tenure in Months"].mean()
    cal.reason_tenure_spread_months = round(float(by_cat_tenure.max() - by_cat_tenure.min()), 2)

    cal.leakage = detect_leakage(df)
    coefficients, auc_value, n, rate = fit_analogue_model(df)
    cal.analogue_coefficients = {k: round(v, 4) for k, v in coefficients.items()}
    cal.analogue_auc = round(auc_value, 4)
    cal.analogue_n = n
    cal.analogue_churn_rate = round(rate, 4)

    cal.notes.append(f"Calibrated from the extended IBM Cognos sample ({len(df):,} customers) in '{source}'.")
    if cal.leakage:
        cal.notes.append(
            "Satisfaction Score and Churn Score are post-hoc annotations and are excluded "
            "from the analogue model; only their marginal distributions are used."
        )
    cal.notes.append(
        f"Tenure is censored at {cal.tenure_max_months} months in the source, so the membership "
        "tenure tail is extended beyond what the seed can evidence."
    )
    if "payment_method_original" in df:
        cal.notes.append(
            "Payment method is taken from the original workbook: the extended workbook "
            "relabels the four original categories into three and folds manual "
            "'Electronic check' customers into 'Bank Withdrawal', which would overstate "
            "the automatic-payment share as 95.6% instead of 43.5%."
        )
    cal.notes.append(
        "Location, population, gender, marital status and dependants are deliberately not "
        "carried over: US geography, and sensitive attributes of no analytical value to a "
        "membership model."
    )
    return cal


def load_calibration(verbose: bool = True, refresh: bool = False) -> IbmCalibration:
    """Return the calibration, preferring the cached JSON, then the workbooks, then the
    published fallback values baked into :class:`IbmCalibration`."""
    if not refresh and CACHE_FILE.exists():
        data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        data["satisfaction_shares"] = {int(k): v for k, v in data.get("satisfaction_shares", {}).items()}
        cal = IbmCalibration(**data)
        if verbose:
            print(f"  seed: cached calibration ({CACHE_FILE.name}, source: {cal.source})")
        return cal

    source_dir = find_source_dir()
    if source_dir is None:
        cal = IbmCalibration()
        cal.notes.append(
            "IBM workbooks not found; using published marginals. Place the extended IBM "
            "Cognos sample in 'IBM Source Files/' and run 'python -m src.generators.calibrate'."
        )
        if verbose:
            print(f"  seed: {cal.notes[-1]}")
        return cal

    df = load_source(source_dir)
    cal = measure(df, source_dir.name)
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(cal.to_json(), encoding="utf-8")
    if verbose:
        print(f"  seed: calibrated from {source_dir} ({len(df):,} rows) -> {CACHE_FILE.name}")
    return cal
