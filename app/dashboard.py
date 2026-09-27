"""
Streamlit dashboard for the Energy Mix Tracker.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine


st.set_page_config(page_title="UK Energy Mix Tracker", page_icon="⚡", layout="wide")

# Resolve DB URL: secrets -> env var -> localhost
try:
    DB_URL = st.secrets["DATABASE_URL"]
except Exception:
    DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost/energy_tracker")


@st.cache_resource
def get_engine():
    return create_engine(DB_URL, future=True)


@st.cache_data(ttl=60)
def load_latest_mix() -> pd.DataFrame:
    sql = """
    WITH latest AS (SELECT MAX(period_start) AS max_period FROM fact_energy_mix)
    SELECT ds.name AS source, fm.percentage, ds.is_renewable
    FROM fact_energy_mix fm
    JOIN dim_energy_source ds ON ds.id = fm.source_id
    WHERE fm.period_start = (SELECT max_period FROM latest)
    ORDER BY fm.percentage DESC
    """
    return pd.read_sql(sql, get_engine())


@st.cache_data(ttl=60)
def load_time_series() -> pd.DataFrame:
    sql = """
    SELECT fm.period_start,
        CASE WHEN ds.is_renewable = 1 THEN 'Renewable' ELSE 'Non-renewable' END AS category,
        SUM(fm.percentage) AS total_pct
    FROM fact_energy_mix fm
    JOIN dim_energy_source ds ON ds.id = fm.source_id
    GROUP BY fm.period_start, category
    ORDER BY fm.period_start
    """
    return pd.read_sql(sql, get_engine())


@st.cache_data(ttl=60)
def load_avg_by_source() -> pd.DataFrame:
    sql = """
    SELECT ds.name AS source,
           ROUND(AVG(fm.percentage)::numeric, 2) AS avg_pct,
           MAX(ds.is_renewable) AS is_renewable
    FROM fact_energy_mix fm
    JOIN dim_energy_source ds ON ds.id = fm.source_id
    GROUP BY ds.name
    ORDER BY avg_pct DESC
    """
    return pd.read_sql(sql, get_engine())


@st.cache_data(ttl=60)
def load_row_count() -> int:
    df = pd.read_sql("SELECT COUNT(*) AS n FROM fact_energy_mix", get_engine())
    return int(df["n"].iloc[0])


@st.cache_data(ttl=3600, show_spinner=False)
def run_forecast():
    from src.forecast import forecast_next_24h
    return forecast_next_24h(holdout=48)


st.title("⚡ UK Energy Mix Tracker")
st.markdown("Real-time breakdown of the UK electricity grid from the Carbon Intensity API.")
st.divider()

try:
    latest = load_latest_mix()
    ts = load_time_series()
    avg = load_avg_by_source()
    n_rows = load_row_count()
except Exception as e:
    st.error(f"DB query failed: {e}")
    st.stop()

renewable_pct = latest[latest["is_renewable"] == 1]["percentage"].sum()
top_source = latest.iloc[0] if not latest.empty else None

col1, col2, col3, col4 = st.columns(4)
col1.metric("Renewables Now", f"{renewable_pct:.1f}%")
if top_source is not None:
    col2.metric("Top Source", top_source["source"].capitalize(), f"{top_source['percentage']:.1f}%")
col3.metric("Observations", f"{n_rows:,}")
col4.metric("Unique Sources", latest["source"].nunique())

st.subheader("📊 Current Energy Mix")
fig_pie = px.pie(latest, names="source", values="percentage",
                 color="is_renewable", color_discrete_map={1: "#2ca02c", 0: "#d62728"}, hole=0.4)
st.plotly_chart(fig_pie, use_container_width=True)

st.subheader("📈 Renewables vs Non-Renewables Over Time")
if not ts.empty:
    fig_line = px.line(ts, x="period_start", y="total_pct", color="category",
                       markers=True, color_discrete_map={"Renewable": "#2ca02c", "Non-renewable": "#d62728"})
    fig_line.update_layout(yaxis_title="% of Grid", xaxis_title="Period")
    st.plotly_chart(fig_line, use_container_width=True)

st.subheader("🏆 Average Contribution by Source")
fig_bar = px.bar(avg, x="avg_pct", y="source", orientation="h",
                 color="is_renewable", color_discrete_map={1: "#2ca02c", 0: "#d62728"})
fig_bar.update_layout(xaxis_title="Average %", yaxis_title="", showlegend=False)
st.plotly_chart(fig_bar, use_container_width=True)


# ============================================================
# 24-HOUR SARIMA FORECAST
# ============================================================
st.divider()
st.subheader("📈 24-Hour Renewables Forecast")
st.caption("SARIMA(1,1,1)(1,1,1,48) — evaluated on the last 24-hour holdout.")

try:
    with st.spinner("Fitting SARIMA model... (~2 min on first run)"):
        fc = run_forecast()

    m1, m2, m3 = st.columns(3)
    m1.metric("MAPE", f"{fc['mape']}%")
    m2.metric("RMSE", f"{fc['rmse']}%")
    m3.metric("AIC", f"{fc['aic']}")

    plot_start = max(0, len(fc["train"]) - 144)
    train_tail = fc["train"].iloc[plot_start:]

    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=train_tail.index, y=train_tail.values,
        mode="lines", name="Training data",
        line=dict(color="#2ca02c", width=1),
    ))
    fig.add_trace(go.Scatter(
        x=fc["test"].index, y=fc["test"].values,
        mode="lines", name="Actual (holdout)",
        line=dict(color="#1f77b4", width=2),
    ))
    fig.add_trace(go.Scatter(
        x=fc["pred"].index, y=fc["pred"].values,
        mode="lines", name="Forecast",
        line=dict(color="#d62728", width=2, dash="dash"),
    ))
    fig.add_trace(go.Scatter(
        x=fc["ci"].index, y=fc["ci"].iloc[:, 1],
        mode="lines", line=dict(width=0),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=fc["ci"].index, y=fc["ci"].iloc[:, 0],
        mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor="rgba(214,39,40,0.15)",
        name="95% CI", hoverinfo="skip",
    ))

    fig.update_layout(
        title="SARIMA Forecast vs Actual — Renewables %",
        xaxis_title="Date",
        yaxis_title="Renewables %",
        hovermode="x unified",
        height=500,
    )
    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        f"Trained on {len(fc['train'])} periods. "
        f"Evaluated on the final {len(fc['pred'])} periods (24 hours)."
    )

except Exception as e:
    st.error(f"❌ Forecast failed: {e}")
    st.info("Forecast requires at least 200 periods of data.")


st.divider()
st.caption("Built with Python, PostgreSQL, and Streamlit.")
