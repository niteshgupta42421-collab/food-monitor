"""
MealFlow360 - What-If Simulator page.

Simulate operational changes and compare the current scenario with a
simulated one. Every result here is labelled SIMULATED - a scenario estimate
based on historical data, never presented as a guaranteed saving.
"""

import streamlit as st

from services import calculations, simulator
from utils import charts, formatting as fmt, ui

start, end = ui.get_date_range()
ui.page_header("What If? — Simulator", f"Scenario estimates based on historical data — {ui.range_label(start, end)}")

st.warning(
    "**Results on this page are simulated.** They are scenario estimates based on your recorded "
    "history (labelled SIMULATED below), not guaranteed savings or predictions."
)

if calculations.period_totals(start, end)["days_with_data"] == 0:
    ui.empty_state(
        "Not enough recorded data in the selected period to simulate scenarios. "
        "Add daily records or load the demo data from the Dashboard."
    )
    st.stop()

# ---------------------------------------------------------------- scenario picker

SCENARIOS = [
    "Reduce / increase production of one food",
    "Change plate waste (serving-size effect)",
    "Change customer count",
    "Set a target waste percentage",
]
scenario = st.radio("Choose a scenario", SCENARIOS, horizontal=False)

rows, meta = None, {"ok": False, "error": "Configure the scenario below."}

production = calculations.production_by_food(start, end)

if scenario == SCENARIOS[0]:
    if production.empty:
        ui.empty_state("No production was recorded for this period.")
        st.stop()
    col_a, col_b = st.columns(2)
    with col_a:
        food_name = st.selectbox("Food item", production["food_name"].tolist())
    with col_b:
        pct = st.slider("Production change (%)", min_value=-50, max_value=50, value=-10, step=5,
                        help="Negative values reduce production; e.g. -10 means 10% less.")
    if st.button("Run simulation", type="primary"):
        food_id = int(production[production["food_name"] == food_name]["food_id"].iloc[0])
        rows, meta = simulator.scenario_production_change(food_id, float(pct), start, end)

elif scenario == SCENARIOS[1]:
    pct = st.slider("Change in plate waste (%)", min_value=-50, max_value=50, value=-25, step=5,
                    help="Reflects smaller/bigger portions or less/more leftover per customer.")
    if st.button("Run simulation", type="primary"):
        rows, meta = simulator.scenario_plate_waste_change(float(pct), start, end)

elif scenario == SCENARIOS[2]:
    pct = st.slider("Change in customers served (%)", min_value=-50, max_value=50, value=10, step=5)
    if st.button("Run simulation", type="primary"):
        rows, meta = simulator.scenario_customers_change(float(pct), start, end)

else:  # target waste percentage
    totals = calculations.period_totals(start, end)
    target = st.slider(
        "Target waste percentage (% of prepared food)", min_value=0.0, max_value=30.0,
        value=round(max(totals["waste_pct"] - 2, 0.0), 1), step=0.5,
        help=f"Current period waste percentage: {fmt.format_percentage(totals['waste_pct'])}",
    )
    if st.button("Run simulation", type="primary"):
        rows, meta = simulator.scenario_target_waste_rate(float(target), start, end)

# ---------------------------------------------------------------- results

if meta.get("ok"):
    st.divider()
    ui.section("Current vs simulated")

    st.markdown(
        f'<div class="fw-method">{ui.chip("simulated")} {meta["headline"]}</div>',
        unsafe_allow_html=True,
    )

    table = rows.copy()
    display = table.copy()
    display["Current"] = display["Current"].map(lambda v: "—" if v is None or v != v else fmt.format_number(v))
    display["Simulated"] = display["Simulated"].map(lambda v: "—" if v is None or v != v else fmt.format_number(v))
    display["Change"] = display["Change"].map(lambda v: "—" if v is None or v != v else f"{v:+,.2f}")
    st.dataframe(display, width="stretch", hide_index=True)

    # Small comparative chart for the two quantity rows (kg-based metrics).
    quantity_rows = table[table["Metric"].str.contains(r"\(kg\)|Customers", regex=True, na=False)]
    quantity_rows = quantity_rows[quantity_rows["Simulated"].notna()]
    if not quantity_rows.empty:
        import plotly.graph_objects as go

        fig = go.Figure()
        fig.add_bar(x=quantity_rows["Metric"], y=quantity_rows["Current"], name="Current", marker_color=charts.GRAY)
        fig.add_bar(x=quantity_rows["Metric"], y=quantity_rows["Simulated"], name="Simulated",
                    marker_color=charts.PURPLE)
        fig.update_layout(barmode="group")
        fig.update_layout(title=dict(text="Current vs simulated (quantity comparison)", font=dict(size=15)),
                          height=360, margin=dict(l=10, r=10, t=48, b=10),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                          font=dict(color="#2E4338"))
        fig.update_xaxes(showgrid=False)
        fig.update_yaxes(showgrid=True, gridcolor="#EAF1EC")
        st.plotly_chart(fig, width="stretch")

    with st.expander("📝 Assumptions used in this simulation", expanded=True):
        for assumption in meta["assumptions"]:
            st.markdown(f"- {assumption}")

elif meta.get("error"):
    st.info(meta["error"])

ui.method_note(
    "Simulations reuse the organization's own recorded waste ratios and the documented impact "
    "factors. They do not model causes (for example why leftovers happen) and must not be "
    "presented as guaranteed results."
)
