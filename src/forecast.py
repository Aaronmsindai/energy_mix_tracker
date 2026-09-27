"""
SARIMA forecasting module for renewable energy mix.
"""

import warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from statsmodels.tsa.statespace.sarimax import SARIMAX
from sklearn.metrics import mean_absolute_percentage_error, mean_squared_error

from src.db import get_session
from src.models import DimEnergySource, FactEnergyMix


def load_renewables_series() -> pd.Series:
    """Load renewables % from the DB as a time-indexed series."""
    session = get_session()
    try:
        from sqlalchemy import select

        rows = session.execute(
            select(FactEnergyMix.period_start, FactEnergyMix.percentage,
                   DimEnergySource.is_renewable)
            .join(DimEnergySource, DimEnergySource.id == FactEnergyMix.source_id)
            .order_by(FactEnergyMix.period_start)
        ).all()

        df = pd.DataFrame(rows, columns=["period_start", "percentage", "is_renewable"])
        df["period_start"] = pd.to_datetime(df["period_start"])

        # Cast to float (DB returns Decimal, which breaks statsmodels)
        df["percentage"] = df["percentage"].astype(float)

        series = (
            df[df["is_renewable"] == 1]
            .groupby("period_start")["percentage"]
            .sum()
            .sort_index()
            .astype(float)
        )
        return series

    finally:
        session.close()


def forecast_next_24h(holdout: int = 48) -> dict:
    """
    Fit a SARIMA model on all-but-the-last `holdout` periods,
    forecast the last `holdout` periods, and return results.
    """
    series = load_renewables_series()

    if len(series) < 200:
        raise ValueError(f"Not enough data: {len(series)} periods (need 200+)")

    # Split
    train = series[:-holdout]
    test = series[-holdout:]

    # Fit SARIMA
    model = SARIMAX(
        train,
        order=(1, 1, 1),
        seasonal_order=(1, 1, 1, 48),
        enforce_stationarity=False,
        enforce_invertibility=False,
    )
    results = model.fit(disp=False)

    # Forecast
    fc = results.get_forecast(steps=holdout)
    pred = fc.predicted_mean
    ci = fc.conf_int()

    # Metrics
    mape = mean_absolute_percentage_error(test, pred) * 100
    rmse = float(np.sqrt(mean_squared_error(test, pred)))

    return {
        "train": train,
        "test": test,
        "pred": pred,
        "ci": ci,
        "mape": round(mape, 2),
        "rmse": round(rmse, 2),
        "aic": round(results.aic, 2),
    }
