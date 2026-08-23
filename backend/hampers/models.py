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
        # A dimension of exactly 0 (seen in real catalog rows for flat items
        # like a greeting card, where whoever filled the sheet left height
        # blank-as-zero instead of leaving it empty) is not a real
        # measurement - treat it the same as a missing dimension, not as
        # "this container/item has zero volume", or a downstream fill-%
        # calculation would silently understate space used.
        if self.length_in is None or self.breadth_in is None or self.height_in is None:
            return None
        if self.length_in <= 0 or self.breadth_in <= 0 or self.height_in <= 0:
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
        # Same dimension-validity rule as HamperContainer.usable_volume_in3 -
        # <= 0 is treated as invalid/unmeasured, not as a real zero volume.
        if self.length_in is None or self.breadth_in is None or self.height_in is None:
            return None
        if self.length_in <= 0 or self.breadth_in <= 0 or self.height_in <= 0:
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
    # Categories present anywhere in the eligible catalog for this request -
    # the yardstick "full coverage" is measured against.
    applicable_categories: list[str] = Field(default_factory=list)
    missing_categories: list[str] = Field(default_factory=list)
    is_full_category_coverage: bool = True
    # True when this recommendation was only included because not enough
    # full-coverage options existed - the BD user should see this distinction
    # rather than have it silently blended in.
    is_category_fallback: bool = False


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
    # False whenever any container/item dimension was missing or invalid and
    # had to be skipped rather than checked - callers must not read fits=True
    # in that case as a real guarantee, only as "not disproven".
    fully_verified: bool = True
    # True when utilisation_ratio was computed while excluding one or more
    # items whose dimensions were missing/invalid - the ratio is then a
    # floor, not a precise estimate, and callers must present it as such
    # (e.g. "at least X%") rather than a bare percentage.
    fill_estimate_partial: bool = False


class HamperRecommendation(BaseModel):
    container: HamperContainer
    items: list[HamperItem]
    total_price: float
    budget_utilisation: float
    composition: HamperCompositionInfo = Field(default_factory=HamperCompositionInfo)
    fit_status: HamperFitStatus
    score: float = 0
    # Human-readable reasons a BD user can read directly, e.g. "Rs 1,496.64 /
    # Rs 1,500.00 used (99.8%)" - populated by the recommender, not derived
    # client-side, so the explanation always matches the actual scoring.
    explanation: list[str] = Field(default_factory=list)


class HamperSearchResult(BaseModel):
    """The hamper API's response contract - what recommend_hampers() returns
    and what /api/hampers/recommendations serves directly, unchanged."""

    recommendations: list[HamperRecommendation]
    requested_count: int
    message: str | None = None
    # Internal per-container rejection reasons (e.g. "must-include item not
    # found") - useful for debugging/support, not necessarily surfaced
    # verbatim as the headline message a BD user sees.
    reasons: list[str] = Field(default_factory=list)

    @property
    def found_count(self) -> int:
        return len(self.recommendations)
