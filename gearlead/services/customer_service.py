from __future__ import annotations

from pathlib import Path
from typing import Any

from gearlead.database import connect, initialize_database


def list_customers(db_path: Path | None = None) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM customers ORDER BY company_name")]


def find_customer(company_name: str, email: str, db_path: Path | None = None) -> dict[str, Any] | None:
    domain = email.rsplit("@", 1)[-1].lower() if "@" in email else ""
    company = company_name.strip().lower()
    for record in list_customers(db_path):
        if domain and record["email_domain"].lower() == domain:
            return record
        if company and record["company_name"].lower() == company:
            return record
    return None

