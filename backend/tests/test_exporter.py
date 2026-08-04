from io import BytesIO

import pytest

from backend.exporter import export_csv, export_pdf, export_recommendations, export_xlsx
from backend.models import PackagingRequirement, Product, Recommendation


def _recommendations() -> list[Recommendation]:
    return [Recommendation(
        products=[Product(name="Samosa", selling_price=40, vendor="Cakewala")],
        total_price=42,
        remaining_budget=58,
        score=99,
        dad_selling_price=40,
        rock_bottom_price=30,
        packaging=[PackagingRequirement(name="Box"), PackagingRequirement(name="Ketchup sachet")],
    )]


def test_export_csv_contains_recommendation_fields():
    payload = export_csv(_recommendations()).decode("utf-8-sig")

    assert "products" in payload
    assert "Samosa" in payload
    assert "Ketchup sachet" in payload


def test_export_xlsx_returns_excel_workbook_bytes():
    pytest.importorskip("openpyxl")

    payload = export_xlsx(_recommendations())

    assert payload.startswith(b"PK")
    assert len(payload) > 1000


def test_export_pdf_returns_pdf_bytes():
    payload = export_pdf(_recommendations())

    assert payload.startswith(b"%PDF-1.4")
    assert b"%%EOF" in payload


def test_export_recommendations_rejects_unknown_format():
    with pytest.raises(ValueError):
        export_recommendations(_recommendations(), "docx")
