from __future__ import annotations

from pathlib import Path

from gearlead.llm_client import LLMClient
from gearlead.schemas import WorkflowResult
from gearlead.tools.completeness_checker import check_missing_fields
from gearlead.tools.customer_checker import check_customer_profile
from gearlead.tools.inquiry_parser import extract_inquiry_fields
from gearlead.tools.lead_scorer import calculate_lead_score
from gearlead.tools.product_matcher import match_product_catalog
from gearlead.tools.reply_generator import generate_reply_draft
from gearlead.tools.strategy_selector import select_follow_up_strategy


def analyze_inquiry(
    text: str,
    use_llm: bool = False,
    db_path: Path | None = None,
    llm_client: LLMClient | None = None,
) -> WorkflowResult:
    status: dict[str, bool] = {}
    inquiry = extract_inquiry_fields(text, use_llm=use_llm, client=llm_client)
    status["extract_inquiry_fields"] = True
    missing, completeness = check_missing_fields(inquiry)
    status["check_missing_fields"] = True
    customer = check_customer_profile(inquiry, db_path)
    status["check_customer_profile"] = True
    product_match = match_product_catalog(inquiry, db_path)
    status["match_product_catalog"] = True
    lead_score = calculate_lead_score(inquiry, customer, product_match)
    status["calculate_lead_score"] = True
    follow_up = select_follow_up_strategy(inquiry, lead_score, customer, product_match, missing)
    status["select_follow_up_strategy"] = True
    reply = generate_reply_draft(inquiry, product_match, lead_score, follow_up, use_llm=use_llm, client=llm_client)
    status["generate_reply_draft"] = True
    return WorkflowResult(
        raw_inquiry=text,
        inquiry=inquiry,
        missing_fields=missing,
        completeness_score=completeness,
        customer_check=customer,
        product_match=product_match,
        lead_score=lead_score,
        follow_up=follow_up,
        reply_draft=reply,
        tool_status=status,
    )

