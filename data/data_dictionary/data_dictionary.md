# Data dictionary

**Synthetic Professional Membership Engagement and Retention Dataset**

All tables are written as UTF-8 CSV with an ISO-8601 date format (`YYYY-MM-DD`) and
timestamps as `YYYY-MM-DD HH:MM:SS`. Booleans are written as `True` / `False`. Empty
cells mean "not applicable", never zero.

Observation window: **2021-09-01** to **2026-08-31**. The as-of date for the dataset is
2026-08-31; nothing is dated after it.

Every member in this dataset is fictional. No real person, organisation, name, address
or date of birth appears anywhere in it.

---

## Entity relationships

```text
members ─┬─< membership_history
         ├─< website_activity
         ├─< login_history
         ├─< event_attendance >── events
         ├─< learning_activity >── courses
         ├─< marketing_engagement >── campaigns
         ├─< member_referrals >── members   (member-to-member advocacy graph)
         ├─< member_feedback
         ├─< model_predictions
         ├─< ai_insights
         └─< member_training_features

data_quality_results  (no member grain; one row per check per pipeline run)
```

`model_predictions.prediction_run_id` is the grain key that `ai_insights` joins on, so
an insight always refers to a specific scoring run rather than to "the latest score".

---

## 1. `members`

Central member dimension. One row per member, holding **current** state.

| Column | Type | Notes |
| --- | --- | --- |
| `member_id` | text | Primary key, format `M0000001`. |
| `join_date` | date | Date the member first joined. May pre-date the observation window. |
| `membership_status` | text | `Active`, `Lapsed`, `Cancelled`, `Suspended`. `Suspended` means a renewal payment failed within the last 45 days and the member has not yet lapsed. |
| `membership_type` | text | Current grade: `Student`, `Associate`, `Professional`, `Chartered`, `Fellow`, `Retired`, `Corporate Affiliate`. |
| `region` | text | Eight regions covering UK, Ireland, Europe and Rest of World. |
| `age_band` | text | `18-24` … `65+`. Banded deliberately: an exact date of birth adds no analytical value. |
| `organisation_type` | text | Employer category. |
| `career_stage` | text | `Student`, `Early career`, `Mid career`, `Senior`, `Executive`, `Retired`. |
| `acquisition_channel` | text | How the member was originally acquired. Correlated with member quality. |
| `renewal_date` | date | Next renewal anniversary. Empty for lapsed and cancelled members. |
| `annual_fee` | decimal | Fee for the current term, after uplifts and any grade change. |
| `auto_renewal` | boolean | Continuous payment mandate in place. |
| `communication_consent` | boolean | If false, the member receives no `marketing_engagement` rows. |
| `churn_date` | date | Renewal date at which the member lapsed. Empty if still a member. |
| `churn_flag` | integer | `1` if the member has lapsed or cancelled, else `0`. |

## 2. `membership_history`

Slowly changing dimension: one row per membership term that overlaps the observation
window. Use this rather than `members` for any point-in-time question.

| Column | Type | Notes |
| --- | --- | --- |
| `membership_history_id` | text | Primary key. |
| `member_id` | text | FK → `members`. |
| `effective_from` | date | First day of the term. |
| `effective_to` | date | Last day of the term. Empty for the currently open term. |
| `membership_type` | text | Grade held during this term. |
| `membership_status` | text | `Active` for completed and open terms; `Lapsed` or `Cancelled` on the final term of a churned member. |
| `annual_fee` | decimal | Fee charged for this term. |
| `renewal_outcome` | text | What happened at the end of the term: `Renewed`, `Upgraded`, `Downgraded`, `Lapsed`, `Cancelled`. Empty for the open term. |
| `churn_category` | text | Top level of the churn taxonomy: `Price`, `Dissatisfaction`, `Attitude`, `Competitor`, `Other`. Empty unless the term ended in a lapse. |
| `cancellation_reason` | text | Specific reason within the category. Always present when `churn_category` is, and never present otherwise. |

The two-level `churn_category` -> `cancellation_reason` structure mirrors the IBM seed,
which uses exactly this shape. The category **weights** are a membership-specific
judgement rather than IBM's: a professional body loses far fewer members to a direct
competitor than a telco does. See `docs/ibm-telco-calibration.md` section 7.

`Cancelled` means the member actively told the organisation they were leaving;
`Lapsed` means the subscription simply was not paid.

## 3. `website_activity`

Weekly grain, one row per member per ISO week in which they had at least one session.
Weeks with no activity are absent rather than zero-filled, which keeps the table around
1.6 million rows instead of 4 million.

| Column | Type | Notes |
| --- | --- | --- |
| `activity_id` | text | Primary key. |
| `member_id` | text | FK → `members`. |
| `activity_date` | date | **Monday** of the week being summarised. |
| `session_count` | integer | Sessions in the week (includes logged-in and anonymous-but-identified sessions). |
| `page_views` | integer | Always ≥ `session_count`. |
| `content_downloads` | integer | Guidance documents, standards, templates. |
| `searches` | integer | Site searches performed. |
| `average_session_minutes` | decimal | Mean session length for the week. |
| `device_type` | text | Dominant device that week: `Desktop`, `Mobile`, `Tablet`. |

## 4. `login_history`

Event grain, one row per authentication attempt.

| Column | Type | Notes |
| --- | --- | --- |
| `login_id` | text | Primary key. |
| `member_id` | text | FK → `members`. |
| `login_timestamp` | timestamp | Working-hours-weighted, with a smaller evening peak. |
| `platform` | text | `Web`, `Mobile app`, `Learning platform`. |
| `session_duration_minutes` | decimal | Log-normally distributed. |
| `successful_login` | boolean | About 4% of attempts fail. |

## 5. `events`

Event catalogue.

| Column | Type | Notes |
| --- | --- | --- |
| `event_id` | text | Primary key. |
| `event_name` | text | Includes the month and year for readability in a report. |
| `event_category` | text | `Webinar`, `Conference`, `Regional branch meeting`, `Technical workshop`, `Networking`, `Awards and celebration`, `Career development`. |
| `event_format` | text | `Online`, `In person`, `Hybrid`. |
| `event_date` | date | Weekday-weighted and seasonally clustered; August and late December are sparse. |
| `region` | text | `All regions` for online events. |
| `capacity` | integer | Higher for online events and conferences. |
| `event_cost` | decimal | Ticket price. Most webinars are free. |

## 6. `event_attendance`

One row per member per event registration.

| Column | Type | Notes |
| --- | --- | --- |
| `attendance_id` | text | Primary key. |
| `event_id` | text | FK → `events`. |
| `member_id` | text | FK → `members`. |
| `registration_date` | date | 1-45 days before the event. |
| `attendance_status` | text | `Attended`, `Cancelled`, `No-show`, `Registered` (event still in the future), `Waitlisted`. |
| `booking_channel` | text | `Website`, `Email link`, `Mobile app`, `Telephone`. |
| `feedback_score` | integer | 1-5. Present for roughly 62% of attended events, empty otherwise. |
| `continuing_development_hours` | decimal | CPD hours earned. Empty unless the status is `Attended`. |

## 7. `courses`

Learning catalogue. Supporting dimension for `learning_activity`.

| Column | Type | Notes |
| --- | --- | --- |
| `course_id` | text | Primary key. |
| `course_name` | text | |
| `course_category` | text | Subject area. |
| `course_level` | text | `Introductory`, `Intermediate`, `Advanced`. |
| `expected_minutes` | integer | Nominal study time. |
| `cpd_hours` | decimal | `expected_minutes` / 60. |
| `launch_date` | date | No learning activity exists before a course's launch date. |

## 8. `learning_activity`

One row per member per course engagement.

| Column | Type | Notes |
| --- | --- | --- |
| `learning_activity_id` | text | Primary key. |
| `member_id` | text | FK → `members`. |
| `course_id` | text | FK → `courses`. |
| `activity_date` | date | |
| `completion_status` | text | `Completed`, `In progress`, `Abandoned`, `Not started`. |
| `completion_percentage` | decimal | Exactly `100` when completed. |
| `assessment_score` | integer | 35-100. Present **only** when completed. |
| `learning_minutes` | decimal | Actual minutes spent; varies around `expected_minutes × completion_percentage`. |

## 9. `campaigns`

Marketing campaign catalogue.

| Column | Type | Notes |
| --- | --- | --- |
| `campaign_id` | text | Primary key. |
| `campaign_name` | text | |
| `campaign_type` | text | `Newsletter`, `Event promotion`, `Renewal reminder`, `Learning promotion`, `Win-back`, `Member survey`, `Upgrade offer`. |
| `start_date` / `end_date` | date | |
| `target_segment` | text | Determines which members receive it. |
| `channel` | text | `Email`, `SMS`, `In-app`, `Direct mail`. |
| `campaign_cost` | decimal | Highest for direct mail. Use with conversions for campaign ROI. |

## 10. `marketing_engagement`

One row per member per campaign send. A member with `communication_consent = False`
never appears. Once a member unsubscribes, no further sends are recorded for them.

| Column | Type | Notes |
| --- | --- | --- |
| `engagement_id` | text | Primary key. |
| `member_id` | text | FK → `members`. |
| `campaign_id` | text | FK → `campaigns`. |
| `sent_date` | date | |
| `delivered` | boolean | ~96.5%. |
| `opened` | boolean | Implies `delivered`. |
| `clicked` | boolean | Implies `opened`. |
| `converted` | boolean | Implies `clicked`. |
| `unsubscribed` | boolean | True on at most one row per member; it is their last send. |

## 11. `member_referrals`

Member-to-member advocacy. One row per referral invitation made **by** a member.

| Column | Type | Notes |
| --- | --- | --- |
| `referral_id` | text | Primary key. |
| `referring_member_id` | text | FK -> `members`. The member who made the referral. |
| `referral_date` | date | |
| `referral_channel` | text | `Word of mouth`, `Referral link`, `Event introduction`, `Employer scheme`. |
| `referral_status` | text | `Joined`, `Invited`, `Declined`, `Expired`. |
| `referred_member_id` | text | FK -> `members`. Present **only** when the status is `Joined`; that member has `acquisition_channel = 'Referral'`. |

This table exists because of the seed. IBM records `Referred a Friend` and
`Number of Referrals`, and referral behaviour turns out to be one of the strongest
leak-free retention signals in it: retained customers referred **4.8x** as many people as
churned ones. IBM records only the count, never who referred whom; joining the edge here
turns that into a real graph, so advocacy can be analysed as a network rather than a
column.

Calibrated so that the share of members making at least one referral, and the mean number
among those who do, both track the seed.

## 12. `member_feedback`

Free-text feedback. The table designed for the LLM layer.

| Column | Type | Notes |
| --- | --- | --- |
| `feedback_id` | text | Primary key. |
| `member_id` | text | FK → `members`. |
| `submitted_date` | date | |
| `feedback_channel` | text | `Annual member survey`, `Event feedback form`, `Support ticket`, `Website feedback widget`, `Cancellation survey`. |
| `feedback_category` | text | Seven themes, from `Events and content` to `Fees and billing`. |
| `rating` | integer | 1-5. |
| `feedback_text` | text | Free text consistent with the rating and category. |
| `sentiment_label` | text | `Positive` (rating ≥ 4), `Neutral` (3), `Negative` (≤ 2). |

The marginal distribution of `rating` on the `Annual member survey` channel is calibrated
to the IBM satisfaction distribution. Event feedback skews higher, because a member has to
have attended to give it, and support tickets skew lower.

`sentiment_label` is the **ground truth**, which makes this table usable to evaluate an
LLM classifier rather than only to feed one. Cancellation-survey rows are the only
feedback dated on or after a member's `churn_date`.

## 13. `model_predictions`

Output of the churn scoring pipeline. One row per member per monthly scoring run, for
members who were still active on the run date.

> **This table's data source depends on where you're looking.** The generated CSVs
> (`data/synthetic/model_predictions.csv`, `data/sample/model_predictions.csv`) hold the
> data generator's **simulated** output — the true log-odds plus noise, as described in
> `docs/data-generation-methodology.md` §6 — produced when the dataset was generated.
> The **live PostgreSQL database**, once `main.ipynb` has been run, holds **real, trained
> model output** instead: three classifiers (Logistic Regression, Random Forest,
> Gradient Boosting) trained on `member_training_features` and compared out-of-time,
> with the winner's predictions computed from features independently reconstructed from
> the raw activity tables. See the README's "Churn model" section and `main.ipynb` for
> the full methodology, metrics and validation. The two sources are not automatically
> kept in sync — reloading the CSVs into Postgres (`02_load_csv.sql`) would overwrite the
> real predictions with the simulated baseline again, so rerun `main.ipynb` afterward if
> that happens.

| Column | Type | Notes |
| --- | --- | --- |
| `prediction_id` | text | Primary key. |
| `prediction_run_id` | text | `RUN-YYYY-MM-DD`. Six month-end runs. |
| `member_id` | text | FK → `members`. |
| `prediction_date` | date | The run date. |
| `churn_probability` | decimal | 0-1, rounded to 4 dp. |
| `risk_category` | text | `Low` (< 0.10), `Medium` (< 0.25), `High` (≥ 0.25). Bands are set relative to the ~9% base rate, not to 0.5. |
| `predicted_churn` | integer | 1 when `churn_probability` ≥ 0.25 (a recall-weighted operating point). |
| `engagement_score` | decimal | 0-100 composite of logins, web sessions, events, learning, email engagement and referrals. |
| `predicted_lifetime_value` | decimal | Annual fee x expected remaining years x contribution margin, in currency. Expected remaining years is capped at 12. Note this is a revenue figure, unlike IBM's `CLTV`, which is a bounded index. |
| `segment_id` | integer | FK -> `segments`. |
| `model_name` / `model_version` | text | Simulated rows: `membership_churn_gbm` v1.4.0. Real rows (Postgres, post-`main.ipynb`): the winning model's identifier, e.g. `membership_churn_logreg` v2.0.0. |
| `top_risk_factor_1..3` | text | Simulated rows: the three largest contributions to the DGP's true log-odds. Real rows: the three active risk-raising flags ranked by the trained model's own permutation importance — a genuine model-derived explanation, not the asserted DGP coefficients. Empty when fewer than three apply. |

## 14. `ai_insights`

LLM-generated narrative, keyed to a specific scoring run. Generated for the latest run
only: every member above low risk, plus a 6% sample of low-risk members for comparison.

| Column | Type | Notes |
| --- | --- | --- |
| `insight_id` | text | Primary key. |
| `prediction_run_id` | text | FK → `model_predictions.prediction_run_id`. |
| `member_id` | text | FK → `members`. |
| `insight_type` | text | Currently `Member retention brief`. |
| `executive_summary` | text | |
| `risk_explanation` | text | |
| `recommended_action` | text | |
| `llm_provider` / `llm_model` / `prompt_version` | text | Provenance for auditability. |
| `generated_at` | timestamp | |
| `validation_status` | text | `Template` for generated placeholder rows. The live LLM stage overwrites these with `Validated`, `Needs review` or `Rejected`. |

> **Note.** The shipped text in this table is template-assembled, not model-generated.
> It exists so the semantic model and report pages can be built before the LLM stage is
> wired up. `validation_status = 'Template'` marks every such row.
>
> **Currently empty in the live database.** `ai_insights.prediction_run_id` carries a
> composite foreign key onto `model_predictions (prediction_run_id, member_id)`, so
> replacing the simulated predictions with real trained-model output (see the note on
> `model_predictions` above) required truncating this table too — its rows pointed at
> `prediction_run_id`/`member_id` pairs that no longer exist as a set. The generated CSVs
> still contain the original template rows; the live database does not, until the LLM
> layer is (re)built against the real predictions.

## 15. `data_quality_results`

One row per check per pipeline run. Feeds the Power BI data-quality page.

| Column | Type | Notes |
| --- | --- | --- |
| `check_id` | text | Primary key. |
| `pipeline_run_id` | text | `PIPE-<day ordinal>`. One run per day for the last 60 days. |
| `source_table` | text | Table the check ran against. |
| `check_name` | text | e.g. `opened_implies_delivered`. |
| `check_category` | text | `Completeness`, `Uniqueness`, `Validity`, `Consistency`, `Referential integrity`, `Governance`. |
| `records_checked` | integer | Anchored to the real row count of the source table. |
| `failed_records` | integer | |
| `failure_rate` | decimal | `failed_records / records_checked`. |
| `severity` | text | `Critical`, `High`, `Medium`, `Low`. |
| `check_timestamp` | timestamp | |

Roughly 8% of runs contain a deliberate incident, where one source table's failure rates
spike by 8-40×. That is what makes the data-quality trend page worth looking at.

## 16. `segments` (supporting dimension)

Behavioural segment reference data, so `model_predictions.segment_id` joins to something
rather than sitting in the model as a bare integer.

| Column | Type | Notes |
| --- | --- | --- |
| `segment_id` | integer | Primary key, 1-7. |
| `segment_name` | text | `Champions`, `Steady professionals`, `Learning-led`, `Event-led`, `Passive renewers`, `Disengaging`, `New and forming`. |
| `segment_strategy` | text | The recommended approach for the segment, for the Segmentation report page. |

## 17. `member_training_features` (supporting table)

Not part of the warehouse: this is the modelling table. One row per **renewal decision**
inside the observation window, with the features as they stood 0-365 days before that
renewal and the outcome that followed. It is the correct training set for a churn model
because features strictly precede the label.

Notable columns: `observation_date` (the renewal date), the fourteen binary model
inputs, a set of descriptive counts (`logins_90d`, `events_attended_365d`, …),
`true_churn_probability` (the probability the generator actually sampled from — use it
to establish the ceiling AUC, never as a model input) and `churn_flag`.
