from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel, Field

from gearlead.config import get_settings
from gearlead.database import initialize_database
from gearlead.schemas import Category, WorkflowResult
from gearlead.services.product_service import list_products
from gearlead.tools.crm_writer import list_leads, save_lead_record
from gearlead.workflow import analyze_inquiry


class AnalyzeInquiryRequest(BaseModel):
    inquiry_text: str = Field(min_length=8)
    use_llm: bool = False


class CreateLeadRequest(BaseModel):
    analysis: WorkflowResult


class CreateLeadResponse(BaseModel):
    lead_id: str
    message: str


class HealthResponse(BaseModel):
    status: str
    service: str
    llm_enabled: bool


app = FastAPI(
    title="GearLead AI API",
    version="1.1.0",
    description="REST API for gaming-peripheral inquiry qualification and product matching.",
)

DB_PATH: Path = initialize_database()


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(status="ok", service="gearlead-ai", llm_enabled=settings.llm_available)


@app.post("/api/v1/inquiries/analyze", response_model=WorkflowResult, tags=["Inquiries"])
def analyze(request: AnalyzeInquiryRequest) -> WorkflowResult:
    try:
        return analyze_inquiry(request.inquiry_text, use_llm=request.use_llm, db_path=DB_PATH)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@app.get("/api/v1/products", response_model=list[dict[str, Any]], tags=["Products"])
def products(category: Category | None = Query(default=None)) -> list[dict[str, Any]]:
    if category == "unknown":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="unknown is not a catalog product category.",
        )
    return list_products(category=category, db_path=DB_PATH)


@app.post(
    "/api/v1/leads",
    response_model=CreateLeadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["CRM"],
)
def create_lead(request: CreateLeadRequest) -> CreateLeadResponse:
    lead_id = save_lead_record(request.analysis, db_path=DB_PATH)
    return CreateLeadResponse(lead_id=lead_id, message="Lead saved for salesperson follow-up.")


@app.get("/api/v1/leads", response_model=list[dict[str, Any]], tags=["CRM"])
def leads(
    priority: str | None = Query(default=None),
    category: Category | None = Query(default=None),
) -> list[dict[str, Any]]:
    rows = list_leads(db_path=DB_PATH)
    if priority:
        rows = [row for row in rows if row["priority"].lower() == priority.lower()]
    if category:
        rows = [row for row in rows if row["category"] == category]
    return rows

