"""
FoodWaste360 - Impact Calculator page.

Visual impact dashboard (spec section 15): waste, estimated food value,
estimated CO2e and the two water metrics - kept separate and never combined:

  * Food water footprint  (waste x documented water factor)
  * Plate-washing water   (estimate from the washing calculator)

Includes the "Methodology & Sources" section with every factor, its value,
unit, source, reference and date.
"""

import streamlit as st

from services import calculations, impact_engine
from utils import charts, formatting as fmt, ui

start, end = ui.get_date_range()
ui.page_header("Impact Calculator", f"Estimated environmental and financial impact — {ui.range_label(start, end)}")

impact = impact_engine.impact_totals(start, end)
washing = calculations.washing_summary(start, end)

if impact["waste_kg"] <= 0:
    ui.empty_state(
        "No waste was recorded in the selected period, so there is no impact to estimate yet. "
        "Record waste or load the demo data from the Dashboard."
    )
    st.stop()

# ---------------------------------------------------------------- headline cards

ui.section("Wasted food and its estimated impact")
row = st.columns(3)
with row[0]:
    ui.metric_card("♻️ Food wasted", fmt.format_kg(impact["waste_kg"]), "Recorded quantities", "measured")
with row[1]:
    ui.metric_card("💰 Estimated food value", fmt.format_currency(impact["value_lost"]),
                   "Wasted kg × cost per kg", "estimated")
with row[2]:
    ui.metric_card("🌍 Estimated CO₂e", fmt.format_co2(impact["co2e"]),
                   f"Coverage: {fmt.format_percentage(impact['co2_coverage_pct'])} of recorded waste", "estimated")

row = st.columns(3)
with row[0]:
    ui.metric_card("💧 Estimated food water footprint", fmt.format_litres(impact["water_litres"]),
                   f"Coverage: {fmt.format_percentage(impact['water_coverage_pct'])} of recorded waste", "estimated")
with row[1]:
    ui.metric_card("🚰 Plate-washing water", fmt.format_litres(washing["total_litres"]),
                   "Separate metric — estimated from the washing calculator", "estimated")
with row[2]:
    total_recorded = calculations.period_totals(start, end)
    ui.metric_card("Waste rate", fmt.format_percentage(total_recorded["waste_pct"]),
                   "Total waste ÷ total prepared × 100", "calculated")

st.caption(
    "The food water footprint and the plate-washing water are intentionally shown separately — "
    "they measure different processes and are never combined."
)

if impact["gaps"]:
    missing_names = ", ".join(gap["food_name"] for gap in impact["gaps"])
    st.warning(
        f"These foods have recorded waste but no documented factor, so they are excluded from "
        f"the estimates above: {missing_names}. Add factors in the Food Database to improve coverage."
    )

# ---------------------------------------------------------------- charts

by_food = impact["by_food"]
ui.section("Impact by food")

col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        charts.bar_by_food(by_food, "value_lost", "Estimated food value lost per food", "₹", color=charts.RED),
        width="stretch",
    )
with col_b:
    st.plotly_chart(
        charts.bar_by_food(by_food, "co2e", "Estimated CO₂e per food", "kg CO₂e", color=charts.PURPLE),
        width="stretch",
    )

col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        charts.bar_by_food(by_food, "water_litres", "Estimated food water footprint per food", "L", color=charts.BLUE),
        width="stretch",
    )
with col_b:
    st.plotly_chart(
        charts.stacked_waste_types(  # share of waste that drives the estimates
            calculations.daily_aggregates(start, end),
            "Recorded waste driving the estimates (daily)",
        ),
        width="stretch",
    )

# ---------------------------------------------------------------- detail table

st.markdown("##### Detail table")
table = by_food[[
    "food_name", "waste", "cost_per_kg", "value_lost", "co2_factor", "co2e", "water_factor", "water_litres",
]].copy()
table.columns = [
    "Food", "Waste (kg)", "Cost (₹/kg)", "Value lost (₹)",
    "CO2e factor (kg/kg)", "CO2e (kg)", "Water factor (L/kg)", "Water (L)",
]
st.dataframe(
    table.style.format({
        "Waste (kg)": "{:,.2f}", "Cost (₹/kg)": "₹{:,.2f}", "Value lost (₹)": "₹{:,.0f}",
        "CO2e factor (kg/kg)": "{:,.2f}", "CO2e (kg)": "{:,.2f}",
        "Water factor (L/kg)": "{:,.1f}", "Water (L)": "{:,.0f}",
    }),
    width="stretch",
    hide_index=True,
)

# ---------------------------------------------------------------- methodology

st.divider()
with st.expander("📚 Methodology & Sources", expanded=False):
    st.markdown(impact_engine.METHODOLOGY_INTRO)

    st.markdown("##### Factors used in these estimates")
    st.dataframe(
        impact_engine.factors_table_for_display(by_food["food_id"].tolist()),
        width="stretch",
        hide_index=True,
    )

    st.markdown(
        """
        ##### What each factor means

        * **CO2e factor (kg CO2e / kg)** — the greenhouse gases (weighted over 100 years)
          associated with producing one kilogram of the food, as a global average.
        * **Water factor (L / kg)** — freshwater withdrawals associated with producing one
          kilogram of the food, as a global average.
        * Factors with "Estimated? = Yes" are proxies or composites (for example, roti uses
          the wheat factor; idli/dosa use a calculated rice + pulses composite). The exact
          method is described in each food's notes.

        ##### Important limitations

        * These values are **estimates, not measurements**. They multiply your recorded
          waste by published average factors.
        * The factors are global averages and do not reflect a specific supplier or region.
        * Financial values use the cost per kg your organization entered — update them in
          the Food Database for better accuracy.
        * You can edit any factor (administrator only); a source is always required.
        """
    )
