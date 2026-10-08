"""
MealFlow360 - Theme system.

Central definition of every colour used by the app. Components never hard-code
colours; they reference the CSS variables injected here (--fw-*), so switching
the theme changes the whole interface at once.

Available themes (Settings -> Appearance -> Theme):
  * light - clean restaurant management interface (default)
  * dark  - modern dark dashboard for night operations
  * warm  - premium food/restaurant visual style

The chosen theme is stored per user in the database (users.theme) and applied
on every page run by apply_css().
"""

import streamlit as st

DEFAULT_THEME = "light"

THEMES: dict[str, dict] = {
    "light": {
        "label": "Light",
        "bg": "#FFFFFF",
        "bg_soft": "#F4F7F5",
        "card": "#FFFFFF",
        "border": "#E3EBE6",
        "text": "#12291E",
        "text_soft": "#40584D",
        "muted": "#6B7F74",
        "accent": "#1B8A5A",
        "accent_dark": "#0F5D3C",
        "accent_soft": "#E3F4EA",
        "flow_step_bg": "#F4F9F6",
        "hero_from": "#1B8A5A",
        "hero_to": "#0B472E",
        "chip_measured_bg": "#E3F4EA", "chip_measured_fg": "#1B8A5A",
        "chip_calculated_bg": "#E4EFFB", "chip_calculated_fg": "#2368B1",
        "chip_estimated_bg": "#FCF0DC", "chip_estimated_fg": "#B26A00",
        "chip_simulated_bg": "#EFE7FB", "chip_simulated_fg": "#6B3FA0",
    },
    "dark": {
        "label": "Dark",
        "bg": "#0F1A14",
        "bg_soft": "#16241C",
        "card": "#16241C",
        "border": "#263A2E",
        "text": "#E8F1EA",
        "text_soft": "#B7C9BE",
        "muted": "#8FA79A",
        "accent": "#35C68A",
        "accent_dark": "#1B8A5A",
        "accent_soft": "#12352A",
        "flow_step_bg": "#1B2C22",
        "hero_from": "#14503A",
        "hero_to": "#0A2419",
        "chip_measured_bg": "#12352A", "chip_measured_fg": "#5BD9A5",
        "chip_calculated_bg": "#14304A", "chip_calculated_fg": "#7CB8F0",
        "chip_estimated_bg": "#3A2C12", "chip_estimated_fg": "#E8B160",
        "chip_simulated_bg": "#2A1F44", "chip_simulated_fg": "#B79BE8",
    },
    "warm": {
        "label": "Warm food",
        "bg": "#FFF9F0",
        "bg_soft": "#FBF1E2",
        "card": "#FFFFFF",
        "border": "#EADDC8",
        "text": "#3A2A1A",
        "text_soft": "#5C4A35",
        "muted": "#8A7A63",
        "accent": "#C05621",
        "accent_dark": "#9C4221",
        "accent_soft": "#FCEBDB",
        "flow_step_bg": "#FDF3E7",
        "hero_from": "#D97706",
        "hero_to": "#92400E",
        "chip_measured_bg": "#E7F3E0", "chip_measured_fg": "#3F7D20",
        "chip_calculated_bg": "#FCEBDB", "chip_calculated_fg": "#9C4221",
        "chip_estimated_bg": "#FDF0CE", "chip_estimated_fg": "#946200",
        "chip_simulated_bg": "#F0E7FB", "chip_simulated_fg": "#6B3FA0",
    },
}


def theme_names() -> list[str]:
    """Ordered theme keys."""
    return list(THEMES.keys())


def theme_label(key: str) -> str:
    """Human-readable theme name."""
    return THEMES.get(key, THEMES[DEFAULT_THEME])["label"]


def palette(key: str) -> dict:
    """Palette for a theme key, falling back to the default theme."""
    return THEMES.get(key, THEMES[DEFAULT_THEME])


def _variables(p: dict) -> str:
    """Render the palette as CSS custom properties."""
    lines = []
    for name, value in p.items():
        if name == "label":
            continue
        lines.append(f"  --fw-{name}: {value};")
    return "\n".join(lines)


def apply_css(key: str) -> None:
    """
    Inject the active theme: the --fw-* variables used by every component,
    plus overrides of Streamlit's own colour variables so built-in widgets
    (inputs, sidebar, tabs) follow the theme too.
    """
    p = palette(key)
    st.markdown(
        f"""
        <style>
        :root {{
{_variables(p)}
        }}
        .stApp, [data-testid="stSidebar"] {{
            --background-color: {p['bg']};
            --secondary-background-color: {p['bg_soft']};
            --text-color: {p['text']};
            --primary-color: {p['accent']};
        }}
        .stApp {{ background-color: {p['bg']}; color: {p['text']}; }}
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{ color: {p['text']}; }}
        [data-testid="stSidebar"] {{ background-color: {p['bg_soft']}; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- session helpers

def active_key() -> str:
    """Theme key active for this session (session override wins over profile)."""
    key = st.session_state.get("fw_theme", DEFAULT_THEME)
    return key if key in THEMES else DEFAULT_THEME


def set_active(key: str) -> None:
    """Set the theme for the current session (persisted by the caller)."""
    if key in THEMES:
        st.session_state["fw_theme"] = key
