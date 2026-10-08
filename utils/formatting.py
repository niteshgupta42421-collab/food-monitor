"""
MealFlow360 - Formatting helpers.

All user-facing numbers are formatted here so units, thousands separators and
rounding stay consistent across every page.

Rules (spec sections 2 and 23-26):
  * A number is formatted exactly ONCE. These functions take raw numeric
    values, never pre-formatted strings, so a double comma ("8,,000") can
    never appear.
  * Thousands use standard comma grouping: 250000 -> "250,000".
  * By default integer values show no decimals (8000 -> "8,000") and other
    values show two decimals (1250.50 -> "1,250.50").
  * Calculations always use the raw numeric values, never display strings.
"""


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide without raising on zero denominators."""
    if denominator in (0, 0.0, None):
        return default
    return numerator / denominator


def format_number(value: float, decimals: int | None = None) -> str:
    """
    Format a number with thousands separators.

    Default rule (spec section 23):
        8000 -> "8,000"     8263 -> "8,263"     1250.50 -> "1,250.50"

    Pass `decimals` explicitly to force a fixed number of decimals.
    """
    number = float(value)
    if decimals is not None:
        return f"{number:,.{decimals}f}"
    rounded = round(number, 2)
    if rounded == int(rounded):
        return f"{rounded:,.0f}"
    return f"{rounded:,.2f}"


def format_kg(value: float, decimals: int | None = None) -> str:
    """Format a weight in kilograms, e.g. '8,000 kg' or '1,250.50 kg'."""
    number = format_number(value, decimals)
    return f"{number} kg"


def format_litres(value: float, decimals: int | None = 0) -> str:
    """Format a volume in litres, e.g. '250,000 L' (0 decimals by default)."""
    number = format_number(value, decimals)
    return f"{number} L"


def format_currency(value: float, decimals: int | None = None) -> str:
    """Format an amount in Indian rupees, e.g. '₹25,000' or '₹1,250.50'."""
    number = format_number(value, decimals)
    return f"₹{number}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Format an already-computed percentage value, e.g. 12.5 -> '12.50%'.

    Important: the caller must pass a percentage (already multiplied by 100),
    not a fraction - the value is never multiplied again here.
    """
    return f"{float(value):.{decimals}f}%"


def format_grams(value: float, decimals: int | None = 0) -> str:
    """Format grams, e.g. '300 g' (0 decimals by default)."""
    number = format_number(value, decimals)
    return f"{number} g"


def format_co2(value: float, decimals: int | None = None) -> str:
    """Format a CO₂e estimate, e.g. '1,250.50 kg CO₂e'."""
    number = format_number(value, decimals)
    return f"{number} kg CO₂e"
