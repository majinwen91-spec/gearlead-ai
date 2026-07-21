from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from gearlead.schemas import InquiryData, ProductCandidate, ProductMatch
from gearlead.services.product_service import list_products


SPEC_ALIASES = {
    "maximum_weight": "weight_grams",
    "minimum_battery_life": "battery_life",
}

LIGHT_CUSTOMIZATION = {
    "logo": "logo_customization", "color": "color_customization",
    "packaging": "packaging_customization",
}
DEEP_CUSTOMIZATION = {"firmware", "new_mold", "artwork"}
SPEC_WEIGHTS = {
    "layout": 2, "connection_type": 2, "sensor_model": 2, "driver_size": 2,
    "aviator_connector": 2, "material": 2, "profile": 2,
}


def _tokens(value: Any) -> set[str]:
    return {token.strip().lower() for token in re.split(r"[,/]", str(value)) if token.strip()}


def _number(value: Any) -> float | None:
    match = re.search(r"\d+(?:\.\d+)?", str(value))
    return float(match.group()) if match else None


def _spec_matches(request_key: str, requested: Any, actual: Any) -> bool:
    if actual in (None, ""):
        return False
    if isinstance(requested, bool):
        return bool(actual) is requested
    if request_key == "maximum_weight":
        return (_number(actual) or 9999) <= float(requested)
    if request_key == "minimum_battery_life":
        return (_number(actual) or 0) >= float(requested)
    if request_key in {"platform_support", "language_layout"}:
        return _tokens(requested).issubset(_tokens(actual))
    if isinstance(requested, (int, float)):
        actual_number = _number(actual)
        return actual_number is not None and actual_number >= float(requested)
    requested_tokens = _tokens(requested)
    actual_tokens = _tokens(actual)
    return bool(requested_tokens & actual_tokens) or str(requested).lower() in str(actual).lower()


def _candidate(product: dict[str, Any], inquiry: InquiryData) -> ProductCandidate:
    requested_specs = inquiry.product_requirements
    matched_weight = 0
    total_weight = sum(SPEC_WEIGHTS.get(key, 1) for key in requested_specs)
    reasons: list[str] = []
    gaps: list[str] = []
    for key, requested in requested_specs.items():
        actual_key = SPEC_ALIASES.get(key, key)
        actual = product["specs"].get(actual_key)
        if _spec_matches(key, requested, actual):
            matched_weight += SPEC_WEIGHTS.get(key, 1)
            reasons.append(f"{key.replace('_', ' ').title()} matches: {requested}.")
        else:
            gaps.append(f"Requested {key.replace('_', ' ')} '{requested}' is not confirmed by this SKU.")
    spec_score = round((matched_weight / total_weight) * 80) if total_weight else 40
    quantity = inquiry.purchase_request.quantity
    if quantity is not None and quantity >= product["standard_moq"]:
        spec_score += 10
        reasons.append(f"Quantity meets the {product['standard_moq']} unit standard MOQ.")
    elif quantity is not None and quantity >= product["trial_moq"]:
        spec_score += 6
        gaps.append(f"Quantity is below standard MOQ but reaches the {product['trial_moq']} unit trial threshold.")
    elif quantity is not None:
        gaps.append(f"Quantity is below the {product['trial_moq']} unit trial threshold.")
    requested_certs = set(inquiry.commercial_requirements.certification_requested)
    if not requested_certs or requested_certs.issubset(set(product["certifications"])):
        spec_score += 5
        if requested_certs:
            reasons.append("Requested certifications are listed for this SKU.")
    else:
        gaps.append("One or more requested certifications require confirmation.")
    target = inquiry.purchase_request.target_market
    if target:
        market_codes = {"Germany": "EU", "France": "EU", "Poland": "EU", "United Kingdom": "UK", "United States": "US", "Japan": "JP"}
        if market_codes.get(target, target) in product["supported_markets"]:
            spec_score += 5
            reasons.append("Target market is supported by the catalog entry.")
        else:
            gaps.append("Target market support requires confirmation.")
    else:
        spec_score += 3
    return ProductCandidate(
        sku=product["sku"], product_name=product["product_name"], category=product["category"],
        match_score=max(0, min(100, spec_score)), standard_moq=product["standard_moq"],
        mass_production_lead_time_days=product["mass_production_lead_time_days"],
        certifications=product["certifications"], reasons=reasons, gaps=gaps,
        specs=product["specs"],
    )


def match_product_catalog(inquiry: InquiryData, db_path: Path | None = None) -> ProductMatch:
    category = inquiry.purchase_request.category
    if category == "unknown":
        return ProductMatch(match_type="No Suitable Match", match_score=0, gaps=["Product category could not be identified."])
    products = list_products(category, db_path)
    if not products:
        return ProductMatch(match_type="No Suitable Match", match_score=0, gaps=["No active products exist in this category."])
    custom = inquiry.customization
    deep_requested = any(getattr(custom, field) for field in DEEP_CUSTOMIZATION)
    if not inquiry.product_requirements and not deep_requested:
        return ProductMatch(
            match_type="No Suitable Match",
            match_score=0,
            gaps=["No category-specific product specifications were provided."],
        )
    product_map = {product["sku"]: product for product in products}
    ranked = sorted((_candidate(product, inquiry) for product in products), key=lambda item: item.match_score, reverse=True)
    if deep_requested:
        odm_candidates = [candidate for candidate in ranked if product_map[candidate.sku]["odm_supported"]]
        if odm_candidates:
            ranked = odm_candidates + [candidate for candidate in ranked if candidate not in odm_candidates]
    candidates = ranked[:3]
    best = candidates[0]
    best_product = product_map[best.sku]
    light_requested = [field for field in LIGHT_CUSTOMIZATION if getattr(custom, field)]
    unsupported_light = [field for field in light_requested if not best_product[LIGHT_CUSTOMIZATION[field]]]
    language_gap = custom.language_layout and "language_layout" in inquiry.product_requirements and any(
        "language layout" in gap.lower() for gap in best.gaps
    )
    if best.match_score < 45:
        match_type = "ODM Feasibility Review" if best_product["odm_supported"] and (deep_requested or light_requested) else "No Suitable Match"
    elif deep_requested or unsupported_light or language_gap:
        match_type = "ODM Feasibility Review" if best_product["odm_supported"] else "No Suitable Match"
    elif light_requested:
        match_type = "Standard SKU + Light Customization"
    elif best.match_score >= 75:
        match_type = "Standard SKU Match"
    elif best_product["odm_supported"]:
        match_type = "ODM Feasibility Review"
    else:
        match_type = "No Suitable Match"
    reasons = list(best.reasons)
    if light_requested and match_type == "Standard SKU + Light Customization":
        reasons.append(f"Catalog supports light customization: {', '.join(light_requested)}.")
    return ProductMatch(
        match_type=match_type,
        recommended_sku=best.sku if match_type != "No Suitable Match" else "",
        match_score=best.match_score,
        reasons=reasons,
        gaps=best.gaps,
        candidates=candidates,
    )
