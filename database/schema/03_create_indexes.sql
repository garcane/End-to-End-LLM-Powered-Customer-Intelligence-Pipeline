-- Secondary indexes for the Synthetic Professional Membership dataset.
--
-- Run AFTER 02_load_csv.sql. Building these against finished tables is much faster
-- than maintaining them row by row during a 5.4 million row \copy.
--
--   psql -d membership -f database/schema/03_create_indexes.sql

BEGIN;

-- ---------------------------------------------------------------------------------
-- Indexes
--
-- Every fact is queried the same two ways: by member (drill-through from a member
-- profile) and by date (trend pages and incremental refresh windows).
-- ---------------------------------------------------------------------------------

CREATE INDEX idx_members_status        ON members (membership_status);
CREATE INDEX idx_members_join_date     ON members (join_date);
CREATE INDEX idx_members_churn_date    ON members (churn_date) WHERE churn_date IS NOT NULL;

CREATE INDEX idx_mh_member             ON membership_history (member_id, effective_from);

CREATE INDEX idx_wa_member_date        ON website_activity (member_id, activity_date);
CREATE INDEX idx_wa_date               ON website_activity (activity_date);

CREATE INDEX idx_lh_member_ts          ON login_history (member_id, login_timestamp);
CREATE INDEX idx_lh_ts                 ON login_history (login_timestamp);

CREATE INDEX idx_ea_member             ON event_attendance (member_id);
CREATE INDEX idx_ea_event              ON event_attendance (event_id);
CREATE INDEX idx_ea_reg_date           ON event_attendance (registration_date);

CREATE INDEX idx_la_member_date        ON learning_activity (member_id, activity_date);
CREATE INDEX idx_la_course             ON learning_activity (course_id);

CREATE INDEX idx_me_member_date        ON marketing_engagement (member_id, sent_date);
CREATE INDEX idx_me_campaign           ON marketing_engagement (campaign_id);

CREATE INDEX idx_mr_referrer           ON member_referrals (referring_member_id, referral_date);
CREATE INDEX idx_mr_referred            ON member_referrals (referred_member_id) WHERE referred_member_id IS NOT NULL;

CREATE INDEX idx_fb_member_date        ON member_feedback (member_id, submitted_date);
CREATE INDEX idx_fb_sentiment          ON member_feedback (sentiment_label);

CREATE INDEX idx_mp_run                ON model_predictions (prediction_run_id);
CREATE INDEX idx_mp_member_date        ON model_predictions (member_id, prediction_date);
CREATE INDEX idx_mp_risk               ON model_predictions (risk_category) WHERE risk_category <> 'Low';

CREATE INDEX idx_ai_run                ON ai_insights (prediction_run_id);

CREATE INDEX idx_dq_run                ON data_quality_results (pipeline_run_id);
CREATE INDEX idx_dq_table_ts           ON data_quality_results (source_table, check_timestamp);

CREATE INDEX idx_events_date           ON events (event_date);
CREATE INDEX idx_campaigns_start       ON campaigns (start_date);

COMMIT;

ANALYZE;
