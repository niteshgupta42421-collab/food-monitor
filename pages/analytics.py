"""
MealFlow360 - Historical Analytics page.

Interactive Plotly charts over the reporting period (spec section 19):
food prepared trend, waste trend, waste %, kitchen/serving/plate waste,
estimated financial impact, estimated CO2e and the estimated food water
footprint. Includes optional filters and a CSV export of the daily table.
"""

import streamlit as st

from services import calculations, impact_engine
from utils import charts, formatting as fmt, ui

start, end = ui.get_date_range()
ui.page_header("Analytics", f"Historical trends — {ui.range_label(start, end)}")

daily = calculations.daily_aggregates(start, end)
daily_impact = impact_engine.daily_impact(start, end)

if daily.empty or ((daily["prepared"] == 0) & (daily["waste"] == 0)).all():
    ui.empty_state(
        "No records were found for the selected period. Choose a different reporting period "
        "in the sidebar or add daily records."
    )
    st.stop()

# ---------------------------------------------------------------- filters

filter_row = st.columns([1, 1, 2])
with filter_row[0]:
    food_options = ["All foods"] + calculations.waste_by_food(start, end)["food_name"].tolist()
    selected_food = st.selectbox("Filter by food (waste charts)", food_options)
with filter_row[1]:
    type_options = ["All categories", "Kitchen waste", "Serving waste", "Plate waste"]
    selected_type = st.selectbox("Filter by waste category", type_options)

# Apply the waste-type filter to the daily waste columns shown in the charts.
W_TYPE_KEYS = {"All categories": ["kitchen", "serving", "plate"],
               "Kitchen waste": ["kitchen"], "Serving waste": ["serving"], "Plate waste": ["plate"]}
visible_types = W_TYPE_KEYS[selected_type]
filtered_daily = daily.copy()
filtered_daily["filtered_waste"] = filtered_daily[visible_types].sum(axis=1)

if selected_food != "All foods":
    # Food-filtered views come from the raw records for that food only.
    waste_df = calculations.waste_by_food(start, end)
    food_row = waste_df[waste_df["food_name"] == selected_food]
    if not food_row.empty:
        filter_note = (
            f"Showing per-food totals for **{selected_food}** where relevant. "
            f"Period total for this food: {fmt.format_kg(food_row['waste'].iloc[0])}."
        )
        st.info(filter_note)

# ---------------------------------------------------------------- headline + trends

ui.section("Trend overview")
row = st.columns(4)
with row[0]:
    ui.metric_card("Days with data", f"{int(((daily['prepared'] > 0) | (daily['waste'] > 0)).sum())}",
                   "Within the selected period", None)
with row[1]:
    ui.metric_card("Total prepared", fmt.format_kg(daily["prepared"].sum()), "Measured", "measured")
with row[2]:
    ui.metric_card("Total waste", fmt.format_kg(filtered_daily["filtered_waste"].sum()),
                   f"Category filter: {selected_type}", "calculated")
with row[3]:
    avg_rate = (filtered_daily["filtered_waste"].sum() / daily["prepared"].sum() * 100
                if daily["prepared"].sum() > 0 else 0.0)
    ui.metric_card("Average waste percentage", fmt.format_percentage(avg_rate), "Filtered waste ÷ prepared",
                   "calculated")

col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        charts.trend_lines(daily, {"prepared": "Prepared (kg)"}, "Food prepared trend"),
        width="stretch",
    )
with col_b:
    st.plotly_chart(
        charts.trend_lines(daily, {"waste": "Total waste (kg)"}, "Total waste trend"),
        width="stretch",
    )

col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        charts.trend_lines(daily, {"waste_pct": "Waste percentage (%)"}, "Waste percentage trend", y_title="%"),
        width="stretch",
    )
with col_b:
    st.plotly_chart(charts.stacked_waste_types(daily), width="stretch")

col_a, col_b = st.columns(2)
with col_a:
    st.plotly_chart(
        charts.trend_lines(
            daily,
            {"kitchen": "Kitchen waste", "serving": "Serving waste", "plate": "Plate waste"},
            "Waste categories over time (lines)",
            y_title="kg",
        ),
        width="stretch",
    )
with col_b:
    by_food = calculations.waste_by_food(start, end)
    if selected_food != "All foods":
        by_food = by_food[by_food["food_name"] == selected_food]
    st.plotly_chart(charts.waste_by_food(by_food, "Waste by food (period)"), width="stretch")

# ---------------------------------------------------------------- impact trends

ui.section("Estimated impact trends (estimates, not measurements)")
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.plotly_chart(
        charts.trend_lines(
            daily_impact, {"value_lost": "Value lost (₹)"},
            "Financial loss trend", y_title="₹", colors=[charts.RED],
        ),
        width="stretch",
    )
with col_b:
    st.plotly_chart(
        charts.trend_lines(
            daily_impact, {"co2e": "CO₂e (kg)"},
            "CO2e trend", y_title="kg CO2e", colors=[charts.PURPLE],
        ),
        width="stretch",
    )
with col_c:
    st.plotly_chart(
        charts.trend_lines(
            daily_impact, {"water_litres": "Water (L)"},
            "Food water footprint trend", y_title="L", colors=[charts.BLUE],
        ),
        width="stretch",
    )

# ---------------------------------------------------------------- daily table + export

st.markdown("##### Daily detail")
detail = daily.merge(daily_impact, on="date", how="left")
export_table = detail.rename(columns={
    "date": "Date", "prepared": "Prepared (kg)", "available": "Available (kg)",
    "served": "Served (kg)", "consumed": "Consumed (kg)",
    "kitchen": "Kitchen waste (kg)", "serving": "Serving waste (kg)", "plate": "Plate waste (kg)",
    "waste": "Total waste (kg)", "waste_pct": "Waste percentage (%)",
    "value_lost": "Estimated value lost (₹)", "co2e": "Estimated CO2e (kg)",
    "water_litres": "Estimated water footprint (L)",
})
st.dataframe(
    export_table.style.format({
        "Prepared (kg)": "{:,.2f}", "Available (kg)": "{:,.2f}",
        "Served (kg)": "{:,.2f}", "Consumed (kg)": "{:,.2f}",
        "Kitchen waste (kg)": "{:,.2f}", "Serving waste (kg)": "{:,.2f}", "Plate waste (kg)": "{:,.2f}",
        "Total waste (kg)": "{:,.2f}", "Waste percentage (%)": "{:.2f}%",
        "Estimated value lost (₹)": "₹{:,.0f}", "Estimated CO2e (kg)": "{:,.2f}",
        "Estimated water footprint (L)": "{:,.0f}",
    }),
    width="stretch",
    hide_index=True,
)

st.download_button(
    "⬇️ Download daily table as CSV",
    data=export_table.to_csv(index=False).encode("utf-8"),
    file_name=f"mealflow360_analytics_{start}_{end}.csv",
    mime="text/csv",
)

st.caption(
    "Prepared and waste quantities are measured values. Available for service, served and consumed "
    "are derived from prepared minus the recorded wastes (kitchen / serving / plate). Waste "
    "percentage, averages and the financial / environmental columns are calculated or estimated "
    "from those measurements."
)
