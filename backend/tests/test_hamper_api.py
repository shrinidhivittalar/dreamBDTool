from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app import app

DATA_PATH = Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"

pytestmark = pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")

client = TestClient(app)


def test_hamper_catalog_status():
    response = client.get("/api/hampers/catalog/status")

    assert response.status_code == 200
    body = response.json()
    assert body["container_count"] > 0
    assert body["item_count"] > 0


def test_hamper_recommendations_endpoint():
    response = client.post(
        "/api/hampers/recommendations",
        json={"budget_min": 1, "budget_max": 1500, "option_count": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert 0 < len(body["recommendations"]) <= 2
    for rec in body["recommendations"]:
        assert rec["total_price"] <= 1500
        assert "explanation" in rec
        assert "container" in rec
        assert "items" in rec


def test_hamper_recommendations_endpoint_invalid_budget_range():
    response = client.post(
        "/api/hampers/recommendations",
        json={"budget_min": 1000, "budget_max": 100, "option_count": 2},
    )

    assert response.status_code == 422


def test_hamper_recommendations_endpoint_impossible_mandatory():
    response = client.post(
        "/api/hampers/recommendations",
        json={
            "budget_min": 1,
            "budget_max": 1500,
            "option_count": 2,
            "mandatory_products": ["Definitely Not A Real Product"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendations"] == []
    assert body["message"]
