from __future__ import annotations

import re
from pathlib import Path

from gearlead.llm_client import LLMClient, LLMError
from gearlead.schemas import FollowUpPlan, InquiryData, LeadScore, ProductMatch


DISCLAIMER = "Draft for salesperson review."
FORBIDDEN_COMMITMENTS = [
    r"(?:delivery|lead time).{0,24}(?:is|are)?\s*(?:guaranteed|confirmed)",
    r"(?:guarantee|confirm).{0,24}(?:delivery|lead time)",
    r"(?:final|confirmed)\s+(?:unit\s+)?price",
    r"(?:price|unit price).{0,20}(?:is confirmed|is final)",
    r"(?:certification|approval).{0,24}(?:is|are)?\s*(?:guaranteed|confirmed)",
    r"(?:credit|payment)\s+terms.{0,20}(?:approved|confirmed)",
]


def _contains_forbidden_commitment(reply: str) -> bool:
    return any(re.search(pattern, reply, re.IGNORECASE) for pattern in FORBIDDEN_COMMITMENTS)


def _deterministic_reply(inquiry: InquiryData, match: ProductMatch, plan: FollowUpPlan) -> str:
    customer = inquiry.customer
    greeting = f"Dear {customer.company_name} team," if customer.company_name else "Dear Customer,"
    category = inquiry.purchase_request.category.replace("_", " ")
    quantity = inquiry.purchase_request.quantity
    request_summary = f"your inquiry for {quantity} units of {category}" if quantity else f"your inquiry about {category}"
    lines = [greeting, "", f"Thank you for {request_summary}."]
    if plan.strategy == "Manual risk review":
        lines += [
            "Before we share commercial terms, we need to complete our standard company verification process.",
            "Please provide your company website, business address, and purchasing contact details.",
        ]
    elif match.match_type == "Standard SKU Match":
        lines += [
            f"Based on the specifications provided, our {match.recommended_sku} is the closest standard match.",
            "We can prepare a formal quotation after confirming the remaining commercial details.",
        ]
    elif match.match_type == "Standard SKU + Light Customization":
        requested = ", ".join(inquiry.customization.requested_items())
        lines += [
            f"Our {match.recommended_sku} can serve as the base model, with support for {requested} customization.",
            "Final pricing and lead time will be confirmed after sample and artwork review.",
        ]
    elif match.match_type == "ODM Feasibility Review":
        lines += [
            "Your request appears suitable for an initial ODM feasibility review.",
            "Our engineering team will need the full specification, artwork or drawings before confirming price and lead time.",
            "We would be glad to arrange a technical call after reviewing those materials.",
        ]
    else:
        lines += [
            "We do not yet have enough information to confirm a suitable standard model.",
            "We can share the relevant catalog and review alternatives once the core specifications are confirmed.",
        ]
    if plan.questions:
        lines += ["", "To proceed, could you please confirm:"]
        lines.extend(f"- {question}" for question in plan.questions)
    lines += ["", "Best regards,", "GearLead Export Sales Team", "", DISCLAIMER]
    return "\n".join(lines)


def generate_reply_draft(
    inquiry: InquiryData,
    match: ProductMatch,
    score: LeadScore,
    plan: FollowUpPlan,
    use_llm: bool = False,
    client: LLMClient | None = None,
) -> str:
    fallback = _deterministic_reply(inquiry, match, plan)
    if not use_llm:
        return fallback
    llm = client or LLMClient.from_settings()
    prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "reply_generation.md"
    prompt = prompt_path.read_text(encoding="utf-8")
    context = f"Inquiry: {inquiry}\nMatch: {match}\nScore: {score}\nPlan: {plan}"
    try:
        reply = llm.chat(prompt, context).strip()
        if DISCLAIMER.lower() not in reply.lower():
            reply += f"\n\n{DISCLAIMER}"
        if _contains_forbidden_commitment(reply):
            return fallback
        return reply
    except LLMError:
        return fallback
