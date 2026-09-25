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
import streamlit as st
from sqlalchemy import create_engine


DB_URL = os.getenv("DATABASE_URL", "postgresql://localhost/energy_tracker")

st.set_page_config(page_title="UK Energy Mix Tracker", page_icon="⚡", layout="wide")


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

st.divider()
st.caption("Built with Python, PostgreSQL, and Streamlit.")
