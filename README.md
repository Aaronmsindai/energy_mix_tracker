# ⚡ Energy Mix Tracker

> End-to-end data pipeline that ingests live UK electricity grid data, stores it in PostgreSQL, and forecasts 24-hour renewable share using SARIMA.

## 🎯 What This Project Does

1. **Fetches** the current UK energy generation mix from the Carbon Intensity API
2. **Stores** raw responses and structured data in PostgreSQL
3. **Backfills** up to 14 days of historical data
4. **Forecasts** the next 24 hours of renewable share using SARIMA
5. **Visualizes** everything in a live Streamlit dashboard

## 🏗️ Architecture

    Carbon Intensity API → src/ingest.py → PostgreSQL → src/forecast.py → Streamlit

## 🛠️ Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12 |
| Database | PostgreSQL 16 |
| ORM | SQLAlchemy 2.0 |
| Forecasting | statsmodels (SARIMA) |
| Dashboard | Streamlit + Plotly |

## 📊 Key Features

- **Idempotent ingestion** — re-running never creates duplicates
- **14-day backfill** — historical data from the API
- **24-hour SARIMA forecast** — with MAPE, RMSE, AIC metrics
- **Interactive dashboard** — current mix, trends, forecasts

## 📈 Forecasting

The dashboard includes a **SARIMA(1,1,1)(1,1,1,48)** model that:

- Trains on 625+ historical periods
- Evaluates on a 24-hour holdout
- Displays **MAPE ~22%**, **RMSE ~11%**, **AIC ~1790**
- Shows actual vs predicted with 95% confidence intervals

## 🚀 How to Run Locally

    git clone git@github.com:Aaronmsindai/energy_mix_tracker.git
    cd energy_mix_tracker
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    createdb energy_tracker
    python -c "from src.db import init_db; init_db()"
    python -m src.seed
    python -m src.backfill --days 14
    streamlit run app/dashboard.py

## 📝 Design Decisions

- **PostgreSQL** over SQLite — needed concurrent read/write
- **Plain scheduler** over Prefect — no dependency conflicts
- **SARIMA** over Prophet/LSTM — interpretable, handles seasonality

## 📜 License

MIT