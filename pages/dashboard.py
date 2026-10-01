"""
FoodWaste360 - Dashboard page.

Shows the headline production, waste and impact numbers for the selected
reporting period, followed by interactive charts and summary tables.
"""

import streamlit as st

from database import database, demo_data
from services import calculations, impact_engine
from utils import charts, formatting as fmt, ui

start, end = ui.get_date_range()
ui.page_header("Dashboard", f"Reporting period: {ui.range_label(start, end)}")

# ---------------------------------------------------------------- empty state

if not database.has_records():
    ui.empty_state(
        "👋 Welcome to FoodWaste360. No records exist yet.<br>"
        "You can start entering daily production and waste, or load the built-in "
        "demo scenario (30 days of realistic hotel data) to explore every feature."
    )
    if st.button("Load Demo Hotel", type="primary"):
        with st.spinner("Generating demo dataset..."):
            summary = demo_data.load_demo_data()
        st.toast(
            f"Demo data loaded: {summary['days']} days "
            f"({summary['start']} → {summary['end']})."
        )
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- aggregates

totals = calculations.period_totals(start, end)
impact = impact_engine.impact_totals(start, end)
washing = calculations.washing_summary(start, end)
daily = calculations.daily_aggregates(start, end)
daily_impact = impact_engine.daily_impact(start, end)

if totals["days_with_data"] == 0:
    ui.empty_state(
        "No records were found for the selected reporting period. "
        "Pick a different period in the sidebar or add daily records."
    )
    st.stop()

# ---------------------------------------------------------------- cards: production

ui.section("Production")
row = st.columns(4)
with row[0]:
    ui.metric_card("Food prepared", fmt.format_kg(totals["prepared"]), "Measured across the period", "measured")
with row[1]:
    ui.metric_card("Food served", fmt.format_kg(totals["served"]), "Measured across the period", "measured")
with row[2]:
    ui.metric_card("Food consumed", fmt.format_kg(totals["consumed"]), "Measured across the period", "measured")
with row[3]:
    ui.metric_card("Food wasted", fmt.format_kg(totals["waste"]), "Total of all three waste categories", "measured")

# ---------------------------------------------------------------- food flow

ui.section("Food flow")
ui.food_flow(totals)

# ---------------------------------------------------------------- cards: waste

ui.section("Waste")
row = st.columns(4)
with row[0]:
    ui.metric_card("Kitchen waste", fmt.format_kg(totals["kitchen"]), "Preparation, spoilage, overproduction", "measured")
with row[1]:
    ui.metric_card("Serving waste", fmt.format_kg(totals["serving"]), "Left at the serving counter", "measured")
with row[2]:
    ui.metric_card("Plate waste", fmt.format_kg(totals["plate"]), "Left uneaten by customers", "measured")
with row[3]:
    ui.metric_card(
        "Waste rate",
        fmt.format_percentage(totals["waste_pct"]),
        "Total waste ÷ total prepared × 100",
        "calculated",
    )

# ---------------------------------------------------------------- cards: impact

ui.section("Impact (estimates)")
row = st.columns(4)
with row[0]:
    ui.metric_card(
        "Estimated food value lost",
        fmt.format_currency(impact["value_lost"]),
        "Wasted kg × cost per kg",
        "estimated",
    )
with row[1]:
    ui.metric_card(
        "Estimated CO₂e",
        fmt.format_co2(impact["co2e"]),
        f"Factor coverage: {fmt.format_percentage(impact['co2_coverage_pct'])} of recorded waste",
        "estimated",
    )
with row[2]:
    ui.metric_card(
        "Estimated food water footprint",
        fmt.format_litres(impact["water_litres"]),
        f"Factor coverage: {fmt.format_percentage(impact['water_coverage_pct'])} of recorded waste",
        "estimated",
    )
with row[3]:
    ui.metric_card(
        "Plate-washing water",
        fmt.format_litres(washing["total_litres"]),
        "Kept separate from the food water footprint",
        "estimated",
    )

if impact["gaps"]:
    missing_names = ", ".join(gap["food_name"] for gap in impact["gaps"])
    st.warning(
        f"Impact factors are missing for: {missing_names}. "
        "Their waste is excluded from the CO₂e / water estimates above. "
        "Add documented factors in the Food Database."
    )

# ---------------------------------------------------------------- charts

ui.section("Visualizations")

chart_row = st.columns(2)
with chart_row[0]:
    st.plotly_chart(
        charts.prepared_consumed_wasted(daily),
        width="stretch",
    )
with chart_row[1]:
    st.plotly_chart(
        charts.waste_type_donut({"kitchen": totals["kitchen"], "serving": totals["serving"], "plate": totals["plate"]}),
        width="stretch",
    )

chart_row = st.columns(2)
by_food = calculations.waste_by_food(start, end)
with chart_row[0]:
    st.plotly_chart(charts.waste_by_food(by_food), width="stretch")
with chart_row[1]:
    st.plotly_chart(charts.stacked_waste_types(daily), width="stretch")

tabs = st.tabs(["Waste trends", "Financial trend", "Environmental trends", "Tables"])

with tabs[0]:
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(
            charts.trend_lines(daily, {"waste": "Total waste (kg)"}, "Daily waste trend"),
            width="stretch",
        )
    with col_b:
        st.plotly_chart(
            charts.trend_lines(daily, {"waste_pct": "Waste rate (%)"}, "Waste rate trend", y_title="%"),
            width="stretch",
        )

with tabs[1]:
    st.plotly_chart(
        charts.trend_lines(
            daily_impact,
            {"value_lost": "Estimated value lost (₹)"},
            "Estimated financial loss trend",
            y_title="₹",
            colors=[charts.RED],
        ),
        width="stretch",
    )

with tabs[2]:
    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(
            charts.trend_lines(
                daily_impact, {"co2e": "Estimated CO₂e (kg)"}, "Estimated CO₂e trend",
                y_title="kg CO₂e", colors=[charts.PURPLE],
            ),
            width="stretch",
        )
    with col_b:
        st.plotly_chart(
            charts.trend_lines(
                daily_impact, {"water_litres": "Estimated water (L)"}, "Estimated food water footprint trend",
                y_title="litres", colors=[charts.BLUE],
            ),
            width="stretch",
        )

with tabs[3]:
    st.markdown("**Waste by food** (recorded quantities)")
    if by_food.empty:
        ui.empty_state("No waste was recorded for this period.")
    else:
        table = by_food[["food_name", "kitchen", "serving", "plate", "waste", "contribution_pct"]].copy()
        table.columns = ["Food", "Kitchen (kg)", "Serving (kg)", "Plate (kg)", "Total waste (kg)", "Share of waste (%)"]
        st.dataframe(
            table.style.format({
                "Kitchen (kg)": "{:,.2f}", "Serving (kg)": "{:,.2f}", "Plate (kg)": "{:,.2f}",
                "Total waste (kg)": "{:,.2f}", "Share of waste (%)": "{:.2f}%",
            }),
            width="stretch",
            hide_index=True,
        )

    st.markdown("**Daily overview**")
    overview = daily.copy()
    overview = overview.rename(columns={
        "date": "Date", "prepared": "Prepared (kg)", "served": "Served (kg)", "consumed": "Consumed (kg)",
        "waste": "Waste (kg)", "waste_pct": "Waste rate (%)",
    })
    st.dataframe(
        overview[["Date", "Prepared (kg)", "Served (kg)", "Consumed (kg)", "Waste (kg)", "Waste rate (%)"]]
        .style.format({
            "Prepared (kg)": "{:,.2f}", "Served (kg)": "{:,.2f}", "Consumed (kg)": "{:,.2f}",
            "Waste (kg)": "{:,.2f}", "Waste rate (%)": "{:.2f}%",
        }),
        width="stretch",
        hide_index=True,
    )

st.caption(
    "CO₂e, water and financial values are estimates based on documented factors and your "
    "recorded quantities — they are not measurements. See the Impact Calculator for sources."
)
