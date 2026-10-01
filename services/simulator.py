"""
FoodWaste360 - What-If Simulator.

Every result produced here is a SIMULATED value: a scenario estimate built from
historical data, never a guaranteed saving. Each scenario returns:
  * a comparison table (Current vs Simulated vs Change),
  * the assumptions used, written out in plain language.

Core method: the simulator measures how waste behaved relative to activity in
the selected period (e.g. "waste was 12% of prepared quantity") and applies
that observed relationship to the changed numbers.
"""

import pandas as pd

from services import calculations, impact_engine
from utils import formatting as fmt


def _comparison_rows(rows: list[tuple[str, float | None, float | None]]) -> pd.DataFrame:
    """Build the standard Metric / Current / Simulated / Change table."""
    frame = pd.DataFrame(rows, columns=["Metric", "Current", "Simulated"])
    frame["Change"] = frame["Simulated"] - frame["Current"]
    return frame


def _impact_of_food_rows(food_rows: pd.DataFrame) -> dict:
    """
    Compute value / CO2e / water for a small per-food table
    (columns: food_id, food_name, waste).

    CO2e and water become NaN when some waste has no documented factor, so the
    UI can show "—" instead of a misleading zero.
    """
    enriched, gaps = impact_engine.attach_impacts(food_rows)
    if enriched.empty:
        return {"value": 0.0, "co2": float("nan"), "water": float("nan"), "missing": []}

    value = float(enriched["value_lost"].sum())
    has_waste = enriched["waste"] > 0
    co2_rows = enriched["co2_factor"].notna() | ~has_waste   # zero waste => zero impact
    water_rows = enriched["water_factor"].notna() | ~has_waste
    co2 = float(enriched.loc[co2_rows, "co2e"].sum()) if co2_rows.any() else float("nan")
    water = float(enriched.loc[water_rows, "water_litres"].sum()) if water_rows.any() else float("nan")
    missing = [gap["food_name"] for gap in gaps]
    return {"value": value, "co2": co2, "water": water, "missing": missing}


def _food_waste_row(start, end, food_id: int, food_name: str) -> pd.DataFrame:
    """One-row waste table for a single food (0 when no waste was recorded)."""
    by_food = calculations.waste_by_food(start, end)
    match = by_food[by_food["food_id"] == food_id]
    waste = float(match["waste"].iloc[0]) if not match.empty else 0.0
    return pd.DataFrame([{"food_id": food_id, "food_name": food_name, "waste": waste}])


# ---------------------------------------------------------------- scenarios

def scenario_production_change(food_id: int, pct_change: float, start, end) -> tuple[pd.DataFrame | None, dict]:
    """Increase or decrease the production quantity of one food by pct_change %."""
    production = calculations.production_by_food(start, end)
    match = production[production["food_id"] == food_id]
    if match.empty or float(match["prepared"].iloc[0]) <= 0:
        return None, {"ok": False, "error": "No production was recorded for this food in the selected period."}
    if pct_change < -100:
        return None, {"ok": False, "error": "A reduction below -100% is not possible."}

    prepared_current = float(match["prepared"].iloc[0])
    food_name = str(match["food_name"].iloc[0])
    waste_row = _food_waste_row(start, end, food_id, food_name)
    waste_current = float(waste_row["waste"].iloc[0])

    # Observed relationship from the organization's own recorded data.
    waste_ratio = fmt.safe_div(waste_current, prepared_current)
    prepared_new = prepared_current * (1 + pct_change / 100)
    # Assumption: the food keeps the same waste ratio at the new production level.
    waste_new = prepared_new * waste_ratio

    current_impact = _impact_of_food_rows(waste_row)
    simulated_row = waste_row.copy()
    simulated_row["waste"] = waste_new
    simulated_impact = _impact_of_food_rows(simulated_row)

    rows = _comparison_rows([
        ("Food prepared (kg)", prepared_current, prepared_new),
        ("Recorded waste (kg)", waste_current, waste_new),
        ("Estimated food value (INR)", current_impact["value"], simulated_impact["value"]),
        ("Estimated CO2e (kg CO2e)", current_impact["co2"], simulated_impact["co2"]),
        ("Estimated water footprint (L)", current_impact["water"], simulated_impact["water"]),
    ])
    meta = {
        "ok": True,
        "headline": (
            f"If {food_name} production changes by {pct_change:+.2f}%, estimated waste would move "
            f"from {fmt.format_kg(waste_current)} to {fmt.format_kg(waste_new)}."
        ),
        "assumptions": [
            f"Over the selected period, recorded waste for {food_name} was {fmt.format_percentage(waste_ratio * 100)} of "
            f"the prepared quantity ({fmt.format_kg(waste_current)} waste vs {fmt.format_kg(prepared_current)} prepared).",
            "The scenario assumes the same waste ratio applies to the changed production quantity.",
            "Impact values reuse the documented factors stored for this food.",
            "Scenario estimate based on historical data - not a guaranteed saving.",
        ],
    }
    return rows, meta


def scenario_plate_waste_change(pct_change: float, start, end) -> tuple[pd.DataFrame | None, dict]:
    """Change plate waste (per-customer leftovers) by pct_change %."""
    plate = calculations.plate_waste_summary(start, end)
    if plate["total_plate_waste"] <= 0:
        return None, {"ok": False, "error": "No plate waste was recorded in the selected period."}

    current_total = plate["total_plate_waste"]
    new_total = current_total * (1 + pct_change / 100)
    avg_current = plate["avg_per_customer_g"]
    avg_new = avg_current * (1 + pct_change / 100)

    by_food = plate["by_food"].copy()
    by_food["waste"] = by_food["quantity_wasted"]
    current_impact = _impact_of_food_rows(by_food)
    simulated_food = by_food.copy()
    simulated_food["waste"] = simulated_food["waste"] * (1 + pct_change / 100)
    simulated_impact = _impact_of_food_rows(simulated_food)

    rows = _comparison_rows([
        ("Plate waste (kg)", current_total, new_total),
        ("Average per customer (g)", avg_current, avg_new),
        ("Estimated food value (INR)", current_impact["value"], simulated_impact["value"]),
        ("Estimated CO2e (kg CO2e)", current_impact["co2"], simulated_impact["co2"]),
        ("Estimated water footprint (L)", current_impact["water"], simulated_impact["water"]),
    ])
    meta = {
        "ok": True,
        "headline": (
            f"If plate waste changes by {pct_change:+.2f}%, the period estimate moves from "
            f"{fmt.format_kg(current_total)} to {fmt.format_kg(new_total)}."
        ),
        "assumptions": [
            "Assumes the change applies evenly to every food's plate waste.",
            "Plate waste is driven by portion sizes and customer behavior; this input applies a direct "
            "percentage change to recorded plate waste rather than modeling those causes.",
            "Scenario estimate based on historical data - not a guaranteed saving.",
        ],
    }
    return rows, meta


def scenario_customers_change(pct_change: float, start, end) -> tuple[pd.DataFrame | None, dict]:
    """Change the number of customers served by pct_change %."""
    plate = calculations.plate_waste_summary(start, end)
    if plate["total_customers"] <= 0:
        return None, {"ok": False, "error": "No customer counts were recorded in the selected period."}

    customers_current = plate["total_customers"]
    customers_new = customers_current * (1 + pct_change / 100)
    # Assumption: per-customer leftover stays constant, so total plate waste
    # scales linearly with the number of customers.
    current_total = plate["total_plate_waste"]
    new_total = current_total * (customers_new / customers_current)

    by_food = plate["by_food"].copy()
    by_food["waste"] = by_food["quantity_wasted"]
    current_impact = _impact_of_food_rows(by_food)
    simulated_food = by_food.copy()
    simulated_food["waste"] = simulated_food["waste"] * (customers_new / customers_current)
    simulated_impact = _impact_of_food_rows(simulated_food)

    rows = _comparison_rows([
        ("Customers served", customers_current, customers_new),
        ("Plate waste (kg)", current_total, new_total),
        ("Average per customer (g)", plate["avg_per_customer_g"], plate["avg_per_customer_g"]),
        ("Estimated food value (INR)", current_impact["value"], simulated_impact["value"]),
        ("Estimated CO2e (kg CO2e)", current_impact["co2"], simulated_impact["co2"]),
        ("Estimated water footprint (L)", current_impact["water"], simulated_impact["water"]),
    ])
    meta = {
        "ok": True,
        "headline": (
            f"With {pct_change:+.2f}% customers, plate waste is estimated to move from "
            f"{fmt.format_kg(current_total)} to {fmt.format_kg(new_total)}."
        ),
        "assumptions": [
            "Assumes plate waste per customer stays constant, so total plate waste scales with the "
            "number of customers.",
            "This scenario covers plate waste only; production quantities and other waste categories "
            "would also need to change in reality.",
            "Scenario estimate based on historical data - not a guaranteed saving.",
        ],
    }
    return rows, meta


def scenario_target_waste_rate(target_pct: float, start, end) -> tuple[pd.DataFrame | None, dict]:
    """Set a target waste rate (% of prepared food) and compare with the current period."""
    totals = calculations.period_totals(start, end)
    if totals["prepared"] <= 0 or totals["waste"] <= 0:
        return None, {"ok": False, "error": "No production and waste data was recorded in the selected period."}
    if target_pct < 0 or target_pct > 100:
        return None, {"ok": False, "error": "The target waste rate must be between 0% and 100%."}

    prepared = totals["prepared"]
    waste_current = totals["waste"]
    waste_new = prepared * target_pct / 100
    scale = fmt.safe_div(waste_new, waste_current, default=1.0)

    by_food = calculations.waste_by_food(start, end)
    current_impact = _impact_of_food_rows(by_food)
    scaled_food = by_food.copy()
    scaled_food["waste"] = scaled_food["waste"] * scale
    simulated_impact = _impact_of_food_rows(scaled_food)

    rows = _comparison_rows([
        ("Total waste (kg)", waste_current, waste_new),
        ("Waste rate (%)", totals["waste_pct"], target_pct),
        ("Estimated food value (INR)", current_impact["value"], simulated_impact["value"]),
        ("Estimated CO2e (kg CO2e)", current_impact["co2"], simulated_impact["co2"]),
        ("Estimated water footprint (L)", current_impact["water"], simulated_impact["water"]),
    ])
    meta = {
        "ok": True,
        "headline": (
            f"A target waste rate of {fmt.format_percentage(target_pct)} would mean about {fmt.format_kg(waste_new)} of waste "
            f"versus {fmt.format_kg(waste_current)} recorded ({fmt.format_percentage(totals['waste_pct'])})."
        ),
        "assumptions": [
            "Assumes the current mix of kitchen/serving/plate waste is preserved and total waste "
            "equals the target percentage of prepared food.",
            f"Current period: prepared {fmt.format_kg(prepared)}, waste {fmt.format_kg(waste_current)}.",
            "Scenario estimate based on historical data - not a guaranteed saving.",
        ],
    }
    return rows, meta
