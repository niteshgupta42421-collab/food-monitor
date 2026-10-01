"""
FoodWaste360 - Shared UI components.

Contains the global CSS, dashboard cards, data-type chips (Measured /
Calculated / Estimated / Simulated as required by section 25), the sidebar
brand block and the global date-range selector.
"""

from datetime import date, timedelta

import streamlit as st

from utils import formatting as fmt

# Chip styling matches the "Important Scientific Rules" (section 25):
# every value shown in the UI can carry a label explaining where it comes from.
_CHIP_CSS = {
    "measured": "fw-chip fw-chip-measured",
    "calculated": "fw-chip fw-chip-calculated",
    "estimated": "fw-chip fw-chip-estimated",
    "simulated": "fw-chip fw-chip-simulated",
}

_CHIP_LABEL = {
    "measured": "MEASURED",
    "calculated": "CALCULATED",
    "estimated": "ESTIMATED",
    "simulated": "SIMULATED",
}


def inject_global_css() -> None:
    """Apply the app-wide stylesheet (call once per page run)."""
    st.markdown(
        """
        <style>
        .fw-card {
            background: #FFFFFF;
            border: 1px solid #E3EBE6;
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 1px 2px rgba(16, 42, 30, 0.04);
            height: 100%;
        }
        .fw-card .fw-label {
            font-size: 0.76rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: #6B7F74;
            font-weight: 700;
        }
        .fw-card .fw-value {
            font-size: 1.5rem;
            font-weight: 750;
            color: #12291E;
            margin-top: 6px;
            line-height: 1.2;
        }
        .fw-card .fw-sub {
            font-size: 0.79rem;
            color: #7B8E84;
            margin-top: 5px;
        }
        .fw-chip {
            display: inline-block;
            font-size: 0.62rem;
            font-weight: 800;
            padding: 2px 8px;
            border-radius: 999px;
            letter-spacing: 0.06em;
            vertical-align: middle;
            margin-left: 6px;
        }
        .fw-chip-measured   { background: #E3F4EA; color: #1B8A5A; }
        .fw-chip-calculated { background: #E4EFFB; color: #2368B1; }
        .fw-chip-estimated  { background: #FCF0DC; color: #B26A00; }
        .fw-chip-simulated  { background: #EFE7FB; color: #6B3FA0; }

        .fw-flow {
            background: #FFFFFF;
            border: 1px solid #E3EBE6;
            border-radius: 14px;
            padding: 14px 16px;
        }
        .fw-flow-step {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 7px 12px;
            border-radius: 10px;
            background: #F4F9F6;
        }
        .fw-flow-arrow {
            text-align: center;
            color: #1B8A5A;
            line-height: 1.4;
            padding: 1px 0;
        }
        .fw-flow-label {
            font-size: 0.76rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: #6B7F74;
            font-weight: 700;
        }
        .fw-flow-value {
            margin-left: auto;
            font-weight: 750;
            color: #12291E;
            font-size: 1.02rem;
        }
        .fw-flow-split {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px dashed #D6E5DB;
            text-align: center;
            color: #486257;
            font-size: 0.85rem;
        }

        .fw-page-title { font-size: 1.7rem; font-weight: 800; color: #12291E; margin-bottom: 0; }
        .fw-page-sub   { color: #6B7F74; font-size: 0.92rem; margin-top: 2px; margin-bottom: 10px; }
        .fw-section    { font-size: 1.12rem; font-weight: 750; color: #1B3A2C; margin-top: 12px; }

        .fw-hero {
            background: linear-gradient(135deg, #1B8A5A 0%, #0F5D3C 60%, #0B472E 100%);
            border-radius: 18px;
            padding: 26px 30px;
            color: #FFFFFF;
            margin-bottom: 14px;
        }
        .fw-hero h1 { color: #FFFFFF; margin: 0; font-size: 1.9rem; }
        .fw-hero p  { margin: 6px 0 0 0; opacity: 0.92; }

        .fw-empty {
            border: 1px dashed #BCD4C6;
            border-radius: 14px;
            background: #F4F9F6;
            padding: 18px 20px;
            color: #486257;
        }
        .fw-method {
            background: #F7FAF8;
            border: 1px solid #E3EBE6;
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 0.88rem;
            color: #40584D;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def page_header(title: str, subtitle: str = "") -> None:
    """Standard page title block."""
    st.markdown(f'<div class="fw-page-title">{title}</div>', unsafe_allow_html=True)
    if subtitle:
        st.markdown(f'<div class="fw-page-sub">{subtitle}</div>', unsafe_allow_html=True)


def section(title: str) -> None:
    """Section heading used between blocks of content."""
    st.markdown(f'<div class="fw-section">{title}</div>', unsafe_allow_html=True)


def chip(kind: str) -> str:
    """Return the HTML for a data-type chip (measured/calculated/estimated/simulated)."""
    css = _CHIP_CSS.get(kind, _CHIP_CSS["estimated"])
    label = _CHIP_LABEL.get(kind, kind.upper())
    return f'<span class="{css}">{label}</span>'


def metric_card(label: str, value: str, sub: str = "", kind: str | None = None) -> None:
    """
    Render one dashboard card.

    `kind` optionally adds a data-type chip: 'measured', 'calculated',
    'estimated' or 'simulated'.
    """
    chip_html = chip(kind) if kind else ""
    sub_html = f'<div class="fw-sub">{sub}</div>' if sub else ""
    st.markdown(
        f"""
        <div class="fw-card">
            <div class="fw-label">{label}{chip_html}</div>
            <div class="fw-value">{value}</div>
            {sub_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def food_flow(totals: dict) -> None:
    """
    Render the prepared -> served -> consumed -> waste flow (spec section 7).

    `totals` is the period_totals() result. Values arrive as raw numbers and
    are formatted exactly once, here.
    """
    steps = [
        ("🍚", "Food prepared", totals["prepared"]),
        ("🍽️", "Food served", totals["served"]),
        ("✅", "Food consumed", totals["consumed"]),
        ("♻️", "Food waste", totals["waste"]),
    ]
    lines = []
    for index, (icon, label, value) in enumerate(steps):
        lines.append(
            '<div class="fw-flow-step">'
            f'<span class="fw-flow-icon">{icon}</span>'
            f'<span class="fw-flow-label">{label}</span>'
            f'<span class="fw-flow-value">{fmt.format_kg(value)}</span>'
            "</div>"
        )
        if index < len(steps) - 1:
            lines.append('<div class="fw-flow-arrow">↓</div>')
    breakdown = (
        '<div class="fw-flow-split">'
        f'Kitchen waste {fmt.format_kg(totals["kitchen"])} + '
        f'Serving waste {fmt.format_kg(totals["serving"])} + '
        f'Plate waste {fmt.format_kg(totals["plate"])}'
        "</div>"
    )
    st.markdown('<div class="fw-flow">' + "".join(lines) + breakdown + "</div>", unsafe_allow_html=True)


def empty_state(message: str) -> None:
    """Friendly empty-state box."""
    st.markdown(f'<div class="fw-empty">{message}</div>', unsafe_allow_html=True)


def method_note(text: str) -> None:
    """Small methodology note box."""
    st.markdown(f'<div class="fw-method">{text}</div>', unsafe_allow_html=True)


def sidebar_brand() -> None:
    """Brand block shown at the top of the sidebar."""
    st.sidebar.markdown(
        """
        <div style="padding: 4px 0 10px 0;">
            <div style="font-size: 1.35rem; font-weight: 800; color: #12291E;">🍽️ FoodWaste360</div>
            <div style="font-size: 0.8rem; color: #6B7F74;">Measure. Understand. Reduce.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- date range

RANGE_PRESETS = ["Today", "Yesterday", "Last 7 days", "Last 30 days", "Custom"]


def date_range_selector() -> None:
    """
    Render the global date-range selector in the sidebar and store the result
    in session state so every analytics page reads the same period.
    """
    today = date.today()
    st.sidebar.markdown("##### 📅 Reporting period")
    preset = st.sidebar.selectbox("Period", RANGE_PRESETS, key="fw_range_preset", label_visibility="collapsed")

    if preset == "Today":
        start = end = today
    elif preset == "Yesterday":
        start = end = today - timedelta(days=1)
    elif preset == "Last 7 days":
        start, end = today - timedelta(days=6), today
    elif preset == "Last 30 days":
        start, end = today - timedelta(days=29), today
    else:  # Custom
        start = st.sidebar.date_input("Start date", value=today - timedelta(days=13), key="fw_range_custom_start")
        end = st.sidebar.date_input("End date", value=today, key="fw_range_custom_end")
        if start > end:
            st.sidebar.error("Start date must be on or before end date. Showing today instead.")
            start = end = today

    st.session_state["fw_range_start"] = start
    st.session_state["fw_range_end"] = end


def get_date_range() -> tuple[date, date]:
    """Return the currently selected global date range (defaults to last 7 days)."""
    today = date.today()
    start = st.session_state.get("fw_range_start", today - timedelta(days=6))
    end = st.session_state.get("fw_range_end", today)
    return start, end


def range_label(start: date, end: date) -> str:
    """Human-readable label for a date range."""
    if start == end:
        return start.strftime("%d %b %Y")
    return f"{start.strftime('%d %b %Y')} → {end.strftime('%d %b %Y')}"
