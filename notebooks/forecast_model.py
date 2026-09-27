"""
Time Series Forecasting — Renewables % of UK Grid

Decomposes the time series, fits a SARIMA model, backtests,
and forecasts the next 24 hours.
"""

from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import statsmodels.api as sm
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import adfuller
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error
from sqlalchemy import create_engine


# ============================================================
# 1. LOAD DATA
# ============================================================
DB_URL = "postgresql+psycopg://localhost/energy_tracker"
print("Loading data...")
engine = create_engine(DB_URL)

df = pd.read_sql("""
    SELECT
        fm.period_start,
        ds.name AS source,
        fm.percentage,
        ds.is_renewable
    FROM fact_energy_mix fm
    JOIN dim_energy_source ds ON ds.id = fm.source_id
    ORDER BY fm.period_start
""", engine)

df["period_start"] = pd.to_datetime(df["period_start"])

# Aggregate to renewables %
renewables = (
    df[df["is_renewable"] == 1]
    .groupby("period_start")["percentage"]
    .sum()
    .sort_index()
)

print(f"  Series length: {len(renewables)}")
print(f"  Range: {renewables.min():.1f}% → {renewables.max():.1f}%")
print(f"  Mean: {renewables.mean():.1f}%")

# Ensure regular frequency (30 min)
renewables = renewables.asfreq("30min")
renewables = renewables.interpolate()   # fill any gaps

print(f"  After resample: {len(renewables)} periods, "
      f"freq={renewables.index.freqstr}")


# ============================================================
# 2. DECOMPOSITION
# ============================================================
print("\nDecomposing series (STL)...")
# Daily cycle = 48 periods of 30 min
decomp = seasonal_decompose(renewables, model="additive", period=48)

fig, axes = plt.subplots(4, 1, figsize=(14, 10))
renewables.plot(ax=axes[0], color="#2ca02c")
axes[0].set_ylabel("Observed")
axes[0].set_title("Time Series Decomposition — Renewables %")

decomp.trend.plot(ax=axes[1], color="#1f77b4")
axes[1].set_ylabel("Trend")

decomp.seasonal.plot(ax=axes[2], color="#ff7f0e")
axes[2].set_ylabel("Seasonal")

decomp.resid.plot(ax=axes[3], color="#d62728")
axes[3].set_ylabel("Residual")

plt.tight_layout()
plt.savefig(Path(__file__).parent / "decomposition.png", dpi=100)
print(f"  Saved: decomposition.png")


# ============================================================
# 3. STATIONARITY TEST (ADF)
# ============================================================
print("\nAugmented Dickey-Fuller test:")
result = adfuller(renewables.dropna(), autolag="AIC")
print(f"  ADF Statistic: {result[0]:.4f}")
print(f"  p-value:       {result[1]:.4f}")
print(f"  Critical values: {result[4]}")

if result[1] < 0.05:
    print("  → Series is STATIONARY (reject null hypothesis)")
    d = 0
else:
    print("  → Series is NON-STATIONARY (fail to reject null)")
    print("  → Will use d=1 (first difference)")
    d = 1


# ============================================================
# 4. TRAIN / TEST SPLIT
# ============================================================
# Last 48 periods = 24 hours as holdout
HOLDOUT = 48
train = renewables[:-HOLDOUT]
test = renewables[-HOLDOUT:]

print(f"\nTrain size: {len(train)}")
print(f"Test size:  {len(test)} (last 24 hours)")


# ============================================================
# 5. FIT SARIMA
# ============================================================
print("\nFitting SARIMA(1,1,1)(1,1,1,48) — this takes 1-2 minutes...")

model = SARIMAX(
    train,
    order=(1, d, 1),
    seasonal_order=(1, 1, 1, 48),
    enforce_stationarity=False,
    enforce_invertibility=False,
)
results = model.fit(disp=False)

print(f"  Model fitted. AIC: {results.aic:.2f}")


# ============================================================
# 6. FORECAST ON HOLDOUT
# ============================================================
print("\nForecasting next 24 hours...")
forecast = results.get_forecast(steps=HOLDOUT)
pred_mean = forecast.predicted_mean
pred_ci = forecast.conf_int()


# ============================================================
# 7. EVALUATE
# ============================================================
mape = mean_absolute_percentage_error(test, pred_mean) * 100
rmse = np.sqrt(mean_squared_error(test, pred_mean))

print(f"\n  MAPE: {mape:.2f}%")
print(f"  RMSE: {rmse:.2f}%")


# ============================================================
# 8. PLOT FORECAST
# ============================================================
fig, ax = plt.subplots(figsize=(14, 6))

# Show last 3 days of training + all test
plot_start = len(train) - 144
ax.plot(train.index[plot_start:], train.values[plot_start:],
        label="Training data", color="#2ca02c", linewidth=1)
ax.plot(test.index, test.values,
        label="Actual (holdout)", color="#1f77b4", linewidth=1.5)
ax.plot(pred_mean.index, pred_mean.values,
        label="Forecast", color="#d62728", linewidth=1.5, linestyle="--")

# Confidence interval
ax.fill_between(pred_ci.index,
                pred_ci.iloc[:, 0],
                pred_ci.iloc[:, 1],
                color="#d62728", alpha=0.2, label="95% CI")

ax.set_title("SARIMA Forecast vs Actual — Renewables %")
ax.set_ylabel("Renewables %")
ax.set_xlabel("Date")
ax.legend()
ax.grid(True, alpha=0.3)

plt.tight_layout()
plt.savefig(Path(__file__).parent / "forecast.png", dpi=100)
print(f"\n  Saved: forecast.png")

# Save the metrics
metrics = {
    "mape": round(mape, 2),
    "rmse": round(rmse, 2),
    "aic": round(results.aic, 2),
}
print(f"\n  Metrics: {metrics}")

print("\n✅ Done.")
