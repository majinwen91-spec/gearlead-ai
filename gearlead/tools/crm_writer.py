from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gearlead.database import connect, initialize_database
from gearlead.schemas import WorkflowResult


def save_lead_record(result: WorkflowResult, db_path: Path | None = None) -> str:
    initialize_database(db_path)
    lead_id = f"LEAD-{uuid.uuid4().hex[:10].upper()}"
    created_at = datetime.now(timezone.utc).isoformat()
    with connect(db_path) as connection:
        connection.execute(
            """INSERT INTO crm_leads
            (lead_id, created_at, customer_name, country, category, requested_quantity,
             lead_score, priority, match_type, recommended_sku, next_action, reply_draft, raw_inquiry)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                lead_id, created_at, result.inquiry.customer.company_name,
                result.inquiry.customer.country, result.inquiry.purchase_request.category,
                result.inquiry.purchase_request.quantity, result.lead_score.total,
                result.lead_score.priority, result.product_match.match_type,
                result.product_match.recommended_sku, result.follow_up.next_action,
                result.reply_draft, result.raw_inquiry,
            ),
        )
        connection.execute(
            "INSERT INTO lead_events (lead_id, event_type, event_at, detail) VALUES (?, ?, ?, ?)",
            (lead_id, "analysis_saved", created_at, json.dumps(result.tool_status)),
        )
    return lead_id


def list_leads(db_path: Path | None = None) -> list[dict[str, Any]]:
    initialize_database(db_path)
    with connect(db_path) as connection:
        return [dict(row) for row in connection.execute("SELECT * FROM crm_leads ORDER BY created_at DESC")]

