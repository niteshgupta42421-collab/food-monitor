"""
MealFlow360 - Production & waste accounting model.

THE single definition of every food quantity in the app. Every page,
service and report derives its numbers from these functions, so a kilogram
of food is never counted in two places at once.

The model (the default accounting flow):

    FOOD PREPARED
          |
          +---> KITCHEN WASTE
          v
    FOOD AVAILABLE FOR SERVICE
          |
          +---> SERVING WASTE
          v
    FOOD SERVED
          |
          +---> PLATE WASTE
          v
    FOOD CONSUMED

Measured inputs (entered by the organization):
  * Food prepared  - the edible food produced by the kitchen (starting quantity)
  * Kitchen waste  - loss before food becomes available for service
  * Serving waste  - food that reached the counter but was not served
  * Plate waste    - food served to customers that was left uneaten

Derived quantities (calculated here, never entered independently):
  * Food available for service = food prepared - kitchen waste
  * Food served                = available for service - serving waste
  * Food consumed              = food served - plate waste

Aggregates:
  * Total waste       = kitchen + serving + plate (each kg counted once)
  * Waste percentage  = total waste / food prepared x 100
  * Unaccounted / measurement difference
        = food prepared - (kitchen + serving + plate + consumed)

The accounting balances exactly by construction (kitchen + serving + plate +
consumed = prepared), so the unaccounted difference is 0 whenever the
recorded data reconciles. A non-zero value means the recorded data does not
reconcile and must be reviewed - it is never silently distributed into
another category.
"""

import pandas as pd


# ---------------------------------------------------------------- the definitions

def available_for_service(prepared, kitchen):
    """Food available for service = food prepared - kitchen waste (kg)."""
    return prepared - kitchen


def served_quantity(prepared, kitchen, serving):
    """Food served = available for service - serving waste (kg)."""
    return available_for_service(prepared, kitchen) - serving


def consumed_quantity(prepared, kitchen, serving, plate):
    """Food consumed = food served - plate waste (kg)."""
    return served_quantity(prepared, kitchen, serving) - plate


def total_waste(kitchen, serving, plate):
    """Total waste = kitchen + serving + plate (kg). Every kilogram counted once."""
    return kitchen + serving + plate


def waste_percentage(waste, prepared):
    """Waste percentage = total waste / food prepared x 100 (0 when nothing was prepared)."""
    prepared = float(prepared)
    if prepared <= 0:
        return 0.0
    return float(waste) / prepared * 100.0


def unaccounted(prepared, kitchen, serving, plate, consumed):
    """Unaccounted / measurement difference = prepared - (kitchen + serving + plate + consumed)."""
    return prepared - (kitchen + serving + plate + consumed)


def flow_totals(prepared, kitchen, serving, plate) -> dict:
    """
    One day or period of the full flow as a dict. This is the canonical shape
    used by calculations.period_totals() and by the UI.
    """
    served = served_quantity(prepared, kitchen, serving)
    consumed = consumed_quantity(prepared, kitchen, serving, plate)
    waste = total_waste(kitchen, serving, plate)
    return {
        "prepared": prepared,
        "kitchen": kitchen,
        "serving": serving,
        "plate": plate,
        "available": available_for_service(prepared, kitchen),
        "served": served,
        "consumed": consumed,
        "waste": waste,
        "waste_pct": waste_percentage(waste, prepared),
        "unaccounted": unaccounted(prepared, kitchen, serving, plate, consumed),
    }


# ---------------------------------------------------------------- table helpers

def _waste_pct_values(waste, prepared):
    """Row-wise waste percentage; NaN where no prepared quantity is available."""
    return (waste / prepared * 100).where(prepared.fillna(0) > 0)


def add_flow_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add the derived flow columns (available, served, consumed, waste,
    waste_pct, unaccounted) to a frame with prepared / kitchen / serving /
    plate columns. Row-wise mirror of the scalar definitions above.
    """
    frame["available"] = frame["prepared"] - frame["kitchen"]
    frame["served"] = frame["available"] - frame["serving"]
    frame["consumed"] = frame["served"] - frame["plate"]
    frame["waste"] = frame["kitchen"] + frame["serving"] + frame["plate"]
    frame["waste_pct"] = _waste_pct_values(frame["waste"], frame["prepared"]).fillna(0.0)
    frame["unaccounted"] = frame["prepared"] - frame["waste"] - frame["consumed"]
    return frame


def add_waste_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add waste and waste_pct_of_prepared to a waste-only frame (kitchen /
    serving / plate columns, prepared optional). Keeps NaN where no prepared
    quantity exists so the UI can show the gap instead of a fake 0%.
    """
    frame["waste"] = frame["kitchen"] + frame["serving"] + frame["plate"]
    if "prepared" in frame.columns:
        frame["waste_pct_of_prepared"] = _waste_pct_values(frame["waste"], frame["prepared"])
    return frame


def flow_issues(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Rows where a derived flow step fell below zero because the recorded waste
    exceeds the prepared quantity (a data-entry error). Expects
    add_flow_columns() to have been applied.
    """
    if frame.empty:
        return frame
    below_zero = (frame["available"] < 0) | (frame["served"] < 0) | (frame["consumed"] < 0)
    return frame[below_zero]
