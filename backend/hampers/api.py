"""Hamper API router - a sibling of the snack-box routes in app.py, kept
separate on purpose so the two domains don't blend into one file (matches
shared/snack_boxes/hampers architecture). app.py includes this router with
one line rather than defining hamper routes itself.

Data loading here is deliberately minimal: the hamper catalog is loaded
once from the checked-in giftbox_data CSV. No daily-refresh/upload
machinery yet - that's snack-box-specific infra in data_provider.py, and
building a hamper equivalent now would be premature (see PHASE1_HAMPERS.md
Phase 5) until there's a real need to keep the catalog current from Zoho.
"""

from pathlib import Path

from fastapi import APIRouter, HTTPException

try:
    from .catalog_loader import HamperCatalogLoadResult, load_hamper_catalog
    from .models import HamperRequest, HamperSearchResult
    from .recommender import recommend_hampers
except ImportError:
    from catalog_loader import HamperCatalogLoadResult, load_hamper_catalog
    from models import HamperRequest, HamperSearchResult
    from recommender import recommend_hampers

# Repo root is three levels up from this file (backend/hampers/api.py).
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"
)

router = APIRouter(prefix="/api/hampers", tags=["hampers"])

_catalog: HamperCatalogLoadResult | None = None


def _get_catalog() -> HamperCatalogLoadResult:
    global _catalog
    if _catalog is None:
        if not DEFAULT_CATALOG_PATH.exists():
            raise HTTPException(status_code=503, detail="Hamper catalog data is not available.")
        _catalog = load_hamper_catalog(DEFAULT_CATALOG_PATH)
    return _catalog


@router.get("/catalog/status")
def hamper_catalog_status() -> dict[str, object]:
    catalog = _get_catalog()
    return {
        "source_name": catalog.report.source_name,
        "container_count": catalog.report.container_count,
        "item_count": catalog.report.item_count,
        "warnings": catalog.report.warnings,
    }


@router.post("/recommendations", response_model=HamperSearchResult)
def create_hamper_recommendations(request: HamperRequest) -> HamperSearchResult:
    catalog = _get_catalog()
    return recommend_hampers(catalog.containers, catalog.items, request)
