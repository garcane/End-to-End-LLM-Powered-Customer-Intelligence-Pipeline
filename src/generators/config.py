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
    "full": ScaleProfile("full", 25_000, 1_600, 295, 90, 6, 60, 1_000),
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


#: Risk bands are set relative to the realised annual lapse rate (~11%), not to 0.5.
#: With an imbalanced outcome, fixed 0.35/0.65 bands would put almost every member in
#: the lowest band and leave the churn-risk report with nothing to show.
RISK_THRESHOLDS = {"low_max": 0.10, "medium_max": 0.25}

#: Probability above which model_predictions.predicted_churn is set to 1.  Chosen to
#: favour recall, which is the usual operating point for a retention campaign.
PREDICTION_THRESHOLD = 0.25

#: Behavioural segments. Exported as segments.csv so that model_predictions.segment_id
#: has a dimension to join to, rather than being a bare integer in the semantic model.
SEGMENTS = {
    1: ("Champions", "High engagement across events, learning and digital. Recruit as advocates."),
    2: ("Steady professionals", "Consistent, unspectacular use. Renew reliably; protect with light touch."),
    3: ("Learning-led", "Engagement is concentrated in CPD. Promote learning pathways and assessments."),
    4: ("Event-led", "Engagement is concentrated in events. Promote the regional and webinar programme."),
    5: ("Passive renewers", "Pay by mandate but barely use anything. Highest silent-lapse risk."),
    6: ("Disengaging", "Activity falling and risk elevated. Priority for retention intervention."),
    7: ("New and forming", "Inside the first year. Onboarding determines whether they become 1-4 or 6."),
}

# --------------------------------------------------------------------------------------
# Behavioural model parameters
# --------------------------------------------------------------------------------------

#: Coefficients for the churn log-odds model.
#:
#: The first nine are published in "Data Recomendations.md" and are used exactly as
#: specified. Two of them (auto_renewal, long_tenure) are independently corroborated by
#: the IBM analogue fit.
#:
#: The extension terms below are no longer asserted: three of the four are estimated
#: from the extended IBM Telco sample by fitting a leak-free logistic model on mapped
#: analogue predictors. See docs/ibm-telco-calibration.md for the fit and the mapping.
CHURN_COEFFICIENTS = {
    "intercept": -2.2,
    # --- published in Data Recomendations.md ---------------------------------------
    "inactive_90_days": 0.9,
    "negative_feedback": 0.7,
    "failed_payment": 0.8,
    "no_event_attendance": 0.6,
    "declining_logins": 0.5,
    "completed_learning": -0.7,
    "attended_first_90_days": -0.6,
    "auto_renewal": -0.5,          # IBM analogue (auto_payment): -0.53
    "long_tenure": -0.4,           # IBM analogue (long_tenure):  -0.64
    # --- extensions ------------------------------------------------------------------
    # Estimated from IBM (high_charge, +0.766). A fee rise matters far more than the
    # +0.30 originally assumed here.
    "fee_increase": 0.77,
    # Estimated from IBM (multi_service, -0.250), fitted on internet subscribers only.
    "multi_service_user": -0.25,
    # Estimated from IBM (referred, -0.206), sign inverted: the feature is the *absence*
    # of advocacy. Churned customers referred 0.21x as many people as retained ones.
    "no_recent_advocacy": 0.21,
    # Retained on domain grounds but reduced from 0.35: IBM's closest analogue (offer
    # take-up) returned +0.03, i.e. no effect. Kept because unopened member
    # communications are a genuine warning sign in a membership body, weighted down
    # because the seed does not support the original figure.
    "low_campaign_engagement": 0.25,
    # No IBM analogue exists. Domain judgement: the student-to-full transition is the
    # single largest lapse point in professional membership.
    "student_to_full_transition": 0.45,
}

#: Membership churn taxonomy, mirroring the two-level structure IBM uses
#: (Churn Category -> Churn Reason).
#:
#: The *structure* is taken from IBM; the *weights* are a domain judgement. A
#: professional body loses far fewer members to a direct competitor than a telco does
#: (IBM: 45% Competitor) and far more to cost and simple non-use. IBM's measured shares
#: are reported alongside these in docs/ibm-telco-calibration.md.
CHURN_CATEGORIES = {
    "Price": (
        0.30,
        [
            ("Cost or affordability", 0.45),
            ("Employer no longer funding", 0.35),
            ("Fee increase at renewal", 0.20),
        ],
    ),
    "Dissatisfaction": (
        0.26,
        [
            ("Lack of relevance to my role", 0.42),
            ("Limited range of events", 0.24),
            ("Content or standards out of date", 0.19),
            ("Learning platform problems", 0.15),
        ],
    ),
    "Other": (
        0.24,
        [
            ("Career change or retirement", 0.40),
            ("Not enough time to use benefits", 0.38),
            ("Moved overseas", 0.12),
            ("Reason not given", 0.10),
        ],
    ),
    "Attitude": (
        0.10,
        [
            ("Attitude of membership support", 0.55),
            ("Poor complaint handling", 0.45),
        ],
    ),
    "Competitor": (
        0.10,
        [
            ("Joined an alternative professional body", 0.62),
            ("Employer scheme with another body", 0.38),
        ],
    ),
}

#: Window for the no_recent_advocacy feature. Referral rates themselves are tuned in
#: activity.REFERRAL_INVITE_RATE_YEAR, calibrated to IBM: 45.8% of customers referred at
#: least one other, averaging 4.27 referrals among those who did.
ADVOCACY_WINDOW_DAYS = 365

#: Nominal churn model quality target.  The "model" in model_predictions is a noisy
#: view of the true log-odds; larger noise means a weaker (more realistic) model.
PREDICTION_NOISE_SD = 0.85

#: Annual fee uplift applied at each renewal (inflationary pricing).
ANNUAL_FEE_UPLIFT = 0.035

#: Probability that a renewal payment fails, by payment mode.
FAILED_PAYMENT_RATE = {"auto": 0.035, "manual": 0.11}

#: Contribution margin on a membership subscription, used to turn expected remaining
#: years into a lifetime value.
#:
#: Note that IBM's CLTV column is a bounded index (2003-6500) rather than a currency
#: amount, so only the *concept* transfers, not the scale or the spread.
#: predicted_lifetime_value here is a real revenue figure -- annual fee times expected
#: remaining years times margin -- and is deliberately more dispersed than IBM's index.
CONTRIBUTION_MARGIN = 0.72

LLM_PROVIDER = "Ollama"
LLM_MODEL = "qwen2.5:7b-instruct"
PROMPT_VERSION = "v1.2.0"
MODEL_NAME = "membership_churn_gbm"
MODEL_VERSION = "1.4.0"
