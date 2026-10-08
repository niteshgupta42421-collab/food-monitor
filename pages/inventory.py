"""
MealFlow360 - Inventory / Remaining Food page.

Shows, for one chosen day, how much of every food remains after sales, with
clear status indicators (🟢 healthy, 🟡 low, 🔴 out) and the carry-over
planner for food kept for the next service.

Important accounting rule: carry-over (reusable food kept for the next
service) is NOT waste. Total waste stays kitchen + serving + plate waste,
each kilogram counted once.
"""

from datetime import date

import pandas as pd
import streamlit as st

from database import database
from services import stock as stock_service
from utils import formatting as fmt, ui

ui.page_header(
    "📦 Inventory & Remaining Food",
    "Stock left after sales for one day - updated automatically as sales are "
    "recorded. Food kept for the next service (carry-over) is planned here and "
    "is never counted as waste.",
)

flash = st.session_state.pop("fw_flash", None)
if flash:
    st.success(flash)

day = st.date_input("Inventory date", value=date.today(), key="inventory_day")
frame = stock_service.day_stock_frame(day)

if frame.empty:
    ui.empty_state(
        f"No production or sales recorded on {day.strftime('%d %b %Y')}. "
        "Record production (Production page) or sales (Sales page) first - "
        "remaining food is derived from them, never entered directly."
    )
    st.stop()

issues = frame[frame["remaining_kg"] < -1e-9]
carry = database.get_remaining_day(day)
carried_total = float(carry["carry_over"].sum()) if not carry.empty else 0.0

remaining_total = float(frame["remaining_kg"].clip(lower=0).sum())
low_count = int((frame["status"] == stock_service.STATUS_LOW).sum())
out_count = int((frame["status"] == stock_service.STATUS_OUT).sum())

col1, col2, col3, col4 = st.columns(4)
with col1:
    ui.metric_card("Remaining food", fmt.format_kg(remaining_total),
                   sub="still available after sales", kind="calculated")
with col2:
    ui.metric_card("Low stock items", fmt.format_number(low_count),
                   sub="at or below threshold", kind="measured")
with col3:
    ui.metric_card("Out of stock items", fmt.format_number(out_count),
                   sub="nothing left to sell", kind="measured")
with col4:
    ui.metric_card("Carry-over planned", fmt.format_kg(carried_total),
                   sub="kept for the next service (not waste)", kind="measured")

if not issues.empty:
    st.warning(
        f"{len(issues)} food item(s) show more sold than available "
        f"({', '.join(issues['food_name'])}). Review the production and sales "
        "entries for this date - remaining food is never allowed to go below zero silently."
    )

ui.section("Stock & carry-over planner")

carry_map = {}
if not carry.empty:
    for _, row in carry.iterrows():
        carry_map[int(row["food_id"])] = row

editor_df = pd.DataFrame([
    {
        "food_id": int(row["food_id"]),
        "Food": row["food_name"],
        "Unit": row["unit"],
        "Prepared (kg)": round(float(row["prepared"]), 2),
        "Sold (kg)": round(float(row["sold_kg"]), 2),
        "Remaining (kg)": round(float(row["remaining_kg"]), 2),
        "Portions left": round(float(row["remaining_units"]), 1) if row["remaining_units"] is not None else float("nan"),
        "Status": stock_service.status_text(row["status"]),
        "Carry-over (kg)": float(carry_map[int(row["food_id"])]["carry_over"]) if int(row["food_id"]) in carry_map else 0.0,
        "Note": carry_map[int(row["food_id"])]["note"] if int(row["food_id"]) in carry_map else "",
    }
    for _, row in frame.iterrows()
])

edited = st.data_editor(
    editor_df,
    hide_index=True,
    width="stretch",
    disabled=["food_id", "Food", "Unit", "Prepared (kg)", "Sold (kg)",
              "Remaining (kg)", "Portions left", "Status"],
    column_config={
        "food_id": None,
        "Prepared (kg)": st.column_config.NumberColumn(format="%.2f kg"),
        "Sold (kg)": st.column_config.NumberColumn(format="%.2f kg"),
        "Remaining (kg)": st.column_config.NumberColumn(format="%.2f kg"),
        "Portions left": st.column_config.NumberColumn(format="%.1f"),
        "Carry-over (kg)": st.column_config.NumberColumn(
            min_value=0.0, step=0.5, format="%.1f kg",
            help="Food safely kept for the next service (refrigerated / reusable). It is NOT waste.",
        ),
        "Note": st.column_config.TextColumn(help="e.g. refrigerated for tomorrow's lunch buffet"),
    },
    key="inventory_editor",
)

if st.button("Save carry-over plan", width="stretch"):
    problems = []
    saved = 0
    for _, row in edited.iterrows():
        value = float(row["Carry-over (kg)"]) if pd.notna(row["Carry-over (kg)"]) else 0.0
        if value > max(float(row["Remaining (kg)"]), 0.0) + 1e-6:
            problems.append(str(row["Food"]))
            continue
        database.upsert_remaining_food(day, int(row["food_id"]), value, str(row["Note"] or ""))
        saved += 1
    if problems:
        st.error("Carry-over cannot exceed the remaining food for: " + ", ".join(problems))
    if saved:
        st.session_state["fw_flash"] = f"Carry-over plan saved for {saved} food item(s)."
        st.rerun()

st.caption(
    "Status rule: 🔴 nothing left to sell · 🟡 remaining portions at or below the food's "
    "low-stock threshold (set per food in the Food Master) · 🟢 healthy stock."
)
ui.method_note(
    "Remaining food = available food − food sold. Carry-over (food kept for the next "
    "service) is tracked here so it is never cooked twice, and it is not counted as "
    "waste. Waste remains kitchen + serving + plate waste only."
)
