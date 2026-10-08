"""
MealFlow360 - Per-food daily stock state.

One function answers, for every food touched on a given day: how much was
prepared, how much is available, how much was sold, what remains, and whether
the remainder is healthy, low or out of stock.

This builds directly on the single accounting model (services/accounting.py):

    remaining = available - sold
    available = prepared - kitchen waste

Pages must not re-derive these numbers themselves, so a kilogram of food is
never counted twice.
"""

import pandas as pd

from database import database
from services import accounting

STATUS_OK = "OK"
STATUS_LOW = "Low"
STATUS_OUT = "Out"

STATUS_ICON = {STATUS_OK: "🟢", STATUS_LOW: "🟡", STATUS_OUT: "🔴"}

DAY_STOCK_COLUMNS = [
    "food_id", "food_name", "unit", "portion_size_g", "low_stock_threshold",
    "production_mode", "prepared", "kitchen_waste", "available", "sold_units", "sold_kg",
    "remaining_kg", "remaining_units", "status", "expected_demand",
]


def classify(remaining_kg: float, remaining_units: float | None, threshold: float) -> str:
    """
    Stock status of one food.

    Out  - nothing (or less than nothing) remains to sell
    Low  - remaining portions are at or below the food's low-stock threshold
    OK   - healthy stock
    """
    if remaining_kg <= 0:
        return STATUS_OUT
    if threshold > 0 and remaining_units is not None and remaining_units <= threshold:
        return STATUS_LOW
    return STATUS_OK


def day_stock_frame(day) -> pd.DataFrame:
    """
    Per-food stock for one day. Only foods with production or sales that day
    are included. `remaining_units` is None when the food has no portion size.
    """
    production = database.get_production_day(day)
    sales = database.get_sales_day(day)
    waste = database.get_waste_day(day)
    if production.empty and sales.empty:
        return pd.DataFrame(columns=DAY_STOCK_COLUMNS)

    foods = database.get_food_items_df().set_index("id")

    prepared = production.groupby("food_id")["quantity_prepared"].sum()
    expected = production.groupby("food_id")["expected_demand"].sum()
    kitchen = (
        waste[waste["waste_type"] == "kitchen"].groupby("food_id")["quantity"].sum()
        if not waste.empty else pd.Series(dtype=float)
    )
    sold_units = sales.groupby("food_id")["quantity_sold"].sum() if not sales.empty else pd.Series(dtype=float)

    rows = []
    for food_id in sorted(set(prepared.index) | set(sold_units.index) | set(expected.index)):
        if food_id not in foods.index:
            continue
        meta = foods.loc[food_id]
        portion = float(meta["portion_size_g"] or 0)
        prepared_kg = float(prepared.get(food_id, 0.0))
        available_kg = accounting.available_for_service(prepared_kg, float(kitchen.get(food_id, 0.0)))
        units_sold = float(sold_units.get(food_id, 0.0))
        kg_sold = units_sold * portion / 1000.0
        remaining_kg = accounting.served_quantity(prepared_kg, float(kitchen.get(food_id, 0.0)), kg_sold)
        remaining_units = remaining_kg / (portion / 1000.0) if portion > 0 else None
        threshold = float(meta["low_stock_threshold"] or 0)
        rows.append({
            "food_id": int(food_id),
            "food_name": meta["food_name"],
            "unit": meta["unit"],
            "portion_size_g": portion,
            "low_stock_threshold": threshold,
            "production_mode": meta["production_mode"],
            "prepared": prepared_kg,
            "kitchen_waste": float(kitchen.get(food_id, 0.0)),
            "available": available_kg,
            "sold_units": units_sold,
            "sold_kg": kg_sold,
            "remaining_kg": remaining_kg,
            "remaining_units": remaining_units,
            "status": classify(remaining_kg, remaining_units, threshold),
            "expected_demand": float(expected.get(food_id, 0.0)),
        })
    return pd.DataFrame(rows, columns=DAY_STOCK_COLUMNS)


def status_text(status: str, unit: str = "") -> str:
    """Status with icon for display, e.g. '🟡 Low'."""
    return f"{STATUS_ICON.get(status, '')} {status}".strip()
