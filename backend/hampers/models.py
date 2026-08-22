from pydantic import BaseModel, Field, model_validator


class HamperContainer(BaseModel):
    """An outer hamper box/basket that items are packed into."""

    name: str
    price: float
    rock_bottom_price: float | None = None
    length_in: float | None = None
    breadth_in: float | None = None
    height_in: float | None = None
    vendor: str = ""
    tags: list[str] = Field(default_factory=list)

    @property
    def usable_volume_in3(self) -> float | None:
        if self.length_in is None or self.breadth_in is None or self.height_in is None:
            return None
        return self.length_in * self.breadth_in * self.height_in


class HamperItem(BaseModel):
    """An item that can be placed inside a hamper container."""

    name: str
    price: float
    rock_bottom_price: float | None = None
    category: str = ""
    vendor: str = ""
    tags: list[str] = Field(default_factory=list)
    length_in: float | None = None
    breadth_in: float | None = None
    height_in: float | None = None
    primary_packaging: str = ""
    secondary_packaging: str = ""

    @property
    def volume_in3(self) -> float | None:
        if self.length_in is None or self.breadth_in is None or self.height_in is None:
            return None
        return self.length_in * self.breadth_in * self.height_in


class HamperRequest(BaseModel):
    budget_min: float = Field(gt=0)
    budget_max: float = Field(gt=0)
    option_count: int = Field(default=5, gt=0, le=10)
    preferred_categories: list[str] = Field(default_factory=list)
    mandatory_products: list[str] = Field(default_factory=list)
    excluded_products: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_budget_range(self) -> "HamperRequest":
        if self.budget_max < self.budget_min:
            raise ValueError("budget_max must be greater than or equal to budget_min.")
        return self


class HamperCompositionInfo(BaseModel):
    category_counts: dict[str, int] = Field(default_factory=dict)


class HamperFitStatus(BaseModel):
    """Conservative, non-bin-packing fit assessment for a candidate
    container + item selection. Volume-ratio based for v1; architected so
    a real packing/arrangement algorithm can replace the check later
    without changing callers."""

    fits: bool
    used_volume_in3: float | None = None
    container_volume_in3: float | None = None
    utilisation_ratio: float | None = None
    notes: str = ""


class HamperRecommendation(BaseModel):
    container: HamperContainer
    items: list[HamperItem]
    total_price: float
    budget_utilisation: float
    composition: HamperCompositionInfo = Field(default_factory=HamperCompositionInfo)
    fit_status: HamperFitStatus
    score: float = 0
