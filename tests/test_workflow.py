from __future__ import annotations

from pathlib import Path

from gearlead.tools.crm_writer import list_leads, save_lead_record
from gearlead.tools.reply_generator import generate_reply_draft
from gearlead.workflow import analyze_inquiry


def test_workflow_completes_all_tools_and_generates_safe_draft(keyboard_inquiry: str, db_path: Path) -> None:
    result = analyze_inquiry(keyboard_inquiry, db_path=db_path)
    assert len(result.tool_status) == 7
    assert all(result.tool_status.values())
    assert "Draft for salesperson review." in result.reply_draft
    assert "guarantee delivery" not in result.reply_draft.lower()
    assert result.follow_up.strategy == "High-priority quotation preparation"


def test_crm_record_round_trip(keyboard_inquiry: str, db_path: Path) -> None:
    result = analyze_inquiry(keyboard_inquiry, db_path=db_path)
    lead_id = save_lead_record(result, db_path=db_path)
    records = list_leads(db_path=db_path)
    assert records[0]["lead_id"] == lead_id
    assert records[0]["recommended_sku"] == "KB75-GASKET-TM"
    assert records[0]["priority"] == "High"


def test_llm_commercial_commitment_falls_back_to_safe_draft(
    keyboard_inquiry: str,
    db_path: Path,
) -> None:
    class UnsafeClient:
        def chat(self, *args, **kwargs) -> str:
            return (
                "Dear buyer, delivery is guaranteed by October 15 and the confirmed unit price "
                "is USD 20. Best regards."
            )

    result = analyze_inquiry(keyboard_inquiry, db_path=db_path)
    reply = generate_reply_draft(
        result.inquiry,
        result.product_match,
        result.lead_score,
        result.follow_up,
        use_llm=True,
        client=UnsafeClient(),
    )

    assert "delivery is guaranteed" not in reply.lower()
    assert "confirmed unit price" not in reply.lower()
    assert "Draft for salesperson review." in reply
