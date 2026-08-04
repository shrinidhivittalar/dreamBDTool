import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware

try:
    from .data_provider import data_provider
    from .exporter import content_type_for, export_recommendations, filename_for
    from .intent_parser import parse_intent_response
    from .models import IntentParseRequest, IntentParseResponse, Product, RecommendationRequest, RecommendationResponse
    from .recommender import recommend
    from .validator import blocking_errors, validate_recommendations
except ImportError:
    from data_provider import data_provider
    from exporter import content_type_for, export_recommendations, filename_for
    from intent_parser import parse_intent_response
    from models import IntentParseRequest, IntentParseResponse, Product, RecommendationRequest, RecommendationResponse
    from recommender import recommend
    from validator import blocking_errors, validate_recommendations


def _auto_refresh_enabled() -> bool:
    return os.environ.get("PRODUCT_AUTO_REFRESH", "false").strip().lower() in {"1", "true", "yes", "on"}


def _validation_message(base_message: str | None, issues) -> str | None:
    warnings = [issue for issue in issues if issue.severity == "warning"]
    if not warnings:
        return base_message
    warning_text = "; ".join(issue.message for issue in warnings[:3])
    return f"{base_message} {warning_text}" if base_message else warning_text


def _validated_response(recommendations, request: RecommendationRequest, catalog_size: int, message: str | None = None) -> RecommendationResponse:
    issues = validate_recommendations(recommendations, request)
    errors = blocking_errors(issues)
    if errors:
        raise HTTPException(status_code=500, detail=[issue.model_dump() for issue in errors])
    return RecommendationResponse(
        recommendations=recommendations,
        catalog_size=catalog_size,
        message=_validation_message(message, issues),
        validation_issues=issues,
    )


def _daily_refresh_enabled() -> bool:
    return os.environ.get("PRODUCT_DAILY_REFRESH", "true").strip().lower() in {"1", "true", "yes", "on"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_provider.load_initial()
    refresh_task = None
    daily_task = None
    if _auto_refresh_enabled():
        interval = int(os.environ.get("PRODUCT_AUTO_REFRESH_MINUTES", str(24 * 60)))
        refresh_task = asyncio.create_task(data_provider.run_auto_refresh(interval))
    # Catalog is pulled automatically every day at 8am; manual pull/upload
    # endpoints (/api/products/refresh, /api/products/upload) remain available
    # for an on-demand re-sync.
    if _daily_refresh_enabled():
        hour = int(os.environ.get("PRODUCT_DAILY_REFRESH_HOUR", "8"))
        minute = int(os.environ.get("PRODUCT_DAILY_REFRESH_MINUTE", "0"))
        daily_task = asyncio.create_task(data_provider.run_daily_refresh(hour, minute))
    try:
        yield
    finally:
        if refresh_task:
            refresh_task.cancel()
        if daily_task:
            daily_task.cancel()


app = FastAPI(title="Dream a Dozen Gift Box Recommendation Tool", lifespan=lifespan)
# ALLOWED_ORIGINS is a comma-separated list (e.g. the deployed frontend's
# Render URL); defaults to the local Vite dev server so nothing extra is
# needed for local development.
allowed_origins = [origin.strip() for origin in os.environ.get("ALLOWED_ORIGINS", "http://localhost:5173").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed_origins, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/products", response_model=list[Product])
def list_products() -> list[Product]:
    return data_provider.get_products()


@app.get("/api/products/status")
def product_data_status() -> dict[str, object]:
    return data_provider.get_status().as_dict()


@app.post("/api/products/refresh")
async def refresh_products() -> dict[str, object]:
    status = await data_provider.refresh_async()
    return status.as_dict()


@app.post("/api/products/upload")
async def upload_products(request: Request) -> dict[str, object]:
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="Upload body is empty")
    filename = request.headers.get("x-filename", "uploaded_catalog.xlsx")
    try:
        status = data_provider.refresh_from_bytes(payload, filename=filename, cache=True)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return status.as_dict()




@app.post("/api/intent/parse", response_model=IntentParseResponse)
def parse_intent_endpoint(request: IntentParseRequest) -> IntentParseResponse:
    return parse_intent_response(
        request.text,
        default_item_count=request.default_item_count,
        default_budget_min=request.default_budget_min,
    )


@app.post("/api/intent/recommendations", response_model=RecommendationResponse)
def recommendations_from_intent(request: IntentParseRequest) -> RecommendationResponse:
    parsed = parse_intent_response(
        request.text,
        default_item_count=request.default_item_count,
        default_budget_min=request.default_budget_min,
    )
    products = data_provider.get_products()
    messages: list[str] = []
    try:
        recommendations = recommend(products, parsed.recommendation_request, messages=messages)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if messages:
        message = messages[0]
    elif not recommendations:
        message = "No valid combinations found for these requirements."
    else:
        message = None
    return _validated_response(recommendations, parsed.recommendation_request, len(products), message)


@app.post("/api/recommendations", response_model=RecommendationResponse)
def create_recommendations(request: RecommendationRequest) -> RecommendationResponse:
    products = data_provider.get_products()
    messages: list[str] = []
    try:
        recommendations = recommend(products, request, messages=messages)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    if messages:
        message = messages[0]
    elif not recommendations:
        message = "No valid combinations found for these requirements."
    else:
        message = None
    return _validated_response(recommendations, request, len(products), message)


@app.post("/api/recommendations/export/{export_format}")
def export_recommendation_file(export_format: str, request: RecommendationRequest, layout: str = "summary") -> Response:
    normalized = "xlsx" if export_format.lower() == "excel" else export_format.lower()
    if normalized not in {"csv", "xlsx", "pdf"}:
        raise HTTPException(status_code=400, detail="Export format must be csv, xlsx, or pdf")
    if layout not in {"summary", "itemized"}:
        raise HTTPException(status_code=400, detail="Export layout must be summary or itemized")

    products = data_provider.get_products()
    try:
        recommendations = recommend(products, request)
        issues = validate_recommendations(recommendations, request)
        errors = blocking_errors(issues)
        if errors:
            raise RuntimeError(f"Recommendation validation failed: {errors[0].message}")
        payload = export_recommendations(recommendations, normalized, layout)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=500, detail=str(error)) from error

    return Response(
        content=payload,
        media_type=content_type_for(normalized),
        headers={"Content-Disposition": f"attachment; filename={filename_for(normalized)}"},
    )
