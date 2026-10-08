"""
MealFlow360 - Recommendation engine ("Waste Detective" + "Smart Recommendations").

Rules of this module (spec sections 16 and 18):
  * Every statement is computed from the recorded data - no invented causes.
  * Observations (what the data shows) are kept clearly separate from
    recommendations (what could be considered next).
  * Each recommendation explains WHY it appeared and which threshold it crossed.

The attention levels below are internal analysis thresholds used to decide when
to surface a recommendation. They are NOT scientific benchmarks.
"""

from services import calculations
from utils import formatting as fmt

# Internal attention levels (share of total waste in the selected period).
ATTENTION_LEVELS = {
    "food_share_high_pct": 20,        # one food >= 20% of total recorded waste
    "plate_share_high_pct": 50,       # plate waste >= 50% of total recorded waste
    "kitchen_share_high_pct": 30,     # kitchen waste >= 30% of total recorded waste
    "serving_share_high_pct": 25,     # serving waste >= 25% of total recorded waste
    "plate_waste_per_customer_g": 250,  # average leftover per customer >= 250 g
    "trend_change_points": 1.0,       # waste percentage move between half-periods (pct points)
    "repeat_pattern_min_days": 5,     # minimum days of data before pattern claims
    "repeat_pattern_share": 0.4,      # appears in top-3 waste foods on >= 40% of days
}


# ---------------------------------------------------------------- helpers

def _half_period_averages(daily):
    """Average waste percentage of the first and second half of the period."""
    recorded = daily[(daily["prepared"] > 0) | (daily["waste"] > 0)].reset_index(drop=True)
    if len(recorded) < ATTENTION_LEVELS["repeat_pattern_min_days"]:
        return None, None
    midpoint = len(recorded) // 2
    first_half = recorded.iloc[:midpoint]
    second_half = recorded.iloc[midpoint:]
    return float(first_half["waste_pct"].mean()), float(second_half["waste_pct"].mean())


def _top_food_third_days(start, end) -> dict:
    """Count how many days each food appeared among the top-3 waste foods."""
    from database import database

    waste = database.get_waste_range(start, end)
    if waste.empty:
        return {}
    per_day = waste.groupby(["date", "food_name"])["quantity"].sum().reset_index()
    counts = {}
    days = per_day["date"].nunique()
    for _, day_rows in per_day.groupby("date"):
        top_three = day_rows.nlargest(3, "quantity")
        for food_name in top_three["food_name"]:
            counts[food_name] = counts.get(food_name, 0) + 1
    return {"days": days, "counts": counts}


# ---------------------------------------------------------------- Waste Detective

def detect_patterns(start, end) -> list[dict]:
    """
    Analyze recorded data and return a list of observations, each with the
    supporting numbers. Returns an empty list when there is not enough data.
    """
    totals = calculations.period_totals(start, end)
    if totals["days_with_data"] == 0:
        return []

    by_food = calculations.waste_by_food(start, end)
    daily = calculations.daily_aggregates(start, end)
    patterns = []

    if not by_food.empty:
        top = by_food.iloc[0]
        patterns.append({
            "title": "Highest overall waste",
            "detail": (
                f"{top['food_name']} contributed the largest share of recorded food waste in this "
                f"period: {fmt.format_kg(top['waste'])} ({fmt.format_percentage(top['contribution_pct'])} of total waste)."
            ),
        })

        for waste_type, label in (("plate", "plate"), ("kitchen", "kitchen"), ("serving", "serving")):
            if by_food[waste_type].sum() > 0:
                top_type = by_food.sort_values(waste_type, ascending=False).iloc[0]
                patterns.append({
                    "title": f"Highest {label} waste",
                    "detail": (
                        f"{top_type['food_name']} recorded the most {label} waste: "
                        f"{fmt.format_kg(top_type[waste_type])}."
                    ),
                })

    # Highest waste day
    recorded_days = daily[(daily["prepared"] > 0) | (daily["waste"] > 0)]
    if not recorded_days.empty:
        worst = recorded_days.sort_values("waste", ascending=False).iloc[0]
        patterns.append({
            "title": "Highest waste day",
            "detail": (
                f"{worst['date']} recorded the highest total waste in this period: "
                f"{fmt.format_kg(worst['waste'])} (waste percentage {fmt.format_percentage(worst['waste_pct'])})."
            ),
        })

    # Waste-percentage trend (first half vs second half of the period)
    first_avg, second_avg = _half_period_averages(daily)
    if first_avg is not None and second_avg is not None:
        change = second_avg - first_avg
        if change >= ATTENTION_LEVELS["trend_change_points"]:
            patterns.append({
                "title": "Increasing waste trend",
                "detail": (
                    f"The average waste percentage rose from {fmt.format_percentage(first_avg)} (first half of the "
                    f"period) to {fmt.format_percentage(second_avg)} (second half)."
                ),
            })
        elif -change >= ATTENTION_LEVELS["trend_change_points"]:
            patterns.append({
                "title": "Decreasing waste trend",
                "detail": (
                    f"The average waste percentage moved from {fmt.format_percentage(first_avg)} (first half of the "
                    f"period) down to {fmt.format_percentage(second_avg)} (second half)."
                ),
            })

    # Repeated pattern: foods that keep appearing among the top-3 waste foods.
    third_days = _top_food_third_days(start, end)
    if third_days and third_days["days"] >= ATTENTION_LEVELS["repeat_pattern_min_days"]:
        days = third_days["days"]
        for food_name, count in sorted(third_days["counts"].items(), key=lambda item: -item[1]):
            share = count / days
            if share >= ATTENTION_LEVELS["repeat_pattern_share"]:
                patterns.append({
                    "title": "Repeated waste pattern",
                    "detail": (
                        f"{food_name} appeared among the top-3 waste foods on {count} of "
                        f"{days} recorded days in this period."
                    ),
                })

    return patterns


# ---------------------------------------------------------------- Smart Recommendations

def generate_recommendations(start, end) -> list[dict]:
    """
    Build data-driven recommendations. Each item contains:
      observation   - what the data shows (with numbers),
      recommendation- what could be considered,
      basis         - why this recommendation appeared (threshold crossed).
    """
    totals = calculations.period_totals(start, end)
    if totals["days_with_data"] == 0 or totals["waste"] <= 0:
        return []

    by_food = calculations.waste_by_food(start, end)
    daily = calculations.daily_aggregates(start, end)
    plate = calculations.plate_waste_summary(start, end)
    recommendations = []

    # 1. One food dominates the waste.
    if not by_food.empty:
        top = by_food.iloc[0]
        if top["contribution_pct"] >= ATTENTION_LEVELS["food_share_high_pct"]:
            recommendations.append({
                "observation": (
                    f"{top['food_name']} accounts for {fmt.format_percentage(top['contribution_pct'])} of total recorded "
                    f"waste in this period ({fmt.format_kg(top['waste'])})."
                ),
                "recommendation": (
                    f"Consider reviewing production quantities for {top['food_name']} for the next "
                    f"service period."
                ),
                "basis": (
                    f"Shown because one food contributes "
                    f"{ATTENTION_LEVELS['food_share_high_pct']}% or more of total waste."
                ),
            })

    # 2. Plate waste dominates.
    plate_share = totals["plate"] / totals["waste"] * 100
    if plate_share >= ATTENTION_LEVELS["plate_share_high_pct"]:
        recommendations.append({
            "observation": (
                f"Plate waste is {fmt.format_percentage(plate_share)} of all recorded waste in this period "
                f"({fmt.format_kg(totals['plate'])}, averaging {fmt.format_grams(plate['avg_per_customer_g'])} per customer)."
            ),
            "recommendation": (
                "Consider reviewing portion sizes and offering refill options where "
                "operationally appropriate."
            ),
            "basis": (
                f"Shown because plate waste is "
                f"{ATTENTION_LEVELS['plate_share_high_pct']}% or more of total recorded waste."
            ),
        })

    # 3. Kitchen waste share is high.
    kitchen_share = totals["kitchen"] / totals["waste"] * 100
    if kitchen_share >= ATTENTION_LEVELS["kitchen_share_high_pct"]:
        recommendations.append({
            "observation": (
                f"Kitchen waste represents {fmt.format_percentage(kitchen_share)} of recorded waste in this period "
                f"({fmt.format_kg(totals['kitchen'])})."
            ),
            "recommendation": "Review production planning and batch sizes.",
            "basis": (
                f"Shown because kitchen waste is "
                f"{ATTENTION_LEVELS['kitchen_share_high_pct']}% or more of total recorded waste."
            ),
        })

    # 4. Serving waste share is high.
    serving_share = totals["serving"] / totals["waste"] * 100
    if serving_share >= ATTENTION_LEVELS["serving_share_high_pct"]:
        recommendations.append({
            "observation": (
                f"Serving waste represents {fmt.format_percentage(serving_share)} of recorded waste in this period "
                f"({fmt.format_kg(totals['serving'])})."
            ),
            "recommendation": (
                "Consider moving to smaller counter batches with more frequent replenishment, "
                "where staffing allows."
            ),
            "basis": (
                f"Shown because serving waste is "
                f"{ATTENTION_LEVELS['serving_share_high_pct']}% or more of total recorded waste."
            ),
        })

    # 5. Rising waste-percentage trend.
    first_avg, second_avg = _half_period_averages(daily)
    if first_avg is not None and second_avg is not None:
        change = second_avg - first_avg
        if change >= ATTENTION_LEVELS["trend_change_points"]:
            recommendations.append({
                "observation": (
                    f"The waste percentage increased across the period: {fmt.format_percentage(first_avg)} in the "
                    f"first half versus {fmt.format_percentage(second_avg)} in the second half."
                ),
                "recommendation": (
                    "Consider reviewing recent production quantities, batch scheduling and service "
                    "timings for the affected days."
                ),
                "basis": (
                    f"Shown because the average waste percentage rose by "
                    f"{change:.2f} percentage points between the two halves of the period."
                ),
            })

    # 6. Average plate waste per customer is high.
    if plate["total_customers"] > 0:
        avg_g = plate["avg_per_customer_g"]
        if avg_g >= ATTENTION_LEVELS["plate_waste_per_customer_g"]:
            recommendations.append({
                "observation": (
                    f"Average recorded plate waste is {fmt.format_grams(avg_g)} per customer across "
                    f"{fmt.format_number(plate['total_customers'])} customers."
                ),
                "recommendation": (
                    "Consider reviewing portion sizes and offering refill options where "
                    "operationally appropriate."
                ),
                "basis": (
                    f"Shown because the average exceeds the app's default attention level of "
                    f"{ATTENTION_LEVELS['plate_waste_per_customer_g']} g per customer."
                ),
            })

    # 7. Data-quality reminder when factors are missing.
    from services import impact_engine

    _, gaps = impact_engine.attach_impacts(by_food)
    if gaps:
        names = ", ".join(gap["food_name"] for gap in gaps[:5])
        recommendations.append({
            "observation": (
                f"Impact factors are missing for {len(gaps)} food(s) with recorded waste "
                f"({names}). Their waste is excluded from CO2e and water estimates."
            ),
            "recommendation": (
                "Add documented factors (with source and reference) in the Food Database so the "
                "impact estimates cover all recorded waste."
            ),
            "basis": "Shown because the impact coverage check found waste without a matching factor.",
        })

    return recommendations
