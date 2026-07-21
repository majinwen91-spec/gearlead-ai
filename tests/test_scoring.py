from __future__ import annotations

import json
from pathlib import Path

from gearlead.config import PROJECT_ROOT
from gearlead.schemas import model_dump_compat
from gearlead.workflow import analyze_inquiry


def _case(case_id: str) -> str:
    for line in (PROJECT_ROOT / "data" / "sample_inquiries.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["id"] == case_id:
            return row["text"]
    raise AssertionError(f"Unknown case {case_id}")


def test_score_is_sum_of_six_dimensions(keyboard_inquiry: str, db_path: Path) -> None:
    result = analyze_inquiry(keyboard_inquiry, db_path=db_path)
    assert result.lead_score.total == sum(model_dump_compat(result.lead_score.breakdown).values())
    assert result.lead_score.priority == "High"


def test_explicit_payment_risk_overrides_numeric_score(db_path: Path) -> None:
    result = analyze_inquiry(_case("H04"), db_path=db_path)
    assert result.customer_check.manual_review_required is True
    assert result.lead_score.priority == "Risk Review"
    assert result.follow_up.strategy == "Manual risk review"


def test_scoring_dimensions_respect_prd_caps(keyboard_inquiry: str, db_path: Path) -> None:
    breakdown = analyze_inquiry(keyboard_inquiry, db_path=db_path).lead_score.breakdown
    assert breakdown.customer_credibility <= 20
    assert breakdown.requirement_clarity <= 20
    assert breakdown.moq_fit <= 15
    assert breakdown.feasibility <= 20
    assert breakdown.commercial_value <= 15
    assert breakdown.urgency <= 10

