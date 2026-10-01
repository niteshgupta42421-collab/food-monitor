"""
FoodWaste360 - Application entry point.

Run with:  streamlit run app.py

Responsibilities of this file:
  * Page configuration and global styling.
  * Database initialization (tables + default food factors + demo users).
  * Simple login screen using the demo accounts (passwords are stored hashed).
  * Sidebar: brand, signed-in user, reporting-period selector, logout.
  * Role-based navigation between the pages/ modules.
"""

import streamlit as st

from database import database, schema
from utils import ui

# ---------------------------------------------------------------- page setup

st.set_page_config(
    page_title="FoodWaste360",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

database.init_db()
ui.inject_global_css()


# ---------------------------------------------------------------- login screen

def show_login() -> None:
    """Centered login card with demo-account quick sign-in buttons."""
    st.markdown(
        """
        <div class="fw-hero">
            <h1>🍽️ FoodWaste360</h1>
            <p><b>Measure. Understand. Reduce.</b><br>
            Smart food waste &amp; impact intelligence for hotels, restaurants,
            cafeterias and large kitchens.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns([1, 1.1, 1])
    with middle:
        st.markdown("##### Sign in")
        with st.form("login_form"):
            email = st.text_input("Email", placeholder="you@example.com")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Sign in", width="stretch")
        if submitted:
            user_row = database.authenticate(email, password)
            if user_row is None:
                st.error("Email or password is incorrect. Please try again.")
            else:
                st.session_state["user"] = {
                    "name": user_row["name"],
                    "email": user_row["email"],
                    "role": user_row["role"],
                }
                st.rerun()

        with st.expander("Demo accounts (click to sign in instantly)"):
            st.caption(
                f"All demo accounts use the password **{schema.DEMO_PASSWORD}**. "
                "These accounts are only for demonstration."
            )
            role_labels = {
                "admin": "Administrator",
                "manager": "Hotel / Restaurant Manager",
                "kitchen": "Kitchen Manager / Chef",
                "staff": "Staff",
            }
            for demo_user in schema.DEMO_USERS:
                if st.button(
                    f"{demo_user['name']} — {role_labels.get(demo_user['role'], demo_user['role'])}",
                    key=f"quick_{demo_user['email']}",
                    width="stretch",
                ):
                    st.session_state["user"] = {
                        "name": demo_user["name"],
                        "email": demo_user["email"],
                        "role": demo_user["role"],
                    }
                    st.rerun()

        st.caption(
            "Privacy note: FoodWaste360 only stores a name, email and role for each user. "
            "No other personal information is collected."
        )


# ---------------------------------------------------------------- access control

if "user" not in st.session_state:
    show_login()
    st.stop()

current_user = st.session_state["user"]
role = current_user["role"]

# Page visibility per role (spec section 2: manager, kitchen manager, staff, admin).
ROLE_PAGES = {
    "Dashboard": {"admin", "manager", "kitchen", "staff"},
    "Production": {"admin", "manager", "kitchen"},
    "Waste Tracking": {"admin", "manager", "kitchen", "staff"},
    "Plate Waste": {"admin", "manager", "kitchen", "staff"},
    "Food Database": {"admin", "manager", "kitchen"},
    "Impact Calculator": {"admin", "manager"},
    "Analytics": {"admin", "manager", "kitchen"},
    "What-If Simulator": {"admin", "manager"},
    "Smart Recommendations": {"admin", "manager"},
    "Reports": {"admin", "manager"},
    "Settings": {"admin"},
}


def allowed(page_title: str) -> bool:
    """True when the signed-in role may see the page."""
    return role in ROLE_PAGES.get(page_title, {"admin"})


# ---------------------------------------------------------------- sidebar

ui.sidebar_brand()

role_display = {
    "admin": "Administrator",
    "manager": "Manager",
    "kitchen": "Kitchen / Chef",
    "staff": "Staff",
}
st.sidebar.markdown(
    f"""
    <div class="fw-card" style="padding: 10px 14px; margin-bottom: 8px;">
        <div class="fw-label">Signed in</div>
        <div style="font-weight: 700; color:#12291E;">{current_user['name']}</div>
        <div class="fw-sub">{role_display.get(role, role)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

ui.date_range_selector()

if st.sidebar.button("Log out", width="stretch"):
    st.session_state.pop("user", None)
    st.rerun()

if not database.has_records():
    st.sidebar.warning("No data recorded yet. Use **Load Demo Hotel** on the Dashboard.")

st.sidebar.caption("FoodWaste360 v1.0 — Measure. Understand. Reduce.")

# ---------------------------------------------------------------- navigation

page_definitions = [
    ("Overview", [
        ("pages/dashboard.py", "Dashboard", "🏠", True),
    ]),
    ("Daily recording", [
        ("pages/production.py", "Production", "🍚", False),
        ("pages/waste.py", "Waste Tracking", "♻️", False),
        ("pages/plate_waste.py", "Plate Waste", "🍽️", False),
    ]),
    ("Insights", [
        ("pages/impact.py", "Impact Calculator", "🌍", False),
        ("pages/analytics.py", "Analytics", "📊", False),
        ("pages/simulator.py", "What-If Simulator", "🔮", False),
        ("pages/recommendations.py", "Smart Recommendations", "🤖", False),
        ("pages/reports.py", "Reports", "📄", False),
    ]),
    ("Administration", [
        ("pages/food_database.py", "Food Database", "🗃️", False),
        ("pages/settings.py", "Settings", "⚙️", False),
    ]),
]

sections: dict[str, list] = {}
for section_name, pages in page_definitions:
    visible = [
        st.Page(path, title=title, icon=icon, default=is_default)
        for path, title, icon, is_default in pages
        if allowed(title)
    ]
    if visible:
        sections[section_name] = visible

if not sections:
    st.error("Your account role does not have access to any pages. Please contact an administrator.")
    st.stop()

navigation = st.navigation(sections)
navigation.run()
