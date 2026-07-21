from __future__ import annotations

import asyncio
from pathlib import Path

import httpx

import api


def request(method: str, path: str, **kwargs) -> httpx.Response:
    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=api.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_endpoint(db_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(api, "DB_PATH", db_path)
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_analyze_products_and_crm_endpoints(
    keyboard_inquiry: str,
    db_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(api, "DB_PATH", db_path)
    analysis_response = request(
        "POST",
        "/api/v1/inquiries/analyze",
        json={"inquiry_text": keyboard_inquiry, "use_llm": False},
    )
    assert analysis_response.status_code == 200
    analysis = analysis_response.json()
    assert analysis["product_match"]["recommended_sku"] == "KB75-GASKET-TM"

    products_response = request("GET", "/api/v1/products", params={"category": "mechanical_keyboard"})
    assert products_response.status_code == 200
    assert len(products_response.json()) == 4

    create_response = request("POST", "/api/v1/leads", json={"analysis": analysis})
    assert create_response.status_code == 201
    assert create_response.json()["lead_id"].startswith("LEAD-")

    leads_response = request("GET", "/api/v1/leads", params={"priority": "High"})
    assert leads_response.status_code == 200
    assert len(leads_response.json()) == 1


def test_api_rejects_short_inquiry(db_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(api, "DB_PATH", db_path)
    response = request(
        "POST",
        "/api/v1/inquiries/analyze",
        json={"inquiry_text": "short", "use_llm": False},
    )

    assert response.status_code == 422
