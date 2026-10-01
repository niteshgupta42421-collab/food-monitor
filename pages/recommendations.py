"""
FoodWaste360 - Smart Recommendations page.

Two sections:
  1. Waste Detective - observations computed from the recorded data
     (highest waste food, highest waste day, trends, repeated patterns).
  2. Smart Recommendations - what could be considered next, each item
     clearly separated into observation / recommendation / why it appeared.

Every statement is based on actual stored data; no unsupported claims.
"""

import streamlit as st

from services import recommendation_engine
from utils import ui

start, end = ui.get_date_range()
ui.page_header("Smart Recommendations", f"Data-based observations — {ui.range_label(start, end)}")

patterns = recommendation_engine.detect_patterns(start, end)
recommendations = recommendation_engine.generate_recommendations(start, end)

if not patterns and not recommendations:
    ui.empty_state(
        "There is not enough recorded data in the selected period to analyze. "
        "Add daily production and waste records, or load the demo data from the Dashboard "
        "and select the Last 30 days reporting period."
    )
    st.stop()

# ---------------------------------------------------------------- Waste Detective

ui.section("🔍 Waste Detective")
st.caption("What the recorded data shows for the selected period — observations only.")

if not patterns:
    ui.empty_state("No notable patterns were found in the selected period.")
else:
    left, right = st.columns(2)
    for index, pattern in enumerate(patterns):
        target = left if index % 2 == 0 else right
        with target:
            st.markdown(
                f"""
                <div class="fw-card" style="margin-bottom: 12px;">
                    <div class="fw-label">{pattern['title']}</div>
                    <div class="fw-sub" style="margin-top:6px; font-size:0.92rem;">{pattern['detail']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------- Recommendations

st.divider()
ui.section("💡 Smart Recommendations")
st.caption(
    "Observation = what the data shows. Recommendation = what could be considered. "
    "Each item explains why it appeared."
)

if not recommendations:
    ui.empty_state(
        "No recommendations were triggered for this period — the recorded data did not cross "
        "any of the app's attention levels."
    )
else:
    for item in recommendations:
        with st.container(border=True):
            col_a, col_b = st.columns([1.6, 1])
            with col_a:
                st.markdown(f"**Observation:** {item['observation']}")
                st.markdown(f"**Recommendation:** {item['recommendation']}")
            with col_b:
                st.caption(f"**Why this appeared:** {item['basis']}")

st.divider()
ui.method_note(
    "Attention levels used to trigger recommendations (e.g. one food contributing 20%+ of total "
    "waste, plate waste at 50%+ of total waste) are internal analysis thresholds, not scientific "
    "benchmarks. Wording deliberately distinguishes what the data shows from what could be tried; "
    "causes are not assumed unless the data supports them."
)
