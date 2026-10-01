"""
FoodWaste360 - Database schema.

This module defines:
  * The SQLite table structure (DDL).
  * Password hashing / verification helpers (PBKDF2, from the standard library).
  * Seed functions that populate default food factors and demo users.

Every factor stored in `food_items` carries its own source and reference so the
application never presents an unsourced environmental number.
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
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    role          TEXT NOT NULL CHECK (role IN ('admin', 'manager', 'kitchen', 'staff')),
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
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
    is_estimated     INTEGER NOT NULL DEFAULT 1 CHECK (is_estimated IN (0, 1)),
    notes            TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS daily_production (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    date               TEXT NOT NULL,
    food_id            INTEGER NOT NULL REFERENCES food_items(id),
    quantity_prepared  REAL NOT NULL DEFAULT 0 CHECK (quantity_prepared >= 0),
    quantity_served    REAL NOT NULL DEFAULT 0 CHECK (quantity_served >= 0),
    quantity_consumed  REAL NOT NULL DEFAULT 0 CHECK (quantity_consumed >= 0),
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
"""

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

# Demo accounts (documented in the README). The password is shared by all
# demo users so the app can be tested immediately after installation.
DEMO_PASSWORD = "demo1234"
DEMO_USERS = [
    {"name": "Admin User",   "email": "admin@foodwaste360.demo",   "role": "admin"},
    {"name": "Priya Sharma", "email": "manager@foodwaste360.demo", "role": "manager"},
    {"name": "Ravi Kumar",   "email": "kitchen@foodwaste360.demo", "role": "kitchen"},
    {"name": "Anita Desai",  "email": "staff@foodwaste360.demo",   "role": "staff"},
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
                     factor_source, factor_reference, factor_date, is_estimated, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if str(row.get("is_estimated", "1")).strip() in {"1", "true", "True", "yes"} else 0,
                    row.get("notes", "").strip(),
                ),
            )
            inserted += 1
    conn.commit()
    return inserted


def seed_users(conn: sqlite3.Connection) -> int:
    """Create the demo user accounts when the users table is empty."""
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count > 0:
        return 0
    for user in DEMO_USERS:
        conn.execute(
            "INSERT INTO users (name, email, role, password_hash) VALUES (?, ?, ?, ?)",
            (user["name"], user["email"], user["role"], hash_password(DEMO_PASSWORD)),
        )
    conn.commit()
    return len(DEMO_USERS)


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
