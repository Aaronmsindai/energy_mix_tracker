"""Time Series Forecasting — Renewables % of UK Grid"""
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sqlalchemy import create_engine

# ============================================================
# CONFIGURATION
# ============================================================
DB_URL = "postgresql+psycopg://localhost/energy_tracker"

print("Connecting...")
engine = create_engine(DB_URL)

print("Loading data...")
df = pd.read_sql("""
    SELECT fm.period_start, ds.name AS source, fm.percentage, ds.is_renewable
    FROM fact_energy_mix fm
    JOIN dim_energy_source ds ON ds.id = fm.source_id
    ORDER BY fm.period_start
""", engine)

df["period_start"] = pd.to_datetime(df["period_start"])
print(f"  Rows loaded:     {len(df):,}")
print(f"  Date range:      {df['period_start'].min()} → {df['period_start'].max()}")
print(f"  Unique sources:  {df['source'].nunique()}")
print(f"  Unique periods:  {df['period_start'].nunique()}")

renewables = (
    df[df["is_renewable"] == 1]
    .groupby("period_start")["percentage"]
    .sum()
    .sort_index()
)

print(f"\nPeriods: {len(renewables)}")
print(f"  Min:   {renewables.min():.1f}%")
print(f"  Max:   {renewables.max():.1f}%")
print(f"  Mean:  {renewables.mean():.1f}%")

fig, ax = plt.subplots(figsize=(14, 5))
renewables.plot(ax=ax, color="#2ca02c")
ax.set_title("Renewables % of UK Grid — Last 14 Days")
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(Path(__file__).parent / "renewables_timeseries.png", dpi=100)

renewables.to_csv(Path(__file__).parent / "renewables.csv", header=["renewables_pct"])
print("\n✅ Done.")
