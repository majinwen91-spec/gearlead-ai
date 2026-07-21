from __future__ import annotations

from gearlead.schemas import CustomerCheck, FollowUpPlan, InquiryData, LeadScore, ProductMatch


QUESTION_MAP = {
    "Customer company name": "Could you share your company name and website?",
    "Customer country": "Which country and sales market will these products be for?",
    "Customer type": "Could you describe your sales channel and buyer profile?",
    "Requested quantity": "What quantity are you planning for the initial order?",
    "Target market": "Which market will the products be sold in?",
    "Required delivery date": "What is your preferred delivery or launch date?",
    "Connection type": "Which connection mode do you require?",
    "Sensor model": "Do you have a preferred sensor model?",
    "Polling rate": "What polling rate do you require?",
    "Maximum mouse weight": "What is your target maximum mouse weight?",
    "Keyboard/keycap layout": "Which physical layout do you need?",
    "Language layout": "Which language layout is required?",
    "Platform compatibility": "Which platforms must the headset support?",
    "Aviator connector": "Which aviator connector do you prefer?",
    "Keycap material": "Which keycap material do you require?",
}


def select_follow_up_strategy(
    inquiry: InquiryData,
    score: LeadScore,
    customer: CustomerCheck,
    match: ProductMatch,
    missing_fields: list[str],
) -> FollowUpPlan:
    questions = [QUESTION_MAP.get(field, f"Could you confirm {field.lower()}?") for field in missing_fields[:5]]
    if customer.manual_review_required:
        return FollowUpPlan(
            strategy="Manual risk review",
            next_action="Verify the company profile and risk flags before sharing commercial terms.",
            suggested_follow_up_days=0,
            questions=questions,
        )
    if score.priority == "High" and len(missing_fields) <= 3 and match.match_type in {"Standard SKU Match", "Standard SKU + Light Customization"}:
        return FollowUpPlan(
            strategy="High-priority quotation preparation",
            next_action="Confirm remaining commercial details and prepare an internal quotation request.",
            suggested_follow_up_days=1,
            questions=questions,
        )
    if score.priority in {"High", "Medium"} or match.match_type == "ODM Feasibility Review":
        if match.match_type == "ODM Feasibility Review":
            questions.extend(["Could you share drawings, artwork, or a complete technical specification?", "Would you be available for a technical feasibility call?"])
        return FollowUpPlan(
            strategy="Request missing information",
            next_action="Collect the missing specifications before confirming price, lead time, or feasibility.",
            suggested_follow_up_days=2,
            questions=list(dict.fromkeys(questions)),
        )
    return FollowUpPlan(
        strategy="Nurture and continue qualification",
        next_action="Send the relevant catalog and qualify quantity, market, and timing before quotation.",
        suggested_follow_up_days=3,
        questions=questions,
    )

