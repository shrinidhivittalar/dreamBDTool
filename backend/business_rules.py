import re

try:
    from .models import PackagingRequirement, Product, RecommendationRequest
    from .pricing import pricing_engine
except ImportError:
    from models import PackagingRequirement, Product, RecommendationRequest
    from pricing import pricing_engine


# Scoring weights are pending BD/finance sign-off.
IN_HOUSE_WEIGHT = 3
HEALTHY_WEIGHT = 2
PREFERRED_WEIGHT = 5

# Broad category groups used by the current unique-category search.
UNIQUE_CATEGORY_GROUPS = ("sweet", "savoury", "healthy")

# These items are client-facing customisation choices, not default box items.
THEMED_CUSTOMISED_PRODUCT_MARKERS = ("theme cupcake",)
THEMED_CUSTOMISED_CATEGORY_MARKERS = ("customisation",)


def _normalized_text(value: str) -> str:
    return " ".join(re.sub(r"[-/]", " ", value).split()).lower()


def _matches(value: str, requested: str) -> bool:
    return _normalized_text(requested) in _normalized_text(value)


def _category_match(product: Product, category: str) -> bool:
    return _matches(product.category, category) or any(_matches(tag, category) for tag in product.tags)


def _category_bucket_match(product: Product, category: str) -> bool:
    """Matches the discrete category-picker taxonomy (Savoury, Healthy
    Savoury, Sweet, FMCG) as mutually exclusive buckets - see the identical
    helper in recommender_rules.py for why this differs from the plain
    substring _category_match above (kept broad here for packaging's
    "is this savory" check, which must still say yes for a Healthy -
    Savoury item).
    """
    matched = _category_match(product, category)
    if not matched:
        return False
    target = _normalized_text(category)
    if target in ("savoury", "savory") and _category_match(product, "healthy"):
        return False
    return True


def _unique_category_groups(product: Product) -> set[str]:
    """Return the broad category slots occupied by a product."""
    groups = {group for group in UNIQUE_CATEGORY_GROUPS if _category_match(product, group)}
    if groups:
        return groups
    fallback = product.category.strip().lower()
    return {fallback} if fallback else set()


def _is_themed_or_customised(product: Product) -> bool:
    return (
        any(_matches(product.name, marker) for marker in THEMED_CUSTOMISED_PRODUCT_MARKERS)
        or any(_matches(product.category, marker) for marker in THEMED_CUSTOMISED_CATEGORY_MARKERS)
        or any(any(_matches(tag, marker) for marker in THEMED_CUSTOMISED_CATEGORY_MARKERS) for tag in product.tags)
    )


def _is_explicitly_mandatory(product: Product, mandatory_products: list[str]) -> bool:
    return any(_matches(product.name, wanted) for wanted in mandatory_products)


def _is_in_house(product: Product) -> bool:
    return "in-house" in product.sourcing.lower() or "dream a dozen" in product.vendor.lower()


def _is_healthy(product: Product) -> bool:
    return any("healthy" in tag.lower() for tag in product.tags)


def _is_preferred(product: Product, preferred: list[str]) -> bool:
    return any(_matches(product.name, wanted) for wanted in preferred)


def _bonus_value(product: Product, preferred: list[str]) -> float:
    return (
        IN_HOUSE_WEIGHT * _is_in_house(product)
        + HEALTHY_WEIGHT * _is_healthy(product)
        + PREFERRED_WEIGHT * _is_preferred(product, preferred)
    )


def _closeness(total: float, budget_min: float, budget_max: float) -> float:
    """Reward staying within [budget_min, budget_max]; penalize drift outside."""
    if budget_min <= total <= budget_max:
        midpoint = (budget_min + budget_max) / 2
        span = (budget_max - budget_min) or 1
        return 100 - 10 * abs(total - midpoint) / span
    if total < budget_min:
        return 95 - 40 * (budget_min - total) / budget_min
    return 95 - 40 * (total - budget_max) / budget_max


class BusinessRulesEngine:
    """Central place for pricing, budget, and packaging business rules."""

    def selling_price(self, product: Product) -> float:
        return pricing_engine.dad_selling_price(product)

    def rock_bottom_price(self, product: Product) -> float:
        return pricing_engine.rock_bottom_price(product)

    def selling_total(self, products: list[Product]) -> float:
        return pricing_engine.dad_selling_total(products)

    def rock_bottom_total(self, products: list[Product]) -> float:
        return pricing_engine.rock_bottom_total(products)

    def budget_total(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        """Budgets are compared through the centralized pricing layer."""
        return pricing_engine.budget_total(products, request)

    def remaining_budget(self, budget_max: float, products: list[Product], request: RecommendationRequest | None = None) -> float:
        return pricing_engine.remaining_budget(budget_max, products, request)

    def packaging_requirements(self, products: list[Product]) -> list[PackagingRequirement]:
        if not products:
            return []
        requirements = [
            PackagingRequirement(name="Box"),
            PackagingRequirement(name="Tissue"),
        ]
        if any(self.requires_ketchup(product) for product in products):
            requirements.append(PackagingRequirement(name="Ketchup sachet"))
        return requirements

    def requires_ketchup(self, product: Product) -> bool:
        return self.is_savory(product)

    def is_savory(self, product: Product) -> bool:
        return _category_match(product, "savory") or _category_match(product, "savoury")

    def closeness(self, total: float, budget_min: float, budget_max: float) -> float:
        return _closeness(total, budget_min, budget_max)


business_rules = BusinessRulesEngine()
