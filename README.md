# End-to-End-LLM-Powered-Customer-Intelligence-Pipeline
## Overview

The AI-Powered Membership Intelligence Platform is an end-to-end analytics solution designed to help organisations better understand member behaviour, identify disengagement risks, and generate actionable recommendations through the use of machine learning and large language models (LLMs).

The project combines traditional data analytics, predictive modelling, and generative AI to transform raw membership activity data into meaningful business insights. Rather than simply presenting metrics in a dashboard, the platform proactively identifies at-risk members, explains behavioural trends, and recommends actions that may improve engagement and retention.

This project was created to demonstrate practical skills across the modern data stack, including data engineering, database design, analytics engineering, machine learning, prompt engineering, and application deployment.

---

## Business Problem

Many organisations collect large volumes of member activity data through CRM systems, websites, events, learning platforms, and marketing tools. However, this information is often spread across multiple systems, making it difficult to answer critical questions such as:

- Which members are likely to disengage?
- What behaviours indicate strong long-term retention?
- Which engagement activities have the greatest impact?
- What actions should staff take to improve member outcomes?
- How can complex analytical findings be communicated to non-technical stakeholders?

Traditional dashboards provide historical reporting but often require manual interpretation. This project aims to bridge that gap by combining predictive analytics with AI-generated business recommendations.

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

The platform is built on the **Synthetic Professional Membership Engagement and
Retention Dataset** — a relational, behaviourally coherent dataset generated for this
project rather than taken from a single public source.

It is a *hybrid*: the member dimension is calibrated against the structure and published
marginals of the IBM Telco Customer Churn dataset, and is then extended with the
membership activity that a real professional body would hold — membership history,
weekly website activity, logins, events, learning, campaigns, feedback, predictions and
data-quality results.

**Scale (full profile):** 25,000 members across a five-year window, 2021-09-01 to
2026-08-31.

| Table | Rows | Grain |
| --- | ---: | --- |
| `members` | 25,000 | One per member (current state) |
| `membership_history` | ~80,000 | One per membership term (SCD) |
| `website_activity` | ~1.6M | Member × week |
| `login_history` | ~2.3M | One per authentication attempt |
| `events` / `event_attendance` | 1,600 / ~300,000 | Catalogue / member × registration |
| `courses` / `learning_activity` | 90 / ~152,000 | Catalogue / member × course engagement |
| `campaigns` / `marketing_engagement` | 265 / ~1.1M | Catalogue / member × send |
| `member_feedback` | ~50,000 | One per free-text submission |
| `model_predictions` | ~118,000 | Member × monthly scoring run |
| `ai_insights` | ~6,300 | Member × latest scoring run |
| `data_quality_results` | 2,820 | Check × pipeline run |

### The point: the data is not random

Churn is not assigned by a coin flip. Behaviour is generated first, from latent member
traits with a year-on-year trend and a seasonal cycle. At each renewal anniversary,
features are measured *from behaviour that has already happened*, a logistic model is
applied, and the outcome is sampled. Activity after a lapse is then deleted.

A model refitted on the resulting training table reaches an out-of-time AUC of **0.77**
and recovers the generating coefficients at **r = 0.97** — genuine, learnable signal,
with enough noise that the problem is not trivial.

### Generating it

```bash
pip install -r requirements.txt
python -m src.generators.run --scale full     # ~5 minutes, ~400 MB
python -m src.validation.validate             # 65 structural, volume and signal checks
```

Profiles are `dev` (1,000 members, ~15 seconds), `demo` (8,000) and `full` (25,000).
Runs are fully reproducible from `--seed`, and each run writes a
`generation_manifest.json` recording the seed, scale, calibration source, model
coefficients and realised row counts.

The generated data is **not committed** — a 250-row extract of every table lives in
[`data/sample/`](data/sample/) instead.

### Documentation

- [Data generation methodology](docs/data-generation-methodology.md) — the business
  rules, the churn model, the validation results and the known simplifications
- [Data dictionary](data/data_dictionary/data_dictionary.md) — every table and column
- [`data/seed/README.md`](data/seed/README.md) — the optional IBM Telco calibration file
- [`database/schema/`](database/schema/) — PostgreSQL DDL (keys, check constraints,
  indexes) and a `psql` load script for the generated CSVs

### Privacy

No names, addresses, dates of birth, email addresses, telephone numbers or payment
details are generated. Age is banded. Every member, event, course and campaign is
fictional.

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
            │
            ▼
 Streamlit Dashboard
 Interactive Reporting
```

---

## Core Features

### Data Integration

The platform ingests data from multiple sources including:

- CRM systems
- Membership databases
- Event registration systems
- Marketing platforms
- Website engagement logs
- Customer feedback datasets

The ETL pipeline cleans, validates, transforms, and standardises incoming data before loading it into the analytical database.

---

### Data Quality Monitoring

Automated validation checks identify issues such as:

- Missing values
- Duplicate records
- Invalid relationships
- Inconsistent member identifiers
- Data freshness concerns

Data quality metrics are surfaced within the dashboard to improve confidence in reporting outputs.

---

### Member Engagement Scoring

A composite engagement score is calculated using behavioural indicators such as:

- Login frequency
- Event attendance
- Membership duration
- Marketing engagement
- Product or service usage
- Website interactions

These scores provide a measurable framework for evaluating member activity and identifying engagement trends.

---

### Predictive Analytics

Machine learning models are used to identify:

#### Churn Risk

Predicts which members are most likely to disengage or lapse based on historical behaviour patterns.

#### Retention Drivers

Identifies which activities are most strongly associated with long-term membership retention.

#### Behavioural Segmentation

Groups members into meaningful clusters based on engagement characteristics and usage patterns.

Example segments may include:

- Highly Engaged Advocates
- Event-Focused Members
- Passive Subscribers
- At-Risk Members
- New Joiners

---

### AI-Generated Insights

The platform uses a Large Language Model (LLM) to transform analytical outputs into clear business recommendations.

Examples include:

**Automated Insight Generation**

> Members who attended at least three events during their first 90 days were significantly more likely to renew their membership compared with non-attendees.

**Retention Recommendations**

> Consider targeting this member segment with event invitations and personalised onboarding communications, as similar members historically show increased engagement after attending their first event.

**Executive Summaries**

> Membership engagement increased by 12% during the previous quarter, driven primarily by growth in online learning participation and webinar attendance.

This layer enables non-technical stakeholders to quickly understand analytical findings without requiring deep statistical knowledge.


---

## Large Language Model (LLM) Integration

A core component of this project is the AI Insight Layer, which converts analytical outputs into actionable business recommendations and plain-English summaries.

The platform is intentionally designed to be model-agnostic, allowing multiple Large Language Models (LLMs) to be used interchangeably depending on deployment requirements, cost constraints, and performance considerations.

Potential use cases include:

- Generating executive summaries from analytical outputs
- Explaining churn predictions and risk factors
- Producing personalised retention recommendations
- Summarising customer feedback and reviews
- Translating technical metrics into business language
- Supporting non-technical stakeholders with AI-generated insights

---

### Option 1: Google Gemini API

Google Gemini provides access to Google's latest family of generative AI models through a simple API interface. The platform offers a generous free tier suitable for experimentation and portfolio projects.

Example implementation:

```python
from google import genai

client = genai.Client(api_key="YOUR_KEY")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Summarise this customer complaint"
)

print(response.text)
```

Potential use cases within this project:

- Executive summary generation
- Customer sentiment analysis
- Churn explanation generation
- Automated business recommendations

---

### Option 2: Ollama (Local Deployment)

For completely free and local execution, the project can integrate with Ollama, allowing open-source models to run directly on a developer machine without external API costs.

Run locally:

```bash
ollama run llama3
```

Example API call:

```python
import requests

response = requests.post(
    "http://localhost:11434/api/generate",
    json={
        "model": "llama3",
        "prompt": "Summarise this customer complaint"
    }
)

print(response.json())
```

Benefits:

- No API costs
- Runs entirely on local hardware
- Supports offline development
- Demonstrates deployment and infrastructure skills
- Easy model switching during experimentation

Supported models include:

- Llama 3
- Mistral
- Qwen 3
- DeepSeek-R1

---

### Option 3: Hugging Face Inference API

The Hugging Face ecosystem provides access to thousands of open-source models through hosted inference endpoints.

Example:

```python
import requests

API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct"

headers = {
    "Authorization": "Bearer YOUR_TOKEN"
}

response = requests.post(
    API_URL,
    headers=headers,
    json={"inputs": "Summarise this complaint"}
)

print(response.json())
```

Potential advantages:

- Large model selection
- Rapid experimentation
- Minimal infrastructure requirements
- Easy integration into existing Python workflows

---

### Option 4: OpenRouter

OpenRouter provides a unified API layer that enables access to multiple commercial and open-source models through a single endpoint.

Available models may include:

- Claude
- Gemini
- GPT
- Llama
- Qwen
- DeepSeek

This approach simplifies experimentation by allowing model comparisons without changing significant portions of application code.

---

### Recommended Approach

For  development and experimentation, Ollama is the preferred implementation due to its zero-cost deployment model and support for modern open-source LLMs.

Models such as:

- Qwen 3 8B
- Llama 3 8B
They 
are more than capable of generating executive summaries, retention recommendations, and business insights for this project while remaining completely free to use.

The architecture has been intentionally designed so that the AI layer can be swapped between local models and cloud-hosted APIs with minimal changes to the wider application.



---

##  Possible Technology Stack 

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

- Scikit-Learn (Random Forest, Logistic Regression
- XGBoost
- LightGBM

### Dashboard & Application

- Power BI
- Plotly
- Streamlit

### Version Control

- Git
- GitHub

### AI Layer

*Implementation details intentionally omitted to allow experimentation with multiple LLM providers and deployment approaches.*

---

## Example Dashboard Components

The dashboard may include:

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
