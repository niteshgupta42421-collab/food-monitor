"""
FoodWaste360 - Impact engine (financial + environmental).

Formulas (spec sections 13, 14 and 15):

    value lost      = wasted kg x cost per kg
    CO2e            = wasted kg x CO2e factor (kg CO2e / kg)
    water footprint = wasted kg x water factor (L / kg)
    washing water   = estimate from the washing calculator inputs

IMPORTANT RULES implemented here:
  * No environmental factor is invented - every factor comes from the
    food database, where each value carries its own source and reference.
  * Foods without a factor are excluded from that estimate and reported
    as coverage gaps instead of being silently estimated.
  * Plate-washing water is always kept separate from the food water footprint.
"""

import pandas as pd

from database import database
from services import calculations
from utils import formatting as fmt

# ---------------------------------------------------------------- methodology text

METHODOLOGY_INTRO = """
**How these numbers are produced**

* **Measured** - quantities and customer counts entered by your team.
* **Calculated** - values derived mathematically from measured data (waste %, averages).
* **Estimated** - values that multiply measured waste by external impact factors
  (CO2e, water footprint, food value). These are estimates, **not measurements**.
* **Simulated** - "What if" scenario results shown only in the Simulator.

Environmental factors are stored per food with their value, unit, source,
reference and date. Factors come from Poore & Nemecek (2018), a global
meta-analysis published in Science, processed by Our World in Data. Where a
prepared dish has no dedicated study (e.g. roti, idli), the closest documented
commodity factor is used as a clearly labelled proxy. You can update any factor
in the Food Database, and every change requires a source.
"""

WASHING_DISCLAIMER = (
    "Plate-washing water is an estimate based on the inputs above. It is kept separate "
    "from the food water footprint because it measures a different process."
)


# ---------------------------------------------------------------- factor access

def get_factors_df() -> pd.DataFrame:
    """Food items with their stored (documented) factors."""
    return database.get_food_items_df()


def attach_impacts(by_food_df: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    """
    Add value_lost / co2e / water_litres columns to a per-food waste table.

    Returns the enriched table and a list of coverage gaps:
    foods whose waste could not be included in an estimate because the
    matching factor is missing.
    """
    result = by_food_df.copy()
    if result.empty:
        for column in ("value_lost", "co2e", "water_litres", "cost_per_kg", "co2_factor", "water_factor"):
            result[column] = pd.Series(dtype="float64")
        return result, []

    factors = get_factors_df().rename(columns={
        "id": "food_id",
        "food_name": "factor_food_name",
        "cost_per_kg": "cost_per_kg",
        "co2_factor": "co2_factor",
        "water_factor": "water_factor",
    })
    factor_columns = [
        "food_id", "cost_per_kg", "co2_factor", "water_factor",
        "factor_source", "factor_reference", "factor_date", "is_estimated", "notes",
    ]
    result = result.merge(factors[factor_columns], on="food_id", how="left")

    # value lost: cost is always present (defaults to 0 -> contributes 0).
    result["value_lost"] = result["waste"] * result["cost_per_kg"].fillna(0.0)
    # CO2e / water: only computed where a documented factor exists.
    result["co2e"] = result["waste"] * result["co2_factor"]
    result["water_litres"] = result["waste"] * result["water_factor"]

    gaps = []
    for _, row in result.iterrows():
        if row["waste"] <= 0:
            continue
        missing = []
        if pd.isna(row["co2_factor"]):
            missing.append("CO2e factor")
        if pd.isna(row["water_factor"]):
            missing.append("water factor")
        if missing:
            gaps.append({"food_name": row["food_name"], "waste": row["waste"], "missing": missing})
    return result, gaps


def impact_totals(start, end) -> dict:
    """
    Full impact summary for a period.

    Returns totals plus a coverage report so the UI can state exactly which
    share of recorded waste is covered by documented factors.
    """
    by_food = calculations.waste_by_food(start, end)
    by_food, gaps = attach_impacts(by_food)

    waste_total = float(by_food["waste"].sum()) if not by_food.empty else 0.0
    co2_covered = float(by_food["co2e"].sum()) if not by_food.empty else 0.0
    water_covered = float(by_food["water_litres"].sum()) if not by_food.empty else 0.0
    value_lost = float(by_food["value_lost"].sum()) if not by_food.empty else 0.0

    # Waste (kg) whose CO2e factor is present - used for the coverage statement.
    if not by_food.empty:
        co2_covered_kg = float(by_food.loc[by_food["co2_factor"].notna(), "waste"].sum())
        water_covered_kg = float(by_food.loc[by_food["water_factor"].notna(), "waste"].sum())
    else:
        co2_covered_kg = water_covered_kg = 0.0

    return {
        "by_food": by_food,
        "gaps": gaps,
        "waste_kg": waste_total,
        "value_lost": value_lost,
        "co2e": co2_covered,
        "water_litres": water_covered,
        "co2_coverage_pct": fmt.safe_div(co2_covered_kg, waste_total) * 100,
        "water_coverage_pct": fmt.safe_div(water_covered_kg, waste_total) * 100,
    }


# ---------------------------------------------------------------- plate-washing water

def plate_washing_water(method: str, plates: int, flow_rate: float | None = None,
                        washing_time: float | None = None, bucket_size: float | None = None,
                        buckets: int | None = None, water_per_cycle: float | None = None,
                        cycles: int | None = None, total_water: float | None = None) -> tuple[float, str]:
    """
    Estimate plate-washing water for one washing method.

    Returns (litres, explanation). The formula used is always written out so
    the user can check exactly how the number was produced.
    """
    if method == "running_tap":
        # Flow rate (L/min) x washing time per plate (min) x number of plates.
        litres = float(flow_rate) * float(washing_time) * int(plates)
        explanation = (
            f"{flow_rate:g} L/min x {washing_time:g} min/plate x {fmt.format_number(int(plates))} plates "
            f"= {fmt.format_litres(litres)} (estimate)."
        )
    elif method == "bucket":
        litres = float(bucket_size) * int(buckets)
        explanation = (
            f"{bucket_size:g} L/bucket x {fmt.format_number(int(buckets))} buckets = {fmt.format_litres(litres)} (estimate)."
        )
    elif method == "dishwasher":
        litres = float(water_per_cycle) * int(cycles)
        explanation = (
            f"{water_per_cycle:g} L/cycle x {fmt.format_number(int(cycles))} cycles = {fmt.format_litres(litres)} (estimate). "
            "Use the water rating of your machine if known."
        )
    else:  # 'other'
        litres = float(total_water)
        explanation = f"Directly entered value: {fmt.format_litres(litres)} (estimate)."
    return litres, explanation


def daily_impact(start, end) -> pd.DataFrame:
    """
    Day-by-day impact values for trend charts: value lost, CO2e and food
    water footprint per date (dates without records are filled with 0).
    """
    daily = calculations.daily_aggregates(start, end)[["date"]].copy()
    waste = database.get_waste_range(start, end)
    if waste.empty:
        for column in ("value_lost", "co2e", "water_litres"):
            daily[column] = 0.0
        return daily

    factors = get_factors_df()[["id", "cost_per_kg", "co2_factor", "water_factor"]].rename(
        columns={"id": "food_id"}
    )
    merged = waste.merge(factors, on="food_id", how="left")
    merged["value_lost"] = merged["quantity"] * merged["cost_per_kg"].fillna(0.0)
    merged["co2e"] = merged["quantity"] * merged["co2_factor"]
    merged["water_litres"] = merged["quantity"] * merged["water_factor"]

    grouped = merged.groupby("date")[["value_lost", "co2e", "water_litres"]].sum().reset_index()
    result = daily.merge(grouped, on="date", how="left").fillna(0.0)
    return result


def factors_table_for_display(food_ids: list[int] | None = None) -> pd.DataFrame:
    """
    Factor table for the "Methodology & Sources" section: value, unit, source,
    reference, date and whether the value is estimated.
    """
    factors = get_factors_df()
    if food_ids is not None and len(food_ids) > 0:
        factors = factors[factors["id"].isin(food_ids)]
    display = factors[[
        "food_name", "co2_factor", "water_factor",
        "factor_source", "factor_reference", "factor_date", "is_estimated",
    ]].copy()
    display = display.rename(columns={
        "food_name": "Food",
        "co2_factor": "CO2e factor (kg CO2e/kg)",
        "water_factor": "Water factor (L/kg)",
        "factor_source": "Source",
        "factor_reference": "Reference",
        "factor_date": "Date/version",
        "is_estimated": "Estimated?",
    })
    display["Estimated?"] = display["Estimated?"].map({1: "Yes", 0: "No"})
    return display
