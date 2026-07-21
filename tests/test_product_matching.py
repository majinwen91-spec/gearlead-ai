from __future__ import annotations

import json
from pathlib import Path

import pytest

from gearlead.config import PROJECT_ROOT
from gearlead.workflow import analyze_inquiry


EXPECTED = {
    "M01": ("GM49-TM-PRO", "Standard SKU + Light Customization"),
    "K01": ("KB75-GASKET-TM", "Standard SKU + Light Customization"),
    "H01": ("HS50-24G-35H", "Standard SKU + Light Customization"),
    "C01": ("CB-YC8-COIL", "Standard SKU + Light Customization"),
    "KC01": ("KC-PBT-CHERRY-135", "ODM Feasibility Review"),
}


def _cases() -> dict[str, str]:
    rows = [
        json.loads(line)
        for line in (PROJECT_ROOT / "data" / "sample_inquiries.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {row["id"]: row["text"] for row in rows}


@pytest.mark.parametrize("case_id", list(EXPECTED))
def test_representative_product_match(case_id: str, db_path: Path) -> None:
    result = analyze_inquiry(_cases()[case_id], db_path=db_path)
    expected_sku, expected_type = EXPECTED[case_id]
    assert result.product_match.recommended_sku == expected_sku
    assert result.product_match.match_type == expected_type
    assert result.product_match.candidates


def test_sparse_inquiry_does_not_force_product_match(db_path: Path) -> None:
    result = analyze_inquiry("Hi, send your cheapest gaming mouse catalog and best price. Maybe 20 units.", db_path=db_path)
    assert result.product_match.match_type == "No Suitable Match"
    assert result.product_match.recommended_sku == ""
