"""
MealFlow360 - Shared UI components.

Contains the global CSS (driven by the theme variables injected in
utils/theme.py), dashboard cards, data-type chips (Measured / Calculated /
Estimated / Simulated), the sidebar brand block and the global date-range
selector.
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
    """Apply the app-wide stylesheet (call once per page run, after theme.apply_css)."""
    st.markdown(
        """
        <style>
        .fw-card {
            background: var(--fw-card);
            border: 1px solid var(--fw-border);
            border-radius: 14px;
            padding: 16px 18px;
            box-shadow: 0 1px 2px rgba(16, 42, 30, 0.05);
            height: 100%;
        }
        .fw-card .fw-label {
            font-size: 0.76rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--fw-muted);
            font-weight: 700;
        }
        .fw-card .fw-value {
            font-size: 1.5rem;
            font-weight: 750;
            color: var(--fw-text);
            margin-top: 6px;
            line-height: 1.2;
        }
        .fw-card .fw-sub {
            font-size: 0.79rem;
            color: var(--fw-muted);
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
        .fw-chip-measured   { background: var(--fw-chip_measured_bg); color: var(--fw-chip_measured_fg); }
        .fw-chip-calculated { background: var(--fw-chip_calculated_bg); color: var(--fw-chip_calculated_fg); }
        .fw-chip-estimated  { background: var(--fw-chip_estimated_bg); color: var(--fw-chip_estimated_fg); }
        .fw-chip-simulated  { background: var(--fw-chip_simulated_bg); color: var(--fw-chip_simulated_fg); }

        .fw-flow {
            background: var(--fw-card);
            border: 1px solid var(--fw-border);
            border-radius: 14px;
            padding: 14px 16px;
        }
        .fw-flow-step {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 7px 12px;
            border-radius: 10px;
            background: var(--fw-flow_step_bg);
        }
        .fw-flow-arrow {
            text-align: center;
            color: var(--fw-accent);
            line-height: 1.4;
            padding: 1px 0;
        }
        .fw-flow-label {
            font-size: 0.76rem;
            letter-spacing: 0.05em;
            text-transform: uppercase;
            color: var(--fw-muted);
            font-weight: 700;
        }
        .fw-flow-value {
            margin-left: auto;
            font-weight: 750;
            color: var(--fw-text);
            font-size: 1.02rem;
        }
        .fw-flow-split {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px dashed var(--fw-border);
            text-align: center;
            color: var(--fw-text_soft);
            font-size: 0.85rem;
        }
        .fw-flow-branch {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 4px 12px 4px 30px;
            color: var(--fw-muted);
            font-size: 0.85rem;
        }
        .fw-flow-branch .fw-flow-value {
            margin-left: auto;
            font-weight: 650;
            color: var(--fw-muted);
            font-size: 0.9rem;
        }
        .fw-flow-check {
            margin-top: 6px;
            text-align: center;
            font-size: 0.8rem;
            color: var(--fw-text_soft);
        }

        .fw-page-title { font-size: 1.7rem; font-weight: 800; color: var(--fw-text); margin-bottom: 0; }
        .fw-page-sub   { color: var(--fw-muted); font-size: 0.92rem; margin-top: 2px; margin-bottom: 10px; }
        .fw-section    { font-size: 1.12rem; font-weight: 750; color: var(--fw-text); margin-top: 12px; }

        .fw-hero {
            background: linear-gradient(135deg, var(--fw-hero_from) 0%, var(--fw-hero_to) 100%);
            border-radius: 18px;
            padding: 26px 30px;
            color: #FFFFFF;
            margin-bottom: 14px;
        }
        .fw-hero h1 { color: #FFFFFF; margin: 0; font-size: 1.9rem; }
        .fw-hero p  { margin: 6px 0 0 0; opacity: 0.92; }

        .fw-empty {
            border: 1px dashed var(--fw-border);
            border-radius: 14px;
            background: var(--fw-flow_step_bg);
            padding: 18px 20px;
            color: var(--fw-text_soft);
        }
        .fw-method {
            background: var(--fw-flow_step_bg);
            border: 1px solid var(--fw-border);
            border-radius: 12px;
            padding: 12px 16px;
            font-size: 0.88rem;
            color: var(--fw-text_soft);
        }
        .fw-status-ok   { color: #1B8A5A; font-weight: 750; }
        .fw-status-low  { color: #B26A00; font-weight: 750; }
        .fw-status-crit { color: #C0392B; font-weight: 750; }
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
    Render the single accounting flow defined in services/accounting.py:

        prepared -> available for service -> served -> consumed,
        with kitchen / serving / plate waste branching off at each step.

    `totals` is the period_totals() result. Values arrive as raw numbers and
    are formatted exactly once, here.
    """
    segments = [
        ("step", "🍚", "Food prepared", totals["prepared"]),
        ("branch", "↳", "Kitchen waste (before service)", totals["kitchen"]),
        ("arrow", "", "", None),
        ("step", "🥘", "Available for service", totals["available"]),
        ("branch", "↳", "Serving waste (at the counter)", totals["serving"]),
        ("arrow", "", "", None),
        ("step", "🍽️", "Food served", totals["served"]),
        ("branch", "↳", "Plate waste (left uneaten)", totals["plate"]),
        ("arrow", "", "", None),
        ("step", "✅", "Food consumed", totals["consumed"]),
    ]
    lines = []
    for kind, icon, label, value in segments:
        if kind == "arrow":
            lines.append('<div class="fw-flow-arrow">↓</div>')
        elif kind == "branch":
            lines.append(
                '<div class="fw-flow-branch">'
                f'<span>{icon}</span><span>{label}</span>'
                f'<span class="fw-flow-value">{fmt.format_kg(value)}</span>'
                "</div>"
            )
        else:
            lines.append(
                '<div class="fw-flow-step">'
                f'<span class="fw-flow-icon">{icon}</span>'
                f'<span class="fw-flow-label">{label}</span>'
                f'<span class="fw-flow-value">{fmt.format_kg(value)}</span>'
                "</div>"
            )
    waste_line = (
        f"Total waste {fmt.format_kg(totals['waste'])} "
        f"(kitchen + serving + plate) · Waste percentage {fmt.format_percentage(totals['waste_pct'])}"
    )
    if round(abs(totals["unaccounted"]), 2) == 0.0:
        # The model balances by construction; the check makes the identity visible.
        balanced_sum = totals["kitchen"] + totals["serving"] + totals["plate"] + totals["consumed"]
        check_line = (
            "Accounting check: "
            f"kitchen {fmt.format_kg(totals['kitchen'])} + serving {fmt.format_kg(totals['serving'])} + "
            f"plate {fmt.format_kg(totals['plate'])} + consumed {fmt.format_kg(totals['consumed'])} = "
            f"{fmt.format_kg(balanced_sum)} ✓"
        )
    else:
        check_line = (
            f"Unaccounted / measurement difference: {fmt.format_kg(totals['unaccounted'])} — "
            "the accounting does not balance; please review the recorded data."
        )
    st.markdown(
        '<div class="fw-flow">'
        + "".join(lines)
        + f'<div class="fw-flow-split">{waste_line}</div>'
        + f'<div class="fw-flow-check">{check_line}</div>'
        + "</div>",
        unsafe_allow_html=True,
    )


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
            <div style="font-size: 1.35rem; font-weight: 800; color: var(--fw-text);">🍽️ MealFlow360</div>
            <div style="font-size: 0.8rem; color: var(--fw-muted);">Sell Smart. Cook Right. Waste Less.</div>
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
