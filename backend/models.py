from pydantic import BaseModel, Field


class Product(BaseModel):
    name: str
    selling_price: float
    rock_bottom_price: float | None = None
    category: str = ""
    vendor: str = ""
    tags: list[str] = Field(default_factory=list)
    sourcing: str = ""


class RecommendationRequest(BaseModel):
    budget: float = Field(gt=0)
    item_count: int = Field(gt=0, le=20)
    preferred_categories: list[str] = Field(default_factory=list)
    mandatory_products: list[str] = Field(default_factory=list)
    preferred_products: list[str] = Field(default_factory=list)
    excluded_products: list[str] = Field(default_factory=list)
    preferred_vendors: list[str] = Field(default_factory=list)
    occasion: str = ""
    buffer_percentage: float = Field(default=10, ge=0, lt=100)
    allow_repeats: bool = False
    required_categories: list[str] = Field(default_factory=list)


class Recommendation(BaseModel):
    products: list[Product]
    total_price: float
    remaining_budget: float
    score: float


class RecommendationResponse(BaseModel):
    recommendations: list[Recommendation]
    catalog_size: int
    message: str | None = None

