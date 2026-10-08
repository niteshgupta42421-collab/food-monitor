"""
MealFlow360 - Sales page.

Records every sale (date, time, food, quantity, price, order type) and shows
the resulting revenue, quantities and estimated profit for the selected
reporting period.

Conversion rule (documented in the Food Master): selling units are converted
to kilograms with the food's portion size, because cost and waste are tracked
in kilograms. Example: 180 plates x 250 g = 45 kg.
"""

from datetime import date, datetime

import streamlit as st

from database import database
from services import finance
from utils import formatting as fmt, ui

ORDER_TYPE_LABELS = {
    "dine-in": "Dine-in",
    "takeaway": "Takeaway",
    "delivery": "Delivery",
    "buffet": "Buffet",
    "other": "Other",
}

ui.page_header(
    "🧾 Sales",
    "Record what was sold. Remaining food, stock status and revenue are derived "
    "automatically - no double entry.",
)

# Flash message set before a rerun (delete actions) so it survives the rerun.
flash = st.session_state.pop("fw_flash", None)
if flash:
    st.success(flash)

foods_df = database.get_food_items_df()
active_foods = foods_df[foods_df["active"] == 1].reset_index(drop=True)

tab_record, tab_history = st.tabs(["✍️ Record a sale", "📚 Sales history"])

# ---------------------------------------------------------------- record a sale

with tab_record:
    if active_foods.empty:
        ui.empty_state(
            "No active food items. Add food items (with a selling price and portion size) "
            "in the <b>Food Master</b> first."
        )
    else:
        food_names = list(active_foods["food_name"])
        selected = st.selectbox("Food item", food_names, key="sales_food_select")
        meta = active_foods[active_foods["food_name"] == selected].iloc[0]

        col_date, col_time, col_note = st.columns([1, 1, 2])
        with col_date:
            sale_date = st.date_input("Sale date", value=date.today(), key="sales_date")
        with col_time:
            sale_time = st.time_input(
                "Sale time",
                value=datetime.now().replace(second=0, microsecond=0).time(),
                step=300,
                key="sales_time",
            )
        with col_note:
            st.caption(
                f"{selected}: 1 {meta['unit']} = {fmt.format_grams(meta['portion_size_g'])} "
                f"· selling price {fmt.format_currency(meta['selling_price'])}"
            )

        with st.form("sale_form", clear_on_submit=True):
            col_qty, col_price, col_type = st.columns(3)
            with col_qty:
                quantity = st.number_input(
                    f"Quantity ({meta['unit']})", min_value=0.0, value=1.0, step=0.5,
                    key=f"sales_qty_{selected}",
                )
            with col_price:
                unit_price = st.number_input(
                    "Unit price (₹)", min_value=0.0,
                    value=float(meta["selling_price"]), step=5.0,
                    key=f"sales_price_{selected}",
                )
            with col_type:
                order_type = st.selectbox(
                    "Order type", list(ORDER_TYPE_LABELS),
                    format_func=lambda key: ORDER_TYPE_LABELS[key],
                    key=f"sales_type_{selected}",
                )
            submitted = st.form_submit_button("Record sale", width="stretch")

        if submitted:
            if quantity <= 0:
                st.error("Please enter a quantity greater than zero.")
            else:
                kg = quantity * float(meta["portion_size_g"]) / 1000.0
                database.add_sale(
                    sale_date,
                    int(meta["id"]),
                    float(quantity),
                    float(unit_price),
                    order_type=order_type,
                    time=f"{sale_time.hour:02d}:{sale_time.minute:02d}",
                    user_id=(st.session_state.get("user") or {}).get("id"),
                )
                st.success(
                    f"Sale recorded: {fmt.format_number(quantity)} {meta['unit']} x "
                    f"{fmt.format_currency(unit_price)} = "
                    f"**{fmt.format_currency(quantity * unit_price)}** "
                    f"· sold ≈ {fmt.format_kg(kg)} of food."
                )

# ---------------------------------------------------------------- sales history

with tab_history:
    start, end = ui.get_date_range()
    st.caption(f"Reporting period: {ui.range_label(start, end)}")

    sales = database.get_sales_range(start, end)
    if sales.empty:
        ui.empty_state(
            "No sales recorded in this period. Record a sale in the first tab, "
            "or load the demo restaurant on the Dashboard."
        )
    else:
        summary = finance.sales_summary(sales)
        per_food = finance.per_food_sales(sales)
        top = per_food.iloc[0] if not per_food.empty else None

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            ui.metric_card("Revenue", fmt.format_currency(summary["revenue"]), kind="calculated")
        with col2:
            ui.metric_card("Items sold", fmt.format_number(summary["units_sold"]),
                           sub=f"{fmt.format_number(summary['entries'])} entries", kind="measured")
        with col3:
            ui.metric_card("Food sold", fmt.format_kg(summary["kg_sold"]),
                           sub="units x portion size", kind="calculated")
        with col4:
            ui.metric_card(
                "Estimated profit",
                fmt.format_currency(summary["profit"]),
                sub=(f"top seller: {top['food_name']}" if top is not None else ""),
                kind="calculated",
            )

        display = sales.copy()
        display["Est. kg"] = (display["quantity_sold"] * display["portion_size_g"].fillna(0) / 1000.0).round(2)
        display = display.rename(columns={
            "date": "Date", "time": "Time", "food_name": "Food",
            "quantity_sold": "Qty", "unit": "Unit", "unit_price": "Unit price (₹)",
            "order_type": "Order type", "total_amount": "Total (₹)",
        })
        st.dataframe(
            display[["Date", "Time", "Food", "Qty", "Unit", "Unit price (₹)",
                     "Order type", "Total (₹)", "Est. kg"]],
            width="stretch", hide_index=True,
            column_config={
                "Unit price (₹)": st.column_config.NumberColumn(format="₹%.2f"),
                "Total (₹)": st.column_config.NumberColumn(format="₹%.2f"),
                "Est. kg": st.column_config.NumberColumn(format="%.2f kg"),
            },
        )

        with st.expander("Delete an entry (mistakes)"):
            options = list(sales["id"])
            choice = st.selectbox(
                "Entry to delete",
                options,
                format_func=lambda i: (
                    lambda r: f"{r['date']} {r['time']} · {r['food_name']} · "
                              f"{fmt.format_number(r['quantity_sold'])} {r['unit']} · "
                              f"{fmt.format_currency(r['total_amount'])}"
                )(sales[sales["id"] == i].iloc[0]),
                key="sales_delete_select",
            )
            if st.button("Delete selected entry", key="sales_delete_button"):
                database.delete_sale(int(choice))
                st.session_state["fw_flash"] = "Sales entry deleted."
                st.rerun()

ui.method_note(
    "How selling units become kilograms: quantity sold x portion size (Food Master) "
    "= mass sold. 180 plates x 250 g = 45 kg. Cost and waste are tracked in kg, so "
    "this conversion is what keeps sales, inventory and waste on one scale."
)
