"""
MealFlow360 - Kitchen Control Center.

The live service view for the kitchen, for today:

  * prepared / sold / remaining / sell-through at a glance,
  * the replenishment planner - "What to cook next?" with the rule
        recommended production = max(expected demand - available food, 0)
    where expected demand is the kitchen's own entry, or the transparent
    sales-history forecast (labelled Estimated) when nothing is entered,
  * smart alerts: out of stock, low stock and low sell-through.

Made-to-order foods are never "out of stock" (they are cooked per order), so
they are excluded from stock recommendations.
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database
from services import forecasting
from services import stock as stock_service
from utils import formatting as fmt, ui

ui.page_header(
    "🍳 Kitchen Control Center",
    "Live service view for today: what is selling, what remains, what to cook "
    "next, and where the risks are. Updates as sales are recorded.",
)

flash = st.session_state.pop("fw_flash", None)
if flash:
    st.success(flash)

day = date.today()
frame = stock_service.day_stock_frame(day)

if frame.empty:
    ui.empty_state(
        f"No production or sales recorded yet today ({day.strftime('%d %b %Y')}). "
        "Record production on the Production page, or load the demo restaurant "
        "from the Dashboard to explore."
    )
    st.stop()

forecast = forecasting.demand_forecast(history_days=14, buffer_pct=10.0, target_date=day)
forecast_by_id = forecast.set_index("food_id") if not forecast.empty else None
stock_by_id = frame.set_index("food_id")

total_prepared = float(frame["prepared"].sum())
total_available = float(frame["available"].clip(lower=0).sum())
total_sold = float(frame["sold_kg"].sum())
total_remaining = float(frame["remaining_kg"].clip(lower=0).sum())
sell_through = forecasting.sell_through_pct(total_sold, total_available)

col1, col2, col3, col4 = st.columns(4)
with col1:
    ui.metric_card("Prepared today", fmt.format_kg(total_prepared),
                   sub="from the kitchen", kind="measured")
with col2:
    ui.metric_card("Sold today", fmt.format_kg(total_sold),
                   sub="from recorded sales", kind="calculated")
with col3:
    ui.metric_card("Remaining now", fmt.format_kg(total_remaining),
                   sub="still available to sell", kind="calculated")
with col4:
    ui.metric_card("Sell-through", fmt.format_percentage(sell_through),
                   sub="food sold ÷ food available", kind="calculated")

tab_next, tab_alerts = st.tabs(["🔥 What to cook next?", "🚦 Stock & alerts"])

# ---------------------------------------------------------------- replenishment

def _replenishment_table() -> pd.DataFrame:
    """One row per active food: expected demand, stock now, recommended cook."""
    active = database.get_food_items_df()
    active = active[active["active"] == 1].reset_index(drop=True)
    rows = []
    for _, food in active.iterrows():
        food_id = int(food["id"])
        stock_row = stock_by_id.loc[food_id] if food_id in stock_by_id.index else None
        db_expected = float(stock_row["expected_demand"]) if stock_row is not None else 0.0
        forecast_kg = 0.0
        if forecast_by_id is not None and food_id in forecast_by_id.index:
            forecast_kg = float(forecast_by_id.loc[food_id]["expected_kg"])
        if db_expected > 0:
            expected, source = db_expected, "Kitchen entry"
        elif forecast_kg > 0:
            expected, source = forecast_kg, "Forecast (estimated)"
        else:
            expected, source = 0.0, "No history yet"
        available = float(stock_row["available"]) if stock_row is not None else 0.0
        portion = float(food["portion_size_g"] or 0)
        made_to_order = food["production_mode"] == "made_to_order"
        recommended = 0.0 if made_to_order else max(expected - available, 0.0)
        rows.append({
            "food_id": food_id,
            "Food": food["food_name"],
            "Expected demand (kg)": round(expected, 2),
            "Source": "Made to order" if made_to_order else source,
            "Available now (kg)": round(available, 2),
            "Recommended to cook (kg)": round(recommended, 2),
            "Portions (est.)": round(recommended / (portion / 1000.0), 1) if portion > 0 and recommended > 0 else float("nan"),
        })
    return pd.DataFrame(rows)


with tab_next:
    replenishment = _replenishment_table()

    if replenishment.empty:
        ui.empty_state("No active food items. Activate foods in the Food Master first.")
    else:
        ui.section("Replenishment planner")
        st.caption(
            "Rule: recommended production = expected demand − available food (never negative). "
            "The expected demand comes from your kitchen entry; edit it below to override the forecast."
        )
        edited = st.data_editor(
            replenishment,
            hide_index=True,
            width="stretch",
            disabled=["food_id", "Food", "Source", "Available now (kg)",
                      "Recommended to cook (kg)", "Portions (est.)"],
            column_config={
                "food_id": None,
                "Expected demand (kg)": st.column_config.NumberColumn(
                    min_value=0.0, step=0.5, format="%.2f kg",
                    help="How much of this food you expect to sell today (kg). Overrides the forecast.",
                ),
                "Recommended to cook (kg)": st.column_config.NumberColumn(
                    format="%.2f kg", help="max(expected demand − available, 0)"),
                "Portions (est.)": st.column_config.NumberColumn(
                    format="%.1f", help="estimated selling portions for the recommended quantity"),
            },
            key="replenish_editor",
        )

        if st.button("Save demand plan", width="stretch", key="cc_save_demand"):
            changed = 0
            for (_, edited_row), (_, original_row) in zip(edited.iterrows(), replenishment.iterrows()):
                new_value = float(edited_row["Expected demand (kg)"]) if pd.notna(edited_row["Expected demand (kg)"]) else 0.0
                if abs(new_value - float(original_row["Expected demand (kg)"])) > 1e-9:
                    database.set_expected_demand(day, int(edited_row["food_id"]), new_value)
                    changed += 1
            if changed:
                st.session_state["fw_flash"] = f"Demand plan saved ({changed} change(s))."
                st.rerun()
            else:
                st.info("No changes to save — edit “Expected demand (kg)” to override the forecast.")

        ui.section("What to cook next")
        cook = replenishment[replenishment["Recommended to cook (kg)"] > 0].sort_values(
            "Recommended to cook (kg)", ascending=False
        )
        if cook.empty:
            st.success("Nothing extra needs cooking right now — current stock covers the expected demand.")
        else:
            columns = st.columns(3)
            for index, (_, row) in enumerate(cook.iterrows()):
                portions = (
                    f" · ≈ {fmt.format_number(row['Portions (est.)'], decimals=1)} portions"
                    if pd.notna(row["Portions (est.)"]) else ""
                )
                with columns[index % 3]:
                    ui.metric_card(
                        f"🔥 {row['Food']}",
                        f"Cook {fmt.format_kg(row['Recommended to cook (kg)'])}",
                        sub=(f"expected {fmt.format_kg(row['Expected demand (kg)'])} · "
                             f"available {fmt.format_kg(row['Available now (kg)'])}{portions}"),
                    )

        ui.method_note(
            "Where 'expected demand' comes from: your kitchen entry if one is saved, otherwise "
            "a transparent forecast from your own recorded sales (recent daily average blended "
            "with the same-weekday average, +10% buffer) — always labelled Estimated. "
            "Foods in made-to-order mode are cooked per order and never recommended here."
        )

# ---------------------------------------------------------------- alerts

with tab_alerts:
    critical, warnings, info = [], [], []
    for _, row in frame.iterrows():
        made_to_order = row["production_mode"] == "made_to_order"
        forecast_kg = 0.0
        if forecast_by_id is not None and int(row["food_id"]) in forecast_by_id.index:
            forecast_kg = float(forecast_by_id.loc[int(row["food_id"])]["expected_kg"])
        expected = max(float(row["expected_demand"]), forecast_kg)
        if not made_to_order and row["remaining_kg"] <= 1e-9 and expected > 0:
            critical.append(
                f"🔴 **{row['food_name']} is out of stock** — about "
                f"{fmt.format_kg(expected)} of expected demand is still to serve."
            )
        elif not made_to_order and row["status"] == stock_service.STATUS_LOW:
            units = fmt.format_number(row["remaining_units"], decimals=1) if row["remaining_units"] is not None else "—"
            warnings.append(
                f"🟡 **{row['food_name']} is running low** — {units} {row['unit']}(s) left, "
                f"at or below the low-stock threshold ({fmt.format_number(row['low_stock_threshold'])})."
            )
        if (not made_to_order and row["available"] > 0
                and row["sold_kg"] / row["available"] < 0.40 and row["remaining_kg"] > 0):
            share = row["sold_kg"] / row["available"] * 100.0
            info.append(
                f"📉 Low sell-through for **{row['food_name']}**: only "
                f"{fmt.format_percentage(share)} of available food has sold, "
                f"{fmt.format_kg(row['remaining_kg'])} still available — consider a promotion, "
                "buffet use, or a smaller next batch."
            )

    if not (critical or warnings or info):
        st.success("✅ No alerts — stock levels look healthy for the current demand.")
    else:
        shown = 0
        for message in critical:
            if shown < 10:
                st.error(message)
                shown += 1
        for message in warnings:
            if shown < 10:
                st.warning(message)
                shown += 1
        for message in info:
            if shown < 10:
                st.info(message)
                shown += 1
        overflow = (len(critical) + len(warnings) + len(info)) - shown
        if overflow > 0:
            st.caption(f"… and {overflow} more alert(s).")

    ui.section("Today per food")
    today = pd.DataFrame([
        {
            "Food": row["food_name"],
            "Status": stock_service.status_text(row["status"]),
            "Prepared (kg)": round(float(row["prepared"]), 2),
            "Sold (kg)": round(float(row["sold_kg"]), 2),
            "Remaining (kg)": round(float(row["remaining_kg"]), 2),
            "Portions left": round(float(row["remaining_units"]), 1) if row["remaining_units"] is not None else float("nan"),
            "Planned demand (kg)": round(float(row["expected_demand"]), 2),
        }
        for _, row in frame.iterrows()
    ])
    st.dataframe(
        today, hide_index=True, width="stretch",
        column_config={
            "Prepared (kg)": st.column_config.NumberColumn(format="%.2f kg"),
            "Sold (kg)": st.column_config.NumberColumn(format="%.2f kg"),
            "Remaining (kg)": st.column_config.NumberColumn(format="%.2f kg"),
            "Portions left": st.column_config.NumberColumn(format="%.1f"),
            "Planned demand (kg)": st.column_config.NumberColumn(format="%.2f kg"),
        },
    )
    st.caption(
        "Status rule: 🔴 nothing left to sell · 🟡 remaining portions at or below the food's "
        "low-stock threshold · 🟢 healthy. Made-to-order foods are excluded from stock alerts."
    )
