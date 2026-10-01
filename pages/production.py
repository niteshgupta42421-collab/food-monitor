"""
FoodWaste360 - Production page.

The kitchen team records, per food item, how much was prepared, served and
consumed on a given day. The totals are calculated automatically and the data
is stored with one row per food per day (editing a day replaces its rows).
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database
from utils import formatting as fmt, ui, validation

ui.page_header(
    "Production",
    "Record what the kitchen prepared, served and consumed for each food item.",
)

foods = database.get_food_items_df()
if foods.empty:
    ui.empty_state("No food items exist yet. Add foods in the Food Database first.")
    st.stop()

selected_date = st.date_input("Production date", value=date.today(), max_value=date.today())
existing = database.get_production_day(selected_date)
existing_by_food = {
    row["food_name"]: (row["quantity_prepared"], row["quantity_served"], row["quantity_consumed"])
    for _, row in existing.iterrows()
}

# ---------------------------------------------------------------- editor table

editor_rows = []
for _, food in foods.iterrows():
    prepared, served, consumed = existing_by_food.get(food["food_name"], (0.0, 0.0, 0.0))
    editor_rows.append({
        "Food": food["food_name"],
        "Prepared (kg)": float(prepared),
        "Served (kg)": float(served),
        "Consumed (kg)": float(consumed),
    })
editor_df = pd.DataFrame(editor_rows)

food_id_by_name = dict(zip(foods["food_name"], foods["id"]))

st.markdown("##### Quantities for the selected day (enter 0 where nothing applies)")
edited = st.data_editor(
    editor_df,
    hide_index=True,
    width="stretch",
    disabled=["Food"],
    column_config={
        "Prepared (kg)": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f"),
        "Served (kg)": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f"),
        "Consumed (kg)": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f"),
    },
    key=f"production_editor_{selected_date}",
)

prepared_total = float(edited["Prepared (kg)"].sum())
served_total = float(edited["Served (kg)"].sum())
consumed_total = float(edited["Consumed (kg)"].sum())

card_row = st.columns(3)
with card_row[0]:
    ui.metric_card("Total prepared", fmt.format_kg(prepared_total), "Calculated from the table", "calculated")
with card_row[1]:
    ui.metric_card("Total served", fmt.format_kg(served_total), "Calculated from the table", "calculated")
with card_row[2]:
    ui.metric_card("Total consumed", fmt.format_kg(consumed_total), "Calculated from the table", "calculated")

# ---------------------------------------------------------------- save

# Live consistency warnings (never block saving, but ask for confirmation).
consistency_warnings = []
for _, row in edited.iterrows():
    consistency_warnings.extend(
        validation.production_consistency_warnings(
            row["Prepared (kg)"], row["Served (kg)"], row["Consumed (kg)"], row["Food"]
        )
    )

confirmed = True
if consistency_warnings:
    st.warning("Please check these entries:\n\n" + "\n".join(f"- {w}" for w in consistency_warnings))
    confirmed = st.checkbox("I have checked the entries above and want to save anyway.")

if st.button("💾 Save production for this day", type="primary", disabled=not confirmed):
    errors = []
    rows_to_save = []
    for _, row in edited.iterrows():
        error = validation.validate_production_row(
            row["Prepared (kg)"], row["Served (kg)"], row["Consumed (kg)"], row["Food"]
        )
        if error:
            errors.append(error)
            continue
        if row["Prepared (kg)"] or row["Served (kg)"] or row["Consumed (kg)"]:
            rows_to_save.append(row)

    if errors:
        for message in errors:
            st.error(message)
    else:
        saved = 0
        for row in rows_to_save:
            food_id = food_id_by_name.get(row["Food"])
            if food_id is None:
                continue
            database.upsert_production(
                selected_date, food_id,
                row["Prepared (kg)"], row["Served (kg)"], row["Consumed (kg)"],
            )
            saved += 1
        # Foods cleared back to zero are removed so the day stays tidy.
        cleared = [
            name for name, values in existing_by_food.items()
            if name not in {r["Food"] for r in rows_to_save} and any(v > 0 for v in values)
        ]
        for name in cleared:
            database.delete_production_row(selected_date, food_id_by_name[name])
        st.toast(f"Saved production for {selected_date} ({saved} food items).")
        st.rerun()

# ---------------------------------------------------------------- day summary + actions

st.divider()
left, right = st.columns([2, 1])

with left:
    st.markdown("##### Saved records for this day")
    if existing.empty:
        ui.empty_state("Nothing has been recorded for this day yet.")
    else:
        table = existing[["food_name", "quantity_prepared", "quantity_served", "quantity_consumed"]].copy()
        table.columns = ["Food", "Prepared (kg)", "Served (kg)", "Consumed (kg)"]
        st.dataframe(
            table.style.format({"Prepared (kg)": "{:,.2f}", "Served (kg)": "{:,.2f}", "Consumed (kg)": "{:,.2f}"}),
            width="stretch",
            hide_index=True,
        )

with right:
    st.markdown("##### Actions")
    if not existing.empty:
        if st.button("🗑️ Delete all rows for this day", width="stretch"):
            database.delete_production_day(selected_date)
            st.toast(f"Deleted production records for {selected_date}.")
            st.rerun()
    with st.expander("➕ Add a custom food item"):
        with st.form("quick_add_food"):
            new_name = st.text_input("Food name")
            new_category = st.text_input("Category (optional)")
            new_cost = st.number_input("Estimated cost per kg (₹)", min_value=0.0, step=1.0, format="%.2f")
            submitted = st.form_submit_button("Add food")
        if submitted:
            error = validation.validate_required(new_name, "Food name")
            if error:
                st.error(error)
            else:
                try:
                    database.add_food_item(food_name=new_name, category=new_category, cost_per_kg=new_cost)
                    st.toast(f"Added '{new_name}'. Set its impact factors in the Food Database.")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))

ui.method_note(
    "These quantities are <b>measured</b> values entered by your team. The totals and the "
    "waste rate on other pages are <b>calculated</b> from them."
)
