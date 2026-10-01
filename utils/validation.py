"""
FoodWaste360 - Input validation helpers.

Every function returns either None (input is fine) or a friendly error/warning
string that can be shown directly in the UI with st.error / st.warning.

Rules implemented here follow section 22 of the project requirements:
quantities cannot be negative, waste above prepared quantity raises a warning,
customers and costs cannot be negative, and required fields cannot be empty.
"""

from datetime import date


# ---------------------------------------------------------------- basic checks

def validate_required(value, field_label: str) -> str | None:
    """Return an error when a required text/value field is empty."""
    if value is None:
        return f"{field_label} is required."
    if isinstance(value, str) and value.strip() == "":
        return f"{field_label} is required."
    return None


def validate_non_negative(value: float | None, field_label: str) -> str | None:
    """Return an error when a number is negative or missing."""
    if value is None:
        return f"{field_label} is required."
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f"{field_label} must be a number."
    if number < 0:
        return f"{field_label} cannot be negative."
    return None


def validate_positive(value: float | None, field_label: str) -> str | None:
    """Return an error when a number is zero, negative or missing."""
    error = validate_non_negative(value, field_label)
    if error:
        return error
    if float(value) == 0:
        return f"{field_label} must be greater than zero."
    return None


def validate_date_order(start: date, end: date) -> str | None:
    """Return an error when the start date is after the end date."""
    if start > end:
        return "The start date must be on or before the end date."
    return None


def validate_factor_fields(co2_factor: float | None, water_factor: float | None,
                           factor_source: str) -> str | None:
    """
    Environmental factors must always carry a source (project rule: factors
    cannot be stored without a documented reference).
    """
    has_factor = co2_factor is not None or water_factor is not None
    if has_factor and (factor_source is None or str(factor_source).strip() == ""):
        return "A factor source is required when a CO2e or water factor is entered."
    return None


# ---------------------------------------------------------------- domain checks

def waste_exceeds_prepared_warning(new_waste_total: float, prepared: float, food_name: str) -> str | None:
    """
    Warn (not block) when recorded waste for one food would exceed what was
    prepared that day. Returns None when there is no problem.
    """
    if prepared is None or prepared <= 0:
        return None
    if new_waste_total > prepared:
        return (
            f"Recorded waste for {food_name} ({new_waste_total:,.1f} kg) would exceed "
            f"the prepared quantity ({prepared:,.1f} kg). Please double-check the entry."
        )
    return None


def production_consistency_warnings(prepared: float, served: float, consumed: float, food_name: str) -> list[str]:
    """Return friendly warnings for unusual production numbers (never blocks saving)."""
    warnings = []
    if prepared is not None and served is not None and served > prepared:
        warnings.append(f"{food_name}: served quantity is higher than the prepared quantity.")
    if served is not None and consumed is not None and consumed > served:
        warnings.append(f"{food_name}: consumed quantity is higher than the served quantity.")
    return warnings


def validate_production_row(prepared, served, consumed, food_name: str) -> str | None:
    """Validate one production row; returns an error message or None."""
    for value, label in ((prepared, "Prepared"), (served, "Served"), (consumed, "Consumed")):
        error = validate_non_negative(value, f"{food_name} - {label} quantity")
        if error:
            return error
    return None


def validate_plate_waste_input(customers, food_rows: list[tuple[str, float | None]]) -> str | None:
    """Validate the plate-waste sheet (customer count and each food quantity)."""
    error = validate_non_negative(customers, "Number of customers served")
    if error:
        return error
    if int(customers) == 0 and any(qty for _, qty in food_rows if qty):
        return "Customers served must be greater than zero when plate waste is recorded."
    for food_name, quantity in food_rows:
        if quantity is None or float(quantity) == 0:
            continue
        error = validate_non_negative(quantity, f"{food_name} plate waste")
        if error:
            return error
    return None


def validate_washing_input(method: str, plates, flow_rate=None, washing_time=None,
                           bucket_size=None, buckets=None, water_per_cycle=None,
                           cycles=None, total_water=None) -> str | None:
    """Validate the plate-washing water calculator inputs for the chosen method."""
    error = validate_non_negative(plates, "Number of plates")
    if error:
        return error

    if method == "running_tap":
        for value, label in ((flow_rate, "Flow rate"), (washing_time, "Washing time per plate")):
            error = validate_positive(value, label)
            if error:
                return error
    elif method == "bucket":
        for value, label in ((bucket_size, "Bucket size"), (buckets, "Number of buckets")):
            error = validate_positive(value, label)
            if error:
                return error
    elif method == "dishwasher":
        for value, label in ((water_per_cycle, "Water per cycle"), (cycles, "Number of cycles")):
            error = validate_positive(value, label)
            if error:
                return error
    elif method == "other":
        error = validate_positive(total_water, "Total water used")
        if error:
            return error
    return None
