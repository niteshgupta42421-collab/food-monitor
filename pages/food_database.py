"""
FoodWaste360 - Food Database page.

Lists every food item with its cost and documented environmental factors.
Administrators can edit costs and factors here; a factor can never be saved
without a source (project rule).

"Direct match" means the factor comes straight from the published dataset for
that commodity; "proxy / composite" values are clearly labelled in the notes.
"""

import streamlit as st

from database import database
from utils import ui, validation

ui.page_header(
    "Food Inventory / Food Database",
    "Manage food items, their estimated cost per kg, and their documented impact factors.",
)

role = st.session_state.get("user", {}).get("role", "staff")
is_admin = role == "admin"

foods = database.get_food_items_df()
if foods.empty:
    ui.empty_state("The food database is empty. Restore data/food_factors.csv and restart the app.")
    st.stop()

# ---------------------------------------------------------------- full table

st.markdown("##### All food items")
table = foods.copy()
table["is_estimated"] = table["is_estimated"].map({1: "Yes", 0: "No"})
table = table.rename(columns={
    "food_name": "Food", "category": "Category", "unit": "Unit", "cost_per_kg": "Cost (₹/kg)",
    "co2_factor": "CO2e (kg/kg)", "water_factor": "Water (L/kg)", "factor_source": "Factor source",
    "factor_reference": "Reference", "factor_date": "Date/version", "is_estimated": "Estimated?",
    "notes": "Notes", "id": "ID",
})
st.dataframe(
    table[[
        "Food", "Category", "Cost (₹/kg)", "CO2e (kg/kg)", "Water (L/kg)",
        "Estimated?", "Factor source", "Date/version", "Notes",
    ]].style.format({"Cost (₹/kg)": "₹{:,.2f}", "CO2e (kg/kg)": "{:,.2f}", "Water (L/kg)": "{:,.1f}"}),
    width="stretch",
    hide_index=True,
)

st.caption(
    "CO2e and water factors come from Poore & Nemecek (2018), a global meta-analysis "
    "published in Science (reference year 2010), processed by Our World in Data. "
    "Full references are stored per food and shown in the Impact Calculator's "
    "Methodology & Sources section. Costs are your organization's own estimates and "
    "can be edited at any time."
)

if not is_admin:
    st.info("Viewing mode — only administrators can edit food items and factors.")
    st.stop()

# ---------------------------------------------------------------- editing (admin)

st.divider()
st.markdown("##### Edit a food item (administrator)")
edit_col, preview_col = st.columns([1.2, 1])

with edit_col:
    selected_name = st.selectbox("Food item to edit", foods["food_name"].tolist())
    selected = foods[foods["food_name"] == selected_name].iloc[0]

    with st.form("edit_food_form"):
        col_a, col_b = st.columns(2)
        with col_a:
            new_category = st.text_input("Category", value=selected["category"] or "")
            new_cost = st.number_input("Estimated cost per kg (₹)", min_value=0.0, step=1.0,
                                       value=float(selected["cost_per_kg"]), format="%.2f")
            new_co2 = st.number_input(
                "CO2e factor (kg CO2e / kg)", min_value=0.0, step=0.01,
                value=float(selected["co2_factor"]) if selected["co2_factor"] is not None else 0.0,
                format="%.2f", help="Leave at 0 only if no documented factor is available.",
            )
            new_water = st.number_input(
                "Water factor (L / kg)", min_value=0.0, step=1.0,
                value=float(selected["water_factor"]) if selected["water_factor"] is not None else 0.0,
                format="%.1f",
            )
        with col_b:
            new_source = st.text_input("Factor source *", value=selected["factor_source"] or "",
                                       help="Required whenever a factor value is stored.")
            new_reference = st.text_input("Reference (URL/citation)", value=selected["factor_reference"] or "")
            new_date = st.text_input("Date/version", value=selected["factor_date"] or "")
            new_estimated = st.checkbox("This factor is an estimate/proxy", value=bool(selected["is_estimated"]))
            new_notes = st.text_area("Notes", value=selected["notes"] or "", height=80)

        save_clicked = st.form_submit_button("💾 Save changes", type="primary")

    if save_clicked:
        co2_value = float(new_co2) if new_co2 > 0 else None
        water_value = float(new_water) if new_water > 0 else None
        error = validation.validate_factor_fields(co2_value, water_value, new_source)
        if error:
            st.error(error + " Factors must always carry a documented source.")
        else:
            database.update_food_item(
                int(selected["id"]),
                category=new_category,
                cost_per_kg=float(new_cost),
                co2_factor=co2_value,
                water_factor=water_value,
                factor_source=new_source,
                factor_reference=new_reference,
                factor_date=new_date,
                is_estimated=1 if new_estimated else 0,
                notes=new_notes,
            )
            st.toast(f"Updated '{selected_name}'.")
            st.rerun()

with preview_col:
    st.markdown("**Current stored record**")
    st.markdown(
        f"""
        <div class="fw-card">
            <div class="fw-label">Factor details</div>
            <div class="fw-sub" style="margin-top:8px;">
                <b>Source:</b> {selected['factor_source'] or '—'}<br>
                <b>Reference:</b> {selected['factor_reference'] or '—'}<br>
                <b>Date/version:</b> {selected['factor_date'] or '—'}<br>
                <b>Estimated:</b> {'Yes' if selected['is_estimated'] else 'No'}<br>
                <b>Notes:</b> {selected['notes'] or '—'}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("**Add a new food item**")
    with st.form("add_food_form"):
        add_name = st.text_input("Food name *")
        add_category = st.text_input("Category")
        add_cost = st.number_input("Cost per kg (₹)", min_value=0.0, step=1.0, value=0.0, format="%.2f")
        add_co2 = st.number_input("CO2e factor (kg/kg)", min_value=0.0, step=0.01, value=0.0, format="%.2f")
        add_water = st.number_input("Water factor (L/kg)", min_value=0.0, step=1.0, value=0.0, format="%.1f")
        add_source = st.text_input("Factor source", help="Required if a factor value is entered.")
        add_reference = st.text_input("Reference (URL/citation)")
        add_estimated = st.checkbox("Factors are estimates/proxies", value=True)
        add_notes = st.text_area("Notes", height=60)
        add_clicked = st.form_submit_button("➕ Add food item")

    if add_clicked:
        error = validation.validate_required(add_name, "Food name")
        co2_value = float(add_co2) if add_co2 > 0 else None
        water_value = float(add_water) if add_water > 0 else None
        if not error:
            error = validation.validate_factor_fields(co2_value, water_value, add_source)
        if error:
            st.error(error)
        else:
            try:
                database.add_food_item(
                    food_name=add_name, category=add_category, cost_per_kg=float(add_cost),
                    co2_factor=co2_value, water_factor=water_value, factor_source=add_source,
                    factor_reference=add_reference, is_estimated=1 if add_estimated else 0,
                    notes=add_notes,
                )
                st.toast(f"Added '{add_name}'.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

    st.markdown("---")
    st.markdown("**Delete a food item**")
    st.caption("A food item can only be deleted when no production, waste or plate records reference it.")
    delete_name = st.selectbox("Food to delete", foods["food_name"].tolist(), key="delete_food_select")
    delete_id = int(foods[foods["food_name"] == delete_name]["id"].iloc[0])
    usage = database.food_item_usage_count(delete_id)
    st.caption(f"Used in {usage} record(s).")
    if st.button("🗑️ Delete food item", disabled=usage > 0):
        try:
            database.delete_food_item(delete_id)
            st.toast(f"Deleted '{delete_name}'.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
