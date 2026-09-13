-- Load the generated CSV files into the schema created by 01_create_tables.sql.
--
-- \copy runs client-side, so no server-side file permissions are needed. Pass the data
-- directory as a psql variable:
--
--   psql -d membership -v datadir=/absolute/path/to/data/synthetic \
--        -f database/schema/02_load_csv.sql
--
-- Order matters: dimensions before facts, and model_predictions before ai_insights,
-- because an insight's foreign key points at the scoring run it explains.

\set ON_ERROR_STOP on

\echo 'Loading dimensions ...'
\set f :datadir '/members.csv'
\copy members FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/events.csv'
\copy events FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/courses.csv'
\copy courses FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/campaigns.csv'
\copy campaigns FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/membership_history.csv'
\copy membership_history FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')

\echo 'Loading facts ...'
\set f :datadir '/website_activity.csv'
\copy website_activity FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/login_history.csv'
\copy login_history FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/event_attendance.csv'
\copy event_attendance FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/learning_activity.csv'
\copy learning_activity FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/marketing_engagement.csv'
\copy marketing_engagement FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/member_feedback.csv'
\copy member_feedback FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')

\echo 'Loading model output ...'
\set f :datadir '/model_predictions.csv'
\copy model_predictions FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/ai_insights.csv'
\copy ai_insights FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/data_quality_results.csv'
\copy data_quality_results FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')
\set f :datadir '/member_training_features.csv'
\copy member_training_features FROM :'f' WITH (FORMAT csv, HEADER true, NULL '')

\echo 'Collecting statistics ...'
ANALYZE;

SELECT relname AS table_name, n_live_tup AS approx_rows
FROM   pg_stat_user_tables
ORDER  BY n_live_tup DESC;
