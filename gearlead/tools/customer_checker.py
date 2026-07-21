from __future__ import annotations

from pathlib import Path

from gearlead.schemas import CustomerCheck, InquiryData
from gearlead.services.customer_service import find_customer


PERSONAL_DOMAINS = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "qq.com", "163.com"}


def check_customer_profile(inquiry: InquiryData, db_path: Path | None = None) -> CustomerCheck:
    customer = inquiry.customer
    score = 0
    explanations: list[str] = []
    flags = list(inquiry.risk_signals)
    domain = customer.email.rsplit("@", 1)[-1].lower() if "@" in customer.email else ""
    corporate_email = bool(domain and domain not in PERSONAL_DOMAINS)
    if corporate_email:
        score += 5
        explanations.append("Corporate email domain provided (+5).")
    if customer.company_name:
        score += 4
        explanations.append("Company name provided (+4).")
    if customer.website:
        score += 4
        explanations.append("Company website provided (+4).")
    if customer.customer_type != "unknown":
        score += 3
        explanations.append("Buyer type is identifiable (+3).")
    if inquiry.purchase_request.target_market:
        score += 4
        explanations.append("Target market is identifiable (+4).")
    record = find_customer(customer.company_name, customer.email, db_path)
    if record:
        if record["historical_orders"] > 0:
            explanations.append(f"CRM history includes {record['historical_orders']} order(s).")
        if record["risk_status"] in {"watchlist", "risky"}:
            flags.append(f"CRM customer status is {record['risk_status']}.")
    quantity = inquiry.purchase_request.quantity or 0
    if quantity >= 5000 and (not customer.company_name or domain in PERSONAL_DOMAINS or not customer.website):
        flags.append("Large claimed order lacks a verifiable corporate profile.")
    high_terms = ("Unusual payment", "Sensitive information", "bypass", "CRM customer status is risky")
    high_risk = any(any(term.lower() in flag.lower() for term in high_terms) for flag in flags)
    risk_level = "high" if high_risk else "medium" if flags else "low"
    return CustomerCheck(
        score=score,
        risk_level=risk_level,
        risk_flags=list(dict.fromkeys(flags)),
        manual_review_required=bool(flags),
        matched_customer_id=record["customer_id"] if record else None,
        explanations=explanations,
    )
