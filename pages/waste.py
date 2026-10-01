"""
FoodWaste360 - Waste Tracking page.

Staff record kitchen waste (overproduction, spoilage, ...) and serving waste
(left at the counter). Plate waste is recorded on the Plate Waste page so the
customer count is captured together with it.

A live warning (with confirmation) appears when recorded waste for a food
would exceed what was prepared that day.
"""

from datetime import date

import streamlit as st

from database import database
from services import calculations
from utils import charts, formatting as fmt, ui, validation

ui.page_header(
    "Waste Tracking",
    "Record kitchen and serving waste. Plate waste is entered on the Plate Waste page.",
)

foods = database.get_food_items_df()
if foods.empty:
    ui.empty_state("No food items exist yet. Add foods in the Food Database first.")
    st.stop()

food_id_by_name = dict(zip(foods["food_name"], foods["id"]))

WASTE_TYPE_OPTIONS = {
    "Kitchen waste": "kitchen",
    "Serving waste": "serving",
}
KITCHEN_REASONS = ["Overproduction", "Preparation waste", "Spoilage", "Burnt food", "Expired food", "Other"]
SERVING_REASONS = ["Counter leftover", "Held too long", "Overproduction", "Other"]

left, right = st.columns([1, 1.3])

# ---------------------------------------------------------------- entry form

with left:
    st.markdown("##### New waste entry")
    entry_date = st.date_input("Date", value=date.today(), max_value=date.today())
    food_name = st.selectbox("Food item", foods["food_name"].tolist())
    waste_type_label = st.radio("Waste category", list(WASTE_TYPE_OPTIONS.keys()), horizontal=True)
    waste_type = WASTE_TYPE_OPTIONS[waste_type_label]
    quantity = st.number_input("Quantity wasted (kg)", min_value=0.0, step=1.0, format="%.1f")

    reason_options = KITCHEN_REASONS if waste_type == "kitchen" else SERVING_REASONS
    reason = st.selectbox("Reason", reason_options)
    note = st.text_input("Note (optional)")

    # Live check against the prepared quantity for that food + day.
    warning = None
    food_id = food_id_by_name[food_name]
    production_day = database.get_production_day(entry_date)
    if not production_day.empty:
        match = production_day[production_day["food_id"] == food_id]
        prepared_today = float(match["quantity_prepared"].iloc[0]) if not match.empty else 0.0
        already_wasted = database.get_food_waste_on_date(food_id, entry_date)
        if quantity > 0:
            warning = validation.waste_exceeds_prepared_warning(
                already_wasted + quantity, prepared_today, food_name
            )
    if warning:
        st.warning(warning)

    confirmed = st.checkbox("Save anyway") if warning else True

    if st.button("💾 Save waste entry", type="primary", disabled=not confirmed):
        error = validation.validate_positive(quantity, "Quantity wasted")
        if error:
            st.error(error)
        else:
            full_reason = f"{reason} — {note}" if note.strip() else reason
            database.add_waste_record(entry_date, food_id, waste_type, quantity, full_reason)
            st.toast(f"Recorded {fmt.format_kg(quantity)} of {waste_type_label.lower()} for {food_name}.")
            st.rerun()

# ---------------------------------------------------------------- day view

with right:
    st.markdown(f"##### Records for {entry_date}")
    day_records = database.get_waste_day(entry_date)
    if day_records.empty:
        ui.empty_state("No waste has been recorded for this date yet.")
    else:
        display = day_records[["id", "food_name", "waste_type", "quantity", "reason"]].copy()
        display.columns = ["ID", "Food", "Category", "Quantity (kg)", "Reason"]
        display["Category"] = display["Category"].str.capitalize()
        st.dataframe(
            display.style.format({"Quantity (kg)": "{:,.2f}"}),
            width="stretch",
            hide_index=True,
        )
        st.plotly_chart(
            charts.waste_type_donut(
                {
                    "kitchen": float(day_records.loc[day_records["waste_type"] == "kitchen", "quantity"].sum()),
                    "serving": float(day_records.loc[day_records["waste_type"] == "serving", "quantity"].sum()),
                    "plate": float(day_records.loc[day_records["waste_type"] == "plate", "quantity"].sum()),
                },
                f"Waste recorded on {entry_date}",
            ),
            width="stretch",
        )

        delete_id = st.selectbox(
            "Delete an entry by ID",
            day_records["id"].tolist(),
            format_func=lambda record_id: (
                f"#{record_id} — "
                + " • ".join(day_records.loc[day_records['id'] == record_id, 'food_name'].astype(str))
            ),
        )
        if st.button("🗑️ Delete selected entry"):
            database.delete_waste_record(int(delete_id))
            st.toast(f"Deleted waste entry #{delete_id}.")
            st.rerun()

# ---------------------------------------------------------------- period summary

start, end = ui.get_date_range()
with st.expander(f"📊 Waste overview for the reporting period ({ui.range_label(start, end)})", expanded=False):
    by_food = calculations.waste_by_food(start, end)
    type_totals = calculations.waste_totals_by_type(start, end)

    cards = st.columns(4)
    with cards[0]:
        ui.metric_card("Kitchen waste", fmt.format_kg(type_totals["kitchen"]), "In the selected period", "measured")
    with cards[1]:
        ui.metric_card("Serving waste", fmt.format_kg(type_totals["serving"]), "In the selected period", "measured")
    with cards[2]:
        ui.metric_card("Plate waste", fmt.format_kg(type_totals["plate"]), "In the selected period", "measured")
    with cards[3]:
        ui.metric_card("Total waste", fmt.format_kg(type_totals["total"]), "All categories", "measured")

    if by_food.empty:
        ui.empty_state("No waste records in this reporting period.")
    else:
        charts_col, table_col = st.columns(2)
        with charts_col:
            st.plotly_chart(charts.waste_by_food(by_food, "Waste by food (period)"), width="stretch")
        with table_col:
            table = by_food[["food_name", "kitchen", "serving", "plate", "waste", "contribution_pct"]].copy()
            table.columns = ["Food", "Kitchen (kg)", "Serving (kg)", "Plate (kg)", "Total (kg)", "Share (%)"]
            st.dataframe(
                table.style.format({
                    "Kitchen (kg)": "{:,.2f}", "Serving (kg)": "{:,.2f}", "Plate (kg)": "{:,.2f}",
                    "Total (kg)": "{:,.2f}", "Share (%)": "{:.2f}%",
                }),
                width="stretch",
                hide_index=True,
            )

ui.method_note(
    "Waste quantities are <b>measured</b> values entered by staff. Revenue and environmental "
    "values derived from them are <b>estimated</b> on the Impact Calculator page."
)
