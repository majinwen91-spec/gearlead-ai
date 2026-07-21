from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


Category = Literal[
    "gaming_mouse",
    "mechanical_keyboard",
    "gaming_headset",
    "custom_cable",
    "custom_keycap",
    "unknown",
]


class CustomerInfo(BaseModel):
    company_name: str = ""
    country: str = ""
    customer_type: str = "unknown"
    email: str = ""
    website: str = ""


class PurchaseRequest(BaseModel):
    category: Category = "unknown"
    quantity: int | None = Field(default=None, ge=0)
    annual_quantity: int | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    currency: str = ""
    target_market: str = ""
    delivery_destination: str = ""
    required_delivery_date: str = ""
    sample_required: bool = False


class CustomizationRequirements(BaseModel):
    logo: bool = False
    color: bool = False
    packaging: bool = False
    firmware: bool = False
    language_layout: bool = False
    new_mold: bool = False
    artwork: bool = False

    def requested_items(self) -> list[str]:
        return [name for name, value in model_dump_compat(self).items() if value]


class CommercialRequirements(BaseModel):
    quotation_requested: bool = False
    catalog_requested: bool = False
    certification_requested: list[str] = Field(default_factory=list)
    payment_terms_requested: bool = False
    exclusivity_requested: bool = False


class InquiryData(BaseModel):
    customer: CustomerInfo = Field(default_factory=CustomerInfo)
    purchase_request: PurchaseRequest = Field(default_factory=PurchaseRequest)
    product_requirements: dict[str, Any] = Field(default_factory=dict)
    customization: CustomizationRequirements = Field(default_factory=CustomizationRequirements)
    commercial_requirements: CommercialRequirements = Field(default_factory=CommercialRequirements)
    risk_signals: list[str] = Field(default_factory=list)


class CustomerCheck(BaseModel):
    score: int = Field(ge=0, le=20)
    risk_level: Literal["low", "medium", "high"] = "low"
    risk_flags: list[str] = Field(default_factory=list)
    manual_review_required: bool = False
    matched_customer_id: str | None = None
    explanations: list[str] = Field(default_factory=list)


class ProductCandidate(BaseModel):
    sku: str
    product_name: str
    category: str
    match_score: int = Field(ge=0, le=100)
    standard_moq: int
    mass_production_lead_time_days: int
    certifications: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    specs: dict[str, Any] = Field(default_factory=dict)


class ProductMatch(BaseModel):
    match_type: Literal[
        "Standard SKU Match",
        "Standard SKU + Light Customization",
        "ODM Feasibility Review",
        "No Suitable Match",
    ]
    recommended_sku: str = ""
    match_score: int = Field(ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    candidates: list[ProductCandidate] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    customer_credibility: int = Field(ge=0, le=20)
    requirement_clarity: int = Field(ge=0, le=20)
    moq_fit: int = Field(ge=0, le=15)
    feasibility: int = Field(ge=0, le=20)
    commercial_value: int = Field(ge=0, le=15)
    urgency: int = Field(ge=0, le=10)

    @property
    def total(self) -> int:
        return sum(model_dump_compat(self).values())


class LeadScore(BaseModel):
    total: int = Field(ge=0, le=100)
    priority: Literal["High", "Medium", "Low", "Risk Review"]
    breakdown: ScoreBreakdown
    explanations: list[str] = Field(default_factory=list)


class FollowUpPlan(BaseModel):
    strategy: Literal[
        "High-priority quotation preparation",
        "Request missing information",
        "Nurture and continue qualification",
        "Manual risk review",
    ]
    next_action: str
    suggested_follow_up_days: int = Field(ge=0)
    questions: list[str] = Field(default_factory=list)


class WorkflowResult(BaseModel):
    raw_inquiry: str
    inquiry: InquiryData
    missing_fields: list[str]
    completeness_score: int = Field(ge=0, le=100)
    customer_check: CustomerCheck
    product_match: ProductMatch
    lead_score: LeadScore
    follow_up: FollowUpPlan
    reply_draft: str
    tool_status: dict[str, bool] = Field(default_factory=dict)
    generated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def model_dump_compat(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def model_validate_compat(model_class: type[BaseModel], data: Any) -> BaseModel:
    if hasattr(model_class, "model_validate"):
        return model_class.model_validate(data)
    return model_class.parse_obj(data)

