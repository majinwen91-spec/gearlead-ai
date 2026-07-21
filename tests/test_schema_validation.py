from __future__ import annotations

import pytest
from pydantic import ValidationError

from gearlead.schemas import InquiryData, model_validate_compat
from gearlead.tools.inquiry_parser import extract_inquiry_fields


def test_parser_returns_valid_schema(keyboard_inquiry: str) -> None:
    inquiry = extract_inquiry_fields(keyboard_inquiry)
    assert isinstance(inquiry, InquiryData)
    assert inquiry.purchase_request.category == "mechanical_keyboard"
    assert inquiry.purchase_request.quantity == 500
    assert inquiry.product_requirements["layout"] == "75%"
    assert inquiry.customization.logo is True


def test_schema_rejects_negative_quantity() -> None:
    with pytest.raises(ValidationError):
        model_validate_compat(
            InquiryData,
            {"purchase_request": {"category": "gaming_mouse", "quantity": -1}},
        )


def test_parser_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="too short"):
        extract_inquiry_fields("  ")

