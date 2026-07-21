from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gearlead.config import PROJECT_ROOT
from gearlead.workflow import analyze_inquiry


@dataclass
class EvaluationReport:
    total_cases: int
    field_extraction_accuracy: float
    product_match_accuracy: float
    priority_accuracy: float
    missing_field_recall: float
    tool_call_success_rate: float
    response_completeness: float
    case_results: list[dict[str, Any]]

    def metrics(self) -> dict[str, float]:
        return {
            "Field Extraction Accuracy": self.field_extraction_accuracy,
            "Product Match Accuracy": self.product_match_accuracy,
            "Priority Classification Accuracy": self.priority_accuracy,
            "Missing Field Recall": self.missing_field_recall,
            "Tool Call Success Rate": self.tool_call_success_rate,
            "Response Completeness": self.response_completeness,
        }


def load_evaluation_data(root: Path = PROJECT_ROOT) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    inquiries = [json.loads(line) for line in (root / "data" / "sample_inquiries.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    gold_rows = json.loads((root / "data" / "evaluation_gold.json").read_text(encoding="utf-8"))
    return inquiries, {row["id"]: row for row in gold_rows}


def _ratio(correct: int, total: int) -> float:
    return round((correct / total) * 100, 1) if total else 0.0


def run_evaluation(root: Path = PROJECT_ROOT, db_path: Path | None = None) -> EvaluationReport:
    inquiries, gold = load_evaluation_data(root)
    field_correct = field_total = product_correct = priority_correct = 0
    missing_hits = missing_total = tool_hits = tool_total = response_hits = 0
    rows: list[dict[str, Any]] = []
    for case in inquiries:
        expected = gold[case["id"]]
        error = ""
        try:
            result = analyze_inquiry(case["text"], use_llm=False, db_path=db_path)
            actual_fields = [
                result.inquiry.purchase_request.category,
                result.inquiry.purchase_request.quantity,
                result.inquiry.customer.country,
            ]
            expected_fields = [expected["category"], expected["quantity"], expected["country"]]
            current_field_correct = sum(actual == wanted for actual, wanted in zip(actual_fields, expected_fields))
            field_correct += current_field_correct
            field_total += len(expected_fields)
            expected_sku = expected["recommended_sku"]
            product_ok = result.product_match.recommended_sku == expected_sku
            product_correct += int(product_ok)
            priority_ok = result.lead_score.priority == expected["priority"]
            priority_correct += int(priority_ok)
            actual_missing = set(result.missing_fields)
            expected_missing = set(expected["missing_fields"])
            missing_hits += len(actual_missing & expected_missing)
            missing_total += len(expected_missing)
            tool_hits += sum(result.tool_status.values())
            tool_total += len(result.tool_status)
            reply_ok = (
                "Draft for salesperson review." in result.reply_draft
                and len(result.reply_draft) >= 180
                and "Best regards" in result.reply_draft
            )
            response_hits += int(reply_ok)
            rows.append({
                "id": case["id"], "case_type": case["case_type"],
                "field_accuracy": _ratio(current_field_correct, len(expected_fields)),
                "expected_sku": expected_sku or "No match",
                "actual_sku": result.product_match.recommended_sku or "No match",
                "product_ok": product_ok, "expected_priority": expected["priority"],
                "actual_priority": result.lead_score.priority, "priority_ok": priority_ok,
                "score": result.lead_score.total, "error": error,
            })
        except Exception as exc:  # evaluation must report individual failures
            field_total += 3
            tool_total += 7
            missing_total += len(expected["missing_fields"])
            rows.append({
                "id": case["id"], "case_type": case["case_type"], "field_accuracy": 0,
                "expected_sku": expected["recommended_sku"] or "No match", "actual_sku": "Error",
                "product_ok": False, "expected_priority": expected["priority"], "actual_priority": "Error",
                "priority_ok": False, "score": 0, "error": str(exc),
            })
    total = len(inquiries)
    return EvaluationReport(
        total_cases=total,
        field_extraction_accuracy=_ratio(field_correct, field_total),
        product_match_accuracy=_ratio(product_correct, total),
        priority_accuracy=_ratio(priority_correct, total),
        missing_field_recall=_ratio(missing_hits, missing_total),
        tool_call_success_rate=_ratio(tool_hits, tool_total),
        response_completeness=_ratio(response_hits, total),
        case_results=rows,
    )

