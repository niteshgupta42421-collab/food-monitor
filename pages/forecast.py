"""
MealFlow360 - Smart Forecast page.

Shows the expected demand for the next service day, computed ONLY from the
organisation's own recorded sales history. Every number here is:

  * labelled Estimated,
  * shown together with the history it is based on (days of sales data),
  * produced by a simple rule that can be explained in one sentence:

        expected = (same-weekday average blended with the recent daily
                    average) x (1 + safety buffer)

No sales history, no forecast - the app never invents a number from nothing.
"""

from datetime import date, timedelta

import streamlit as st

from database import database
from services import forecasting
from utils import formatting as fmt, ui

ui.page_header(
    "📈 Smart Forecast",
    "Expected demand for the next service day, based only on your own recorded "
    "sales history. Transparent, explainable, and always labelled Estimated.",
)

target = date.today() + timedelta(days=1)

col_a, col_b, col_c = st.columns([1, 1, 2])
with col_a:
    history_days = st.selectbox("History window", [7, 14, 30], index=1,
                                format_func=lambda d: f"Last {d} days", key="forecast_history")
with col_b:
    buffer_pct = st.slider("Safety buffer", min_value=0, max_value=25, value=10,
                           format="%d%%", key="forecast_buffer")
with col_c:
    st.caption(
        f"Planning for **{target.strftime('%A, %d %b %Y')}** (next service day) "
        f"· history window: {history_days} days · buffer: {buffer_pct}%"
    )

forecast = forecasting.demand_forecast(history_days=history_days, buffer_pct=float(buffer_pct),
                                       target_date=target)

if forecast.empty:
    ui.empty_state(
        "No sales history yet — a forecast needs recorded sales. Record sales on the "
        "Sales page (or load the demo restaurant on the Dashboard), then come back."
    )
    st.stop()

ui.section(f"Expected demand {ui.chip('estimated')}")

display = forecast.rename(columns={
    "food_name": "Food",
    "unit": "Unit",
    "avg_daily_units": "Avg sold / day",
    "same_weekday_avg": f"Same-weekday avg ({target.strftime('%a')})",
    "expected_units": "Expected demand",
    "expected_kg": "Expected (kg)",
    "days_with_sales": "Days of sales data",
})
st.dataframe(
    display[["Food", "Unit", "Avg sold / day", f"Same-weekday avg ({target.strftime('%a')})",
             "Expected demand", "Expected (kg)", "Days of sales data"]],
    hide_index=True, width="stretch",
    column_config={
        "Avg sold / day": st.column_config.NumberColumn(format="%.1f"),
        f"Same-weekday avg ({target.strftime('%a')})": st.column_config.NumberColumn(format="%.1f"),
        "Expected demand": st.column_config.NumberColumn(format="%.1f"),
        "Expected (kg)": st.column_config.NumberColumn(format="%.2f kg"),
    },
)

total_kg = float(forecast["expected_kg"].sum())
st.caption(
    f"Total expected production for {target.strftime('%d %b')}: **{fmt.format_kg(total_kg)}** "
    "(sum of the per-food expectations)."
)

with st.expander("📊 Sales history used by this forecast"):
    trend_food = st.selectbox("Food", list(forecast["food_name"]), key="forecast_trend_food")
    food_id = int(forecast[forecast["food_name"] == trend_food].iloc[0]["food_id"])
    history = database.get_sales_range(target - timedelta(days=history_days - 1), target)
    daily = (history[history["food_id"] == food_id]
             .groupby("date")["quantity_sold"].sum()
             .rename("units sold"))
    if daily.empty:
        st.caption("No recorded sales for this food in the window.")
    else:
        st.bar_chart(daily)

ui.method_note(
    "How the forecast works: for each food, the same-weekday average (from your history) "
    "is blended 50/50 with the recent daily average, then the safety buffer is added and the "
    "result is rounded UP to the nearest half portion. With little history the forecast leans "
    "on the recent average; with none, no forecast is shown. A forecast is an estimate, "
    "not a promise — the kitchen always stays in control."
)
