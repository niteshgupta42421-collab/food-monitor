"""
MealFlow360 - Demo data loader: The Urban Thali.

Creates a deterministic 30-day dataset for the demo restaurant
"The Urban Thali" (~520 covers/day, 8 dishes) so every feature can be
explored immediately:

    * production  - what the kitchen cooked each day,
    * sales       - entries split across lunch and dinner service (times,
                    quantities, order types), from which revenue, kg sold and
                    remaining food are derived,
    * waste       - kitchen / serving / plate records (plate via the
                    plate-waste sheet),
    * remaining   - the carry-over planned for the next service (not waste),
    * expected demand on the final day, so "What to cook next?" has data.

Documented base day (the final generated day):

    Dish      Prepared (units)   Sold (units)   Story on the last day
    Rice      180 plates         177 plates     near sell-out  -> Low 🟡
    Dal       160 bowls          155 bowls      healthy stock  -> OK 🟢
    Chapati   320 pieces         320 pieces     sold out       -> Out 🔴
    Biryani   95 plates          38 plates      overstock, 12 kg carried over
    Paneer    75 plates          74 plates      near sell-out  -> Low 🟡
    Bhaji     140 portions       134 portions   healthy stock  -> OK 🟢
    Curd      110 bowls          104 bowls      0.5 kg carried over
    Dosa      120 plates         120 plates     made to order

    Prepared ≈ 193.15 kg/day · waste ≈ 13.4 kg/day
    (kitchen 2.0 + serving 2.3 + plate 9.1) ≈ 6.9%

The generator is deterministic (fixed random seed): the same dataset is
created on every machine. Earlier days carry small variation so trends are
meaningful; the final day always uses the exact base values above, so the
Dashboard "today" view matches this table. Remaining food is always derived
(available − sold), never stored; only the planned carry-over rows are
written to remaining_food.
"""

import random
from datetime import date, timedelta

from database import database

DEMO_DAYS = 30
RANDOM_SEED = 360
BASE_CUSTOMERS = 520
RESTAURANT_NAME = "The Urban Thali"

# Base scenario per food:
#   prepared_units / sold_units   - selling units (portion size converts to kg)
#   kitchen / serving / plate     - waste in kg for the base day
#   expected_units                - kitchen demand plan for the FINAL day only
#   carry_kg                      - carry-over planned on the FINAL day only
BASE_SCENARIO = {
    "Rice":    {"prepared_units": 180, "sold_units": 177, "kitchen": 0.5, "serving": 0.3,
                "plate": 2.5, "expected_units": 184},
    "Dal":     {"prepared_units": 160, "sold_units": 155, "kitchen": 0.3, "serving": 0.1,
                "plate": 1.5},
    "Chapati": {"prepared_units": 320, "sold_units": 320, "kitchen": 0.0, "serving": 0.5,
                "plate": 1.0, "expected_units": 340},
    "Biryani": {"prepared_units": 95, "sold_units": 38, "kitchen": 0.8, "serving": 1.0,
                "plate": 1.5, "carry_kg": 12.0,
                "carry_note": "Refrigerated for tomorrow's biryani rice"},
    "Paneer":  {"prepared_units": 75, "sold_units": 74, "kitchen": 0.1, "serving": 0.0,
                "plate": 0.6, "expected_units": 80},
    "Bhaji":   {"prepared_units": 140, "sold_units": 134, "kitchen": 0.2, "serving": 0.3,
                "plate": 1.0},
    "Curd":    {"prepared_units": 110, "sold_units": 104, "kitchen": 0.1, "serving": 0.1,
                "plate": 0.4, "carry_kg": 0.5, "carry_note": "Refrigerated for the curries"},
    "Dosa":    {"prepared_units": 120, "sold_units": 120, "kitchen": 0.0, "serving": 0.0,
                "plate": 0.6},
}

LUNCH_TIMES = ["12:15", "12:45", "13:20", "13:55", "14:30", "15:10"]
DINNER_TIMES = ["19:10", "19:45", "20:20", "21:00", "21:40", "22:10"]
ORDER_TYPES = ["dine-in", "takeaway", "delivery", "buffet", "other"]
ORDER_WEIGHTS = [6, 2, 1, 0.5, 0.3]

KITCHEN_REASONS = ["Overproduction", "Preparation waste", "Spoilage", "Burnt food", "Expired food"]


def load_demo_data(days: int = DEMO_DAYS, end_day: date | None = None) -> dict:
    """
    Replace all record tables with a generated Urban Thali dataset.

    Returns a small summary dict for user feedback.
    """
    end_day = end_day or date.today()
    start_day = end_day - timedelta(days=days - 1)

    foods_df = database.get_food_items_df()
    available_names = set(foods_df["food_name"])
    missing = [name for name in BASE_SCENARIO if name not in available_names]
    if missing:
        raise ValueError(
            "The demo needs these food items: " + ", ".join(missing) +
            ". Restore data/food_factors.csv and restart the app."
        )
    food_meta = {
        row["food_name"]: {
            "id": int(row["id"]),
            "portion_kg": float(row["portion_size_g"]) / 1000.0,
            "selling_price": float(row["selling_price"]),
        }
        for _, row in foods_df.iterrows()
    }

    rng = random.Random(RANDOM_SEED)
    day_scales = [rng.uniform(0.90, 1.10) for _ in range(days)]

    database.clear_all_records()

    production_rows = 0
    sales_rows = 0
    waste_rows = 0
    washing_rows = 0
    remaining_rows = 0
    expected_rows = 0

    for offset in range(days):
        day = start_day + timedelta(days=offset)
        is_last_day = offset == days - 1
        scale = 1.0 if is_last_day else day_scales[offset]
        if is_last_day:
            customers = BASE_CUSTOMERS
        else:
            customers = int(round(BASE_CUSTOMERS * scale * rng.uniform(0.95, 1.05)))
        plate_rows_for_day = []

        for name, base in BASE_SCENARIO.items():
            meta = food_meta[name]
            food_id = meta["id"]
            portion_kg = meta["portion_kg"]

            prepared_units = round(base["prepared_units"] * scale)
            sold_units = round(base["sold_units"] * scale)
            kitchen = _scaled_amount(base["kitchen"], scale, rng, is_last_day)
            serving = _scaled_amount(base["serving"], scale, rng, is_last_day)
            plate = _scaled_amount(base["plate"], scale, rng, is_last_day)

            prepared_kg = round(prepared_units * portion_kg, 2)
            available_kg = round(prepared_kg - kitchen, 2)

            # Never sell more than the kitchen made available; the recorded
            # data must never produce a negative remaining quantity.
            sold_kg = round(sold_units * portion_kg, 2)
            while sold_kg > available_kg and sold_units > 0:
                sold_units -= 1
                sold_kg = round(sold_units * portion_kg, 2)

            # Save-time snapshots follow the single accounting model exactly:
            # served = available - serving waste; consumed = served - plate waste.
            served = round(max(available_kg - serving, 0.0), 2)
            consumed = round(max(served - plate, 0.0), 2)

            database.upsert_production(day, food_id, prepared_kg, served, consumed)
            production_rows += 1
            plate_rows_for_day.append((food_id, plate))

            if kitchen > 0:
                database.add_waste_record(day, food_id, "kitchen", kitchen,
                                          rng.choice(KITCHEN_REASONS))
                waste_rows += 1
            if serving > 0:
                database.add_waste_record(day, food_id, "serving", serving,
                                          "Counter leftover (closing)")
                waste_rows += 1

            # Daily sales split into 2-3 service entries.
            for index, entry_units in enumerate(_split_units(sold_units, rng)):
                if entry_units <= 0:
                    continue
                time_slots = LUNCH_TIMES if index == 0 else DINNER_TIMES
                database.add_sale(
                    day, food_id, entry_units, meta["selling_price"],
                    order_type=rng.choices(ORDER_TYPES, weights=ORDER_WEIGHTS, k=1)[0],
                    time=rng.choice(time_slots),
                )
                sales_rows += 1

        # Plate-waste sheet (also writes the 'plate' ledger entries).
        database.replace_plate_waste_day(day, customers, plate_rows_for_day)

        # Example plate-washing record: running tap at 6 L/min, 15 s per plate.
        flow_rate, minutes_per_plate = 6.0, 0.25
        water_used = round(flow_rate * minutes_per_plate * customers, 1)
        database.add_washing_record(
            day=day, method="running_tap", plates=customers, water_used=water_used,
            flow_rate=flow_rate, washing_time=minutes_per_plate,
            details="Demo estimate: 6 L/min tap, 15 s per plate",
        )
        washing_rows += 1

        # The final day also gets the kitchen's demand plan and the carry-over
        # plan, so the Kitchen Control Center and Inventory pages are alive.
        if is_last_day:
            for name, base in BASE_SCENARIO.items():
                meta = food_meta[name]
                if "expected_units" in base:
                    database.set_expected_demand(day, meta["id"],
                                                 round(base["expected_units"] * meta["portion_kg"], 2))
                    expected_rows += 1
                if "carry_kg" in base:
                    database.upsert_remaining_food(day, meta["id"], base["carry_kg"],
                                                   base.get("carry_note", ""))
                    remaining_rows += 1

    return {
        "restaurant": RESTAURANT_NAME,
        "days": days,
        "start": start_day,
        "end": end_day,
        "production_rows": production_rows,
        "sales_rows": sales_rows,
        "waste_rows": waste_rows,
        "washing_rows": washing_rows,
        "remaining_rows": remaining_rows,
        "expected_rows": expected_rows,
        "customers_per_day": BASE_CUSTOMERS,
    }


def _scaled_amount(base_value: float, scale: float, rng: random.Random,
                   is_last_day: bool) -> float:
    """Scale a kg amount with the day, adding jitter except on the final day."""
    if base_value <= 0:
        return 0.0
    if is_last_day:
        return round(base_value, 2)
    return round(base_value * scale * rng.uniform(0.85, 1.15), 2)


def _split_units(total_units: float, rng: random.Random) -> list[float]:
    """
    Split one day's sold units into 2-3 service entries (whole units).

    The rounded parts are corrected on the last entry so their sum is exactly
    the day's total - the sales history always matches the production story.
    """
    entry_count = rng.choice([2, 2, 3])
    if entry_count == 2:
        first = rng.uniform(0.45, 0.55)
        weights = [first, 1.0 - first]
    else:
        raw = [rng.uniform(0.8, 1.2) for _ in range(3)]
        total = sum(raw)
        weights = [value / total for value in raw]
    parts = [round(total_units * weight) for weight in weights]
    residue = round(total_units - sum(parts))
    parts[-1] = parts[-1] + residue
    return [max(part, 0) for part in parts]
