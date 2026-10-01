"""
FoodWaste360 - Settings page (administrators only).

Contains: data management (load demo hotel / clear records), user management,
application information and the security notes.
"""

from datetime import date

import streamlit as st

from database import database, demo_data
from utils import ui, validation

ui.page_header("Settings", "Administration: data management, users and application information.")

role = st.session_state.get("user", {}).get("role", "staff")
if role != "admin":
    st.error("Settings are only available to administrators. Please contact your system administrator.")
    st.stop()

# ---------------------------------------------------------------- data management

ui.section("📦 Data management")

counts = database.table_counts()
count_cols = st.columns(6)
labels = [
    ("Production rows", counts["daily_production"]),
    ("Waste records", counts["waste_records"]),
    ("Plate-waste rows", counts["plate_waste"]),
    ("Washing records", counts["washing_records"]),
    ("Food items", counts["food_items"]),
    ("Users", counts["users"]),
]
for column, (label, value) in zip(count_cols, labels):
    with column:
        ui.metric_card(label, f"{value:,}", "", None)

st.markdown("##### Demo data")
st.caption(
    "The demo dataset recreates a realistic hotel scenario: about 8,000 kg prepared per day, "
    "1,000 kg waste (250 kitchen / 150 serving / 600 plate = 12.5%) with 30 days of day-to-day "
    "variation. It is deterministic - the same data is generated every time."
)
demo_confirm = st.checkbox("I understand that loading demo data **replaces all existing records** (users and foods are kept).")
if st.button("Load Demo Hotel", type="primary", disabled=not demo_confirm):
    with st.spinner("Generating demo dataset..."):
        summary = demo_data.load_demo_data()
    st.toast(
        f"Demo data loaded: {summary['days']} days ({summary['start']} → {summary['end']}), "
        f"{summary['production_rows']} production rows."
    )
    st.rerun()

st.markdown("##### Clear records")
st.caption("Removes all production, waste, plate-waste and washing records. Users and food items are kept.")
delete_confirm = st.checkbox("I understand that clearing **permanently deletes all records** (this cannot be undone).")
if st.button("🗑️ Clear all records", disabled=not delete_confirm):
    database.clear_all_records()
    st.toast("All records were cleared.")
    st.rerun()

# ---------------------------------------------------------------- users

st.divider()
ui.section("👥 User management")
st.caption(
    "FoodWaste360 stores only a name, email and role for each user — no other personal information "
    "is collected (spec section 26). Passwords are stored as salted PBKDF2 hashes, never in plain text."
)

users = database.get_all_users()
role_labels = {
    "admin": "Administrator",
    "manager": "Hotel / Restaurant Manager",
    "kitchen": "Kitchen Manager / Chef",
    "staff": "Staff",
}
user_table = [{
    "Name": user["name"],
    "Email": user["email"],
    "Role": role_labels.get(user["role"], user["role"]),
    "Created": user["created_at"],
} for user in users]
st.dataframe(user_table, width="stretch", hide_index=True)

with st.expander("➕ Add a user"):
    with st.form("add_user_form"):
        new_name = st.text_input("Full name")
        new_email = st.text_input("Email")
        new_role = st.selectbox("Role", list(role_labels.keys()),
                                format_func=lambda key: role_labels[key])
        new_password = st.text_input("Initial password", type="password", help="Minimum 8 characters.")
        submitted = st.form_submit_button("Create user")

    if submitted:
        error = validation.validate_required(new_name, "Full name")
        if not error:
            error = validation.validate_required(new_email, "Email")
        if not error and "@" not in new_email:
            error = "Please enter a valid email address."
        if not error and len(new_password) < 8:
            error = "The initial password must be at least 8 characters."
        if error:
            st.error(error)
        else:
            try:
                database.create_user(new_name, new_email, new_role, new_password)
                st.toast(f"Created user '{new_name}'.")
                st.rerun()
            except ValueError as exc:
                st.error(str(exc))

# ---------------------------------------------------------------- application info

st.divider()
ui.section("ℹ️ Application information")

info_cols = st.columns(2)
with info_cols[0]:
    ui.method_note(
        f"""
        <b>FoodWaste360 v1.0</b><br>
        Tagline: Measure. Understand. Reduce.<br>
        Database file: <code>data/foodwaste360.db</code> (SQLite)<br>
        Food factor data file: <code>data/food_factors.csv</code><br>
        Today: {date.today().strftime('%d %b %Y')}
        """
    )
with info_cols[1]:
    ui.method_note(
        """
        <b>Security &amp; data notes</b><br>
        • All SQL queries are parameterized (no string-built SQL).<br>
        • Passwords are stored as salted PBKDF2-SHA256 hashes.<br>
        • No API keys are used in version 1 and none are stored in the code.
        If an external AI/API service is added later, its key must be provided
        through an environment variable, never committed to the source code.<br>
        • Only name, email and role are collected for users.
        """
    )

st.caption(
    "Environmental factors must always carry a source, value with unit and date (see the Food "
    "Database). Estimates are never presented as measurements; simulated results only appear in "
    "the What-If Simulator."
)
