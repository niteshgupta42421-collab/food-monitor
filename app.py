"""
MealFlow360 - Application entry point.

Sell Smart. Cook Right. Waste Less.

Run with:  streamlit run app.py

Responsibilities of this file:
  * Page configuration, theme application and global styling.
  * Database initialization (tables + in-place migrations + seed data).
  * Authentication: sign in, create account, password reset. Passwords are
    stored hashed (PBKDF2) and are never kept in plain text.
  * Sidebar: brand, signed-in user, restaurant name, reporting period, logout.
  * Role-based navigation between the pages/ modules.
"""

import re

import streamlit as st

from database import database, schema
from utils import theme, ui

# ---------------------------------------------------------------- page setup

st.set_page_config(
    page_title="MealFlow360",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded",
)

database.init_db()
ui.inject_global_css()
theme.apply_css(theme.active_key())

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MIN_PASSWORD_LENGTH = 8


# ---------------------------------------------------------------- authentication

def start_session(user: dict) -> None:
    """Sign the user in, apply their saved theme and rerun."""
    st.session_state["user"] = {
        "id": user.get("id"),
        "name": user["name"],
        "email": user["email"],
        "role": user["role"],
        "restaurant": (user.get("restaurant_name") or user.get("restaurant") or "").strip(),
    }
    theme.set_active(user.get("theme") or database.get_user_theme(user["email"]))
    st.rerun()


def validate_new_password(password: str, confirm: str) -> str | None:
    """Return an error message for an invalid password pair, else None."""
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Password must be at least {MIN_PASSWORD_LENGTH} characters."
    if password != confirm:
        return "Passwords do not match."
    return None


def show_login() -> None:
    """Branded landing screen: sign in, create account, password reset."""
    st.markdown(
        """
        <div class="fw-hero">
            <h1>🍽️ MealFlow360</h1>
            <p><b>Sell Smart. Cook Right. Waste Less.</b><br>
            One platform for sales, kitchen production, remaining food and
            waste intelligence — for hotels, restaurants, cafeterias and large
            kitchens.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, middle, right = st.columns([1, 1.2, 1])
    with middle:
        tab_in, tab_register, tab_forgot = st.tabs(
            ["👤 Sign in", "📝 Create account", "🔑 Forgot password"]
        )

        # ---------------------------------------------------------- sign in
        with tab_in:
            with st.form("login_form"):
                email = st.text_input("Email", placeholder="you@example.com")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Sign in", width="stretch")
            if submitted:
                if not email.strip() or not password:
                    st.error("Please enter email and password.")
                else:
                    user_row = database.authenticate(email, password)
                    if user_row is None:
                        st.error("Invalid email or password.")
                    else:
                        start_session(dict(user_row))

            with st.expander("Demo accounts (click to sign in instantly)"):
                st.caption(
                    f"Flagship demo login: **{schema.DEMO_ACCOUNT_EMAIL}** / "
                    f"**{schema.DEMO_ACCOUNT_PASSWORD}**. "
                    f"Role accounts use the password **{schema.DEMO_PASSWORD}**."
                )
                role_labels = {
                    "admin": "Administrator",
                    "manager": "Restaurant Manager",
                    "kitchen": "Kitchen Manager / Chef",
                    "staff": "Staff",
                }
                for demo_user in schema.DEMO_USERS:
                    if st.button(
                        f"{demo_user['name']} — {role_labels.get(demo_user['role'], demo_user['role'])}",
                        key=f"quick_{demo_user['email']}",
                        width="stretch",
                    ):
                        profile = database.get_user_profile(demo_user["email"])
                        start_session(dict(profile) if profile is not None else demo_user)

        # ---------------------------------------------------------- create account
        with tab_register:
            st.caption(
                "Create your account to manage one restaurant or kitchen. "
                "The registering user becomes the administrator and can add team members in Settings."
            )
            with st.form("register_form"):
                reg_name = st.text_input("Full name")
                reg_email = st.text_input("Email", placeholder="you@example.com")
                reg_restaurant = st.text_input("Restaurant / kitchen name (optional)")
                reg_password = st.text_input("Password", type="password",
                                             help=f"At least {MIN_PASSWORD_LENGTH} characters.")
                reg_confirm = st.text_input("Confirm password", type="password")
                register = st.form_submit_button("Create account", width="stretch")
            if register:
                if not reg_name.strip() or not reg_email.strip() or not reg_password:
                    st.error("Please fill in your name, email and password.")
                elif not EMAIL_PATTERN.match(reg_email.strip()):
                    st.error("Please enter a valid email address.")
                else:
                    problem = validate_new_password(reg_password, reg_confirm)
                    if problem:
                        st.error(problem)
                    else:
                        try:
                            database.create_user(reg_name, reg_email, role="admin",
                                                 password=reg_password,
                                                 restaurant_name=reg_restaurant)
                        except ValueError as error:
                            st.error(str(error))
                        else:
                            profile = database.get_user_profile(reg_email)
                            start_session(dict(profile) if profile is not None else {
                                "name": reg_name.strip(),
                                "email": reg_email.strip().lower(),
                                "role": "admin",
                                "restaurant_name": reg_restaurant,
                            })

        # ---------------------------------------------------------- password reset
        with tab_forgot:
            st.caption(
                "No email service is configured (offline demo), so the reset is verified "
                "against the registered name on the account."
            )
            with st.form("forgot_form"):
                forgot_email = st.text_input("Account email")
                forgot_name = st.text_input("Name on the account")
                forgot_password = st.text_input("New password", type="password")
                forgot_confirm = st.text_input("Confirm new password", type="password")
                reset = st.form_submit_button("Reset password", width="stretch")
            if reset:
                if not forgot_email.strip() or not forgot_name.strip() or not forgot_password:
                    st.error("Please fill in every field.")
                else:
                    problem = validate_new_password(forgot_password, forgot_confirm)
                    if problem:
                        st.error(problem)
                    else:
                        profile = database.get_user_profile(forgot_email)
                        if profile is None or profile["name"].strip().lower() != forgot_name.strip().lower():
                            st.error("We couldn't verify that email and name combination.")
                        else:
                            database.update_user_password(forgot_email, forgot_password)
                            st.success("Password updated. You can now sign in with the new password.")

        st.caption(
            "Privacy note: MealFlow360 stores only a name, email, role and optional "
            "restaurant name for each user."
        )


# ---------------------------------------------------------------- access control

if "user" not in st.session_state:
    show_login()
    st.stop()

current_user = st.session_state["user"]
role = current_user["role"]

# Page visibility per role. Settings is visible to every role (profile and
# appearance are personal); the page itself shows the admin-only sections only
# to administrators.
ROLE_PAGES = {
    "Dashboard": {"admin", "manager", "kitchen", "staff"},
    "Sales": {"admin", "manager", "staff"},
    "Plate Waste": {"admin", "manager", "kitchen", "staff"},
    "Kitchen Control Center": {"admin", "manager", "kitchen"},
    "Production": {"admin", "manager", "kitchen"},
    "Inventory": {"admin", "manager", "kitchen", "staff"},
    "Waste Tracking": {"admin", "manager", "kitchen", "staff"},
    "Impact Calculator": {"admin", "manager"},
    "Analytics": {"admin", "manager", "kitchen"},
    "Smart Forecast": {"admin", "manager", "kitchen"},
    "What-If Simulator": {"admin", "manager"},
    "Smart Recommendations": {"admin", "manager"},
    "Reports": {"admin", "manager"},
    "Food Master": {"admin", "manager", "kitchen"},
    "Settings": {"admin", "manager", "kitchen", "staff"},
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
restaurant_line = (
    f'<div class="fw-sub">🏠 {current_user["restaurant"]}</div>'
    if current_user.get("restaurant") else ""
)
st.sidebar.markdown(
    f"""
    <div class="fw-card" style="padding: 10px 14px; margin-bottom: 8px;">
        <div class="fw-label">Signed in</div>
        <div style="font-weight: 700; color: var(--fw-text);">{current_user['name']}</div>
        <div class="fw-sub">{role_display.get(role, role)}</div>
        {restaurant_line}
    </div>
    """,
    unsafe_allow_html=True,
)

ui.date_range_selector()

if st.sidebar.button("Log out", width="stretch"):
    st.session_state.pop("user", None)
    st.session_state.pop("fw_theme", None)
    st.rerun()

if not database.has_records():
    st.sidebar.warning("No data recorded yet. Load **The Urban Thali** demo from the Dashboard.")

st.sidebar.caption("MealFlow360 v2.0 — Sell Smart. Cook Right. Waste Less.")

# ---------------------------------------------------------------- navigation

page_definitions = [
    ("Overview", [
        ("pages/dashboard.py", "Dashboard", "🏠", True),
    ]),
    ("Sales & service", [
        ("pages/sales.py", "Sales", "🧾", False),
        ("pages/plate_waste.py", "Plate Waste", "🍽️", False),
    ]),
    ("Kitchen", [
        ("pages/kitchen_control.py", "Kitchen Control Center", "🍳", False),
        ("pages/production.py", "Production", "🍚", False),
        ("pages/inventory.py", "Inventory", "📦", False),
        ("pages/waste.py", "Waste Tracking", "♻️", False),
    ]),
    ("Insights", [
        ("pages/impact.py", "Impact Calculator", "🌍", False),
        ("pages/analytics.py", "Analytics", "📊", False),
        ("pages/forecast.py", "Smart Forecast", "📈", False),
        ("pages/simulator.py", "What-If Simulator", "🔮", False),
        ("pages/recommendations.py", "Smart Recommendations", "🤖", False),
        ("pages/reports.py", "Reports", "📄", False),
    ]),
    ("Administration", [
        ("pages/food_database.py", "Food Master", "🗃️", False),
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
