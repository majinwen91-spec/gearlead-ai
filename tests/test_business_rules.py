from __future__ import annotations

from pathlib import Path

from gearlead.workflow import analyze_inquiry


def test_customer_market_and_destination_are_extracted_separately(db_path: Path) -> None:
    text = (
        "We are RheinGear GmbH, a distributor based in Germany. "
        "Contact sales@rheingear.de and visit https://rheingear.de. "
        "We need 500 tri-mode gaming mice with PAW3395 and 4K polling "
        "for the United States market. Delivery to Los Angeles by October 15."
    )

    result = analyze_inquiry(text, db_path=db_path)

    assert result.inquiry.customer.country == "Germany"
    assert result.inquiry.purchase_request.target_market == "United States"
    assert result.inquiry.purchase_request.delivery_destination == "Los Angeles"


def test_price_only_inquiry_is_quality_warning_not_risk(db_path: Path) -> None:
    result = analyze_inquiry(
        "Hi, send your cheapest gaming mouse catalog and best price. Maybe 20 units.",
        db_path=db_path,
    )

    assert result.customer_check.quality_warnings
    assert result.customer_check.risk_flags == []
    assert result.customer_check.manual_review_required is False
    assert result.lead_score.priority == "Low"
    assert result.follow_up.strategy == "Nurture and continue qualification"


def test_explicit_payment_request_remains_manual_risk(db_path: Path) -> None:
    result = analyze_inquiry(
        "We need 10000 gaming headsets for the United States market. "
        "Contact buyer@gmail.com and accept payment to a personal account.",
        db_path=db_path,
    )

    assert result.customer_check.risk_flags
    assert result.customer_check.manual_review_required is True
    assert result.lead_score.priority == "Risk Review"


def test_hard_constraint_conflict_cannot_be_standard_match(db_path: Path) -> None:
    text = (
        "We are FullBoard Ltd, a retailer in the United Kingdom. "
        "Contact sales@fullboard.co.uk and visit https://fullboard.co.uk. "
        "We need 500 full-size wired mechanical keyboards with hot-swappable switches, "
        "ANSI-US layout, for delivery by November 1."
    )

    result = analyze_inquiry(text, db_path=db_path)

    assert result.product_match.recommended_sku == ""
    assert result.product_match.match_type == "No Suitable Match"
    assert any(candidate.hard_constraint_gaps for candidate in result.product_match.candidates)


def test_negative_hot_swap_requirement_is_preserved(db_path: Path) -> None:
    text = (
        "We are Budget Keys Ltd, a United Kingdom retailer. "
        "We need 500 full-size wired mechanical keyboards that are not hot-swappable, "
        "with ANSI-US layout for delivery by November 1."
    )

    result = analyze_inquiry(text, db_path=db_path)

    assert "hot_swappable" in result.inquiry.product_requirements
    assert result.inquiry.product_requirements["hot_swappable"] is False
    assert "Hot-swap requirement" not in result.missing_fields
    assert result.product_match.match_type == "Standard SKU Match"
    assert result.product_match.recommended_sku == "KB104-WIRED-RGB"
