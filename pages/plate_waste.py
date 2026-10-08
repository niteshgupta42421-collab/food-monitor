"""
MealFlow360 - Plate Waste page.

Tab 1 - Plate Waste Analysis: customers served, per-food leftovers, the
average plate waste per customer, and day/period summaries.

Tab 2 - Plate-Washing Water: an estimate calculator for the water used to
wash plates, with several washing methods. This water is kept separate from
the food water footprint everywhere in the app.
"""

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from database import database
from services import calculations, impact_engine
from utils import charts, formatting as fmt, ui, validation

ui.page_header(
    "Plate Waste",
    "Analyze customer plate waste and estimate the water used to wash plates.",
)

foods = database.get_food_items_df()
if foods.empty:
    ui.empty_state("No food items exist yet. Add foods in the Food Database first.")
    st.stop()

food_id_by_name = dict(zip(foods["food_name"], foods["id"]))

tab_plate, tab_washing = st.tabs(["🍽️ Plate Waste Analysis", "🚰 Plate-Washing Water"])

# ================================================================ TAB 1: plate waste

with tab_plate:
    left, right = st.columns([1, 1.3])

    with left:
        st.markdown("##### Daily plate-waste sheet")
        plate_date = st.date_input("Date", value=date.today(), max_value=date.today(), key="plate_date")

        saved_day = database.get_plate_waste_day(plate_date)
        customers_default = int(saved_day["customers_served"].iloc[0]) if not saved_day.empty else 0
        customers = st.number_input(
            "Number of customers served", min_value=0, step=50, value=customers_default,
            help="Total customers served on this date (used for the per-customer average).",
        )

        saved_by_food = dict(zip(saved_day["food_name"], saved_day["quantity_wasted"])) if not saved_day.empty else {}
        plate_editor_df = pd.DataFrame([
            {"Food": food["food_name"], "Plate waste (kg)": float(saved_by_food.get(food["food_name"], 0.0))}
            for _, food in foods.iterrows()
        ])

        st.caption("Enter the leftover quantity per food (0 where nothing was left).")
        edited_plate = st.data_editor(
            plate_editor_df,
            hide_index=True,
            width="stretch",
            disabled=["Food"],
            column_config={
                "Plate waste (kg)": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f"),
            },
            key=f"plate_editor_{plate_date}",
        )

        rows = [(row["Food"], row["Plate waste (kg)"]) for _, row in edited_plate.iterrows()]
        total_plate_day = float(edited_plate["Plate waste (kg)"].sum())
        avg_g_day = (total_plate_day / customers * 1000) if customers > 0 else 0.0

        # Warn (with confirmation) when plate waste exceeds the prepared quantity.
        save_confirmed = True
        production_day = database.get_production_day(plate_date)
        if not production_day.empty and total_plate_day > 0:
            prepared_total = float(production_day["quantity_prepared"].sum())
            if total_plate_day > prepared_total:
                st.warning(
                    f"Plate waste ({fmt.format_kg(total_plate_day)}) is higher than the total prepared "
                    f"quantity for {plate_date} ({fmt.format_kg(prepared_total)}). Please double-check."
                )
                save_confirmed = st.checkbox("I have checked the plate-waste numbers.")

        if st.button("💾 Save plate-waste sheet", type="primary", disabled=not save_confirmed, key="save_plate"):
            error = validation.validate_plate_waste_input(customers, rows)
            if error:
                st.error(error)
            else:
                saved_rows = [(food_id_by_name[name], qty) for name, qty in rows]
                database.replace_plate_waste_day(plate_date, customers, saved_rows)
                st.toast(f"Saved plate-waste sheet for {plate_date}.")
                st.rerun()

    with right:
        st.markdown(f"##### Summary for {plate_date}")
        summary_cards = st.columns(3)
        with summary_cards[0]:
            ui.metric_card("Plate waste", fmt.format_kg(total_plate_day), "From the sheet on the left", "measured")
        with summary_cards[1]:
            ui.metric_card("Customers served", fmt.format_number(customers), "Entered for this date", "measured")
        with summary_cards[2]:
            ui.metric_card("Average per customer", fmt.format_grams(avg_g_day), "Plate waste ÷ customers", "calculated")

        if customers > 0 and total_plate_day > 0:
            st.info(
                f"Average estimated plate waste: **{fmt.format_grams(avg_g_day)}/customer** "
                f"({fmt.format_kg(total_plate_day)} ÷ {fmt.format_number(customers)} customers)."
            )
        elif total_plate_day > 0:
            st.warning("Enter the number of customers served to calculate the per-customer average.")

        if total_plate_day > 0 and not edited_plate.empty:
            # The chart builder expects "food_name" + "waste" columns, so rename
            # the friendly editor column labels here.
            day_food = edited_plate[edited_plate["Plate waste (kg)"] > 0].rename(
                columns={"Food": "food_name", "Plate waste (kg)": "waste"}
            )
            if not day_food.empty:
                st.plotly_chart(charts.waste_by_food(day_food, "Plate waste by food (this date)"), width="stretch")

    # Period overview -----------------------------------------------------
    start, end = ui.get_date_range()
    st.divider()
    st.markdown(f"##### Plate waste over the reporting period ({ui.range_label(start, end)})")

    plate_period = calculations.plate_waste_summary(start, end)
    period_cards = st.columns(4)
    with period_cards[0]:
        ui.metric_card("Total plate waste", fmt.format_kg(plate_period["total_plate_waste"]),
                       f"{plate_period['days_recorded']} day(s) recorded", "measured")
    with period_cards[1]:
        ui.metric_card("Customers served", fmt.format_number(plate_period["total_customers"]),
                       "Sum of daily counts", "measured")
    with period_cards[2]:
        ui.metric_card("Average per customer", fmt.format_grams(plate_period["avg_per_customer_g"]),
                       "Total plate waste ÷ total customers", "calculated")
    with period_cards[3]:
        if plate_period["total_plate_waste"] > 0:
            top_food = plate_period["by_food"].iloc[0]
            ui.metric_card("Top plate-waste food", top_food["food_name"],
                           f"{fmt.format_kg(top_food['quantity_wasted'])} in the period", "measured")
        else:
            ui.metric_card("Top plate-waste food", "—", "No plate waste recorded", None)

    if plate_period["by_food"].empty:
        ui.empty_state("No plate waste was recorded in the reporting period.")
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            st.plotly_chart(
                charts.waste_by_food(
                    plate_period["by_food"].rename(columns={"quantity_wasted": "waste"}),
                    "Plate waste by food (period)",
                ),
                width="stretch",
            )
        with col_b:
            customer_days = database.get_customers_by_day(start, end)
            if not customer_days.empty:
                daily_plate = database.get_plate_waste_range(start, end)
                daily_agg = daily_plate.groupby("date")["quantity_wasted"].sum().reset_index()
                daily_agg = daily_agg.merge(customer_days, on="date", how="left")
                daily_agg["avg_g_per_customer"] = (
                    daily_agg["quantity_wasted"] / daily_agg["customers_served"] * 1000
                ).where(daily_agg["customers_served"] > 0, 0.0)
                st.plotly_chart(
                    charts.trend_lines(
                        daily_agg, {"avg_g_per_customer": "g per customer"},
                        "Average plate waste per customer", y_title="g", colors=[charts.RED],
                    ),
                    width="stretch",
                )

# ================================================================ TAB 2: washing water

with tab_washing:
    st.markdown("##### Estimate the water used to wash plates")
    st.caption(
        "Choose your washing method and enter your own measurements — the app does not assume "
        "a universal water-consumption value."
    )

    METHOD_LABELS = {
        "Running tap": "running_tap",
        "Bucket method": "bucket",
        "Dishwasher": "dishwasher",
        "Other / total known": "other",
    }

    wash_date = st.date_input("Date", value=date.today(), max_value=date.today(), key="wash_date")
    method_label = st.radio("Washing method", list(METHOD_LABELS.keys()), horizontal=True)
    method = METHOD_LABELS[method_label]

    # Method-specific inputs ------------------------------------------------
    flow_rate = washing_time = bucket_size = water_per_cycle = total_water = None
    buckets = cycles = 0
    plates = 0
    details = ""

    if method == "running_tap":
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            flow_rate = st.number_input("Water flow rate (litres/minute)", min_value=0.0, step=0.5,
                                        value=6.0, format="%.1f")
        with col_b:
            seconds_per_plate = st.number_input("Washing time per plate (seconds)", min_value=0.0, step=5.0,
                                                value=15.0, format="%.0f")
            washing_time = seconds_per_plate / 60.0  # convert to minutes for the formula
        with col_c:
            plates = st.number_input("Number of plates washed", min_value=0, step=50, value=0)
        details = f"Running tap: {flow_rate:g} L/min, {seconds_per_plate:g} s/plate"

    elif method == "bucket":
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            bucket_size = st.number_input("Bucket size (litres)", min_value=0.0, step=1.0, value=15.0, format="%.1f")
        with col_b:
            buckets = st.number_input("Number of buckets used", min_value=0, step=1, value=0)
        with col_c:
            plates = st.number_input("Number of plates washed", min_value=0, step=50, value=0)
        details = f"Bucket method: {bucket_size:g} L buckets, {int(buckets)} buckets"

    elif method == "dishwasher":
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            water_per_cycle = st.number_input(
                "Water per cycle (litres)", min_value=0.0, step=0.5, value=0.0, format="%.1f",
                help="Use the water rating of your machine if known.",
            )
        with col_b:
            cycles = st.number_input("Number of cycles", min_value=0, step=1, value=0)
        with col_c:
            plates = st.number_input("Number of plates washed", min_value=0, step=50, value=0)
        details = f"Dishwasher: {water_per_cycle:g} L/cycle, {int(cycles)} cycles"

    else:  # other
        col_a, col_b = st.columns(2)
        with col_a:
            total_water = st.number_input("Total water used (litres)", min_value=0.0, step=10.0, value=0.0, format="%.1f")
        with col_b:
            plates = st.number_input("Number of plates washed", min_value=0, step=50, value=0)
        details = "Directly entered total"

    # Compute ---------------------------------------------------------------
    error = validation.validate_washing_input(
        method, plates, flow_rate=flow_rate, washing_time=washing_time,
        bucket_size=bucket_size, buckets=buckets, water_per_cycle=water_per_cycle,
        cycles=cycles, total_water=total_water,
    )

    estimated_litres = None
    explanation = ""
    if error is None:
        estimated_litres, explanation = impact_engine.plate_washing_water(
            method, plates, flow_rate=flow_rate, washing_time=washing_time,
            bucket_size=bucket_size, buckets=buckets, water_per_cycle=water_per_cycle,
            cycles=cycles, total_water=total_water,
        )

    result_cols = st.columns([1, 1.6])
    with result_cols[0]:
        if estimated_litres is not None:
            ui.metric_card("Estimated water usage", fmt.format_litres(estimated_litres),
                           "You can save this estimate as a record", "estimated")
        else:
            ui.metric_card("Estimated water usage", "—", "Complete the inputs to see the estimate", None)
    with result_cols[1]:
        if error:
            st.warning(error)
        elif explanation:
            st.info(explanation + " " + impact_engine.WASHING_DISCLAIMER)

    if st.button("💾 Save washing record", type="primary", disabled=estimated_litres is None):
        database.add_washing_record(
            day=wash_date, method=method, plates=int(plates), water_used=float(estimated_litres),
            flow_rate=flow_rate, washing_time=washing_time, details=details,
        )
        st.toast(f"Saved washing-water estimate for {wash_date}.")
        st.rerun()

    # Records + period totals ----------------------------------------------
    st.divider()
    recent_start = date.today() - timedelta(days=29)
    recent = database.get_washing_range(recent_start, date.today())
    if not recent.empty:
        st.markdown("##### Recent washing records (last 30 days)")
        table = recent[["id", "date", "washing_method", "plates", "water_used", "details"]].copy()
        table.columns = ["ID", "Date", "Method", "Plates", "Water (L)", "Details"]
        table["Method"] = table["Method"].str.replace("_", " ").str.title()
        st.dataframe(
            table.style.format({"Water (L)": "{:,.0f}", "Plates": "{:,.0f}"}),
            width="stretch", hide_index=True,
        )
        delete_id = st.selectbox("Delete a record by ID", table["ID"].tolist(), key="wash_delete_id")
        if st.button("🗑️ Delete selected washing record"):
            database.delete_washing_record(int(delete_id))
            st.toast(f"Deleted washing record #{delete_id}.")
            st.rerun()
    else:
        ui.empty_state("No plate-washing records yet. Use the calculator above and save a record.")

    start, end = ui.get_date_range()
    washing_period = calculations.washing_summary(start, end)
    if washing_period["records"] > 0:
        st.markdown(f"##### Washing water in the reporting period ({ui.range_label(start, end)})")
        cards = st.columns(3)
        with cards[0]:
            ui.metric_card("Total washing water", fmt.format_litres(washing_period["total_litres"]),
                           f"{washing_period['records']} record(s)", "estimated")
        with cards[1]:
            ui.metric_card("Plates washed", fmt.format_number(washing_period["total_plates"]),
                           "Sum of recorded plates", "measured")
        with cards[2]:
            ui.metric_card(
                "Litres per plate",
                f"{fmt.format_litres(washing_period['total_litres'] / washing_period['total_plates'], 2)}"
                if washing_period["total_plates"] > 0 else "—",
                "Total water ÷ plates", "calculated",
            )
        by_method = washing_period["by_method"].copy()
        if not by_method.empty:
            by_method["washing_method"] = by_method["washing_method"].str.replace("_", " ").str.title()
            by_method = by_method.rename(columns={"washing_method": "food_name", "litres": "waste"})
            st.plotly_chart(
                charts.waste_by_food(by_method, "Washing water by method (period)", unit="L"),
                width="stretch",
            )

    ui.method_note(impact_engine.WASHING_DISCLAIMER + " All washing-water values are estimates.")
