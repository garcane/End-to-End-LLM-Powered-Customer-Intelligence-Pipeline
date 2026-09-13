# Data generation methodology

**Synthetic Professional Membership Engagement and Retention Dataset**

This document is the deliverable that matters. Anyone can upload synthetic CSV files;
what makes them defensible is a written account of the data-generating process, the
business rules encoded in it, and the checks that confirm the result behaves the way it
was supposed to.

---

## 1. Why synthetic, and why hybrid

The project needs a member dimension with churn outcomes **and** event attendance,
website activity, login history, learning participation, marketing engagement,
longitudinal behaviour and free-text feedback. No public dataset has all of that.

The approach follows the recommendation in `Data Recomendations.md`:

```text
IBM Telco churn structure (calibration)
        +
synthetically generated membership activity
        =
complete membership intelligence dataset
```

IBM Telco contributes **structure and marginals**, not rows. Specifically:

| Quantity carried over | Published value | How it is used |
| --- | --- | --- |
| Tenure mean / sd (months) | 32.4 / 24.6 | Shapes the gamma distribution behind `join_date`, stretched ×1.6 because membership terms are annual rather than monthly |
| Month-to-month contract share | 55.0% | Sets the base rate for `auto_renewal = False` |
| Automatic payment share | 43.3% | Cross-checks the same |
| Churn rate | 26.5% | Sense-check on the realised cumulative lapse rate |
| Senior citizen share | 16.2% | Nudges the `65+` age band |
| Churned/retained charge ratio | 1.166 | Justifies the fee-sensitivity term in the churn model |

Telco-specific columns — phone service, multiple lines, streaming TV — are deliberately
dropped. Copying them across is exactly what makes a portfolio project look like a
re-skinned churn tutorial.

**The seed file is optional.** If `data/seed/ibm_telco_churn.csv` is present, these
quantities are measured from it directly; if not, the published marginals above are used
and the run is annotated accordingly in `generation_manifest.json`. The generator works
offline either way.

---

## 2. Structure of the generator

```text
src/generators/
├── config.py       scale profiles, reference vocabularies, model coefficients
├── seed.py         IBM Telco calibration (measured, or published fallback)
├── utils.py        deterministic RNG streams, streaming CSV writers, date maths
├── members.py      member dimension + latent behavioural traits
├── catalogues.py   events, campaigns, courses
├── features.py     feature extraction + the churn data-generating process
├── templates.py    free-text feedback and placeholder insight narrative
├── activity.py     per-member simulation, churn assignment, row emission
├── data_quality.py data-quality check results
└── run.py          CLI orchestrator
src/validation/
└── validate.py     structural, volume and signal validation
```

Run it with:

```bash
python -m src.generators.run --scale full      # 25,000 members, ~5 minutes
python -m src.validation.validate
```

Scale profiles are `dev` (1,000 members, ~15s), `demo` (8,000) and `full` (25,000).
Members are processed in chunks and rows are streamed straight to CSV, so peak memory
stays in the tens of megabytes even at full scale — it runs comfortably on a laptop
with 8 GB of RAM.

Every run is reproducible from `--seed`, and each table draws from its own named RNG
sub-stream, so changing the number of random draws in one generator does not shift the
output of all the others.

---

## 3. The member as a latent person

Each member is created with traits that are never exported but drive everything
observable:

* `engagement` — a Beta(2.2, 2.8) draw, multiplied by a membership-grade uplift, shifted
  by acquisition-channel quality, and nudged upwards by tenure (members who have already
  survived several renewals are, by selection, more engaged).
* `event_affinity`, `learning_affinity`, `email_affinity`, `web_affinity` — engagement
  plus independent noise, so channel preferences differ between members.
* `satisfaction` — drives feedback ratings and unsubscribe rates.
* `drift` — a year-on-year multiplicative trend, `Normal(-0.04, 0.30)`. This is the term
  that produces genuinely *declining* members rather than members who are uniformly
  quiet.
* `price_sensitivity` — interacts with fee increases at renewal.

Demographics are sampled as a chain, not independently:
`age_band → career_stage → membership_type`. A 22-year-old is very unlikely to be a
Fellow, and the dataset should reflect that.

---

## 4. Behaviour over time

For each active week the member's activity level is:

```text
level(w) = exp(drift × years_since_join) × seasonality(w)
```

`seasonality` encodes a spring and autumn programme, an August lull and a near-total
shutdown over Christmas. Events are scheduled on the same seasonal curve and are
weekday-weighted, so event attendance and web traffic move together for the right
reason rather than by coincidence.

Activity volumes per week are then Poisson draws:

| Table | Rate |
| --- | --- |
| Logins | `1.05 × web_affinity × level` per week |
| Extra web sessions | `0.30 × web_affinity × level` per week |
| Event registrations | `7.5 × event_affinity × level` per year |
| Learning activities | `3.5 × learning_affinity × level` per year |

Weeks with no web sessions are not written at all, which is both realistic and what
keeps `website_activity` near 1.6 million rows rather than 4 million.

Marketing sends are driven by the campaign catalogue and its `target_segment`: a member
receives a campaign only if they have consented, match the segment, and have not
previously unsubscribed. Open, click, convert and unsubscribe are a strict nested
hierarchy, so `clicked` can never be true where `opened` is false.

---

## 5. The churn data-generating process

This is the part that determines whether the dataset is worth anything.

At **each renewal anniversary**, features are measured from behaviour that has already
been generated, and only from behaviour that precedes the renewal date:

* 90-day and prior-90-day login counts (giving both a level and a trend)
* event attendance and learning completions over the last 365 days
* campaign open rate over the last 180 days
* worst feedback rating over the last 365 days
* whether an event was attended within 90 days of joining
* tenure, auto-renewal status, and whether the renewal payment failed
* whether this renewal carries a large fee increase for a price-sensitive member
* whether the member is moving off the student rate

Those features go into the logistic model published in `Data Recomendations.md`:

```python
churn_log_odds = (
    -2.2
    + 0.9 * inactive_90_days
    + 0.7 * negative_feedback
    + 0.8 * failed_payment
    + 0.6 * no_event_attendance
    + 0.5 * declining_logins
    - 0.7 * completed_learning
    - 0.6 * attended_first_90_days
    - 0.5 * auto_renewal
    - 0.4 * long_tenure
)
```

with four documented extensions:

```python
    + 0.35 * low_campaign_engagement      # sent 4+ campaigns, opens under 15%
    + 0.30 * fee_increase                 # big repricing AND price_sensitivity > 0.6
    + 0.45 * student_to_full_transition   # the single largest real-world lapse point
    - 0.45 * multi_service_user           # uses 3+ of web, events, learning, email
```

The outcome is then sampled:

```python
churn_probability = 1 / (1 + np.exp(-churn_log_odds))
churn_flag = np.random.binomial(1, churn_probability)
```

**The intercept was not tuned.** With the published −2.2, the realised lapse rate comes
out at roughly 8-9% per renewal decision and ~20% cumulative over the five-year window,
which is a plausible figure for a professional body. No calibration offset is applied.

Once a renewal lapses, **every activity row dated on or after that date is discarded**,
across all seven activity tables, and the member is excluded from later scoring runs.
The only exception is the cancellation survey, which by definition arrives at the exit.
This ordering — behaviour, then features, then outcome, then truncation — is what makes
the label learnable rather than circular.

---

## 6. Predictions and insights

`model_predictions` simulates six monthly scoring runs. The "model" sees the true
log-odds plus `Normal(0, 0.85)` noise, which yields out-of-time AUC around 0.77: good
enough to be useful, far enough from 1.0 to be honest. Risk bands are set at 0.10 and
0.25 rather than at 0.35/0.65, because with a 9% base rate fixed mid-range bands would
put 95% of members in the lowest band and leave the churn-risk report with nothing to
display.

`top_risk_factor_1..3` are the three largest positive contributions to that member's
log-odds, so the explanation shown in Power BI is arithmetically consistent with the
score next to it.

`ai_insights` rows are **template-assembled placeholders**, flagged as
`validation_status = 'Template'`. They let the semantic model and the AI Insight Centre
page be built before the Ollama/Gemini stage exists; the live pipeline overwrites them,
keyed on `prediction_run_id` so a narrative can never drift onto a stale score.

---

## 7. Validation

`python -m src.validation.validate` runs 65 checks in five groups.

**Structure** — primary keys unique across all eleven keyed tables; every foreign key
resolves; every categorical value inside its declared domain; nested booleans consistent
(`clicked → opened → delivered`); `assessment_score` present if and only if a course was
completed.

**Causal consistency** — no login, web, event, learning, marketing, feedback or
prediction row dated on or after a member's `churn_date` (cancellation surveys excepted);
`churn_date > join_date`; churned members have no forward renewal date and active
members all have one.

**Volume** — row counts per member against the ranges recommended in
`Data Recomendations.md`. Enforced on the `full` profile; reported as warnings on the
smaller profiles, which deliberately cut the campaign catalogue and the number of
scoring runs.

**Signal** — the important group. A logistic regression is fitted from scratch (scipy
L-BFGS, no sklearn dependency) on `member_training_features`, holding out the most
recent third of observations as an out-of-time test set. The suite asserts that:

* the realised lapse rate is between 5% and 22% per renewal decision;
* the ceiling AUC from the true propensity is between 0.72 and 0.95;
* a refitted model reaches out-of-time AUC above 0.68;
* every fitted coefficient has the same sign as the one that generated the data;
* fitted and generating coefficients correlate at r ≥ 0.85.

**Business plausibility** — email open rate, click-through rate, event attendance rate,
negative-feedback share, and a direct check that members who lapse logged in less often
in the 90 days before renewal than members who renewed.

A representative full-scale run:

```text
annual lapse rate                  8.4% per renewal decision
ceiling AUC (true propensity)      0.772
out-of-time AUC of a refitted model 0.772
fitted vs true coefficients        r = 0.965
email open rate                    42.0%
event attendance rate              64.6% of registrations
lapsing vs renewing members        4.5 vs 8.9 logins in the prior 90 days
```

---

## 8. Privacy

No names, addresses, dates of birth, email addresses, telephone numbers or payment
details are generated. Age is banded. Every member, event, course and campaign is
fictional. There is nothing in this dataset to de-identify, because there was never an
identity in it.

---

## 9. Known simplifications

Stated plainly, because a generator that claims to be realistic in every respect is not
credible:

* Churn is evaluated **only at renewal anniversaries**. Mid-term cancellation happens in
  reality; here it is folded into the renewal decision.
* Members never rejoin after lapsing. There is no win-back readmission path, even though
  `Win-back` campaigns exist in the catalogue.
* Event capacity is not enforced. `Waitlisted` is sampled at a flat 3% rather than
  emerging from oversubscription.
* Renewals that pre-date the observation window are assumed successful — the member is
  still present, so by construction they must have renewed. This creates a mild survivor
  effect in the earliest cohorts.
* `website_activity` is weekly, so within-week sequencing is lost. This was a deliberate
  trade for a table of 1.6 million rows instead of 4 million.
* Free-text feedback is drawn from a sentence bank rather than a language model. It is
  varied enough to exercise summarisation and classification, but it is not open-ended
  natural language.
* Region is a single flat attribute; there is no organisation hierarchy or household
  structure.
