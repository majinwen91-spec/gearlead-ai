from __future__ import annotations

from gearlead.schemas import CustomerCheck, InquiryData, LeadScore, ProductMatch, ScoreBreakdown


def calculate_lead_score(inquiry: InquiryData, customer: CustomerCheck, match: ProductMatch) -> LeadScore:
    explanations = list(customer.explanations)
    clarity = 0
    if inquiry.purchase_request.category != "unknown": clarity += 4
    spec_count = len([value for value in inquiry.product_requirements.values() if value not in (None, "")])
    clarity += min(6, spec_count * 2)
    if inquiry.purchase_request.quantity is not None: clarity += 4
    if inquiry.customization.requested_items() or inquiry.commercial_requirements.quotation_requested: clarity += 3
    if inquiry.commercial_requirements.certification_requested or inquiry.purchase_request.target_market: clarity += 3
    clarity = min(20, clarity)
    explanations.append(f"Requirement clarity contributes {clarity}/20 based on category, specs, quantity, customization, and market data.")

    quantity = inquiry.purchase_request.quantity
    candidate = match.candidates[0] if match.candidates else None
    if quantity is None:
        moq = 2
    elif candidate and quantity >= candidate.standard_moq:
        moq = 15
    elif candidate and quantity >= max(10, candidate.standard_moq // 4):
        moq = 10
    elif inquiry.purchase_request.annual_quantity:
        moq = 5
    else:
        moq = 5
    explanations.append(f"MOQ fit contributes {moq}/15.")

    feasibility_map = {
        "Standard SKU Match": 20,
        "Standard SKU + Light Customization": 16,
        "ODM Feasibility Review": 10,
        "No Suitable Match": 4,
    }
    feasibility = feasibility_map[match.match_type]
    customer_type_points = {"brand": 5, "distributor": 5, "wholesaler": 4, "retailer": 3, "ecommerce": 3, "trading": 2, "unknown": 0}
    commercial = customer_type_points.get(inquiry.customer.customer_type, 1)
    commercial_quantity = quantity or ((inquiry.purchase_request.annual_quantity or 0) // 4)
    if commercial_quantity:
        if commercial_quantity >= 2000: commercial += 5
        elif commercial_quantity >= 500: commercial += 4
        elif commercial_quantity >= 100: commercial += 2
    if inquiry.purchase_request.annual_quantity: commercial += 3
    if inquiry.commercial_requirements.exclusivity_requested: commercial += 1
    commercial = min(15, commercial)
    urgent_text = inquiry.purchase_request.required_delivery_date.lower()
    if urgent_text:
        urgency = 10
    elif inquiry.purchase_request.sample_required:
        urgency = 6
    else:
        urgency = 2
    breakdown = ScoreBreakdown(
        customer_credibility=customer.score,
        requirement_clarity=clarity,
        moq_fit=moq,
        feasibility=feasibility,
        commercial_value=commercial,
        urgency=urgency,
    )
    total = breakdown.total
    if customer.manual_review_required:
        priority = "Risk Review"
    elif total >= 80:
        priority = "High"
    elif total >= 60:
        priority = "Medium"
    else:
        priority = "Low"
    explanations.extend([
        f"Product feasibility contributes {feasibility}/20 ({match.match_type}).",
        f"Commercial value contributes {commercial}/15.",
        f"Urgency contributes {urgency}/10.",
    ])
    return LeadScore(total=total, priority=priority, breakdown=breakdown, explanations=explanations)
