"""
FoodWaste360 - Demo data loader.

Creates the documented demo hotel scenario so the app can be explored
immediately:

    Prepared: 8,000 kg/day     Waste: 1,000 kg/day
    Kitchen 250 kg | Serving 150 kg | Plate 600 kg   ->   12.50% waste rate

This matches the specification's demo scenario (sections 9 and 28), including
the food-wise split:

    Rice  2,500 kg prepared / 300 kg waste      Dal   1,000 kg / 120 kg
    Roti  1,500 kg / 150 kg                     Bhaji 1,000 kg / 180 kg
    Other 2,000 kg / 250 kg

The generator is deterministic (fixed random seed), so the same dataset is
created on every machine. Past days carry a small amount of variation so
trends and pattern detection have something to work with, while the LAST day
is always generated at the exact base values (so the current-day dashboard
shows the documented 8,000 kg / 1,000 kg / 12.50%). The per-day waste-rate
factors are mean-corrected, so the waste rate over the whole history is
12.50% as well.
"""

import random
from datetime import date, timedelta

from database import database

# Base scenario: food name -> (prepared kg, kitchen waste kg, serving waste kg, plate waste kg)
# Totals: 8,000 prepared; 250 kitchen + 150 serving + 600 plate = 1,000 kg waste (12.50%).
BASE_SCENARIO = {
    "Rice":  (2500, 50, 70, 180),
    "Dal":   (1000, 30,  0,  90),
    "Roti":  (1500, 30, 50,  70),
    "Bhaji": (1000, 60,  0, 120),
    "Other": (2000, 80, 30, 140),
}

BASE_CUSTOMERS = 2000      # customers served per day in the demo scenario
DEMO_DAYS = 30             # length of the generated history
RANDOM_SEED = 360          # fixed seed -> same demo data everywhere


def load_demo_data(days: int = DEMO_DAYS, end_day: date | None = None) -> dict:
    """
    Replace all record tables with a generated demo dataset.

    Returns a small summary dict for user feedback.
    """
    end_day = end_day or date.today()
    start_day = end_day - timedelta(days=days - 1)

    name_to_id = {}
    for name in BASE_SCENARIO:
        food_id = database.get_food_id(name)
        if food_id is None:
            raise ValueError(
                f"Demo data needs the food item '{name}'. It is missing from the food database."
            )
        name_to_id[name] = food_id

    rng = random.Random(RANDOM_SEED)

    # Day activity (prepared scales with it) and a per-day waste-rate factor
    # (so waste rises and falls a little relative to production, which makes
    # the trend detection meaningful). The rate factors are corrected so the
    # weighted-average waste rate over the whole history stays exactly at the
    # documented 12.50%.
    day_scales = [rng.uniform(0.88, 1.12) for _ in range(days)]
    rate_factors = [rng.uniform(0.96, 1.04) for _ in range(max(days - 1, 0))]
    if days > 1:
        weighted_sum = sum(s * f for s, f in zip(day_scales[:-1], rate_factors))
        remaining_weight = sum(day_scales) - day_scales[-1]
        if remaining_weight > 0:
            correction = weighted_sum / remaining_weight
            rate_factors = [f / correction for f in rate_factors]

    database.clear_all_records()

    production_rows = 0
    waste_rows = 0
    washing_rows = 0

    for offset in range(days):
        day = start_day + timedelta(days=offset)
        is_last_day = offset == days - 1
        # The last day is kept at the exact base values.
        day_scale = 1.0 if is_last_day else day_scales[offset]
        rate_factor = 1.0 if is_last_day else rate_factors[offset]
        if is_last_day:
            customers = BASE_CUSTOMERS
        else:
            customers = int(round(BASE_CUSTOMERS * day_scale * rng.uniform(0.95, 1.05)))
        plate_rows_for_day = []

        for name, (prepared_kg, kitchen_kg, serving_kg, plate_kg) in BASE_SCENARIO.items():
            food_id = name_to_id[name]

            prepared = round(prepared_kg * day_scale, 2)
            waste_target = round((kitchen_kg + serving_kg + plate_kg) * day_scale * rate_factor, 2)
            kitchen, serving, plate = _split_waste(
                [kitchen_kg, serving_kg, plate_kg], waste_target, rng, jitter=not is_last_day
            )

            served = round(max(prepared - kitchen, 0.0), 2)
            consumed = round(max(served - serving - plate, 0.0), 2)

            database.upsert_production(day, food_id, prepared, served, consumed)
            production_rows += 1
            plate_rows_for_day.append((food_id, plate))

            if kitchen > 0:
                database.add_waste_record(day, food_id, "kitchen", kitchen, _demo_kitchen_reason(rng))
                waste_rows += 1
            if serving > 0:
                database.add_waste_record(day, food_id, "serving", serving, "Counter/display leftover")
                waste_rows += 1

        # Plate-waste sheet for the day (also writes the 'plate' ledger entries).
        database.replace_plate_waste_day(day, customers, plate_rows_for_day)

        # Example plate-washing record: running tap at 6 L/min, 15 seconds per plate.
        flow_rate, minutes_per_plate = 6.0, 0.25
        water_used = round(flow_rate * minutes_per_plate * customers, 1)
        database.add_washing_record(
            day=day,
            method="running_tap",
            plates=customers,
            water_used=water_used,
            flow_rate=flow_rate,
            washing_time=minutes_per_plate,
            details="Demo estimate: 6 L/min tap, 15 s per plate",
        )
        washing_rows += 1

    return {
        "days": days,
        "start": start_day,
        "end": end_day,
        "production_rows": production_rows,
        "waste_rows": waste_rows,
        "plate_days": days,
        # Note: plate waste for each day was written via replace_plate_waste_day.
        "washing_rows": washing_rows,
    }


def _split_waste(base_streams: list[float], target_total: float,
                 rng: random.Random, jitter: bool = True) -> list[float]:
    """
    Split a waste total into kitchen / serving / plate amounts.

    The base kitchen/serving/plate proportions are used, optionally with a
    little random variation, then normalized so the three rounded values sum
    to exactly `target_total` (any rounding residue is corrected on the
    largest stream). Keeping the sums exact is what keeps the documented
    12.50% demo waste rate intact.
    """
    if target_total <= 0:
        return [0.0, 0.0, 0.0]

    weights = list(base_streams)
    if jitter:
        weights = [w * rng.uniform(0.85, 1.15) for w in weights]
    weight_sum = sum(weights)
    if weight_sum <= 0:  # all base streams are zero - fall back to an even split
        weights = [1.0, 1.0, 1.0]
        weight_sum = 3.0

    streams = [round(target_total * w / weight_sum, 2) for w in weights]
    residue = round(target_total - sum(streams), 2)
    if residue:
        largest = max(range(3), key=lambda index: streams[index])
        streams[largest] = round(streams[largest] + residue, 2)
    return streams


_KITCHEN_REASONS = ["Overproduction", "Preparation waste", "Spoilage", "Burnt food", "Expired food"]


def _demo_kitchen_reason(rng: random.Random) -> str:
    """Pick a plausible kitchen-waste reason for the demo data."""
    return rng.choice(_KITCHEN_REASONS)
