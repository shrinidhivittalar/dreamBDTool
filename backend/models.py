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
    # None means no preference on item count - the recommender is free to
    # pick whatever size (up to MAX_ITEM_COUNT) fits the budget best.
    item_count: int | None = Field(default=None, gt=0, le=10)
    preferred_categories: list[str] = Field(default_factory=list)
    mandatory_products: list[str] = Field(default_factory=list)
    preferred_products: list[str] = Field(default_factory=list)
    excluded_products: list[str] = Field(default_factory=list)
    preferred_vendors: list[str] = Field(default_factory=list)
    occasion: str = ""
    # All three real combinations: sweets-only, savory-only, or a mixed box.
    sweet_preference: Literal["sweet_only", "savory_only", "savory_and_sweet"] = "savory_and_sweet"
    required_categories: list[str] = Field(default_factory=list)
    include_themed_customised: bool = False

    @model_validator(mode="after")
    def _validate_budget_range(self) -> "RecommendationRequest":
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min.")
        return self


class PackagingRequirement(BaseModel):
    name: str


class Recommendation(BaseModel):
    products: list[Product]
    total_price: float
    remaining_budget: float
    score: float
    dad_selling_price: float = 0
    rock_bottom_price: float = 0
    customization_surcharge: float = 0
    packaging_cost: float = 0
    discount: float = 0
    packaging: list[PackagingRequirement] = Field(default_factory=list)


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    code: str
    message: str
    option_index: int | None = None


class RecommendationResponse(BaseModel):
    recommendations: list[Recommendation]
    catalog_size: int
    message: str | None = None
    validation_issues: list[ValidationIssue] = Field(default_factory=list)


class IntentParseRequest(BaseModel):
    text: str = Field(min_length=1)
    default_item_count: int | None = Field(default=None, gt=0, le=10)
    default_budget_min: float = Field(default=1, gt=0)


class IntentParseResponse(BaseModel):
    filters: dict[str, object]
    recommendation_request: RecommendationRequest
    confidence: float
    notes: list[str] = Field(default_factory=list)


