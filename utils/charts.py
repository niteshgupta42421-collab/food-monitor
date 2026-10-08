"""
MealFlow360 - Plotly chart builders.

All charts share the same palette and layout so the app looks consistent.
Each function returns a plotly Figure; pages render it with st.plotly_chart.
"""

import plotly.graph_objects as go

# Shared palette (greens for positives, orange/red for waste, blue for impact).
GREEN = "#1B8A5A"
LIGHT_GREEN = "#4DB183"
ORANGE = "#E8871E"
RED = "#D64545"
BLUE = "#2368B1"
PURPLE = "#6B3FA0"
GRAY = "#94A69C"

WASTE_TYPE_LABELS = {"kitchen": "Kitchen waste", "serving": "Serving waste", "plate": "Plate waste"}
WASTE_TYPE_COLORS = {"kitchen": ORANGE, "serving": BLUE, "plate": RED}


def _finish(fig: go.Figure, title: str, height: int = 380, y_title: str = "") -> go.Figure:
    """Apply the common layout to a figure."""
    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        height=height,
        margin=dict(l=10, r=10, t=48, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        font=dict(family="sans-serif", color="#2E4338"),
    )
    fig.update_xaxes(showgrid=False)
    fig.update_yaxes(showgrid=True, gridcolor="#EAF1EC")
    if y_title:
        fig.update_yaxes(title_text=y_title)
    return fig


def prepared_consumed_wasted(daily_df, title: str = "Food prepared vs consumed vs wasted") -> go.Figure:
    """Grouped bar chart of prepared / consumed / wasted quantities per day."""
    fig = go.Figure()
    if daily_df.empty:
        return _finish(fig, title)
    x = daily_df["date"].astype(str)
    fig.add_bar(x=x, y=daily_df["prepared"], name="Prepared", marker_color=GREEN)
    fig.add_bar(x=x, y=daily_df["consumed"], name="Consumed", marker_color=LIGHT_GREEN)
    fig.add_bar(x=x, y=daily_df["waste"], name="Wasted", marker_color=ORANGE)
    fig.update_layout(barmode="group")
    return _finish(fig, title, y_title="kg")


def waste_type_donut(totals: dict, title: str = "Kitchen vs serving vs plate waste") -> go.Figure:
    """Donut chart of the three waste categories."""
    labels, values, colors = [], [], []
    for key in ("kitchen", "serving", "plate"):
        value = float(totals.get(key, 0) or 0)
        if value > 0:
            labels.append(WASTE_TYPE_LABELS[key])
            values.append(value)
            colors.append(WASTE_TYPE_COLORS[key])
    fig = go.Figure()
    if not values:
        return _finish(fig, title)
    fig.add_pie(
        labels=labels,
        values=values,
        hole=0.55,
        marker=dict(colors=colors),
        textinfo="label+percent",
        hovertemplate="%{label}: %{value:,.1f} kg (%{percent})<extra></extra>",
    )
    return _finish(fig, title)


def waste_by_food(waste_df, title: str = "Waste by food type", unit: str = "kg") -> go.Figure:
    """
    Horizontal bar chart of a per-food quantity.

    Expects a DataFrame with columns "food_name" and "waste", where "waste"
    is the quantity to plot (waste in kg, washing water in litres, ...).
    """
    fig = go.Figure()
    if waste_df.empty:
        return _finish(fig, title)
    ordered = waste_df.sort_values("waste", ascending=True)
    fig.add_bar(
        x=ordered["waste"],
        y=ordered["food_name"],
        orientation="h",
        marker_color=ORANGE,
        hovertemplate="%{y}: %{x:,.1f} " + unit + "<extra></extra>",
    )
    fig.update_layout(showlegend=False)
    return _finish(fig, title, height=max(320, 44 * len(ordered) + 120), y_title="")


def trend_lines(daily_df, columns: dict, title: str, y_title: str = "", colors: list = None) -> go.Figure:
    """
    Multi-line trend chart.

    `columns` maps DataFrame column name -> legend label,
    e.g. {"waste": "Total waste", "kitchen": "Kitchen waste"}.
    """
    fig = go.Figure()
    if daily_df.empty:
        return _finish(fig, title, y_title=y_title)
    x = daily_df["date"].astype(str)
    palette = colors or [GREEN, ORANGE, BLUE, RED, PURPLE, GRAY]
    for index, (column, label) in enumerate(columns.items()):
        if column not in daily_df.columns:
            continue
        fig.add_scatter(
            x=x,
            y=daily_df[column],
            name=label,
            mode="lines+markers",
            line=dict(width=2.5, color=palette[index % len(palette)]),
            hovertemplate="%{x}<br>" + label + ": %{y:,.1f}<extra></extra>",
        )
    return _finish(fig, title, y_title=y_title)


def stacked_waste_types(daily_df, title: str = "Daily waste by category") -> go.Figure:
    """Stacked bar chart of kitchen / serving / plate waste per day."""
    fig = go.Figure()
    if daily_df.empty:
        return _finish(fig, title)
    x = daily_df["date"].astype(str)
    for key in ("kitchen", "serving", "plate"):
        if key in daily_df.columns:
            fig.add_bar(x=x, y=daily_df[key], name=WASTE_TYPE_LABELS[key], marker_color=WASTE_TYPE_COLORS[key])
    fig.update_layout(barmode="stack")
    return _finish(fig, title, y_title="kg")


def bar_by_food(by_food_df, value_col: str, title: str, unit_label: str, color: str = BLUE) -> go.Figure:
    """Horizontal bar chart of any per-food metric (value lost, CO2e, water, ...)."""
    fig = go.Figure()
    if by_food_df.empty or value_col not in by_food_df.columns:
        return _finish(fig, title)
    ordered = by_food_df.sort_values(value_col, ascending=True)
    fig.add_bar(
        x=ordered[value_col],
        y=ordered["food_name"],
        orientation="h",
        marker_color=color,
        hovertemplate="%{y}: %{x:,.1f} " + unit_label + "<extra></extra>",
    )
    fig.update_layout(showlegend=False)
    return _finish(fig, title, height=max(320, 44 * len(ordered) + 120))


def prepared_by_food(production_by_food_df, title: str = "Food prepared by item") -> go.Figure:
    """Horizontal bar chart of prepared quantity per food."""
    fig = go.Figure()
    if production_by_food_df.empty:
        return _finish(fig, title)
    ordered = production_by_food_df.sort_values("prepared", ascending=True)
    fig.add_bar(
        x=ordered["prepared"],
        y=ordered["food_name"],
        orientation="h",
        marker_color=GREEN,
        hovertemplate="%{y}: %{x:,.1f} kg<extra></extra>",
    )
    fig.update_layout(showlegend=False)
    return _finish(fig, title, height=max(320, 44 * len(ordered) + 120))
