"""Generate the data-quality check results that feed the Power BI data-quality page.

Row counts per check are anchored to the *actual* row counts of the generated tables and
grown backwards over time, so the trend line in the report is consistent with the data
that was produced rather than free-floating.
"""

from __future__ import annotations

import numpy as np

from . import config
from .utils import iso_ts

DQ_COLUMNS = [
    "check_id",
    "pipeline_run_id",
    "source_table",
    "check_name",
    "check_category",
    "records_checked",
    "failed_records",
    "failure_rate",
    "severity",
    "check_timestamp",
]

#: (source_table, check_name, check_category, baseline failure rate, severity)
CHECKS = [
    ("members", "member_id_not_null", "Completeness", 0.0000, "Critical"),
    ("members", "member_id_unique", "Uniqueness", 0.0000, "Critical"),
    ("members", "join_date_not_future", "Validity", 0.0002, "High"),
    ("members", "membership_type_in_reference_list", "Validity", 0.0004, "Medium"),
    ("members", "annual_fee_within_expected_range", "Validity", 0.0011, "Medium"),
    ("members", "region_not_null", "Completeness", 0.0018, "Low"),
    ("members", "churn_date_after_join_date", "Consistency", 0.0000, "Critical"),
    ("membership_history", "no_overlapping_terms", "Consistency", 0.0009, "High"),
    ("membership_history", "member_id_foreign_key", "Referential integrity", 0.0003, "Critical"),
    ("membership_history", "effective_to_after_effective_from", "Validity", 0.0001, "High"),
    ("membership_history", "annual_fee_not_null", "Completeness", 0.0006, "Medium"),
    ("website_activity", "member_id_foreign_key", "Referential integrity", 0.0012, "Critical"),
    ("website_activity", "activity_date_within_window", "Validity", 0.0005, "High"),
    ("website_activity", "page_views_ge_session_count", "Consistency", 0.0021, "Medium"),
    ("website_activity", "no_duplicate_member_week", "Uniqueness", 0.0004, "High"),
    ("website_activity", "average_session_minutes_positive", "Validity", 0.0007, "Low"),
    ("login_history", "member_id_foreign_key", "Referential integrity", 0.0009, "Critical"),
    ("login_history", "login_timestamp_parseable", "Validity", 0.0003, "High"),
    ("login_history", "session_duration_within_range", "Validity", 0.0026, "Low"),
    ("login_history", "no_duplicate_login_id", "Uniqueness", 0.0000, "Critical"),
    ("events", "event_id_unique", "Uniqueness", 0.0000, "Critical"),
    ("events", "capacity_positive", "Validity", 0.0008, "Medium"),
    ("events", "event_cost_not_negative", "Validity", 0.0000, "Medium"),
    ("event_attendance", "event_id_foreign_key", "Referential integrity", 0.0014, "Critical"),
    ("event_attendance", "member_id_foreign_key", "Referential integrity", 0.0011, "Critical"),
    ("event_attendance", "attendance_status_in_reference_list", "Validity", 0.0002, "High"),
    ("event_attendance", "registration_before_event_date", "Consistency", 0.0017, "Medium"),
    ("event_attendance", "feedback_score_between_1_and_5", "Validity", 0.0004, "Low"),
    ("learning_activity", "course_id_foreign_key", "Referential integrity", 0.0010, "Critical"),
    ("learning_activity", "completion_percentage_between_0_and_100", "Validity", 0.0003, "High"),
    ("learning_activity", "completed_implies_100_percent", "Consistency", 0.0013, "Medium"),
    ("learning_activity", "assessment_score_present_when_completed", "Completeness", 0.0029, "Low"),
    ("campaigns", "campaign_id_unique", "Uniqueness", 0.0000, "Critical"),
    ("campaigns", "end_date_after_start_date", "Validity", 0.0006, "Medium"),
    ("marketing_engagement", "campaign_id_foreign_key", "Referential integrity", 0.0008, "Critical"),
    ("marketing_engagement", "opened_implies_delivered", "Consistency", 0.0005, "High"),
    ("marketing_engagement", "clicked_implies_opened", "Consistency", 0.0004, "High"),
    ("marketing_engagement", "sent_date_within_campaign_window", "Validity", 0.0031, "Low"),
    ("member_feedback", "rating_between_1_and_5", "Validity", 0.0002, "High"),
    ("member_feedback", "feedback_text_not_empty", "Completeness", 0.0024, "Medium"),
    ("member_feedback", "sentiment_label_in_reference_list", "Validity", 0.0007, "Medium"),
    ("model_predictions", "churn_probability_between_0_and_1", "Validity", 0.0000, "Critical"),
    ("model_predictions", "one_row_per_member_per_run", "Uniqueness", 0.0003, "High"),
    ("model_predictions", "risk_category_matches_probability_band", "Consistency", 0.0009, "Medium"),
    ("ai_insights", "prediction_run_id_foreign_key", "Referential integrity", 0.0006, "Critical"),
    ("ai_insights", "executive_summary_not_empty", "Completeness", 0.0034, "Medium"),
    ("ai_insights", "validation_status_reviewed", "Governance", 0.0180, "Low"),
]


def generate_data_quality(rng: np.random.Generator, row_counts: dict[str, int], as_of: int, n_runs: int):
    """Yield data-quality rows for ``n_runs`` daily pipeline runs ending at ``as_of``."""
    check_id = 0
    for run_index in range(n_runs):
        run_ord = as_of - (n_runs - 1 - run_index)
        run_id = f"PIPE-{run_ord}"
        # The warehouse grows over time, so earlier runs checked fewer records.
        growth = 1.0 - 0.0009 * (n_runs - 1 - run_index)
        # Occasional bad days: a source feed misbehaves and failure rates spike.
        incident = rng.random() < 0.08
        incident_table = str(rng.choice([c[0] for c in CHECKS])) if incident else None

        for source_table, name, category, base_rate, severity in CHECKS:
            total = int(max(row_counts.get(source_table, 1_000) * growth, 1))
            rate = base_rate * float(rng.lognormal(0, 0.55))
            if incident_table == source_table:
                rate *= float(rng.uniform(8, 40))
            rate = min(rate, 0.35)
            failed = int(rng.binomial(total, rate)) if rate > 0 else 0
            check_id += 1
            yield [
                f"DQ{check_id:08d}",
                run_id,
                source_table,
                name,
                category,
                total,
                failed,
                round(failed / total, 6),
                severity,
                iso_ts(run_ord, int(rng.integers(120, 200))),
            ]
