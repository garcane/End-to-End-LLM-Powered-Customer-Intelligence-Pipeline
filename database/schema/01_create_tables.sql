-- Synthetic Professional Membership Engagement and Retention Dataset
-- PostgreSQL schema for the raw landing layer.
--
-- Column names and types match the generated CSV files exactly, so the files load with
-- \copy and no transformation. Star-schema views for the Power BI semantic model belong
-- in a later migration, not here.
--
--   psql -d membership -f database/schema/01_create_tables.sql
--   psql -d membership -f database/schema/02_load_csv.sql   (edit the path first)

BEGIN;

DROP TABLE IF EXISTS data_quality_results, ai_insights, model_predictions,
    member_training_features, member_feedback, marketing_engagement, learning_activity,
    event_attendance, login_history, website_activity, membership_history,
    campaigns, courses, events, members CASCADE;

-- ---------------------------------------------------------------------------------
-- Dimensions
-- ---------------------------------------------------------------------------------

CREATE TABLE members (
    member_id             VARCHAR(12)  PRIMARY KEY,
    join_date             DATE         NOT NULL,
    membership_status     VARCHAR(20)  NOT NULL,
    membership_type       VARCHAR(30)  NOT NULL,
    region                VARCHAR(40)  NOT NULL,
    age_band              VARCHAR(10)  NOT NULL,
    organisation_type     VARCHAR(40)  NOT NULL,
    career_stage          VARCHAR(20)  NOT NULL,
    acquisition_channel   VARCHAR(30)  NOT NULL,
    renewal_date          DATE,
    annual_fee            NUMERIC(10, 2) NOT NULL,
    auto_renewal          BOOLEAN      NOT NULL,
    communication_consent BOOLEAN      NOT NULL,
    churn_date            DATE,
    churn_flag            SMALLINT     NOT NULL,
    CONSTRAINT members_status_chk    CHECK (membership_status IN ('Active','Lapsed','Cancelled','Suspended')),
    CONSTRAINT members_churn_chk     CHECK (churn_flag IN (0, 1)),
    CONSTRAINT members_churn_seq_chk CHECK (churn_date IS NULL OR churn_date > join_date),
    -- A lapsed member has an exit date and no forward renewal date, and vice versa.
    CONSTRAINT members_churn_dates_chk CHECK (
        (churn_flag = 1 AND churn_date IS NOT NULL AND renewal_date IS NULL)
     OR (churn_flag = 0 AND churn_date IS NULL     AND renewal_date IS NOT NULL)
    )
);

CREATE TABLE events (
    event_id       VARCHAR(12)  PRIMARY KEY,
    event_name     TEXT         NOT NULL,
    event_category VARCHAR(40)  NOT NULL,
    event_format   VARCHAR(20)  NOT NULL,
    event_date     DATE         NOT NULL,
    region         VARCHAR(40)  NOT NULL,
    capacity       INTEGER      NOT NULL CHECK (capacity > 0),
    event_cost     NUMERIC(10, 2) NOT NULL CHECK (event_cost >= 0)
);

CREATE TABLE courses (
    course_id        VARCHAR(12) PRIMARY KEY,
    course_name      TEXT        NOT NULL,
    course_category  VARCHAR(60) NOT NULL,
    course_level     VARCHAR(20) NOT NULL,
    expected_minutes INTEGER     NOT NULL CHECK (expected_minutes > 0),
    cpd_hours        NUMERIC(6, 2) NOT NULL,
    launch_date      DATE        NOT NULL
);

CREATE TABLE campaigns (
    campaign_id    VARCHAR(12) PRIMARY KEY,
    campaign_name  TEXT        NOT NULL,
    campaign_type  VARCHAR(30) NOT NULL,
    start_date     DATE        NOT NULL,
    end_date       DATE        NOT NULL,
    target_segment VARCHAR(40) NOT NULL,
    channel        VARCHAR(20) NOT NULL,
    campaign_cost  NUMERIC(12, 2) NOT NULL CHECK (campaign_cost >= 0),
    CONSTRAINT campaigns_dates_chk CHECK (end_date >= start_date)
);

-- ---------------------------------------------------------------------------------
-- Slowly changing dimension
-- ---------------------------------------------------------------------------------

CREATE TABLE membership_history (
    membership_history_id VARCHAR(14) PRIMARY KEY,
    member_id             VARCHAR(12) NOT NULL REFERENCES members (member_id),
    effective_from        DATE        NOT NULL,
    effective_to          DATE,
    membership_type       VARCHAR(30) NOT NULL,
    membership_status     VARCHAR(20) NOT NULL,
    annual_fee            NUMERIC(10, 2) NOT NULL,
    renewal_outcome       VARCHAR(20),
    cancellation_reason   VARCHAR(60),
    CONSTRAINT mh_dates_chk CHECK (effective_to IS NULL OR effective_to >= effective_from)
);

-- ---------------------------------------------------------------------------------
-- Facts
-- ---------------------------------------------------------------------------------

CREATE TABLE website_activity (
    activity_id             VARCHAR(14) PRIMARY KEY,
    member_id               VARCHAR(12) NOT NULL REFERENCES members (member_id),
    activity_date           DATE        NOT NULL,   -- Monday of the ISO week
    session_count           INTEGER     NOT NULL CHECK (session_count > 0),
    page_views              INTEGER     NOT NULL,
    content_downloads       INTEGER     NOT NULL,
    searches                INTEGER     NOT NULL,
    average_session_minutes NUMERIC(8, 1) NOT NULL,
    device_type             VARCHAR(12) NOT NULL,
    CONSTRAINT wa_pageviews_chk CHECK (page_views >= session_count),
    CONSTRAINT wa_week_uq UNIQUE (member_id, activity_date)
);

CREATE TABLE login_history (
    login_id                 VARCHAR(14) PRIMARY KEY,
    member_id                VARCHAR(12) NOT NULL REFERENCES members (member_id),
    login_timestamp          TIMESTAMP   NOT NULL,
    platform                 VARCHAR(24) NOT NULL,
    session_duration_minutes NUMERIC(8, 1) NOT NULL,
    successful_login         BOOLEAN     NOT NULL
);

CREATE TABLE event_attendance (
    attendance_id                VARCHAR(14) PRIMARY KEY,
    event_id                     VARCHAR(12) NOT NULL REFERENCES events (event_id),
    member_id                    VARCHAR(12) NOT NULL REFERENCES members (member_id),
    registration_date            DATE        NOT NULL,
    attendance_status            VARCHAR(16) NOT NULL,
    booking_channel              VARCHAR(16) NOT NULL,
    feedback_score               SMALLINT    CHECK (feedback_score BETWEEN 1 AND 5),
    continuing_development_hours NUMERIC(6, 2),
    CONSTRAINT ea_status_chk CHECK (attendance_status IN ('Attended','Cancelled','No-show','Registered','Waitlisted'))
);

CREATE TABLE learning_activity (
    learning_activity_id  VARCHAR(14) PRIMARY KEY,
    member_id             VARCHAR(12) NOT NULL REFERENCES members (member_id),
    course_id             VARCHAR(12) NOT NULL REFERENCES courses (course_id),
    activity_date         DATE        NOT NULL,
    completion_status     VARCHAR(16) NOT NULL,
    completion_percentage NUMERIC(5, 1) NOT NULL CHECK (completion_percentage BETWEEN 0 AND 100),
    assessment_score      SMALLINT    CHECK (assessment_score BETWEEN 0 AND 100),
    learning_minutes      NUMERIC(8, 1) NOT NULL,
    CONSTRAINT la_status_chk CHECK (completion_status IN ('Completed','In progress','Abandoned','Not started')),
    -- An assessment score exists if and only if the course was completed.
    CONSTRAINT la_completed_chk CHECK (
        (completion_status = 'Completed' AND completion_percentage = 100 AND assessment_score IS NOT NULL)
     OR (completion_status <> 'Completed' AND assessment_score IS NULL)
    )
);

CREATE TABLE marketing_engagement (
    engagement_id VARCHAR(14) PRIMARY KEY,
    member_id     VARCHAR(12) NOT NULL REFERENCES members (member_id),
    campaign_id   VARCHAR(12) NOT NULL REFERENCES campaigns (campaign_id),
    sent_date     DATE        NOT NULL,
    delivered     BOOLEAN     NOT NULL,
    opened        BOOLEAN     NOT NULL,
    clicked       BOOLEAN     NOT NULL,
    converted     BOOLEAN     NOT NULL,
    unsubscribed  BOOLEAN     NOT NULL,
    -- The engagement funnel is strictly nested.
    CONSTRAINT me_funnel_chk CHECK (
        (NOT opened    OR delivered)
    AND (NOT clicked   OR opened)
    AND (NOT converted OR clicked)
    )
);

CREATE TABLE member_feedback (
    feedback_id       VARCHAR(12) PRIMARY KEY,
    member_id         VARCHAR(12) NOT NULL REFERENCES members (member_id),
    submitted_date    DATE        NOT NULL,
    feedback_channel  VARCHAR(30) NOT NULL,
    feedback_category VARCHAR(40) NOT NULL,
    rating            SMALLINT    NOT NULL CHECK (rating BETWEEN 1 AND 5),
    feedback_text     TEXT        NOT NULL,
    sentiment_label   VARCHAR(10) NOT NULL,
    CONSTRAINT fb_sentiment_chk CHECK (sentiment_label IN ('Positive','Neutral','Negative')),
    -- sentiment_label is ground truth derived from rating; keep them consistent.
    CONSTRAINT fb_sentiment_rating_chk CHECK (
        (rating >= 4 AND sentiment_label = 'Positive')
     OR (rating  = 3 AND sentiment_label = 'Neutral')
     OR (rating <= 2 AND sentiment_label = 'Negative')
    )
);

-- ---------------------------------------------------------------------------------
-- Model and AI output
-- ---------------------------------------------------------------------------------

CREATE TABLE model_predictions (
    prediction_id     VARCHAR(14) PRIMARY KEY,
    prediction_run_id VARCHAR(20) NOT NULL,
    member_id         VARCHAR(12) NOT NULL REFERENCES members (member_id),
    prediction_date   DATE        NOT NULL,
    churn_probability NUMERIC(6, 4) NOT NULL CHECK (churn_probability BETWEEN 0 AND 1),
    risk_category     VARCHAR(10) NOT NULL CHECK (risk_category IN ('Low','Medium','High')),
    predicted_churn   SMALLINT    NOT NULL CHECK (predicted_churn IN (0, 1)),
    engagement_score  NUMERIC(5, 1) NOT NULL CHECK (engagement_score BETWEEN 0 AND 100),
    segment_id        SMALLINT    NOT NULL CHECK (segment_id BETWEEN 1 AND 7),
    model_name        VARCHAR(60) NOT NULL,
    model_version     VARCHAR(20) NOT NULL,
    top_risk_factor_1 TEXT,
    top_risk_factor_2 TEXT,
    top_risk_factor_3 TEXT,
    CONSTRAINT mp_run_member_uq UNIQUE (prediction_run_id, member_id)
);

CREATE TABLE ai_insights (
    insight_id         VARCHAR(12) PRIMARY KEY,
    prediction_run_id  VARCHAR(20) NOT NULL,
    member_id          VARCHAR(12) NOT NULL REFERENCES members (member_id),
    insight_type       VARCHAR(40) NOT NULL,
    executive_summary  TEXT        NOT NULL,
    risk_explanation   TEXT        NOT NULL,
    recommended_action TEXT        NOT NULL,
    llm_provider       VARCHAR(40) NOT NULL,
    llm_model          VARCHAR(60) NOT NULL,
    prompt_version     VARCHAR(20) NOT NULL,
    generated_at       TIMESTAMP   NOT NULL,
    validation_status  VARCHAR(20) NOT NULL,
    -- The insight must attach to the exact scoring run it explains, never to a stale one.
    CONSTRAINT ai_run_fk FOREIGN KEY (prediction_run_id, member_id)
        REFERENCES model_predictions (prediction_run_id, member_id)
);

CREATE TABLE data_quality_results (
    check_id        VARCHAR(12) PRIMARY KEY,
    pipeline_run_id VARCHAR(24) NOT NULL,
    source_table    VARCHAR(40) NOT NULL,
    check_name      VARCHAR(80) NOT NULL,
    check_category  VARCHAR(30) NOT NULL,
    records_checked BIGINT      NOT NULL CHECK (records_checked > 0),
    failed_records  BIGINT      NOT NULL CHECK (failed_records >= 0),
    failure_rate    NUMERIC(9, 6) NOT NULL,
    severity        VARCHAR(12) NOT NULL,
    check_timestamp TIMESTAMP   NOT NULL,
    CONSTRAINT dq_failed_chk CHECK (failed_records <= records_checked)
);

-- ---------------------------------------------------------------------------------
-- Modelling table (feature store, not part of the warehouse)
-- ---------------------------------------------------------------------------------

CREATE TABLE member_training_features (
    member_id                  VARCHAR(12) NOT NULL REFERENCES members (member_id),
    observation_date           DATE        NOT NULL,
    tenure_years               NUMERIC(8, 3) NOT NULL,
    logins_90d                 INTEGER     NOT NULL,
    logins_prior_90d           INTEGER     NOT NULL,
    days_since_last_login      INTEGER     NOT NULL,
    web_sessions_90d           NUMERIC(10, 1) NOT NULL,
    web_sessions_prior_90d     NUMERIC(10, 1) NOT NULL,
    events_attended_365d       INTEGER     NOT NULL,
    learning_completions_365d  INTEGER     NOT NULL,
    campaigns_sent_180d        INTEGER     NOT NULL,
    campaign_open_rate_180d    NUMERIC(6, 4) NOT NULL,
    services_used              SMALLINT    NOT NULL,
    min_rating_365d            NUMERIC(3, 1),
    inactive_90_days           SMALLINT    NOT NULL,
    negative_feedback          SMALLINT    NOT NULL,
    failed_payment             SMALLINT    NOT NULL,
    no_event_attendance        SMALLINT    NOT NULL,
    declining_logins           SMALLINT    NOT NULL,
    completed_learning         SMALLINT    NOT NULL,
    attended_first_90_days     SMALLINT    NOT NULL,
    auto_renewal               SMALLINT    NOT NULL,
    long_tenure                SMALLINT    NOT NULL,
    low_campaign_engagement    SMALLINT    NOT NULL,
    fee_increase               SMALLINT    NOT NULL,
    student_to_full_transition SMALLINT    NOT NULL,
    multi_service_user         SMALLINT    NOT NULL,
    true_churn_probability     NUMERIC(6, 4) NOT NULL,
    churn_flag                 SMALLINT    NOT NULL CHECK (churn_flag IN (0, 1)),
    PRIMARY KEY (member_id, observation_date)
);

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
