"""
MealFlow360 - Settings page.

Personal sections (every role):
  * Profile - full name and restaurant / kitchen name (shown in the sidebar).
  * Appearance - light / dark / warm theme, saved per user.

Administration sections (administrators only):
  * Data management - load The Urban Thali demo, clear records.
  * User management - list and add users.

About - application, security and demo-account notes for everyone.
"""

from datetime import date

import streamlit as st

from database import database, demo_data
from utils import theme, ui, validation

ui.page_header(
    "⚙️ Settings",
    "Your profile and appearance, plus administration for data and users.",
)

role = st.session_state.get("user", {}).get("role", "staff")
is_admin = role == "admin"
user_email = st.session_state.get("user", {}).get("email", "")

tab_labels = ["👤 Profile & appearance"]
if is_admin:
    tab_labels += ["📦 Data management", "👥 User management"]
tab_labels += ["ℹ️ About"]
tabs = st.tabs(tab_labels)

# ---------------------------------------------------------------- profile & appearance

with tabs[0]:
    profile = database.get_user_profile(user_email) if user_email else None
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown("##### 👤 Profile")
        with st.form("profile_form"):
            name_value = profile["name"] if profile else st.session_state.get("user", {}).get("name", "")
            restaurant_value = (profile["restaurant_name"] if profile else "") or ""
            new_name = st.text_input("Full name", value=name_value)
            new_restaurant = st.text_input(
                "Restaurant / kitchen name", value=restaurant_value,
                help="Shown in the sidebar under your name.",
            )
            save_profile = st.form_submit_button("💾 Save profile", type="primary")
        if save_profile:
            error = validation.validate_required(new_name, "Full name")
            if error:
                st.error(error)
            else:
                database.update_user_profile(user_email, name=new_name, restaurant_name=new_restaurant)
                st.session_state["user"]["name"] = new_name.strip()
                st.session_state["user"]["restaurant"] = new_restaurant.strip()
                st.toast("Profile saved.")
                st.rerun()

    with col_right:
        st.markdown("##### 🎨 Appearance")
        descriptions = {
            "light": "Clean and bright — recommended for daytime service.",
            "dark": "Modern dark dashboard — easy on the eyes for night operations.",
            "warm": "Premium food and restaurant look with warm tones.",
        }
        chosen = st.radio(
            "Theme", theme.theme_names(), horizontal=True,
            index=theme.theme_names().index(theme.active_key()),
            format_func=theme.theme_label, key="settings_theme_radio",
        )
        st.caption(descriptions.get(chosen, ""))
        if chosen != theme.active_key():
            theme.set_active(chosen)
            if user_email:
                database.set_user_theme(user_email, chosen)
            st.rerun()

        active_palette = theme.palette(theme.active_key())
        st.markdown(
            f"""
            <div class="fw-card" style="margin-top:6px;">
                <div class="fw-label">Active theme — {theme.theme_label(theme.active_key())}</div>
                <div style="display:flex; gap:8px; margin-top:10px;">
                    <div style="width:44px; height:26px; border-radius:6px; background:{active_palette['bg']}; border:1px solid {active_palette['border']};"></div>
                    <div style="width:44px; height:26px; border-radius:6px; background:{active_palette['card']}; border:1px solid {active_palette['border']};"></div>
                    <div style="width:44px; height:26px; border-radius:6px; background:{active_palette['accent']};"></div>
                    <div style="width:44px; height:26px; border-radius:6px; background:{active_palette['accent_soft']}; border:1px solid {active_palette['border']};"></div>
                </div>
                <div class="fw-sub" style="margin-top:8px;">Saved per user — your theme follows you on every sign-in.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

# ---------------------------------------------------------------- data management (admin)

if is_admin:
    with tabs[1]:
        counts = database.table_counts()
        count_cols = st.columns(4)
        labels = [
            ("Production rows", counts["daily_production"]),
            ("Sales rows", counts["sales"]),
            ("Waste records", counts["waste_records"]),
            ("Remaining-food rows", counts["remaining_food"]),
        ]
        for column, (label, value) in zip(count_cols, labels):
            with column:
                ui.metric_card(label, f"{value:,}", "", None)

        st.markdown("##### 🍛 Demo data — The Urban Thali")
        st.caption(
            "The demo recreates **The Urban Thali**, a ~520-cover restaurant: 8 dishes and 30 "
            "deterministic days of production, sales, waste and carry-over — including near "
            "sell-outs, one sold-out dish and one overstocked dish. It replaces all record data "
            "(users and food items are kept)."
        )
        demo_confirm = st.checkbox(
            "I understand that loading demo data **replaces all existing records** "
            "(users and foods are kept)."
        )
        if st.button("🍛 Load The Urban Thali demo", type="primary", disabled=not demo_confirm):
            with st.spinner("Generating The Urban Thali demo dataset..."):
                summary = demo_data.load_demo_data()
            st.toast(
                f"Loaded {summary['days']} days ({summary['start']} → {summary['end']}): "
                f"{summary['production_rows']} production and {summary['sales_rows']} sales rows."
            )
            st.rerun()

        st.markdown("##### 🗑️ Clear records")
        st.caption(
            "Removes all production, waste, plate-waste, washing, sales and remaining-food "
            "records. Users and food items are kept."
        )
        delete_confirm = st.checkbox(
            "I understand that clearing **permanently deletes all records** (this cannot be undone)."
        )
        if st.button("🗑️ Clear all records", disabled=not delete_confirm):
            database.clear_all_records()
            st.toast("All records were cleared.")
            st.rerun()

    # ------------------------------------------------------------ user management (admin)

    with tabs[2]:
        st.caption(
            "MealFlow360 stores only a name, email, role and optional restaurant name for each "
            "user — no other personal information is collected. Passwords are stored as salted "
            "PBKDF2 hashes, never in plain text."
        )
        users = database.get_all_users()
        role_labels = {
            "admin": "Administrator",
            "manager": "Restaurant Manager",
            "kitchen": "Kitchen Manager / Chef",
            "staff": "Staff",
        }
        user_table = [{
            "Name": user["name"],
            "Email": user["email"],
            "Role": role_labels.get(user["role"], user["role"]),
            "Restaurant": user["restaurant_name"] or "—",
            "Created": user["created_at"],
        } for user in users]
        st.dataframe(user_table, width="stretch", hide_index=True)

        with st.expander("➕ Add a user"):
            with st.form("add_user_form"):
                new_name = st.text_input("Full name")
                new_email = st.text_input("Email")
                new_role = st.selectbox("Role", list(role_labels.keys()),
                                        format_func=lambda key: role_labels[key])
                new_restaurant = st.text_input("Restaurant / kitchen name (optional)")
                new_password = st.text_input("Initial password", type="password",
                                             help="Minimum 8 characters.")
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
                        database.create_user(new_name, new_email, new_role, new_password,
                                             restaurant_name=new_restaurant)
                        st.toast(f"Created user '{new_name}'.")
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))

# ---------------------------------------------------------------- about

about_index = 3 if is_admin else 1
with tabs[about_index]:
    info_cols = st.columns(2)
    with info_cols[0]:
        ui.method_note(
            f"""
            <b>MealFlow360 v2.0</b><br>
            Tagline: Sell Smart. Cook Right. Waste Less.<br>
            Database file: <code>data/foodwaste360.db</code> (SQLite)<br>
            Food data file: <code>data/food_factors.csv</code><br>
            Themes: Light · Dark · Warm (saved per user)<br>
            Today: {date.today().strftime('%d %b %Y')}
            """
        )
    with info_cols[1]:
        ui.method_note(
            """
            <b>Security &amp; data notes</b><br>
            • All SQL queries are parameterized (no string-built SQL).<br>
            • Passwords are stored as salted PBKDF2-SHA256 hashes.<br>
            • Sign in, account creation and password reset are handled in the app;
            no email service is used (offline demo).<br>
            • No API keys are used and none are stored in the code. If an external
            AI/API service is added later, its key must come from an environment
            variable, never the source code.
            """
        )

    st.markdown("##### Demo accounts")
    st.markdown(
        """
        - **Flagship demo login:** **demo@mealflow360.com** / **Demo@123**
          (Administrator, full access).
        - **Role accounts:** `admin@mealflow360.demo`, `manager@mealflow360.demo`,
          `kitchen@mealflow360.demo`, `staff@mealflow360.demo` — password **demo1234**.
        """
    )
    st.caption(
        "Environmental factors must always carry a source, value with unit and date (Food "
        "Master). Estimates are never presented as measurements; simulated results only "
        "appear in the What-If Simulator."
    )
