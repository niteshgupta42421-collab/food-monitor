"""
MealFlow360 - Production page.

The kitchen records the measured Food Prepared quantity per food item for a
day - the starting quantity of the single accounting model
(services/accounting.py). Available for service, served and consumed are NOT
entered here; they are derived from the prepared quantity and the recorded
waste, so food can never be counted twice:

    prepared -> available (prepared - kitchen waste)
             -> served    (available - serving waste)
             -> consumed  (served - plate waste)

The page shows the derived values live while you type, and asks for
confirmation when recorded waste exceeds a prepared quantity (the flow
cannot go below zero).
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database
from services import accounting
from utils import formatting as fmt, ui, validation

ui.page_header(
    "Production",
    "Record the Food Prepared quantity per food item. Available, served and consumed are calculated from it and the recorded waste.",
)

foods = database.get_food_items_df()
if foods.empty:
    ui.empty_state("No food items exist yet. Add foods in the Food Database first.")
    st.stop()

selected_date = st.date_input("Production date", value=date.today(), max_value=date.today())
existing = database.get_production_day(selected_date)
existing_by_food = {
    row["food_name"]: float(row["quantity_prepared"]) for _, row in existing.iterrows()
}

# The day's recorded waste drives the derived quantities. Waste lives in one
# ledger (kitchen / serving / plate), so no category is ever added twice.
waste_lookup = {name: {"kitchen": 0.0, "serving": 0.0, "plate": 0.0} for name in foods["food_name"]}
waste_day = database.get_waste_day(selected_date)
for _, record in waste_day.iterrows():
    entry = waste_lookup.setdefault(record["food_name"], {"kitchen": 0.0, "serving": 0.0, "plate": 0.0})
    entry[record["waste_type"]] += float(record["quantity"])


def day_flow(prepared_by_food: dict) -> pd.DataFrame:
    """Per-food accounting flow for the day: prepared + recorded waste -> derived quantities."""
    rows = [
        {
            "food_name": name,
            "prepared": float(prepared_by_food.get(name, 0.0)),
            **waste_lookup.get(name, {"kitchen": 0.0, "serving": 0.0, "plate": 0.0}),
        }
        for name in foods["food_name"]
    ]
    return accounting.add_flow_columns(pd.DataFrame(rows))


# ---------------------------------------------------------------- editor table

editor_df = pd.DataFrame([
    {"Food": name, "Prepared (kg)": existing_by_food.get(name, 0.0)}
    for name in foods["food_name"]
])

st.markdown("##### Food prepared for the selected day (enter 0 where nothing was prepared)")
edited = st.data_editor(
    editor_df,
    hide_index=True,
    width="stretch",
    disabled=["Food"],
    column_config={
        "Prepared (kg)": st.column_config.NumberColumn(min_value=0.0, step=1.0, format="%.1f"),
    },
    key=f"production_editor_{selected_date}",
)
edited["Prepared (kg)"] = pd.to_numeric(edited["Prepared (kg)"], errors="coerce").fillna(0.0)

flow = day_flow(dict(zip(edited["Food"], edited["Prepared (kg)"])))

card_row = st.columns(4)
with card_row[0]:
    ui.metric_card("Food prepared", fmt.format_kg(flow["prepared"].sum()),
                   "Measured - entered in the table above", "measured")
with card_row[1]:
    ui.metric_card("Available for service", fmt.format_kg(flow["available"].sum()),
                   "Prepared - kitchen waste", "calculated")
with card_row[2]:
    ui.metric_card("Food served", fmt.format_kg(flow["served"].sum()),
                   "Available - serving waste", "calculated")
with card_row[3]:
    ui.metric_card("Food consumed", fmt.format_kg(flow["consumed"].sum()),
                   "Served - plate waste", "calculated")

with st.expander("🧮 How these quantities are calculated"):
    st.markdown(
        """
        The app uses one accounting model on every page
        (`services/accounting.py`), so food is never counted twice:

        * **Available for service** = prepared − kitchen waste
        * **Food served** = available for service − serving waste
        * **Food consumed** = food served − plate waste
        * **Total waste** = kitchen + serving + plate

        Waste quantities come from the Waste Tracking and Plate Waste pages
        for this date. Nothing is entered twice, and the flow always balances:
        kitchen + serving + plate + consumed = prepared.
        """
    )

st.markdown("##### Calculated flow for the selected day")
preview = flow[[
    "food_name", "prepared", "kitchen", "serving", "plate", "available", "served", "consumed",
]].copy()
preview.columns = [
    "Food", "Prepared (kg)", "Kitchen waste (kg)", "Serving waste (kg)", "Plate waste (kg)",
    "Available (kg)", "Served (kg)", "Consumed (kg)",
]
st.dataframe(
    preview.style.format({
        "Prepared (kg)": "{:,.2f}", "Kitchen waste (kg)": "{:,.2f}", "Serving waste (kg)": "{:,.2f}",
        "Plate waste (kg)": "{:,.2f}", "Available (kg)": "{:,.2f}", "Served (kg)": "{:,.2f}",
        "Consumed (kg)": "{:,.2f}",
    }),
    width="stretch",
    hide_index=True,
)
st.caption(
    "Waste columns are the recorded entries for this date; available / served / consumed are derived "
    "from them and the prepared quantities above."
)

# ---------------------------------------------------------------- save

# Ask for confirmation when recorded waste exceeds the prepared quantity
# (a flow step would fall below zero).
flow_warnings = validation.flow_violation_warnings(flow)
confirmed = True
if flow_warnings:
    st.warning("Please check these entries:\n\n" + "\n".join(f"- {w}" for w in flow_warnings))
    confirmed = st.checkbox("I have checked the entries above and want to save anyway.")

if st.button("💾 Save production for this day", type="primary", disabled=not confirmed):
    errors = []
    rows_to_save = []
    for _, row in edited.iterrows():
        error = validation.validate_non_negative(row["Prepared (kg)"], f"{row['Food']} - Prepared quantity")
        if error:
            errors.append(error)
            continue
        if row["Prepared (kg)"] > 0:
            rows_to_save.append(row)

    if errors:
        for message in errors:
            st.error(message)
    else:
        flow_by_food = flow.set_index("food_name")
        food_id_by_name = dict(zip(foods["food_name"], foods["id"]))
        saved = 0
        for row in rows_to_save:
            food_id = food_id_by_name.get(row["Food"])
            if food_id is None:
                continue
            # Served and consumed are written as a snapshot of the model at
            # save time; every page re-derives them from prepared + waste.
            snapshot = flow_by_food.loc[row["Food"]]
            database.upsert_production(
                selected_date, food_id,
                row["Prepared (kg)"], float(snapshot["served"]), float(snapshot["consumed"]),
            )
            saved += 1
        # Foods cleared back to zero are removed so the day stays tidy.
        saved_names = {row["Food"] for row in rows_to_save}
        cleared = [
            name for name, prepared in existing_by_food.items()
            if prepared > 0 and name not in saved_names
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
        saved_flow = day_flow(existing_by_food)
        table = saved_flow[saved_flow["prepared"] > 0][[
            "food_name", "prepared", "kitchen", "serving", "plate", "available", "served", "consumed",
        ]].copy()
        table.columns = [
            "Food", "Prepared (kg)", "Kitchen (kg)", "Serving (kg)", "Plate (kg)",
            "Available (kg)", "Served (kg)", "Consumed (kg)",
        ]
        st.dataframe(
            table.style.format({column: "{:,.2f}" for column in table.columns[1:]}),
            width="stretch",
            hide_index=True,
        )
        st.caption(
            "Prepared quantities are measured. The waste columns are this day's recorded entries; "
            "available / served / consumed are derived from them by the accounting model."
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
    "Prepared quantities are <b>measured</b> values entered by your team. Available, served and "
    "consumed are <b>calculated</b> by the app's single accounting model from the prepared quantity "
    "and the recorded waste - they are never entered separately, so food cannot be double-counted."
)
