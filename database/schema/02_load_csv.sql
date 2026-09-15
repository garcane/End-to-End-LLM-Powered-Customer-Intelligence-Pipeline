-- Load the generated CSV files into the schema created by 01_create_tables.sql.
--
-- \copy runs client-side, so no server-side file permissions are needed.
--
-- Paths below are hardcoded absolute paths rather than built from a psql variable.
-- An earlier version used the `\set f :datadir '/x.csv'` concatenation trick, which is
-- fragile when the two setup lines are pasted into a GUI terminal panel (pgAdmin's PSQL
-- Tool, VS Code, etc.) rather than typed at a native psql prompt -- line-ending and
-- buffering differences can silently corrupt the variable, producing a \copy against an
-- empty or malformed filename. Hardcoding avoids that class of failure entirely.
--
-- To point this at a different checkout, edit DATA_DIR below (search and replace).
--
-- Order matters: dimensions before facts, and model_predictions before ai_insights,
-- because an insight's foreign key points at the scoring run it explains.

\set ON_ERROR_STOP on
\set DATA_DIR 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic'

\echo 'Loading dimensions ...'
\copy members FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/members.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy events FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/events.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy courses FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/courses.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy segments FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/segments.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy campaigns FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/campaigns.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy membership_history FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/membership_history.csv' WITH (FORMAT csv, HEADER true, NULL '')

\echo 'Loading facts ...'
\copy website_activity FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/website_activity.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy login_history FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/login_history.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy event_attendance FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/event_attendance.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy learning_activity FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/learning_activity.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy marketing_engagement FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/marketing_engagement.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy member_referrals FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/member_referrals.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy member_feedback FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/member_feedback.csv' WITH (FORMAT csv, HEADER true, NULL '')

\echo 'Loading model output ...'
\copy model_predictions FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/model_predictions.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy ai_insights FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/ai_insights.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy data_quality_results FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/data_quality_results.csv' WITH (FORMAT csv, HEADER true, NULL '')
\copy member_training_features FROM 'C:/Users/Student/End-to-End-LLM-Powered-Customer-Intelligence-Pipeline/data/synthetic/member_training_features.csv' WITH (FORMAT csv, HEADER true, NULL '')

\echo 'Load complete.'

SELECT relname AS table_name, n_live_tup AS approx_rows
FROM   pg_stat_user_tables
ORDER  BY n_live_tup DESC;
