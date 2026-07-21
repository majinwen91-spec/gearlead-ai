from __future__ import annotations

import csv
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from gearlead.config import get_settings


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    sku TEXT NOT NULL UNIQUE,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    base_price_min REAL,
    base_price_max REAL,
    currency TEXT NOT NULL DEFAULT 'USD',
    standard_moq INTEGER NOT NULL,
    trial_moq INTEGER NOT NULL,
    sample_available INTEGER NOT NULL,
    sample_lead_time_days INTEGER NOT NULL,
    mass_production_lead_time_days INTEGER NOT NULL,
    oem_supported INTEGER NOT NULL,
    odm_supported INTEGER NOT NULL,
    logo_customization INTEGER NOT NULL,
    color_customization INTEGER NOT NULL,
    packaging_customization INTEGER NOT NULL,
    certifications TEXT NOT NULL,
    supported_markets TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mouse_specs (
    product_id TEXT PRIMARY KEY REFERENCES products(product_id),
    connection_type TEXT, sensor_model TEXT, max_dpi INTEGER, polling_rate TEXT,
    weight_grams INTEGER, switch_type TEXT, button_count INTEGER,
    battery_capacity TEXT, shape TEXT, rgb INTEGER, software_support INTEGER
);

CREATE TABLE IF NOT EXISTS keyboard_specs (
    product_id TEXT PRIMARY KEY REFERENCES products(product_id),
    layout TEXT, key_count INTEGER, connection_type TEXT, switch_type TEXT,
    hot_swappable INTEGER, mounting_structure TEXT, keycap_material TEXT,
    keycap_profile TEXT, case_material TEXT, firmware_support TEXT,
    language_layout TEXT, battery_capacity TEXT
);

CREATE TABLE IF NOT EXISTS headset_specs (
    product_id TEXT PRIMARY KEY REFERENCES products(product_id),
    connection_type TEXT, driver_size TEXT, audio_channel TEXT,
    microphone_type TEXT, noise_reduction TEXT, battery_life TEXT,
    platform_support TEXT, weight_grams INTEGER, rgb INTEGER,
    ear_cushion_material TEXT
);

CREATE TABLE IF NOT EXISTS cable_specs (
    product_id TEXT PRIMARY KEY REFERENCES products(product_id),
    cable_type TEXT, connector_a TEXT, connector_b TEXT,
    aviator_connector TEXT, total_length TEXT, coil_length TEXT,
    sleeve_material TEXT, available_colors TEXT, data_standard TEXT
);

CREATE TABLE IF NOT EXISTS keycap_specs (
    product_id TEXT PRIMARY KEY REFERENCES products(product_id),
    material TEXT, manufacturing_method TEXT, profile TEXT, layout TEXT,
    language TEXT, key_count INTEGER, shine_through INTEGER,
    custom_artwork_supported INTEGER, pantone_matching INTEGER
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    country TEXT,
    email_domain TEXT,
    customer_type TEXT,
    website TEXT,
    historical_inquiries INTEGER NOT NULL DEFAULT 0,
    historical_orders INTEGER NOT NULL DEFAULT 0,
    risk_status TEXT NOT NULL DEFAULT 'normal',
    notes TEXT
);

CREATE TABLE IF NOT EXISTS crm_leads (
    lead_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    customer_name TEXT,
    country TEXT,
    category TEXT,
    requested_quantity INTEGER,
    lead_score INTEGER,
    priority TEXT,
    match_type TEXT,
    recommended_sku TEXT,
    next_action TEXT,
    reply_draft TEXT,
    raw_inquiry TEXT
);

CREATE TABLE IF NOT EXISTS lead_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id TEXT NOT NULL REFERENCES crm_leads(lead_id),
    event_type TEXT NOT NULL,
    event_at TEXT NOT NULL,
    detail TEXT
);

CREATE TABLE IF NOT EXISTS scoring_rules (
    rule_id TEXT PRIMARY KEY,
    dimension TEXT NOT NULL,
    condition_label TEXT NOT NULL,
    points INTEGER NOT NULL,
    explanation TEXT NOT NULL
);
"""


SPEC_TABLES = {
    "gaming_mouse": (
        "mouse_specs",
        ["connection_type", "sensor_model", "max_dpi", "polling_rate", "weight_grams", "switch_type", "button_count", "battery_capacity", "shape", "rgb", "software_support"],
    ),
    "mechanical_keyboard": (
        "keyboard_specs",
        ["layout", "key_count", "connection_type", "switch_type", "hot_swappable", "mounting_structure", "keycap_material", "keycap_profile", "case_material", "firmware_support", "language_layout", "battery_capacity"],
    ),
    "gaming_headset": (
        "headset_specs",
        ["connection_type", "driver_size", "audio_channel", "microphone_type", "noise_reduction", "battery_life", "platform_support", "weight_grams", "rgb", "ear_cushion_material"],
    ),
    "custom_cable": (
        "cable_specs",
        ["cable_type", "connector_a", "connector_b", "aviator_connector", "total_length", "coil_length", "sleeve_material", "available_colors", "data_standard"],
    ),
    "custom_keycap": (
        "keycap_specs",
        ["material", "manufacturing_method", "profile", "layout", "language", "key_count", "shine_through", "custom_artwork_supported", "pantone_matching"],
    ),
}


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialize_database(db_path: Path | None = None, force_seed: bool = False) -> Path:
    settings = get_settings()
    path = db_path or settings.database_path
    with connect(path) as connection:
        connection.executescript(SCHEMA)
        count = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        if force_seed or count == 0:
            _seed_products(connection, settings.project_root / "data" / "seed_products.csv")
        customer_count = connection.execute("SELECT COUNT(*) FROM customers").fetchone()[0]
        if force_seed or customer_count == 0:
            _seed_customers(connection, settings.project_root / "data" / "seed_customers.csv")
        rule_count = connection.execute("SELECT COUNT(*) FROM scoring_rules").fetchone()[0]
        if force_seed or rule_count == 0:
            _seed_rules(connection)
    return path


def _bool_int(value: str) -> int:
    return int(str(value).strip().lower() in {"1", "true", "yes"})


def _seed_products(connection: sqlite3.Connection, path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            connection.execute(
                """INSERT OR REPLACE INTO products VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    row["product_id"], row["sku"], row["product_name"], row["category"],
                    row["status"], float(row["base_price_min"]), float(row["base_price_max"]),
                    row["currency"], int(row["standard_moq"]), int(row["trial_moq"]),
                    _bool_int(row["sample_available"]), int(row["sample_lead_time_days"]),
                    int(row["mass_production_lead_time_days"]), _bool_int(row["oem_supported"]),
                    _bool_int(row["odm_supported"]), _bool_int(row["logo_customization"]),
                    _bool_int(row["color_customization"]), _bool_int(row["packaging_customization"]),
                    row["certifications"], row["supported_markets"],
                ),
            )
            table, columns = SPEC_TABLES[row["category"]]
            specs = json.loads(row["specs_json"])
            values = [specs.get(column) for column in columns]
            placeholders = ",".join("?" for _ in range(len(columns) + 1))
            connection.execute(
                f"INSERT OR REPLACE INTO {table} (product_id,{','.join(columns)}) VALUES ({placeholders})",
                [row["product_id"], *values],
            )


def _seed_customers(connection: sqlite3.Connection, path: Path) -> None:
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            connection.execute(
                "INSERT OR REPLACE INTO customers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    row["customer_id"], row["company_name"], row["country"], row["email_domain"],
                    row["customer_type"], row["website"], int(row["historical_inquiries"]),
                    int(row["historical_orders"]), row["risk_status"], row["notes"],
                ),
            )


def _seed_rules(connection: sqlite3.Connection) -> None:
    rules = [
        ("cred_email", "customer_credibility", "Corporate email", 5, "A corporate domain is provided."),
        ("cred_company", "customer_credibility", "Company name", 4, "The buyer identifies a company."),
        ("clarity_category", "requirement_clarity", "Product category", 4, "The category is identifiable."),
        ("moq_standard", "moq_fit", "Meets standard MOQ", 15, "Quantity reaches the recommended SKU MOQ."),
        ("fit_sku", "feasibility", "Standard SKU", 20, "An existing SKU can satisfy the request."),
        ("urgency_date", "urgency", "Commercial date", 10, "The inquiry states a delivery or launch date."),
    ]
    connection.executemany("INSERT OR REPLACE INTO scoring_rules VALUES (?, ?, ?, ?, ?)", rules)

