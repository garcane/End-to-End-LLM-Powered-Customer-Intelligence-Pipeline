# Seed data

The generator calibrates against the **extended IBM Cognos Telco Customer Churn sample**:
six workbooks covering 7,043 customers.

## Where the files go

```text
IBM Source Files/
  Telco_customer_churn.xlsx
  Telco_customer_churn_demographics.xlsx
  Telco_customer_churn_location.xlsx
  Telco_customer_churn_population.xlsx
  Telco_customer_churn_services.xlsx
  Telco_customer_churn_status.xlsx
```

`data/seed/ibm/` and `data/seed/` are also searched, in that order.

The workbooks are **not committed** (see `.gitignore`). They are an IBM sample dataset,
distributed by IBM and mirrored on Kaggle.

## How they are used

```bash
python -m src.generators.calibrate
```

This measures the seed and writes two artefacts, both of which **are** committed:

- `data/seed/ibm_calibration.json` — every measured quantity, the leakage audit and the
  fitted analogue coefficients. The generator reads this, so it never needs Excel.
- `docs/ibm-telco-calibration.md` — the same content as a readable report.

If the workbooks are absent, the generator falls back to the published marginals of the
same dataset and records `"source": "published-marginals"` in the manifest.

## What is taken, and what is not

Only structural marginals and statistical relationships are carried over. **No IBM row is
copied into the output.**

Carried over: tenure distribution, exact-age distribution, contract and payment-method
shares, paperless-billing share, referral behaviour, the satisfaction marginal, the
two-level churn-reason taxonomy, and the fitted analogue coefficients.

Dropped: city, zip code, latitude, longitude and zip-level population (US-specific and
irrelevant to a UK membership body); gender, marital status and dependants (sensitive,
and of no analytical value here); and the telco service columns, which have no membership
analogue.

Excluded as leaked: `Satisfaction Score` and `Churn Score`. Both were assigned after the
churn outcome was known. See `docs/ibm-telco-calibration.md` section 1.

Reference: <https://www.ibm.com/docs/en/cognos-analytics/12.0.x?topic=samples-telco-customer-churn>
