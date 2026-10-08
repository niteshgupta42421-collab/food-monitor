"""
MealFlow360 - Dashboard page.

Headline numbers for the selected reporting period: revenue and sales, the
production / waste flow, financial and environmental impact - plus a live
alert strip for today's stock.
"""

from datetime import date

import streamlit as st

from database import database, demo_data
from services import accounting, calculations, finance, impact_engine
from services import stock as stock_service
from utils import charts, formatting as fmt, ui

start, end = ui.get_date_range()
ui.page_header("Dashboard", f"Reporting period: {ui.range_label(start, end)}")

# ---------------------------------------------------------------- empty state

if not database.has_records():
    ui.empty_state(
        "👋 Welcome to MealFlow360. No records exist yet.<br>"
        "Start entering production and sales, or load the built-in "
        "<b>The Urban Thali</b> demo (30 days of realistic restaurant data) to explore every feature."
    )
    if st.button("🍛 Load The Urban Thali demo", type="primary"):
        with st.spinner("Generating The Urban Thali demo dataset..."):
            summary = demo_data.load_demo_data()
        st.toast(
            f"Loaded {summary['days']} days ({summary['start']} → {summary['end']}): "
            f"{summary['sales_rows']} sales rows."
        )
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- aggregates

totals = calculations.period_totals(start, end)
impact = impact_engine.impact_totals(start, end)
washing = calculations.washing_summary(start, end)
daily = calculations.daily_aggregates(start, end)
daily_impact = impact_engine.daily_impact(start, end)
sales = database.get_sales_range(start, end)

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
    ui.metric_card("Available for service", fmt.format_kg(totals["available"]),
                   "Prepared − kitchen waste", "calculated")
with row[2]:
    ui.metric_card("Food served", fmt.format_kg(totals["served"]),
                   "Available − serving waste", "calculated")
with row[3]:
    ui.metric_card("Food consumed", fmt.format_kg(totals["consumed"]),
                   "Served − plate waste", "calculated")

# ---------------------------------------------------------------- food flow

ui.section("Food flow")
ui.food_flow(totals)

flow_issues = accounting.flow_issues(daily)
if not flow_issues.empty:
    st.warning(
        f"On {len(flow_issues)} day(s) in this period the recorded waste is higher than the prepared "
        "food, so a flow step falls below zero. Please review those entries on the Waste Tracking "
        "and Plate Waste pages."
    )

# ---------------------------------------------------------------- cards: sales

ui.section("Sales & revenue")
if sales.empty:
    st.caption(
        "No sales recorded in this period yet. Record sales on the Sales page — revenue, "
        "sell-through and remaining food appear here automatically."
    )
else:
    summary = finance.sales_summary(sales)
    sell_through = (summary["kg_sold"] / totals["available"] * 100.0) if totals["available"] > 0 else 0.0
    row = st.columns(4)
    with row[0]:
        ui.metric_card("Revenue", fmt.format_currency(summary["revenue"]),
                       f"{fmt.format_number(summary['entries'])} recorded sales", "calculated")
    with row[1]:
        ui.metric_card("Food sold", fmt.format_kg(summary["kg_sold"]),
                       f"{fmt.format_number(summary['units_sold'])} selling units", "calculated")
    with row[2]:
        ui.metric_card("Estimated ingredient cost", fmt.format_currency(summary["cost"]),
                       "kg sold × cost per kg", "estimated")
    with row[3]:
        ui.metric_card("Estimated profit", fmt.format_currency(summary["profit"]),
                       f"Sell-through {fmt.format_percentage(sell_through)} of available food", "estimated")

    per_food = finance.per_food_sales(sales)
    with st.expander("🏆 Top sellers in this period"):
        top = per_food.head(8).rename(columns={
            "food_name": "Food", "unit": "Unit", "units_sold": "Units sold",
            "kg_sold": "Sold (kg)", "revenue": "Revenue (₹)", "cost": "Cost (₹)",
            "profit": "Profit (₹)",
        })
        st.dataframe(
            top[["Food", "Unit", "Units sold", "Sold (kg)", "Revenue (₹)", "Cost (₹)",
                 "Profit (₹)"]].style.format({
                     "Units sold": "{:,.0f}", "Sold (kg)": "{:,.2f}",
                     "Revenue (₹)": "₹{:,.2f}", "Cost (₹)": "₹{:,.2f}", "Profit (₹)": "₹{:,.2f}",
                 }),
            width="stretch", hide_index=True,
        )

# ---------------------------------------------------------------- today's live stock

today_frame = stock_service.day_stock_frame(date.today())
today_frame = today_frame[today_frame["production_mode"] != "made_to_order"]
if not today_frame.empty:
    remaining_now = float(today_frame["remaining_kg"].clip(lower=0).sum())
    out_names = list(today_frame[today_frame["status"] == stock_service.STATUS_OUT]["food_name"])
    low_names = list(today_frame[today_frame["status"] == stock_service.STATUS_LOW]["food_name"])
    line = (f"**Live stock ({date.today().strftime('%d %b')}):** "
            f"{fmt.format_kg(remaining_now)} remaining after sales")
    if out_names:
        line += " · 🔴 out of stock: " + ", ".join(out_names[:4]) + ("…" if len(out_names) > 4 else "")
    if low_names:
        line += " · 🟡 low: " + ", ".join(low_names[:4]) + ("…" if len(low_names) > 4 else "")
    if out_names or low_names:
        st.warning(line + " — open the Kitchen Control Center for actions.")
    else:
        st.info(line + " · no stock alerts.")

# ---------------------------------------------------------------- cards: waste

ui.section("Waste")
row = st.columns(5)
with row[0]:
    ui.metric_card("Kitchen waste", fmt.format_kg(totals["kitchen"]), "Preparation, spoilage, overproduction", "measured")
with row[1]:
    ui.metric_card("Serving waste", fmt.format_kg(totals["serving"]), "Left at the serving counter", "measured")
with row[2]:
    ui.metric_card("Plate waste", fmt.format_kg(totals["plate"]), "Left uneaten by customers", "measured")
with row[3]:
    ui.metric_card("Total waste", fmt.format_kg(totals["waste"]), "Kitchen + serving + plate", "calculated")
with row[4]:
    ui.metric_card(
        "Waste percentage",
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
            charts.trend_lines(daily, {"waste_pct": "Waste percentage (%)"}, "Waste percentage trend", y_title="%"),
            width="stretch",
        )

with tabs[1]:
    if not sales.empty:
        sales_daily = finance.add_kg_column(sales)
        sales_daily["cost_amount"] = sales_daily["kg_sold"] * sales_daily["cost_per_kg"].fillna(0)
        sales_daily = sales_daily.groupby("date", as_index=False).agg(
            revenue=("total_amount", "sum"), cost=("cost_amount", "sum"))
        sales_daily["profit"] = sales_daily["revenue"] - sales_daily["cost"]
        st.plotly_chart(
            charts.trend_lines(
                sales_daily,
                {"revenue": "Revenue (₹)", "profit": "Estimated profit (₹)"},
                "Daily revenue & estimated profit",
                y_title="₹",
            ),
            width="stretch",
        )
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
        "date": "Date", "prepared": "Prepared (kg)", "available": "Available (kg)",
        "served": "Served (kg)", "consumed": "Consumed (kg)",
        "waste": "Total waste (kg)", "waste_pct": "Waste percentage (%)",
    })
    st.dataframe(
        overview[["Date", "Prepared (kg)", "Available (kg)", "Served (kg)", "Consumed (kg)",
                  "Total waste (kg)", "Waste percentage (%)"]]
        .style.format({
            "Prepared (kg)": "{:,.2f}", "Available (kg)": "{:,.2f}", "Served (kg)": "{:,.2f}",
            "Consumed (kg)": "{:,.2f}", "Total waste (kg)": "{:,.2f}", "Waste percentage (%)": "{:.2f}%",
        }),
        width="stretch",
        hide_index=True,
    )

st.caption(
    "CO₂e, water and financial values are estimates based on documented factors and your "
    "recorded quantities — they are not measurements. See the Impact Calculator for sources."
)
