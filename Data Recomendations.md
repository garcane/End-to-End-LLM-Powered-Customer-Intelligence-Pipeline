# Dataset Selection and Rationale

## Why this dataset was used

The project uses the **Synthetic Professional Membership Engagement and Retention Dataset**, a relational dataset created to support an end-to-end membership intelligence platform. The dataset was chosen because no single public dataset provided the membership history, engagement behaviour, churn outcomes, and feedback needed to demonstrate the full analytical workflow.

The dataset combines statistical evidence from the extended IBM Cognos Telco Customer Churn sample with fictional, membership-specific activity. IBM's sample provides a useful benchmark for churn-related distributions and relationships, while generated activity tables represent behaviours that are important to a professional membership organisation, such as event attendance, website use, learning, marketing engagement, and referrals.

The result is a project-specific dataset rather than an unchanged copy of a standard churn benchmark. It supports analysis of how member behaviour changes over time, how engagement relates to retention, and how analytical results can inform recommendations.

## Why the IBM dataset was not used on its own

The IBM Telco Customer Churn dataset contains useful churn labels and customer attributes, including tenure, contracts, charges, and service usage. On its own, however, it is primarily a customer-level churn dataset. It does not provide the longitudinal membership activity required to analyse event attendance, website engagement, learning participation, campaign responses, or member feedback.

Using the sample unchanged would therefore limit the project to a conventional churn-classification exercise. Extending it with synthetic activity makes it possible to demonstrate a broader analytical pipeline while retaining a real dataset as a source of statistical calibration.

The dataset is used as a source of **structure, marginal distributions, and statistical evidence**; IBM customer records are not copied into the generated output. Some membership-specific relationships are generated for the project, and the calibration process documents which values are measured from the IBM source and which are synthetic.

## Dataset design

The generated dataset models 25,000 fictional members across a five-year period, from 2021-09-01 to 2026-08-31. It includes related tables for:

- Members and membership history
- Weekly website activity and login history
- Events and event attendance
- Courses and learning activity
- Campaigns and marketing engagement
- Member referrals and free-text feedback
- Monthly model predictions and AI insights
- Data-quality results and behavioural segments

The relational structure supports analysis at different grains, from a current member profile to weekly activity and monthly scoring runs. It also enables the pipeline to connect predictions with the activity and outcomes used to interpret them.

## Behavioural relationships

The synthetic data is designed to contain learnable, non-random relationships. Engagement patterns such as inactivity, event participation, learning completion, campaign response, feedback, and membership tenure contribute to churn propensity. Outcomes are sampled with variation, so the predictive task retains uncertainty rather than becoming a deterministic lookup.

This approach makes it possible to evaluate churn models on historical behaviour and subsequent outcomes, while also checking that the generated data reflects the intended business rules. The dataset-generation methodology and validation results are documented in the repository's [data generation methodology](docs/data-generation-methodology.md) and [IBM Telco calibration report](docs/ibm-telco-calibration.md).

## Scale and suitability

The full profile contains 25,000 members and millions of activity records across several fact tables. This scale is large enough to demonstrate relational modelling, data validation, feature engineering, predictive modelling, and analytical queries, while remaining practical to generate and use on a typical development machine. A smaller sample is provided in [`data/sample/`](data/sample/) for exploration.

The synthetic approach also avoids copying personal records into the project. Members and related entities are fictional, and direct identifiers such as names, addresses, dates of birth, email addresses, and telephone numbers are not generated.

## Alternatives considered

A transaction dataset such as **UCI Online Retail II** can support purchase-frequency and recency analysis, but it does not contain membership status, event participation, learning activity, or explicit churn labels. A churn label would need to be inferred from a chosen inactivity window, making it less directly suited to the membership use case.

Basic bank-churn datasets and flat subscription datasets have similar limitations: they may provide a churn outcome, but generally lack the related time-based activity needed for a membership intelligence platform. A large row count alone would not provide the relational and behavioural depth required by this project.

## Summary

The Synthetic Professional Membership Engagement and Retention Dataset was used because it provides a better fit for the project's business question than any single unmodified public dataset. IBM Telco data contributes a documented statistical foundation, while synthetic membership activity supplies the domain-specific history needed for engagement analysis, churn prediction, and actionable insight generation.

## References

1. [IBM Cognos Analytics — Telco customer churn sample](https://www.ibm.com/docs/en/cognos-analytics/12.0.x?topic=samples-telco-customer-churn)
2. [UCI Machine Learning Repository — Online Retail II](https://archive.ics.uci.edu/ml/datasets/online%2Bretail%2BII)
