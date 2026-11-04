# End-to-End LLM-Powered Customer Intelligence Pipeline

## Overview

The AI-Powered Membership Intelligence Platform is an end-to-end analytics solution designed to help organisations better understand member behaviour, identify disengagement risks, and generate actionable recommendations through the use of machine learning and large language models (LLMs).

The project combines traditional data analytics, predictive modelling, and generative AI to transform raw membership activity data into meaningful business insights. Rather than simply presenting historical dashboards, it aims to explain what is happening, why it matters, and what the organisation should do next.

This project was created to demonstrate practical skills across the modern data stack, including data engineering, database design, analytics engineering, machine learning, prompt engineering, and AI integration.

---

## AI Model Used

The AI layer in this project ultimately used Ollama as the local inference runtime, with the Qwen model as the model choice for generating business insights and recommendations.

This means the system was designed to run locally, without a paid cloud API, while still producing explainable member intelligence and AI-generated recommendations.

Example local usage:

```bash
ollama run qwen3:8b
```

Example API call:

```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "qwen3:8b",
        "prompt": "Summarise the churn risk patterns for this membership cohort"
    }
)

print(response.json())
```

---

## Business Problem

Many organisations collect large volumes of member activity data through CRM systems, websites, events, learning platforms, and marketing tools. However, this information is often spread across multiple systems and remains difficult to interpret at the member level.

Typical questions include:

- Which members are likely to disengage?
- What behaviours indicate strong long-term retention?
- Which engagement activities have the greatest impact?
- What actions should staff take to improve member outcomes?
- How can complex analytical findings be communicated to non-technical stakeholders?

Traditional dashboards provide historical reporting but often require manual interpretation. This project bridges that gap by combining predictive analytics with AI-generated business recommendations.

---

## Project Objectives

The platform aims to:

- Consolidate structured and unstructured membership data
- Create a central analytical data model
- Measure member engagement and activity levels
- Predict disengagement or lapse risk
- Automatically identify behavioural patterns
- Generate plain-English explanations of analytical findings
- Recommend targeted retention and engagement actions
- Provide an interactive dashboard for business users

---

## Dataset

The platform is built on the Synthetic Professional Membership Engagement and Retention Dataset, a relational, behaviourally coherent dataset generated for this project rather than taken from a single public source.

It is a hybrid: the member dimension is calibrated against the extended IBM Cognos Telco Customer Churn sample and then extended with realistic membership activity data such as membership history, website activity, event participation, learning behaviour, campaigns, referrals, feedback, predictions, and data quality results.

This project includes a full data generation pipeline, feature engineering, risk scoring, and AI insight output generation.

---

## Churn Model

The dataset supports a robust churn prediction pipeline using machine learning models, with the project evaluating several classifiers on a strict out-of-time validation split.

The modelling stack includes:

- Logistic Regression
- Random Forest
- Gradient Boosting

The predictive layer scores members on engagement, retention risk, and churn likelihood, then turns those outputs into business-friendly decisions and explanations.

---

## Solution Architecture

```text
CRM / Membership Data
Event Attendance Data
Website Activity Logs
Marketing Engagement Data
Customer Feedback & Reviews
            │
            ▼
      ETL Pipeline
         Python
            │
            ▼
      PostgreSQL
   Analytical Database
            │
            ▼
  Feature Engineering Layer
            │
            ▼
 Predictive ML Models
 Engagement Scoring
 Churn Prediction
 Segmentation Analysis
            │
            ▼
     AI Insight Layer
   (Ollama + Qwen)
            │
            ▼
 Streamlit Dashboard
 Interactive Reporting
```

---

## Large Language Model Integration

A core component of this project is the AI insight layer, which converts analytical outputs into actionable business recommendations and plain-English summaries.

The platform is intentionally designed to be model-agnostic, allowing multiple large language models to be used depending on deployment requirements, cost constraints, and infrastructure preferences.

### Ollama + Qwen (Actual Implementation)

This project ultimately used Ollama as the local model runtime and the Qwen model as the LLM for generating insights.

Why this setup was selected:

- No external API cost
- Easy local execution
- Works well for experimentation and portfolio use cases
- Suitable for producing summaries, recommendations, and business explanations
- Aligns with the goal of demonstrating an end-to-end AI stack using open-source tooling

The architecture allows for easy swapping between local models and hosted APIs with minimal changes to the larger application.

---

## Technology Stack

### Data Engineering

- Python
- Pandas
- Polars
- DuckDB
- NumPy
- SQLAlchemy

### Database

- PostgreSQL

### Machine Learning

- Scikit-Learn
- XGBoost
- LightGBM

### Dashboard & Application

- Power BI
- Plotly
- Streamlit

### AI Layer

- Ollama
- Qwen model
- Local LLM inference

### Version Control

- Git
- GitHub

---

## Example Dashboard Components

### Executive Overview

- Total members
- Active members
- Engagement trends
- Churn forecasts

### Engagement Analytics

- Login activity trends
- Event attendance analysis
- Cohort retention curves
- Segment distribution

### Churn Risk Monitor

- High-risk member lists
- Risk scoring explanations
- Contributing behavioural factors

### AI Insight Centre

- Automated summaries
- Recommended interventions
- Behavioural pattern explanations
- Executive reporting outputs

---

## Future Enhancements

Potential future developments include:

- Real-time event streaming
- Automated retraining pipelines
- Recommendation systems
- RAG-based document search
- Vector databases
- Multi-agent AI workflows
- CRM integration
- Automated email generation
- Scenario forecasting and simulation

---

## Learning Outcomes

This project demonstrates:

- End-to-end data pipeline development
- Database design and modelling
- Data quality engineering
- Predictive analytics
- Machine learning deployment
- Prompt engineering
- AI integration
- Dashboard development
- Business-focused analytics
- Full project lifecycle management

---

## Author

Developed as a portfolio project to demonstrate modern data analytics, machine learning, and AI engineering capabilities through the creation of a production-style membership intelligence platform.
