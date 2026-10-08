"""
MealFlow360 - Sales & financial metrics.

Turns recorded sales into the money figures used across the app: revenue,
ingredient cost and profit. Selling units (plates, bowls, pieces) are converted
to kilograms with each food's portion size, because the cost price is
documented per kilogram; the money figures are therefore Calculated values,
derived from recorded sales and the prices in the Food Master.
"""

import pandas as pd


def add_kg_column(frame: pd.DataFrame) -> pd.DataFrame:
    """
    Add kg_sold = quantity_sold x portion_size_g / 1000 to a sales frame.

    Returns a copy so callers never mutate the frame they were given.
    """
    frame = frame.copy()
    frame["kg_sold"] = frame["quantity_sold"] * frame["portion_size_g"].fillna(0) / 1000.0
    return frame


def sales_summary(sales_df: pd.DataFrame) -> dict:
    """
    Aggregate money and quantities for a sales frame.

    Returns revenue, ingredient cost, profit, kg sold, units (plates) sold and
    the number of recorded entries. Never raises on an empty frame.
    """
    if sales_df is None or sales_df.empty:
        return {"revenue": 0.0, "cost": 0.0, "profit": 0.0,
                "kg_sold": 0.0, "units_sold": 0.0, "entries": 0}
    frame = add_kg_column(sales_df)
    cost = float((frame["kg_sold"] * frame["cost_per_kg"].fillna(0)).sum())
    revenue = float(frame["total_amount"].sum())
    return {
        "revenue": revenue,
        "cost": cost,
        "profit": revenue - cost,
        "kg_sold": float(frame["kg_sold"].sum()),
        "units_sold": float(frame["quantity_sold"].sum()),
        "entries": int(len(frame)),
    }


def per_food_sales(sales_df: pd.DataFrame) -> pd.DataFrame:
    """Per-food revenue, cost, profit and quantities for a sales frame."""
    columns = ["food_name", "unit", "units_sold", "kg_sold", "revenue", "cost", "profit"]
    if sales_df is None or sales_df.empty:
        return pd.DataFrame(columns=columns)
    frame = add_kg_column(sales_df)
    frame["cost_amount"] = frame["kg_sold"] * frame["cost_per_kg"].fillna(0)
    grouped = frame.groupby(["food_name", "unit"], as_index=False).agg(
        units_sold=("quantity_sold", "sum"),
        kg_sold=("kg_sold", "sum"),
        revenue=("total_amount", "sum"),
        cost=("cost_amount", "sum"),
    )
    grouped["profit"] = grouped["revenue"] - grouped["cost"]
    return grouped.sort_values("revenue", ascending=False).reset_index(drop=True)
