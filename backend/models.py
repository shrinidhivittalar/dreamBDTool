from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Product(BaseModel):
    name: str
    selling_price: float
    rock_bottom_price: float | None = None
    category: str = ""
    vendor: str = ""
    tags: list[str] = Field(default_factory=list)
    sourcing: str = ""


class RecommendationRequest(BaseModel):
    budget_min: float = Field(gt=0)
    budget_max: float = Field(gt=0)
    item_count: int = Field(gt=0, le=20)
    preferred_categories: list[str] = Field(default_factory=list)
    mandatory_products: list[str] = Field(default_factory=list)
    preferred_products: list[str] = Field(default_factory=list)
    excluded_products: list[str] = Field(default_factory=list)
    preferred_vendors: list[str] = Field(default_factory=list)
    occasion: str = ""
    sweet_preference: Literal["any", "sweet_only", "no_sweet"] = "any"
    allow_repeats: bool = False
    required_categories: list[str] = Field(default_factory=list)
    price_includes_gst: bool = False
    include_themed_customised: bool = False

    @model_validator(mode="after")
    def _validate_budget_range(self) -> "RecommendationRequest":
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min.")
        return self


class Recommendation(BaseModel):
    products: list[Product]
    total_price: float
    remaining_budget: float
    score: float


class RecommendationResponse(BaseModel):
    recommendations: list[Recommendation]
    catalog_size: int
    message: str | None = None

