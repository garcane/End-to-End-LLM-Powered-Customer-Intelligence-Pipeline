"""Configuration for the Synthetic Professional Membership Engagement and Retention Dataset.

Everything that controls the shape, scale and behaviour of the generated data lives
here so that the generation process is reproducible and auditable.  See
docs/data-generation-methodology.md for the reasoning behind these values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

# --------------------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SEED_DIR = DATA_DIR / "seed"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
SAMPLE_DIR = DATA_DIR / "sample"
DICTIONARY_DIR = DATA_DIR / "data_dictionary"

IBM_SEED_FILE = SEED_DIR / "ibm_telco_churn.csv"

# --------------------------------------------------------------------------------------
# Observation window
# --------------------------------------------------------------------------------------

#: First date for which behavioural activity is generated.
WINDOW_START = date(2021, 9, 1)
#: Last date for which behavioural activity is generated ("today" for the dataset).
AS_OF_DATE = date(2026, 8, 31)
#: Earliest possible join date (legacy members pre-date the activity window).
EARLIEST_JOIN = date(2014, 1, 1)

DEFAULT_SEED = 20260913

# --------------------------------------------------------------------------------------
# Scale profiles
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class ScaleProfile:
    """Controls dataset volume.  Row counts for every other table follow from
    ``n_members`` because all activity is generated per member and per active week."""

    name: str
    n_members: int
    n_events: int
    n_campaigns: int
    n_courses: int
    #: Number of monthly scoring runs to emit into model_predictions.
    n_prediction_runs: int
    #: Number of pipeline runs to emit into data_quality_results.
    n_pipeline_runs: int
    #: Members processed per chunk.  Lower values use less memory.
    chunk_size: int


SCALE_PROFILES = {
    # Fast smoke-test scale: runs in a few seconds.
    "dev": ScaleProfile("dev", 1_000, 160, 60, 30, 3, 20, 500),
    # Mid scale, useful for iterating on the Power BI model without a long wait.
    "demo": ScaleProfile("demo", 8_000, 700, 150, 60, 6, 40, 1_000),
    # Portfolio scale, as recommended in "Data Recomendations.md".
    "full": ScaleProfile("full", 25_000, 1_600, 265, 90, 6, 60, 1_000),
}

DEFAULT_SCALE = "full"

# --------------------------------------------------------------------------------------
# Reference vocabularies
# --------------------------------------------------------------------------------------

REGIONS = [
    ("London and South East", 0.27),
    ("Midlands", 0.15),
    ("North of England", 0.16),
    ("South West and Wales", 0.11),
    ("Scotland and Northern Ireland", 0.09),
    ("Republic of Ireland", 0.05),
    ("Europe (non-UK)", 0.08),
    ("Rest of World", 0.09),
]

MEMBERSHIP_TYPES = [
    # name, base annual fee, share of new joiners
    ("Student", 35.0, 0.14),
    ("Associate", 120.0, 0.22),
    ("Professional", 245.0, 0.34),
    ("Chartered", 395.0, 0.17),
    ("Fellow", 520.0, 0.05),
    ("Retired", 75.0, 0.04),
    ("Corporate Affiliate", 310.0, 0.04),
]

#: Relative engagement uplift by membership type (multiplies the latent engagement trait).
TYPE_ENGAGEMENT_UPLIFT = {
    "Student": 0.85,
    "Associate": 0.92,
    "Professional": 1.00,
    "Chartered": 1.18,
    "Fellow": 1.30,
    "Retired": 0.70,
    "Corporate Affiliate": 1.05,
}

AGE_BANDS = [
    ("18-24", 0.11),
    ("25-34", 0.27),
    ("35-44", 0.24),
    ("45-54", 0.19),
    ("55-64", 0.13),
    ("65+", 0.06),
]

ORGANISATION_TYPES = [
    ("Private sector - large", 0.26),
    ("Private sector - SME", 0.23),
    ("Public sector", 0.19),
    ("Charity or not-for-profit", 0.09),
    ("Higher education", 0.10),
    ("Self-employed or consultant", 0.09),
    ("Not currently employed", 0.04),
]

CAREER_STAGES = [
    ("Student", 0.12),
    ("Early career", 0.26),
    ("Mid career", 0.33),
    ("Senior", 0.21),
    ("Executive", 0.05),
    ("Retired", 0.03),
]

ACQUISITION_CHANNELS = [
    ("Organic search", 0.21),
    ("Employer scheme", 0.18),
    ("Referral", 0.15),
    ("Event", 0.12),
    ("Paid social", 0.11),
    ("Email campaign", 0.10),
    ("University partnership", 0.08),
    ("Direct", 0.05),
]

#: Acquisition channels associated with above/below average member quality.
CHANNEL_QUALITY = {
    "Organic search": 0.03,
    "Employer scheme": 0.10,
    "Referral": 0.12,
    "Event": 0.08,
    "Paid social": -0.12,
    "Email campaign": -0.04,
    "University partnership": -0.02,
    "Direct": 0.05,
}

DEVICE_TYPES = [("Desktop", 0.52), ("Mobile", 0.36), ("Tablet", 0.12)]
LOGIN_PLATFORMS = [("Web", 0.61), ("Mobile app", 0.29), ("Learning platform", 0.10)]

EVENT_CATEGORIES = [
    ("Webinar", 0.34),
    ("Conference", 0.09),
    ("Regional branch meeting", 0.19),
    ("Technical workshop", 0.16),
    ("Networking", 0.12),
    ("Awards and celebration", 0.04),
    ("Career development", 0.06),
]

EVENT_FORMATS = [("Online", 0.58), ("In person", 0.30), ("Hybrid", 0.12)]

BOOKING_CHANNELS = [("Website", 0.58), ("Email link", 0.24), ("Mobile app", 0.13), ("Telephone", 0.05)]

ATTENDANCE_STATUSES = ["Attended", "Cancelled", "No-show", "Registered", "Waitlisted"]

CAMPAIGN_TYPES = [
    ("Newsletter", 0.30),
    ("Event promotion", 0.22),
    ("Renewal reminder", 0.16),
    ("Learning promotion", 0.12),
    ("Win-back", 0.08),
    ("Member survey", 0.07),
    ("Upgrade offer", 0.05),
]

CAMPAIGN_CHANNELS = [("Email", 0.74), ("SMS", 0.08), ("In-app", 0.11), ("Direct mail", 0.07)]

TARGET_SEGMENTS = [
    "All members",
    "Lapsing risk",
    "New joiners",
    "Highly engaged",
    "Learning audience",
    "Regional audience",
    "Student and early career",
]

COURSE_CATALOGUE_PREFIXES = [
    "Foundations of",
    "Advanced",
    "Practical",
    "Leading",
    "Introduction to",
    "Certificate in",
    "Masterclass:",
]

COURSE_TOPICS = [
    "Data Governance",
    "Professional Ethics",
    "Project Delivery",
    "Risk Management",
    "Stakeholder Communication",
    "Sustainability Reporting",
    "Digital Transformation",
    "People Leadership",
    "Regulatory Compliance",
    "Financial Awareness",
    "Coaching and Mentoring",
    "Change Management",
]

FEEDBACK_CHANNELS = [
    ("Annual member survey", 0.24),
    ("Event feedback form", 0.31),
    ("Support ticket", 0.18),
    ("Website feedback widget", 0.15),
    ("Cancellation survey", 0.12),
]

FEEDBACK_CATEGORIES = [
    "Events and content",
    "Learning and development",
    "Membership value",
    "Website and digital services",
    "Communications",
    "Customer service",
    "Fees and billing",
]

CANCELLATION_REASONS = [
    ("Cost or affordability", 0.26),
    ("Lack of relevance to my role", 0.21),
    ("Not enough time to use benefits", 0.17),
    ("Employer no longer funding", 0.14),
    ("Joined an alternative body", 0.09),
    ("Career change or retirement", 0.08),
    ("Service dissatisfaction", 0.05),
]

#: Risk bands are set relative to the realised annual lapse rate (~11%), not to 0.5.
#: With an imbalanced outcome, fixed 0.35/0.65 bands would put almost every member in
#: the lowest band and leave the churn-risk report with nothing to show.
RISK_THRESHOLDS = {"low_max": 0.10, "medium_max": 0.25}

#: Probability above which model_predictions.predicted_churn is set to 1.  Chosen to
#: favour recall, which is the usual operating point for a retention campaign.
PREDICTION_THRESHOLD = 0.25

SEGMENTS = {
    1: "Champions",
    2: "Steady professionals",
    3: "Learning-led",
    4: "Event-led",
    5: "Passive renewers",
    6: "Disengaging",
    7: "New and forming",
}

# --------------------------------------------------------------------------------------
# Behavioural model parameters
# --------------------------------------------------------------------------------------

#: Coefficients for the churn log-odds model, as published in "Data Recomendations.md"
#: and extended with a small number of additional, documented terms.
CHURN_COEFFICIENTS = {
    "intercept": -2.2,
    "inactive_90_days": 0.9,
    "negative_feedback": 0.7,
    "failed_payment": 0.8,
    "no_event_attendance": 0.6,
    "declining_logins": 0.5,
    "completed_learning": -0.7,
    "attended_first_90_days": -0.6,
    "auto_renewal": -0.5,
    "long_tenure": -0.4,
    # Extensions beyond the published formula.
    "low_campaign_engagement": 0.35,
    "fee_increase": 0.30,
    "student_to_full_transition": 0.45,
    "multi_service_user": -0.45,
}

#: Nominal churn model quality target.  The "model" in model_predictions is a noisy
#: view of the true log-odds; larger noise means a weaker (more realistic) model.
PREDICTION_NOISE_SD = 0.85

#: Annual fee uplift applied at each renewal (inflationary pricing).
ANNUAL_FEE_UPLIFT = 0.035

#: Probability that a renewal payment fails, by payment mode.
FAILED_PAYMENT_RATE = {"auto": 0.035, "manual": 0.11}

LLM_PROVIDER = "Ollama"
LLM_MODEL = "qwen2.5:7b-instruct"
PROMPT_VERSION = "v1.2.0"
MODEL_NAME = "membership_churn_gbm"
MODEL_VERSION = "1.4.0"
