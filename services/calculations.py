"""
FoodWaste360 - Core calculations.

Turns raw database rows into the aggregate tables used by the dashboard,
analytics, impact and report pages. All outputs here are CALCULATED values
(derived mathematically from MEASURED entries by the organization).
"""

import pandas as pd

from database import database
from utils.formatting import safe_div

WASTE_TYPES = ("kitchen", "serving", "plate")


def daily_aggregates(start, end) -> pd.DataFrame:
    """
    One row per calendar day in the range with prepared / served / consumed
    quantities, waste totals per category and the waste percentage.
    """
    days = pd.date_range(start, end, freq="D").strftime("%Y-%m-%d")
    result = pd.DataFrame(index=pd.Index(days, name="date"))

    production = database.get_production_range(start, end)
    if not production.empty:
        prod_daily = production.groupby("date")[
            ["quantity_prepared", "quantity_served", "quantity_consumed"]
        ].sum()
        prod_daily = prod_daily.rename(columns={
            "quantity_prepared": "prepared",
            "quantity_served": "served",
            "quantity_consumed": "consumed",
        })
        result = result.join(prod_daily, how="left")

    waste = database.get_waste_range(start, end)
    if not waste.empty:
        waste_daily = waste.groupby(["date", "waste_type"])["quantity"].sum().unstack(fill_value=0.0)
        for waste_type in WASTE_TYPES:
            if waste_type not in waste_daily.columns:
                waste_daily[waste_type] = 0.0
        result = result.join(waste_daily[list(WASTE_TYPES)], how="left")

    for column in ("prepared", "served", "consumed", "kitchen", "serving", "plate"):
        if column not in result.columns:
            result[column] = 0.0
    result = result.fillna(0.0)

    result["waste"] = result["kitchen"] + result["serving"] + result["plate"]
    # Waste % = total waste / total prepared x 100 (spec section 9). Guarded for zero.
    result["waste_pct"] = (result["waste"] / result["prepared"] * 100).where(result["prepared"] > 0, 0.0)

    return result.reset_index()


def period_totals(start, end) -> dict:
    """Headline totals for a period (used by dashboard, impact and reports)."""
    daily = daily_aggregates(start, end)
    prepared = float(daily["prepared"].sum())
    waste_total = float(daily["waste"].sum())
    return {
        "prepared": prepared,
        "served": float(daily["served"].sum()),
        "consumed": float(daily["consumed"].sum()),
        "waste": waste_total,
        "kitchen": float(daily["kitchen"].sum()),
        "serving": float(daily["serving"].sum()),
        "plate": float(daily["plate"].sum()),
        "waste_pct": safe_div(waste_total, prepared) * 100,
        "days_with_data": int(((daily["prepared"] > 0) | (daily["waste"] > 0)).sum()),
    }


def production_by_food(start, end) -> pd.DataFrame:
    """Prepared / served / consumed totals per food for the period."""
    production = database.get_production_range(start, end)
    if production.empty:
        return pd.DataFrame(columns=["food_id", "food_name", "prepared", "served", "consumed"])
    grouped = production.groupby(["food_id", "food_name"])[
        ["quantity_prepared", "quantity_served", "quantity_consumed"]
    ].sum().reset_index()
    return grouped.rename(columns={
        "quantity_prepared": "prepared",
        "quantity_served": "served",
        "quantity_consumed": "consumed",
    }).sort_values("prepared", ascending=False)


def waste_by_food(start, end) -> pd.DataFrame:
    """
    Per-food waste table for the period: each waste type, total waste,
    the food's own waste percentage (of what was prepared) and its
    contribution to the total waste of the period.
    """
    waste = database.get_waste_range(start, end)
    if waste.empty:
        return pd.DataFrame(columns=[
            "food_id", "food_name", "kitchen", "serving", "plate",
            "waste", "prepared", "waste_pct_of_prepared", "contribution_pct",
        ])

    per_food = waste.groupby(["food_id", "food_name", "waste_type"])["quantity"].sum().unstack(fill_value=0.0)
    for waste_type in WASTE_TYPES:
        if waste_type not in per_food.columns:
            per_food[waste_type] = 0.0
    per_food = per_food[list(WASTE_TYPES)].reset_index()
    per_food["waste"] = per_food["kitchen"] + per_food["serving"] + per_food["plate"]

    production = production_by_food(start, end)
    if not production.empty:
        per_food = per_food.merge(
            production[["food_id", "prepared"]], on="food_id", how="left"
        )
    else:
        per_food["prepared"] = None

    # Waste % per food uses the food's own prepared quantity as the base.
    per_food["waste_pct_of_prepared"] = (
        per_food["waste"] / per_food["prepared"] * 100
    ).where(per_food["prepared"].fillna(0) > 0)

    total_waste = float(per_food["waste"].sum())
    if total_waste > 0:
        per_food["contribution_pct"] = per_food["waste"] / total_waste * 100
    else:
        per_food["contribution_pct"] = 0.0

    return per_food.sort_values("waste", ascending=False).reset_index(drop=True)


def waste_totals_by_type(start, end) -> dict:
    """Total waste per category plus the overall total, for the period."""
    waste = database.get_waste_range(start, end)
    if waste.empty:
        return {"kitchen": 0.0, "serving": 0.0, "plate": 0.0, "total": 0.0}
    grouped = waste.groupby("waste_type")["quantity"].sum()
    totals = {waste_type: float(grouped.get(waste_type, 0.0)) for waste_type in WASTE_TYPES}
    totals["total"] = sum(totals.values())
    return totals


def plate_waste_summary(start, end) -> dict:
    """
    Plate-waste analysis for the period: total plate waste, customers served
    (sum of the daily counts) and the average leftover per customer.
    """
    plate = database.get_plate_waste_range(start, end)
    customers = database.get_customers_by_day(start, end)
    total_plate = float(plate["quantity_wasted"].sum()) if not plate.empty else 0.0
    total_customers = int(customers["customers_served"].sum()) if not customers.empty else 0

    avg_kg = safe_div(total_plate, total_customers)
    per_food = pd.DataFrame(columns=["food_id", "food_name", "quantity_wasted"])
    if not plate.empty:
        per_food = plate.groupby(["food_id", "food_name"])["quantity_wasted"].sum().reset_index()
        per_food = per_food.sort_values("quantity_wasted", ascending=False).reset_index(drop=True)

    return {
        "total_plate_waste": total_plate,
        "total_customers": total_customers,
        "avg_per_customer_kg": avg_kg,
        "avg_per_customer_g": avg_kg * 1000,
        "days_recorded": int(customers.shape[0]) if not customers.empty else 0,
        "by_food": per_food,
    }


def washing_summary(start, end) -> dict:
    """Plate-washing water totals for the period (all inputs are estimates)."""
    washing = database.get_washing_range(start, end)
    if washing.empty:
        return {"total_litres": 0.0, "total_plates": 0, "records": 0, "by_method": pd.DataFrame()}
    by_method = washing.groupby("washing_method").agg(
        litres=("water_used", "sum"),
        plates=("plates", "sum"),
        records=("id", "count"),
    ).reset_index()
    return {
        "total_litres": float(washing["water_used"].sum()),
        "total_plates": int(washing["plates"].sum()),
        "records": int(washing.shape[0]),
        "by_method": by_method,
    }
