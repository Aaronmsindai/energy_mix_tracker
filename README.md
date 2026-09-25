⚡ Energy Mix Tracker

End-to-end data pipeline that ingests live UK electricity grid data from the Carbon Intensity API, stores it in PostgreSQL, and visualizes it in a Streamlit analytics dashboard.

🌐 What This Project Does

Every time the pipeline runs, it:

1. Fetches the current UK energy generation mix from a public API
2. Stores the raw JSON response in raw_generation (audit trail)
3. Parses the fuel mix and inserts one row per energy source into fact_energy_mix
4. Skips duplicates using PostgreSQL ON CONFLICT DO NOTHING (idempotent)
5. Serves an interactive dashboard showing current mix, renewables trend, and top sources

🏗️ Architecture

```
Carbon Intensity API → src/ingest.py → PostgreSQL → Streamlit Dashboard
```

Database schema (star schema):

· dim_country — Country reference
· dim_energy_source — Energy source + renewable flag
· raw_generation — Raw API responses (audit)
· fact_energy_mix — Cleaned analytics rows

🛠️ Tech Stack

Layer Technology
Language Python 3.12
Database PostgreSQL 16
ORM SQLAlchemy 2.0
API Client requests
Scheduler Python time.sleep loop
Dashboard Streamlit + Plotly
Testing Pytest

📊 Key Features

· Idempotent ingestion — re-running the pipeline never creates duplicates
· Raw audit trail — every API response stored verbatim
· Dimensional schema — star schema with fact + dimension tables
· Live dashboard — metric cards, donut chart, trend line, source ranking
· Zero-config scheduler — plain Python loop, no heavyweight orchestration

## ⚠️ Note on Cold Starts

This app is deployed on Streamlit Community Cloud (free tier), which
sleeps after 15 minutes of inactivity. The first visit may take 30–60
seconds to wake up both the Streamlit server and the Neon database.
After that, the app is instant.

🚀 How to Run Locally

Prerequisites

· Python 3.12
· PostgreSQL 16 (Postgres.app recommended on Mac)

Setup

```bash
git clone git@github.com:Deodael/energy_mix_tracker.git
cd energy_mix_tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

createdb energy_tracker
python -c "from src.db import init_db; init_db()"
python -m src.seed
python flows/daily_pipeline.py

streamlit run app/dashboard.py
```

Open http://localhost:8501 in your browser.

📂 Project Structure

```
energy_mix_tracker/
├── src/
│   ├── db.py              # Engine + session factory
│   ├── models.py          # SQLAlchemy models (4 tables)
│   ├── ingest.py          # ETL: API to PostgreSQL
│   └── seed.py            # Dimension table seeder
├── flows/
│   └── daily_pipeline.py  # Scheduler / entrypoint
├── app/
│   └── dashboard.py       # Streamlit UI
├── tests/
├── sql/
├── requirements.txt
└── README.md
```

📈 Sample Insights

After ingesting several periods, the dashboard shows:

· Renewables typically contribute 30-50% of the UK grid
· Gas remains the largest single source (~30-40%)
· Coal has been phased out — consistently 0%
· Wind is highly variable — swings from 5% to 40%

📝 Design Decisions

Why PostgreSQL over SQLite?
SQLite is file-based with single-writer locking. This project writes on a schedule while the dashboard reads — PostgreSQL handles concurrent access with row-level locking.

Why a plain scheduler instead of Prefect/Airflow?
For a single-task pipeline, time.sleep is simpler and has no dependency conflicts. Prefect was evaluated but hit Pydantic version issues. Airflow/Prefect earn their complexity when there are multiple dependent tasks.

Why SQLAlchemy ORM instead of raw SQL?
Type safety, FK relationships, and portability. ON CONFLICT DO NOTHING uses PostgreSQL's pg_insert extension for clean idempotent upserts.

📜 License

MIT — see LICENSE.

🙏 Acknowledgments

· Data source: UK Carbon Intensity API
· Stack: PostgreSQL, SQLAlchemy, Streamlit, Plotly
