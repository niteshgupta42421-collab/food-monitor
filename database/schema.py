"""
MealFlow360 - Database schema.

This module defines:
  * The SQLite table structure (DDL) for a fresh database.
  * In-place migrations (ALTER TABLE) so existing databases gain the new
    sales / inventory / theme columns without losing data.
  * Password hashing / verification helpers (PBKDF2, from the standard library).
  * Seed functions that populate default food items and demo users.

Every factor stored in `food_items` carries its own source and reference so the
application never presents an unsourced environmental number.

Food quantities follow the single accounting model in services/accounting.py:
`quantity_prepared` and the `waste_records` categories are the measured inputs;
`quantity_served` / `quantity_consumed` are save-time snapshots and are never
read for display (served and consumed are always re-derived). The `sales`
table records the quantities actually sold, from which remaining food is
derived.
"""

import csv
import hashlib
import secrets
import sqlite3
from pathlib import Path

# ---------------------------------------------------------------- paths

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
FOOD_FACTORS_CSV = DATA_DIR / "food_factors.csv"

# ---------------------------------------------------------------- DDL

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    name            TEXT NOT NULL,
    email           TEXT NOT NULL UNIQUE,
    role            TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'kitchen', 'staff')),
    password_hash   TEXT NOT NULL,
    restaurant_name TEXT NOT NULL DEFAULT '',
    theme           TEXT NOT NULL DEFAULT 'light',
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS food_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    food_name        TEXT NOT NULL UNIQUE,
    category         TEXT NOT NULL DEFAULT '',
    unit             TEXT NOT NULL DEFAULT 'kg',
    cost_per_kg      REAL NOT NULL DEFAULT 0 CHECK (cost_per_kg >= 0),
    co2_factor       REAL CHECK (co2_factor IS NULL OR co2_factor >= 0),
    water_factor     REAL CHECK (water_factor IS NULL OR water_factor >= 0),
    factor_source    TEXT NOT NULL DEFAULT '',
    factor_reference TEXT NOT NULL DEFAULT '',
    factor_date      TEXT NOT NULL DEFAULT '',
    factor_version   TEXT NOT NULL DEFAULT '',
    is_estimated     INTEGER NOT NULL DEFAULT 1 CHECK (is_estimated IN (0, 1)),
    selling_price    REAL NOT NULL DEFAULT 0 CHECK (selling_price >= 0),
    portion_size_g   REAL NOT NULL DEFAULT 0 CHECK (portion_size_g >= 0),
    low_stock_threshold REAL NOT NULL DEFAULT 0 CHECK (low_stock_threshold >= 0),
    production_mode  TEXT NOT NULL DEFAULT 'pre_prepared'
                     CHECK (production_mode IN ('pre_prepared', 'made_to_order')),
    active           INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1)),
    notes            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS daily_production (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    date               TEXT NOT NULL,
    food_id            INTEGER NOT NULL REFERENCES food_items(id),
    quantity_prepared  REAL NOT NULL DEFAULT 0 CHECK (quantity_prepared >= 0),
    quantity_served    REAL NOT NULL DEFAULT 0 CHECK (quantity_served >= 0),
    quantity_consumed  REAL NOT NULL DEFAULT 0 CHECK (quantity_consumed >= 0),
    batch_note         TEXT NOT NULL DEFAULT '',
    expected_demand    REAL NOT NULL DEFAULT 0 CHECK (expected_demand >= 0),
    UNIQUE (date, food_id)
);

CREATE TABLE IF NOT EXISTS sales (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    date          TEXT NOT NULL,
    time          TEXT NOT NULL DEFAULT '',
    food_id       INTEGER NOT NULL REFERENCES food_items(id),
    quantity_sold REAL NOT NULL CHECK (quantity_sold >= 0),
    unit_price    REAL NOT NULL CHECK (unit_price >= 0),
    order_type    TEXT NOT NULL DEFAULT 'dine-in'
                  CHECK (order_type IN ('dine-in', 'takeaway', 'delivery', 'buffet', 'other')),
    total_amount  REAL NOT NULL DEFAULT 0,
    user_id       INTEGER REFERENCES users(id),
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS remaining_food (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    date               TEXT NOT NULL,
    food_id            INTEGER NOT NULL REFERENCES food_items(id),
    carry_over         REAL NOT NULL DEFAULT 0 CHECK (carry_over >= 0),
    note               TEXT NOT NULL DEFAULT '',
    UNIQUE (date, food_id)
);

CREATE TABLE IF NOT EXISTS waste_records (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    date       TEXT NOT NULL,
    food_id    INTEGER NOT NULL REFERENCES food_items(id),
    waste_type TEXT NOT NULL CHECK (waste_type IN ('kitchen', 'serving', 'plate')),
    quantity   REAL NOT NULL CHECK (quantity >= 0),
    reason     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plate_waste (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    date             TEXT NOT NULL,
    customers_served INTEGER NOT NULL CHECK (customers_served >= 0),
    food_id          INTEGER NOT NULL REFERENCES food_items(id),
    quantity_wasted  REAL NOT NULL CHECK (quantity_wasted >= 0),
    UNIQUE (date, food_id)
);

CREATE TABLE IF NOT EXISTS washing_records (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    date           TEXT NOT NULL,
    washing_method TEXT NOT NULL CHECK (washing_method IN ('running_tap', 'bucket', 'dishwasher', 'other')),
    plates         INTEGER NOT NULL CHECK (plates >= 0),
    water_used     REAL NOT NULL CHECK (water_used >= 0),
    flow_rate      REAL CHECK (flow_rate IS NULL OR flow_rate >= 0),
    washing_time   REAL CHECK (washing_time IS NULL OR washing_time >= 0),
    details        TEXT NOT NULL DEFAULT '',
    created_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_waste_date  ON waste_records (date);
CREATE INDEX IF NOT EXISTS idx_prod_date   ON daily_production (date);
CREATE INDEX IF NOT EXISTS idx_plate_date  ON plate_waste (date);
CREATE INDEX IF NOT EXISTS idx_wash_date   ON washing_records (date);
CREATE INDEX IF NOT EXISTS idx_sales_date  ON sales (date);
CREATE INDEX IF NOT EXISTS idx_remain_date ON remaining_food (date);
"""

# ---------------------------------------------------------------- migrations

# Columns added after the first release. migrate_schema() applies only the
# missing ones, so existing databases keep their data and gain the new fields.
MIGRATIONS: list[tuple[str, str, str]] = [
    ("users", "restaurant_name", "TEXT NOT NULL DEFAULT ''"),
    ("users", "theme", "TEXT NOT NULL DEFAULT 'light'"),
    ("food_items", "factor_version", "TEXT NOT NULL DEFAULT ''"),
    ("food_items", "selling_price", "REAL NOT NULL DEFAULT 0"),
    ("food_items", "portion_size_g", "REAL NOT NULL DEFAULT 0"),
    ("food_items", "low_stock_threshold", "REAL NOT NULL DEFAULT 0"),
    ("food_items", "production_mode", "TEXT NOT NULL DEFAULT 'pre_prepared'"),
    ("food_items", "active", "INTEGER NOT NULL DEFAULT 1"),
    ("daily_production", "batch_note", "TEXT NOT NULL DEFAULT ''"),
    ("daily_production", "expected_demand", "REAL NOT NULL DEFAULT 0"),
]


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Column names currently present on a table."""
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate_schema(conn: sqlite3.Connection) -> list[str]:
    """
    Bring an existing database up to date in place. Returns the list of
    columns that were actually added (useful for logging/tests).
    """
    added = []
    for table, column, ddl in MIGRATIONS:
        if column not in _table_columns(conn, table):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")
            added.append(f"{table}.{column}")
    # Rebrand of the demo accounts: keep existing rows working under the new
    # MealFlow360 identity.
    conn.execute(
        "UPDATE users SET email = REPLACE(email, '@foodwaste360.demo', '@mealflow360.demo') "
        "WHERE email LIKE '%@foodwaste360.demo'"
    )
    conn.commit()
    return added

# ---------------------------------------------------------------- password helpers

def hash_password(password: str) -> str:
    """Return a salted PBKDF2 hash string in the form 'salt$hash'."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000)
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Check a plain password against a stored 'salt$hash' value."""
    try:
        salt, expected = stored_hash.split("$", 1)
        digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 120_000)
        return secrets.compare_digest(digest.hex(), expected)
    except (ValueError, AttributeError):
        return False

# ---------------------------------------------------------------- seeding

# Demo accounts (documented in the README). The role accounts share one
# password so the app can be tested immediately after installation; the
# flagship demo account follows the published MealFlow360 credentials.
DEMO_PASSWORD = "demo1234"
DEMO_ACCOUNT_EMAIL = "demo@mealflow360.com"
DEMO_ACCOUNT_PASSWORD = "Demo@123"
DEMO_USERS = [
    {"name": "Demo Account", "email": DEMO_ACCOUNT_EMAIL, "role": "admin", "password": DEMO_ACCOUNT_PASSWORD},
    {"name": "Admin User",   "email": "admin@mealflow360.demo",   "role": "admin", "password": DEMO_PASSWORD},
    {"name": "Priya Sharma", "email": "manager@mealflow360.demo", "role": "manager", "password": DEMO_PASSWORD},
    {"name": "Ravi Kumar",   "email": "kitchen@mealflow360.demo", "role": "kitchen", "password": DEMO_PASSWORD},
    {"name": "Anita Desai",  "email": "staff@mealflow360.demo",   "role": "staff", "password": DEMO_PASSWORD},
]


def create_tables(conn: sqlite3.Connection) -> None:
    """Create every table if it does not exist yet."""
    conn.executescript(SCHEMA_SQL)
    conn.commit()


def seed_food_items(conn: sqlite3.Connection) -> int:
    """
    Load the default food items and their documented impact factors from
    data/food_factors.csv. Only runs when the food_items table is empty.

    Returns the number of food items inserted.
    """
    count = conn.execute("SELECT COUNT(*) FROM food_items").fetchone()[0]
    if count > 0:
        return 0
    if not FOOD_FACTORS_CSV.exists():
        return 0

    inserted = 0
    with open(FOOD_FACTORS_CSV, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            conn.execute(
                """
                INSERT INTO food_items
                    (food_name, category, unit, cost_per_kg, co2_factor, water_factor,
                     factor_source, factor_reference, factor_date, factor_version,
                     is_estimated, selling_price, portion_size_g, low_stock_threshold,
                     production_mode, active, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["food_name"].strip(),
                    row.get("category", "").strip(),
                    row.get("unit", "kg").strip() or "kg",
                    _to_float_or_zero(row.get("cost_per_kg")),
                    _to_float_or_none(row.get("co2_factor")),
                    _to_float_or_none(row.get("water_factor")),
                    row.get("factor_source", "").strip(),
                    row.get("factor_reference", "").strip(),
                    row.get("factor_date", "").strip(),
                    row.get("factor_version", "").strip(),
                    1 if str(row.get("is_estimated", "1")).strip() in {"1", "true", "True", "yes"} else 0,
                    _to_float_or_zero(row.get("selling_price")),
                    _to_float_or_zero(row.get("portion_size_g")),
                    _to_float_or_zero(row.get("low_stock_threshold")),
                    "made_to_order" if str(row.get("production_mode", "")).strip() == "made_to_order"
                    else "pre_prepared",
                    1 if str(row.get("active", "1")).strip() in {"1", "true", "True", "yes"} else 0,
                    row.get("notes", "").strip(),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def seed_users(conn: sqlite3.Connection) -> int:
    """Ensure every demo account exists (safe for fresh and existing databases)."""
    inserted = 0
    for user in DEMO_USERS:
        exists = conn.execute("SELECT 1 FROM users WHERE email = ?", (user["email"],)).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO users (name, email, role, password_hash) VALUES (?, ?, ?, ?)",
            (user["name"], user["email"], user["role"], hash_password(user["password"])),
        )
        inserted += 1
    conn.commit()
    return inserted


def backfill_food_sales_fields(conn: sqlite3.Connection) -> int:
    """
    Fill the new sales/inventory fields (selling price, portion size, low-stock
    threshold, production mode, factor version) for pre-existing food rows that
    still carry the migration defaults. Rows an administrator has already
    edited (non-zero selling price or portion size) are left untouched.

    Returns the number of food rows updated.
    """
    if not FOOD_FACTORS_CSV.exists():
        return 0
    updated = 0
    with open(FOOD_FACTORS_CSV, "r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            name = row["food_name"].strip()
            cursor = conn.execute(
                """
                UPDATE food_items SET
                    unit = ?, selling_price = ?, portion_size_g = ?,
                    low_stock_threshold = ?, production_mode = ?, factor_version = ?
                WHERE food_name = ? AND selling_price = 0 AND portion_size_g = 0
                """,
                (
                    row.get("unit", "kg").strip() or "kg",
                    _to_float_or_zero(row.get("selling_price")),
                    _to_float_or_zero(row.get("portion_size_g")),
                    _to_float_or_zero(row.get("low_stock_threshold")),
                    "made_to_order" if str(row.get("production_mode", "")).strip() == "made_to_order"
                    else "pre_prepared",
                    row.get("factor_version", "").strip(),
                    name,
                ),
            )
            updated += cursor.rowcount
    conn.commit()
    return updated


# ---------------------------------------------------------------- small helpers

def _to_float_or_none(value) -> float | None:
    """Convert a CSV value to float, returning None for empty/invalid input."""
    if value is None:
        return None
    text = str(value).strip()
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_float_or_zero(value) -> float:
    """Convert a CSV value to float, returning 0.0 for empty/invalid input."""
    result = _to_float_or_none(value)
    return 0.0 if result is None else result
