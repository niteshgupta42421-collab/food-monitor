"""
MealFlow360 - Data access layer.

All database reads and writes go through this module so that every SQL query
is written once, is parameterized (no string-built SQL), and is easy to test.

Dates are stored as ISO strings ('YYYY-MM-DD'). Functions accept datetime.date
objects (or ISO strings) and convert them consistently.
"""

import sqlite3
from datetime import date as date_type
from pathlib import Path

import pandas as pd

from database import schema

DB_PATH = schema.DATA_DIR / "foodwaste360.db"

# Columns that may be updated on a food item (whitelist keeps updates safe).
_FOOD_EDITABLE_FIELDS = {
    "food_name", "category", "unit", "cost_per_kg", "co2_factor", "water_factor",
    "factor_source", "factor_reference", "factor_date", "factor_version", "is_estimated",
    "selling_price", "portion_size_g", "low_stock_threshold", "production_mode", "active",
    "notes",
}


# ---------------------------------------------------------------- connection / setup

def get_connection() -> sqlite3.Connection:
    """Open a SQLite connection with foreign keys enabled and named columns."""
    schema.DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create tables, migrate old databases in place and seed defaults."""
    with get_connection() as conn:
        schema.create_tables(conn)
        schema.migrate_schema(conn)
        schema.seed_food_items(conn)
        schema.backfill_food_sales_fields(conn)
        schema.seed_users(conn)


def _iso(day) -> str:
    """Accept a date object or string and always return 'YYYY-MM-DD'."""
    if isinstance(day, date_type):
        return day.isoformat()
    return str(day)


def _read_df(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run a SELECT and return the result as a DataFrame."""
    with get_connection() as conn:
        return pd.read_sql_query(sql, conn, params=params)


# ---------------------------------------------------------------- users

def authenticate(email: str, password: str) -> sqlite3.Row | None:
    """Return the user row when email + password match, otherwise None."""
    with get_connection() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if row and schema.verify_password(password, row["password_hash"]):
        return row
    return None


def get_all_users() -> list[sqlite3.Row]:
    """Return all user accounts (without password hashes exposed)."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, email, role, restaurant_name, theme, created_at FROM users ORDER BY id"
        ).fetchall()


def get_user_profile(email: str) -> sqlite3.Row | None:
    """Profile fields (name, restaurant, theme) for one user."""
    with get_connection() as conn:
        return conn.execute(
            "SELECT id, name, email, role, restaurant_name, theme FROM users WHERE email = ?",
            (email.strip().lower(),),
        ).fetchone()


def update_user_profile(email: str, name: str | None = None,
                        restaurant_name: str | None = None) -> None:
    """Update the editable profile fields of one user."""
    sets, params = [], []
    if name is not None:
        sets.append("name = ?")
        params.append(name.strip())
    if restaurant_name is not None:
        sets.append("restaurant_name = ?")
        params.append(restaurant_name.strip())
    if not sets:
        return
    params.append(email.strip().lower())
    with get_connection() as conn:
        conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE email = ?", tuple(params))
        conn.commit()


def set_user_theme(email: str, theme: str) -> None:
    """Persist the chosen theme for one user."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET theme = ? WHERE email = ?", (theme, email.strip().lower()))
        conn.commit()


def get_user_theme(email: str) -> str:
    """Theme key stored for one user (falls back to 'light')."""
    with get_connection() as conn:
        row = conn.execute("SELECT theme FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    if row and row["theme"]:
        return row["theme"]
    return "light"


def update_user_password(email: str, new_password: str) -> bool:
    """Set a new password for one user. Returns False when the email is unknown."""
    with get_connection() as conn:
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (schema.hash_password(new_password), email.strip().lower()),
        )
        conn.commit()
        return cursor.rowcount > 0


def create_user(name: str, email: str, role: str, password: str, restaurant_name: str = "") -> None:
    """Create a new user. Raises ValueError for duplicates or invalid roles."""
    if role not in {"admin", "manager", "kitchen", "staff"}:
        raise ValueError("Role must be one of: admin, manager, kitchen, staff.")
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (name, email, role, password_hash, restaurant_name) VALUES (?, ?, ?, ?, ?)",
                (name.strip(), email.strip().lower(), role, schema.hash_password(password),
                 restaurant_name.strip()),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"A user with email '{email}' already exists.")


# ---------------------------------------------------------------- food items

def get_food_items_df() -> pd.DataFrame:
    """All food items with their cost, sales and documented impact factors."""
    return _read_df(
        """
        SELECT id, food_name, category, unit, cost_per_kg, selling_price, portion_size_g,
               low_stock_threshold, production_mode, active,
               co2_factor, water_factor, factor_source, factor_reference, factor_date,
               factor_version, is_estimated, notes
        FROM food_items
        ORDER BY food_name
        """
    )


def get_active_food_names() -> list[str]:
    """Sorted list of active food names (for entry select boxes)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT food_name FROM food_items WHERE active = 1 ORDER BY food_name"
        ).fetchall()
    return [row["food_name"] for row in rows]


def get_food_names() -> list[str]:
    """Sorted list of food names (for select boxes)."""
    with get_connection() as conn:
        rows = conn.execute("SELECT food_name FROM food_items ORDER BY food_name").fetchall()
    return [row["food_name"] for row in rows]


def get_food_id(food_name: str) -> int | None:
    """Look up a food id by name."""
    with get_connection() as conn:
        row = conn.execute("SELECT id FROM food_items WHERE food_name = ?", (food_name,)).fetchone()
    return row["id"] if row else None


def add_food_item(food_name: str, category: str = "", unit: str = "kg", cost_per_kg: float = 0.0,
                  co2_factor: float | None = None, water_factor: float | None = None,
                  factor_source: str = "", factor_reference: str = "", factor_date: str = "",
                  factor_version: str = "", is_estimated: int = 1, selling_price: float = 0.0,
                  portion_size_g: float = 0.0, low_stock_threshold: float = 0.0,
                  production_mode: str = "pre_prepared", active: int = 1, notes: str = "") -> int:
    """Insert a new food item and return its id."""
    if production_mode not in {"pre_prepared", "made_to_order"}:
        raise ValueError("Production mode must be 'pre_prepared' or 'made_to_order'.")
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO food_items
                    (food_name, category, unit, cost_per_kg, co2_factor, water_factor,
                     factor_source, factor_reference, factor_date, factor_version, is_estimated,
                     selling_price, portion_size_g, low_stock_threshold, production_mode, active, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (food_name.strip(), category.strip(), unit.strip() or "kg", float(cost_per_kg),
                 co2_factor, water_factor, factor_source.strip(), factor_reference.strip(),
                 factor_date.strip(), factor_version.strip(), int(is_estimated),
                 float(selling_price), float(portion_size_g), float(low_stock_threshold),
                 production_mode, int(active), notes.strip()),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.IntegrityError:
        raise ValueError(f"A food item named '{food_name}' already exists.")


def update_food_item(food_id: int, **fields) -> None:
    """Update whitelisted columns of one food item."""
    clean = {key: value for key, value in fields.items() if key in _FOOD_EDITABLE_FIELDS}
    if not clean:
        return
    assignments = ", ".join(f"{column} = ?" for column in clean)
    try:
        with get_connection() as conn:
            conn.execute(
                f"UPDATE food_items SET {assignments} WHERE id = ?",
                (*clean.values(), food_id),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError("The update would create a duplicate food name.")


def food_item_usage_count(food_id: int) -> int:
    """How many production / waste / plate / sales rows reference this food."""
    with get_connection() as conn:
        total = 0
        for table in ("daily_production", "waste_records", "plate_waste", "sales", "remaining_food"):
            total += conn.execute(f"SELECT COUNT(*) FROM {table} WHERE food_id = ?", (food_id,)).fetchone()[0]
    return total


def delete_food_item(food_id: int) -> None:
    """Delete a food item only when no records reference it."""
    if food_item_usage_count(food_id) > 0:
        raise ValueError("This food item is used in existing records and cannot be deleted.")
    with get_connection() as conn:
        conn.execute("DELETE FROM food_items WHERE id = ?", (food_id,))
        conn.commit()


# ---------------------------------------------------------------- daily production

def upsert_production(day, food_id: int, prepared: float, served: float, consumed: float) -> None:
    """
    Insert or update the production row for one food on one date.

    `prepared` is the measured starting quantity of the accounting model
    (services/accounting.py). `served` and `consumed` are stored only as a
    snapshot at save time; every page re-derives them from prepared + waste
    records, so food can never be double-counted by reading these columns.
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_production (date, food_id, quantity_prepared, quantity_served, quantity_consumed)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (date, food_id) DO UPDATE SET
                quantity_prepared = excluded.quantity_prepared,
                quantity_served   = excluded.quantity_served,
                quantity_consumed = excluded.quantity_consumed
            """,
            (_iso(day), food_id, float(prepared), float(served), float(consumed)),
        )
        conn.commit()


def delete_production_day(day) -> None:
    """Remove every production row for one date."""
    with get_connection() as conn:
        conn.execute("DELETE FROM daily_production WHERE date = ?", (_iso(day),))
        conn.commit()


def delete_production_row(day, food_id: int) -> None:
    """Remove the production row for one food on one date (used when cleared to 0)."""
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM daily_production WHERE date = ? AND food_id = ?",
            (_iso(day), food_id),
        )
        conn.commit()


def set_expected_demand(day, food_id: int, expected_demand: float) -> None:
    """
    Store the kitchen's expected demand (kg) for one food on one date.

    Creates a zero-production row when none exists yet, so tomorrow's demand
    can be planned before cooking starts.
    """
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO daily_production (date, food_id, quantity_prepared, quantity_served,
                                          quantity_consumed, expected_demand)
            VALUES (?, ?, 0, 0, 0, ?)
            ON CONFLICT (date, food_id) DO UPDATE SET expected_demand = excluded.expected_demand
            """,
            (_iso(day), food_id, float(expected_demand)),
        )
        conn.commit()


def get_production_day(day) -> pd.DataFrame:
    """
    Production rows (joined with food names) for a single date.

    `quantity_served` / `quantity_consumed` are save-time snapshots; use
    services.accounting (prepared + waste records) for the displayed values.
    """
    return _read_df(
        """
        SELECT dp.date, dp.food_id, f.food_name, dp.quantity_prepared, dp.quantity_served, dp.quantity_consumed,
               dp.batch_note, dp.expected_demand
        FROM daily_production dp
        JOIN food_items f ON f.id = dp.food_id
        WHERE dp.date = ?
        ORDER BY f.food_name
        """,
        (_iso(day),),
    )


def get_production_range(start, end) -> pd.DataFrame:
    """Production rows for a date range (inclusive)."""
    # batch_note and expected_demand are included so kitchen planning pages can
    # read them without a second query.
    return _read_df(
        """
        SELECT dp.date, dp.food_id, f.food_name, dp.quantity_prepared, dp.quantity_served, dp.quantity_consumed,
               dp.batch_note, dp.expected_demand
        FROM daily_production dp
        JOIN food_items f ON f.id = dp.food_id
        WHERE dp.date BETWEEN ? AND ?
        ORDER BY dp.date, f.food_name
        """,
        (_iso(start), _iso(end)),
    )


# ---------------------------------------------------------------- waste records

def add_waste_record(day, food_id: int, waste_type: str, quantity: float, reason: str = "") -> int:
    """Record one waste entry (kitchen / serving / plate)."""
    if waste_type not in {"kitchen", "serving", "plate"}:
        raise ValueError("Waste type must be kitchen, serving or plate.")
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO waste_records (date, food_id, waste_type, quantity, reason) VALUES (?, ?, ?, ?, ?)",
            (_iso(day), food_id, waste_type, float(quantity), reason.strip()),
        )
        conn.commit()
        return cursor.lastrowid


def delete_waste_record(record_id: int) -> None:
    """Delete a single waste entry."""
    with get_connection() as conn:
        conn.execute("DELETE FROM waste_records WHERE id = ?", (record_id,))
        conn.commit()


def get_waste_range(start, end) -> pd.DataFrame:
    """Waste entries (joined with food names) for a date range."""
    return _read_df(
        """
        SELECT wr.id, wr.date, wr.food_id, f.food_name, wr.waste_type, wr.quantity, wr.reason
        FROM waste_records wr
        JOIN food_items f ON f.id = wr.food_id
        WHERE wr.date BETWEEN ? AND ?
        ORDER BY wr.date DESC, wr.id DESC
        """,
        (_iso(start), _iso(end)),
    )


def get_waste_day(day) -> pd.DataFrame:
    """Waste entries for one date."""
    return get_waste_range(day, day)


def get_food_waste_on_date(food_id: int, day) -> float:
    """Total recorded waste (all three types) for one food on one date."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(quantity), 0) AS total FROM waste_records WHERE food_id = ? AND date = ?",
            (food_id, _iso(day)),
        ).fetchone()
    return float(row["total"])


def replace_plate_waste_day(day, customers: int, rows: list[tuple[int, float]]) -> None:
    """
    Save the plate-waste sheet for one date.

    Plate waste is stored in two places so that totals stay consistent:
      * `waste_records` (waste_type = 'plate') is the single waste ledger.
      * `plate_waste` keeps the customer count used for the per-customer average.
    Existing entries for the date are replaced, which makes editing a day easy.
    """
    day_iso = _iso(day)
    with get_connection() as conn:
        conn.execute("DELETE FROM waste_records WHERE date = ? AND waste_type = 'plate'", (day_iso,))
        conn.execute("DELETE FROM plate_waste WHERE date = ?", (day_iso,))
        for food_id, quantity in rows:
            if quantity is None or float(quantity) <= 0:
                continue
            conn.execute(
                "INSERT INTO waste_records (date, food_id, waste_type, quantity, reason) VALUES (?, ?, 'plate', ?, ?)",
                (day_iso, food_id, float(quantity), "Plate waste (from plate-waste sheet)"),
            )
            conn.execute(
                "INSERT INTO plate_waste (date, customers_served, food_id, quantity_wasted) VALUES (?, ?, ?, ?)",
                (day_iso, int(customers), food_id, float(quantity)),
            )
        conn.commit()


def get_plate_waste_day(day) -> pd.DataFrame:
    """Plate-waste rows for one date."""
    return _read_df(
        """
        SELECT pw.date, pw.customers_served, pw.food_id, f.food_name, pw.quantity_wasted
        FROM plate_waste pw
        JOIN food_items f ON f.id = pw.food_id
        WHERE pw.date = ?
        ORDER BY f.food_name
        """,
        (_iso(day),),
    )


def get_plate_waste_range(start, end) -> pd.DataFrame:
    """Plate-waste rows for a date range."""
    return _read_df(
        """
        SELECT pw.date, pw.customers_served, pw.food_id, f.food_name, pw.quantity_wasted
        FROM plate_waste pw
        JOIN food_items f ON f.id = pw.food_id
        WHERE pw.date BETWEEN ? AND ?
        ORDER BY pw.date, f.food_name
        """,
        (_iso(start), _iso(end)),
    )


def get_customers_by_day(start, end) -> pd.DataFrame:
    """Customers served per recorded date (one row per day)."""
    return _read_df(
        """
        SELECT date, MAX(customers_served) AS customers_served
        FROM plate_waste
        WHERE date BETWEEN ? AND ?
        GROUP BY date
        ORDER BY date
        """,
        (_iso(start), _iso(end)),
    )


# ---------------------------------------------------------------- plate washing

def add_washing_record(day, method: str, plates: int, water_used: float,
                       flow_rate: float | None = None, washing_time: float | None = None,
                       details: str = "") -> int:
    """Store one estimated plate-washing water record."""
    if method not in {"running_tap", "bucket", "dishwasher", "other"}:
        raise ValueError("Unknown washing method.")
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO washing_records (date, washing_method, plates, water_used, flow_rate, washing_time, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (_iso(day), method, int(plates), float(water_used), flow_rate, washing_time, details.strip()),
        )
        conn.commit()
        return cursor.lastrowid


def delete_washing_record(record_id: int) -> None:
    """Delete one washing-water record."""
    with get_connection() as conn:
        conn.execute("DELETE FROM washing_records WHERE id = ?", (record_id,))
        conn.commit()


def get_washing_range(start, end) -> pd.DataFrame:
    """Washing-water records for a date range."""
    return _read_df(
        """
        SELECT id, date, washing_method, plates, water_used, flow_rate, washing_time, details
        FROM washing_records
        WHERE date BETWEEN ? AND ?
        ORDER BY date DESC, id DESC
        """,
        (_iso(start), _iso(end)),
    )


# ---------------------------------------------------------------- sales

ORDER_TYPES = ("dine-in", "takeaway", "delivery", "buffet", "other")


def add_sale(day, food_id: int, quantity_sold: float, unit_price: float,
             order_type: str = "dine-in", time: str = "", user_id: int | None = None) -> int:
    """Record one sales entry. Returns the new row id."""
    if order_type not in ORDER_TYPES:
        raise ValueError(f"Order type must be one of: {', '.join(ORDER_TYPES)}.")
    quantity = float(quantity_sold)
    price = float(unit_price)
    with get_connection() as conn:
        cursor = conn.execute(
            """
            INSERT INTO sales (date, time, food_id, quantity_sold, unit_price, order_type, total_amount, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (_iso(day), time.strip(), food_id, quantity, price, order_type,
             round(quantity * price, 2), user_id),
        )
        conn.commit()
        return cursor.lastrowid


def delete_sale(sale_id: int) -> None:
    """Delete one sales entry."""
    with get_connection() as conn:
        conn.execute("DELETE FROM sales WHERE id = ?", (sale_id,))
        conn.commit()


def get_sales_range(start, end) -> pd.DataFrame:
    """Sales entries (joined with food names) for a date range."""
    return _read_df(
        """
        SELECT s.id, s.date, s.time, s.food_id, f.food_name, f.unit, f.portion_size_g, f.cost_per_kg,
               s.quantity_sold, s.unit_price, s.order_type, s.total_amount
        FROM sales s
        JOIN food_items f ON f.id = s.food_id
        WHERE s.date BETWEEN ? AND ?
        ORDER BY s.date DESC, s.time DESC, s.id DESC
        """,
        (_iso(start), _iso(end)),
    )


def get_sales_day(day) -> pd.DataFrame:
    """Sales entries for one date."""
    return get_sales_range(day, day)


# ---------------------------------------------------------------- remaining food

def upsert_remaining_food(day, food_id: int, carry_over: float, note: str = "") -> None:
    """Record the carry-over (reusable) quantity for one food on one date."""
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO remaining_food (date, food_id, carry_over, note)
            VALUES (?, ?, ?, ?)
            ON CONFLICT (date, food_id) DO UPDATE SET
                carry_over = excluded.carry_over,
                note       = excluded.note
            """,
            (_iso(day), food_id, float(carry_over), note.strip()),
        )
        conn.commit()


def get_remaining_range(start, end) -> pd.DataFrame:
    """Carry-over rows (joined with food names) for a date range."""
    return _read_df(
        """
        SELECT rf.date, rf.food_id, f.food_name, rf.carry_over, rf.note
        FROM remaining_food rf
        JOIN food_items f ON f.id = rf.food_id
        WHERE rf.date BETWEEN ? AND ?
        ORDER BY rf.date, f.food_name
        """,
        (_iso(start), _iso(end)),
    )


def get_remaining_day(day) -> pd.DataFrame:
    """Carry-over rows for one date."""
    return get_remaining_range(day, day)


# ---------------------------------------------------------------- housekeeping

def table_counts() -> dict:
    """Row counts for each data table (used on the dashboard and settings)."""
    with get_connection() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("daily_production", "waste_records", "plate_waste", "washing_records",
                          "sales", "remaining_food", "food_items", "users")
        }


def has_records() -> bool:
    """True when at least one production, waste or sales row exists."""
    counts = table_counts()
    return (counts["daily_production"] + counts["waste_records"] + counts["sales"]) > 0


def clear_all_records() -> None:
    """Delete all operational records (keeps foods + users)."""
    with get_connection() as conn:
        for table in ("daily_production", "waste_records", "plate_waste", "washing_records",
                      "sales", "remaining_food"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
