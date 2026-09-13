# Seed data

The generator calibrates the member dimension against the **IBM Telco Customer Churn**
dataset. The file itself is not redistributed here.

## Optional: use the real file

Download `WA_Fn-UseC_-Telco-Customer-Churn.csv` (the IBM Cognos Analytics sample, also
mirrored on Kaggle), save it as:

```text
data/seed/ibm_telco_churn.csv
```

and re-run the generator. `src/generators/seed.py` will measure tenure, contract type,
payment method, churn rate and charge ratio directly from it, and
`generation_manifest.json` will record `"source": ".../ibm_telco_churn.csv"`.

## Without the file

The generator runs offline using the published marginals of the same dataset, listed in
`docs/data-generation-methodology.md` §1. The manifest records
`"source": "published-marginals"` so any extract can be traced to which path was used.

Only structural marginals are carried over. No IBM row is copied into the output.

Reference: <https://www.ibm.com/docs/en/cognos-analytics/12.0.x?topic=samples-telco-customer-churn>
