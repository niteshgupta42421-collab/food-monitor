"""
MealFlow360 - Demand forecasting.

A deliberately transparent forecast: the expected demand for a food is based
only on the organisation's own recorded sales history. There is no external
data and no black box - every number the app shows is:

  * labelled Estimated in the UI,
  * reported together with the history it is based on (days of sales),
  * produced by a simple rule that can be explained in one sentence:

        expected = (blend of the same-weekday average and the recent daily
                    average) x (1 + safety buffer)

With no sales history, no forecast is produced - the app never invents a
number from nothing.
"""

import math
from datetime import date, timedelta

import pandas as pd

from database import database

DEFAULT_HISTORY_DAYS = 14
DEFAULT_BUFFER_PCT = 10.0
FORECAST_COLUMNS = [
    "food_id", "food_name", "unit", "portion_size_g", "avg_daily_units",
    "same_weekday_avg", "expected_units", "expected_kg", "days_with_sales",
]


def demand_forecast(history_days: int = DEFAULT_HISTORY_DAYS,
                    buffer_pct: float = DEFAULT_BUFFER_PCT,
                    target_date=None) -> pd.DataFrame:
    """
    Expected demand per food for one service day, from recorded sales only.

    history_days  how far back the sales window reaches (including the target date)
    buffer_pct    safety margin added on top of the historical averages
    target_date   the day being planned (defaults to today); the weekday of
                  this date decides which weekday average is blended in

    Columns: food_id, food_name, unit, portion_size_g, avg_daily_units,
    same_weekday_avg, expected_units, expected_kg, days_with_sales.
    """
    target = target_date or date.today()
    start = target - timedelta(days=history_days - 1)
    sales = database.get_sales_range(start, target)
    if sales.empty:
        return pd.DataFrame(columns=FORECAST_COLUMNS)

    sales = sales.copy()
    sales["date"] = pd.to_datetime(sales["date"]).dt.date
    target_weekday = target.weekday()

    rows = []
    grouped = sales.groupby(["food_id", "food_name", "unit", "portion_size_g"])
    for (food_id, food_name, unit, portion), group in grouped:
        daily = group.groupby("date")["quantity_sold"].sum()
        days_with_sales = int(len(daily))
        if days_with_sales < 1:
            continue
        avg_daily = float(daily.mean())
        weekday_values = [quantity for day, quantity in daily.items() if day.weekday() == target_weekday]
        same_weekday_avg = float(sum(weekday_values) / len(weekday_values)) if weekday_values else None
        base = avg_daily if same_weekday_avg is None else 0.5 * same_weekday_avg + 0.5 * avg_daily
        expected_units = round_up_to_half(base * (1.0 + buffer_pct / 100.0))
        portion = float(portion or 0)
        rows.append({
            "food_id": int(food_id),
            "food_name": food_name,
            "unit": unit,
            "portion_size_g": portion,
            "avg_daily_units": round(avg_daily, 2),
            "same_weekday_avg": None if same_weekday_avg is None else round(same_weekday_avg, 2),
            "expected_units": expected_units,
            "expected_kg": round(expected_units * portion / 1000.0, 2),
            "days_with_sales": days_with_sales,
        })
    frame = pd.DataFrame(rows, columns=FORECAST_COLUMNS)
    return frame.sort_values("expected_units", ascending=False).reset_index(drop=True)


def sell_through_pct(sold_kg: float, available_kg: float) -> float:
    """Sell-through = food sold / food available x 100 (0 when nothing is available)."""
    if not available_kg or available_kg <= 0:
        return 0.0
    return float(sold_kg) / float(available_kg) * 100.0


def round_up_to_half(value: float) -> float:
    """Round up to the nearest 0.5 selling units (a forecast never rounds down)."""
    return math.ceil(float(value) * 2.0) / 2.0
