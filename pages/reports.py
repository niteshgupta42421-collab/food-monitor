"""
MealFlow360 - Reports page.

Generates a period summary report containing (spec section 20):
date range, the full accounting flow (prepared, available for service,
served, consumed, the three waste categories, waste percentage and the
accounting check), food-wise waste, estimated financial impact, estimated
CO2e, estimated food water footprint, plate-washing water, key observations
and recommendations.

Export: CSV download of the full report and of the food-wise table.
(PDF export is a deliberately marked future placeholder - not implemented.)
"""

import pandas as pd
import streamlit as st

from services import calculations, impact_engine, recommendation_engine
from utils import charts, formatting as fmt, ui

start, end = ui.get_date_range()
ui.page_header("Reports", f"Summary report — {ui.range_label(start, end)}")

totals = calculations.period_totals(start, end)
if totals["days_with_data"] == 0:
    ui.empty_state(
        "No records were found for the selected period, so there is no report to generate. "
        "Choose a different period in the sidebar or add data."
    )
    st.stop()

impact = impact_engine.impact_totals(start, end)
plate = calculations.plate_waste_summary(start, end)
washing = calculations.washing_summary(start, end)
# The impact engine enriches waste_by_food with value_lost / co2e / water_litres,
# which the food-wise table and its CSV export below rely on.
by_food = impact["by_food"]
patterns = recommendation_engine.detect_patterns(start, end)
recommendations = recommendation_engine.generate_recommendations(start, end)

# ---------------------------------------------------------------- summary cards

ui.section("Report summary")
row = st.columns(4)
with row[0]:
    ui.metric_card("Food prepared", fmt.format_kg(totals["prepared"]), "Measured", "measured")
with row[1]:
    ui.metric_card("Food available for service", fmt.format_kg(totals["available"]),
                   "Prepared − kitchen waste", "calculated")
with row[2]:
    ui.metric_card("Food served", fmt.format_kg(totals["served"]),
                   "Available − serving waste", "calculated")
with row[3]:
    ui.metric_card("Food consumed", fmt.format_kg(totals["consumed"]),
                   "Served − plate waste", "calculated")

row = st.columns(5)
with row[0]:
    ui.metric_card("Kitchen waste", fmt.format_kg(totals["kitchen"]), "Measured", "measured")
with row[1]:
    ui.metric_card("Serving waste", fmt.format_kg(totals["serving"]), "Measured", "measured")
with row[2]:
    ui.metric_card("Plate waste", fmt.format_kg(totals["plate"]),
                   f"{fmt.format_grams(plate['avg_per_customer_g'])} per customer", "measured")
with row[3]:
    ui.metric_card("Total waste", fmt.format_kg(totals["waste"]),
                   "Kitchen + serving + plate", "calculated")
with row[4]:
    ui.metric_card("Waste percentage", fmt.format_percentage(totals["waste_pct"]),
                   "Total waste ÷ prepared × 100", "calculated")

row = st.columns(4)
with row[0]:
    ui.metric_card("Customers served", fmt.format_number(plate["total_customers"]), "Measured", "measured")
with row[1]:
    ui.metric_card("Average plate waste per customer", fmt.format_grams(plate["avg_per_customer_g"]),
                   "Plate waste ÷ customers served", "calculated")
with row[2]:
    ui.metric_card("Days with data", str(totals["days_with_data"]), "Days with prepared or waste records", None)
with row[3]:
    ui.metric_card("Reporting period", ui.range_label(start, end), "Selected in the sidebar", None)

row = st.columns(4)
with row[0]:
    ui.metric_card("Estimated food value", fmt.format_currency(impact["value_lost"]), "Waste × cost per kg", "estimated")
with row[1]:
    ui.metric_card("Estimated CO₂e", fmt.format_co2(impact["co2e"]), "Waste × CO₂e factor", "estimated")
with row[2]:
    ui.metric_card("Estimated food water footprint", fmt.format_litres(impact["water_litres"]),
                   "Waste × water factor", "estimated")
with row[3]:
    ui.metric_card("Plate-washing water", fmt.format_litres(washing["total_litres"]),
                   "Separate from the food water footprint", "estimated")

# ---------------------------------------------------------------- food-wise table

ui.section("Food-wise waste")
if by_food.empty:
    ui.empty_state("No waste was recorded in this period.")
else:
    food_table = by_food[[
        "food_name", "prepared", "kitchen", "serving", "plate", "waste",
        "waste_pct_of_prepared", "contribution_pct", "value_lost", "co2e", "water_litres",
    ]].copy()
    food_table.columns = [
        "Food", "Prepared (kg)", "Kitchen (kg)", "Serving (kg)", "Plate (kg)", "Total waste (kg)",
        "Waste % of prepared", "Share of total waste (%)",
        "Estimated value lost (₹)", "Estimated CO2e (kg)", "Estimated water (L)",
    ]
    st.dataframe(
        food_table.style.format({
            "Prepared (kg)": "{:,.2f}", "Kitchen (kg)": "{:,.2f}", "Serving (kg)": "{:,.2f}",
            "Plate (kg)": "{:,.2f}", "Total waste (kg)": "{:,.2f}",
            "Waste % of prepared": "{:.2f}%", "Share of total waste (%)": "{:.2f}%",
            "Estimated value lost (₹)": "₹{:,.0f}", "Estimated CO2e (kg)": "{:,.2f}",
            "Estimated water (L)": "{:,.0f}",
        }),
        width="stretch",
        hide_index=True,
    )
    st.plotly_chart(charts.waste_by_food(by_food), width="stretch")

# ---------------------------------------------------------------- observations + recommendations

ui.section("Key observations")
if not patterns:
    st.markdown("_No notable patterns were detected in this period._")
else:
    for pattern in patterns:
        st.markdown(f"- **{pattern['title']}:** {pattern['detail']}")

ui.section("Recommendations")
if not recommendations:
    st.markdown("_No recommendations were triggered for this period._")
else:
    for item in recommendations:
        st.markdown(f"- **{item['recommendation']}**  \n  _{item['observation']} ({item['basis']})_")

# ---------------------------------------------------------------- exports

st.divider()
ui.section("Export")

# Full report as a flat section/metric/value CSV.
report_lines = [
    ("Report", "Reporting period", f"{start} to {end}"),
    ("Report", "Days with data", str(totals["days_with_data"])),
    ("Production", "Food prepared (kg)", f"{totals['prepared']:.1f}"),
    ("Production", "Food available for service (kg)", f"{totals['available']:.1f}"),
    ("Production", "Food served (kg)", f"{totals['served']:.1f}"),
    ("Production", "Food consumed (kg)", f"{totals['consumed']:.1f}"),
    ("Waste", "Kitchen waste (kg)", f"{totals['kitchen']:.1f}"),
    ("Waste", "Serving waste (kg)", f"{totals['serving']:.1f}"),
    ("Waste", "Plate waste (kg)", f"{totals['plate']:.1f}"),
    ("Waste", "Total waste (kg)", f"{totals['waste']:.1f}"),
    ("Waste", "Waste percentage (%)", f"{totals['waste_pct']:.2f}"),
    ("Accounting check", "Kitchen + serving + plate + consumed (kg)",
     f"{totals['kitchen'] + totals['serving'] + totals['plate'] + totals['consumed']:.1f}"),
    ("Accounting check", "Unaccounted / measurement difference (kg)", f"{totals['unaccounted']:.1f}"),
    ("Plate waste", "Customers served", str(plate["total_customers"])),
    ("Plate waste", "Average per customer (g)", f"{plate['avg_per_customer_g']:.1f}"),
    ("Impact (estimated)", "Food value lost (INR)", f"{impact['value_lost']:.0f}"),
    ("Impact (estimated)", "CO2e (kg)", f"{impact['co2e']:.1f}"),
    ("Impact (estimated)", "CO2e coverage (% of waste)", f"{impact['co2_coverage_pct']:.1f}"),
    ("Impact (estimated)", "Food water footprint (L)", f"{impact['water_litres']:.0f}"),
    ("Impact (estimated)", "Water factor coverage (% of waste)", f"{impact['water_coverage_pct']:.1f}"),
    ("Plate washing (estimated)", "Washing water (L)", f"{washing['total_litres']:.0f}"),
    ("Plate washing (estimated)", "Plates washed", str(washing["total_plates"])),
]
for pattern in patterns:
    report_lines.append(("Observation", pattern["title"], pattern["detail"]))
for item in recommendations:
    report_lines.append(("Recommendation", item["recommendation"], item["basis"]))

report_df = pd.DataFrame(report_lines, columns=["Section", "Metric", "Value"])

export_col, food_export_col, pdf_col = st.columns(3)
with export_col:
    st.download_button(
        "⬇️ Download full report (CSV)",
        data=report_df.to_csv(index=False).encode("utf-8"),
        file_name=f"mealflow360_report_{start}_{end}.csv",
        mime="text/csv",
        width="stretch",
    )
with food_export_col:
    if by_food.empty:
        st.button("⬇️ Download food-wise table (CSV)", disabled=True, width="stretch")
    else:
        st.download_button(
            "⬇️ Download food-wise table (CSV)",
            data=food_table.to_csv(index=False).encode("utf-8"),
            file_name=f"mealflow360_foodwise_{start}_{end}.csv",
            mime="text/csv",
            width="stretch",
        )
with pdf_col:
    st.button("📄 PDF export — planned, not yet implemented", disabled=True, width="stretch")

ui.method_note(
    "All environmental and financial values in this report are <b>estimates</b> produced from "
    "measured quantities and documented factors (see the Impact Calculator's Methodology & "
    "Sources). They are not exact measurements."
)
