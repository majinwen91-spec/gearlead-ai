from __future__ import annotations

from pathlib import Path

from gearlead.services.evaluation_service import run_evaluation


def test_poc_evaluation_meets_prd_targets(db_path: Path) -> None:
    report = run_evaluation(db_path=db_path)
    assert report.total_cases == 25
    assert report.field_extraction_accuracy >= 80
    assert report.product_match_accuracy >= 80
    assert report.priority_accuracy >= 75
    assert report.missing_field_recall >= 80
    assert report.tool_call_success_rate >= 95
    assert report.response_completeness >= 80

