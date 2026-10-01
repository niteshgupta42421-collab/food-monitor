"""
FoodWaste360 - Data access layer.

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
    "factor_source", "factor_reference", "factor_date", "is_estimated", "notes",
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
    """Create tables and seed default foods + demo users (safe to call often)."""
    with get_connection() as conn:
        schema.create_tables(conn)
        schema.seed_food_items(conn)
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
        return conn.execute("SELECT id, name, email, role, created_at FROM users ORDER BY id").fetchall()


def create_user(name: str, email: str, role: str, password: str) -> None:
    """Create a new user. Raises ValueError for duplicates or invalid roles."""
    if role not in {"admin", "manager", "kitchen", "staff"}:
        raise ValueError("Role must be one of: admin, manager, kitchen, staff.")
    try:
        with get_connection() as conn:
            conn.execute(
                "INSERT INTO users (name, email, role, password_hash) VALUES (?, ?, ?, ?)",
                (name.strip(), email.strip().lower(), role, schema.hash_password(password)),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"A user with email '{email}' already exists.")


# ---------------------------------------------------------------- food items

def get_food_items_df() -> pd.DataFrame:
    """All food items with their cost and documented impact factors."""
    return _read_df(
        """
        SELECT id, food_name, category, unit, cost_per_kg, co2_factor, water_factor,
               factor_source, factor_reference, factor_date, is_estimated, notes
        FROM food_items
        ORDER BY food_name
        """
    )


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
                  is_estimated: int = 1, notes: str = "") -> int:
    """Insert a new food item and return its id."""
    try:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO food_items
                    (food_name, category, unit, cost_per_kg, co2_factor, water_factor,
                     factor_source, factor_reference, factor_date, is_estimated, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (food_name.strip(), category.strip(), unit.strip() or "kg", float(cost_per_kg),
                 co2_factor, water_factor, factor_source.strip(), factor_reference.strip(),
                 factor_date.strip(), int(is_estimated), notes.strip()),
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
    """How many production / waste / plate rows reference this food."""
    with get_connection() as conn:
        total = 0
        for table in ("daily_production", "waste_records", "plate_waste"):
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
    """Insert or update the production row for one food on one date."""
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


def get_production_day(day) -> pd.DataFrame:
    """Production rows (joined with food names) for a single date."""
    return _read_df(
        """
        SELECT dp.date, dp.food_id, f.food_name, dp.quantity_prepared, dp.quantity_served, dp.quantity_consumed
        FROM daily_production dp
        JOIN food_items f ON f.id = dp.food_id
        WHERE dp.date = ?
        ORDER BY f.food_name
        """,
        (_iso(day),),
    )


def get_production_range(start, end) -> pd.DataFrame:
    """Production rows for a date range (inclusive)."""
    return _read_df(
        """
        SELECT dp.date, dp.food_id, f.food_name, dp.quantity_prepared, dp.quantity_served, dp.quantity_consumed
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


# ---------------------------------------------------------------- housekeeping

def table_counts() -> dict:
    """Row counts for each data table (used on the dashboard and settings)."""
    with get_connection() as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in ("daily_production", "waste_records", "plate_waste", "washing_records", "food_items", "users")
        }


def has_records() -> bool:
    """True when at least one production or waste row exists."""
    counts = table_counts()
    return (counts["daily_production"] + counts["waste_records"]) > 0


def clear_all_records() -> None:
    """Delete all production, waste, plate-waste and washing records (keeps foods + users)."""
    with get_connection() as conn:
        for table in ("daily_production", "waste_records", "plate_waste", "washing_records"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
