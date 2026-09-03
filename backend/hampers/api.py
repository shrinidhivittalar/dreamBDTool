"""Hamper API router - a sibling of the snack-box routes in app.py, kept
separate on purpose so the two domains don't blend into one file (matches
shared/snack_boxes/hampers architecture). app.py includes this router with
one line rather than defining hamper routes itself.

Manual catalog upload mirrors the snack-box pattern in data_provider.py
(cache-to-disk so a plain restart keeps the uploaded data, same ephemeral-
disk-on-redeploy caveat) - no Zoho/daily-refresh equivalent, since hampers
still has no automated source to pull from (see PHASE1_HAMPERS.md Phase 5).
"""

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

try:
    from .catalog_loader import HamperCatalogLoadResult, load_hamper_catalog, load_hamper_catalog_bytes
    from .models import HamperRequest, HamperSearchResult
    from .recommender import recommend_hampers
except ImportError:
    from catalog_loader import HamperCatalogLoadResult, load_hamper_catalog, load_hamper_catalog_bytes
    from models import HamperRequest, HamperSearchResult
    from recommender import recommend_hampers

# Isolated from the try/except above on purpose: ..stats reaches outside
# the hampers package (up to backend/stats.py), which fails differently
# depending on how the app is launched - `uvicorn backend.app:app` from the
# repo root makes it a valid parent-package-relative import, but Render's
# actual run command (`uvicorn app:app` from inside backend/) has no
# parent package for hampers.api at all, so ..stats raises immediately.
# Bundling it into the block above meant that failure aborted the whole
# try, which fell through to a bare `from catalog_loader import ...` that
# collides with the snack-box's own backend/catalog_loader.py (same bare
# module name, already cached under it) - a real deploy break, not
# hypothetical. Keeping this in its own try/except means a stats-import
# fallback can never drag the catalog/model/recommender imports down with
# it again.
try:
    from ..stats import record_hamper_recommendation
except ImportError:
    from stats import record_hamper_recommendation

# Repo root is three levels up from this file (backend/hampers/api.py).
DEFAULT_CATALOG_PATH = (
    Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"
)
# No suffix here on purpose - the actual cache file's extension is derived
# from whatever the uploaded file's extension was (see _cache_file), since
# the loader dispatches on suffix (.csv vs .xlsx/.xls).
DEFAULT_CACHE_PATH = Path(__file__).resolve().parents[2] / ".cache" / "hamper_catalog"
CACHE_PATH = Path(os.environ.get("HAMPER_CATALOG_CACHE_PATH", str(DEFAULT_CACHE_PATH)))

router = APIRouter(prefix="/api/hampers", tags=["hampers"])

_catalog: HamperCatalogLoadResult | None = None


def _cache_file(filename: str | None = None) -> Path:
    if CACHE_PATH.suffix:
        return CACHE_PATH
    suffix = Path(filename or "hampers.csv").suffix or ".csv"
    return CACHE_PATH.with_suffix(suffix)


def _get_catalog() -> HamperCatalogLoadResult:
    global _catalog
    if _catalog is None:
        # An uploaded catalog (cached to disk) takes priority over the
        # checked-in default, same rule as the snack-box data provider - a
        # plain server restart after an upload should not silently revert
        # to the old bundled sheet.
        cache_file = _cache_file()
        if cache_file.exists():
            _catalog = load_hamper_catalog(cache_file, source_name=cache_file.name)
        elif DEFAULT_CATALOG_PATH.exists():
            _catalog = load_hamper_catalog(DEFAULT_CATALOG_PATH)
        else:
            raise HTTPException(status_code=503, detail="Hamper catalog data is not available.")
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


@router.get("/products", response_model=list[str])
def list_hamper_products() -> list[str]:
    """Item names only, for the mandatory/excluded product autocomplete -
    mirrors the snack-box GET /api/products used the same way, just without
    the full Product payload since the dropdown only needs names."""
    catalog = _get_catalog()
    return sorted(item.name for item in catalog.items)


@router.post("/catalog/upload")
async def upload_hamper_catalog(request: Request) -> dict[str, object]:
    global _catalog
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="Upload body is empty")
    filename = request.headers.get("x-filename", "uploaded_hampers.csv")
    try:
        result = load_hamper_catalog_bytes(payload, filename=filename)
    except (ValueError, RuntimeError) as error:
        # Same reasoning as the snack-box upload endpoint: a missing
        # required column or a file with zero valid rows is a business
        # error the BD user needs to see and act on, not an opaque 500.
        raise HTTPException(status_code=400, detail=str(error)) from error
    if not result.containers or not result.items:
        raise HTTPException(
            status_code=400,
            detail="Uploaded catalog must contain at least one container and one item.",
        )

    cache_file = _cache_file(filename)
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    temp_path = cache_file.with_suffix(cache_file.suffix + ".tmp")
    temp_path.write_bytes(payload)
    temp_path.replace(cache_file)

    _catalog = result
    return {
        "source_name": result.report.source_name,
        "container_count": result.report.container_count,
        "item_count": result.report.item_count,
        "warnings": result.report.warnings,
    }


@router.post("/recommendations", response_model=HamperSearchResult)
def create_hamper_recommendations(request: HamperRequest) -> HamperSearchResult:
    record_hamper_recommendation()
    catalog = _get_catalog()
    return recommend_hampers(catalog.containers, catalog.items, request, catalog.eligible_container_names)
