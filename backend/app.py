from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from .excel_loader import load_products
    from .models import Product, RecommendationRequest, RecommendationResponse
    from .recommender import recommend
except ImportError:
    from excel_loader import load_products
    from models import Product, RecommendationRequest, RecommendationResponse
    from recommender import recommend


ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "products.xlsx"
FALLBACK_CATALOG = ROOT / "Input Data - Quotations Tool_Sheet1.csv"
CATALOG_PATH = CATALOG if CATALOG.exists() else FALLBACK_CATALOG
products: list[Product] = load_products(CATALOG_PATH)

app = FastAPI(title="Dream a Dozen Gift Box Recommendation Tool")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/products", response_model=list[Product])
def list_products() -> list[Product]:
    return products


@app.post("/api/recommendations", response_model=RecommendationResponse)
def create_recommendations(request: RecommendationRequest) -> RecommendationResponse:
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
    return RecommendationResponse(recommendations=recommendations, catalog_size=len(products), message=message)



