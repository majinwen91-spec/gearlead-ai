from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from gearlead.database import SPEC_TABLES, connect, initialize_database


BOOLEAN_FIELDS = {
    "sample_available", "oem_supported", "odm_supported", "logo_customization",
    "color_customization", "packaging_customization", "rgb", "software_support",
    "hot_swappable", "shine_through", "custom_artwork_supported", "pantone_matching",
}


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    result = dict(row)
    for field in BOOLEAN_FIELDS & result.keys():
        result[field] = bool(result[field])
    for field in ("certifications", "supported_markets"):
        if field in result:
            result[field] = [value.strip() for value in (result[field] or "").split(",") if value.strip()]
    return result


def list_products(category: str | None = None, db_path: Path | None = None) -> list[dict[str, Any]]:
    initialize_database(db_path)
    query = "SELECT * FROM products WHERE status = 'active'"
    params: list[Any] = []
    if category:
        query += " AND category = ?"
        params.append(category)
    query += " ORDER BY category, sku"
    with connect(db_path) as connection:
        products = [_row_to_dict(row) for row in connection.execute(query, params).fetchall()]
        for product in products:
            table, _ = SPEC_TABLES[product["category"]]
            spec = connection.execute(f"SELECT * FROM {table} WHERE product_id = ?", (product["product_id"],)).fetchone()
            product["specs"] = _row_to_dict(spec) if spec else {}
            product["specs"].pop("product_id", None)
    return products


def get_product(sku: str, db_path: Path | None = None) -> dict[str, Any] | None:
    return next((product for product in list_products(db_path=db_path) if product["sku"] == sku), None)

