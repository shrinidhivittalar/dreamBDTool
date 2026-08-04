import re

try:
    from .models import Product
    from .recommender_config import (
        HEALTHY_WEIGHT,
        IN_HOUSE_WEIGHT,
        PREFERRED_WEIGHT,
        THEMED_CUSTOMISED_CATEGORY_MARKERS,
        THEMED_CUSTOMISED_PRODUCT_MARKERS,
        UNIQUE_CATEGORY_GROUPS,
    )
except ImportError:
    from models import Product
    from recommender_config import (
        HEALTHY_WEIGHT,
        IN_HOUSE_WEIGHT,
        PREFERRED_WEIGHT,
        THEMED_CUSTOMISED_CATEGORY_MARKERS,
        THEMED_CUSTOMISED_PRODUCT_MARKERS,
        UNIQUE_CATEGORY_GROUPS,
    )


def _normalized_text(value: str) -> str:
    # Collapses "-", "/" and repeated whitespace to a single space so
    # catalog punctuation quirks (e.g. "Healthy - Savoury" vs a "Healthy
    # Savoury" filter) don't silently zero out an otherwise-valid match.
    return " ".join(re.sub(r"[-/]", " ", value).split()).lower()


def _matches(value: str, requested: str) -> bool:
    return _normalized_text(requested) in _normalized_text(value)


# Strips a trailing size/variant qualifier (with or without a leading dash)
# so "Fudgy walnut brownie - mini" and "Fudgy Walnut brownie" resolve to the
# same base product - a box shouldn't carry two sizes of the same flavor.
_VARIANT_SUFFIX_RE = re.compile(
    r"\s*-?\s*\b(mini|half|small|large|full|single|double|regular)\b\s*$",
    re.IGNORECASE,
)


def _base_product_key(product: Product) -> str:
    name = product.name.strip().lower()
    while True:
        stripped = _VARIANT_SUFFIX_RE.sub("", name).strip()
        if stripped == name:
            return name
        name = stripped


def _category_match(product: Product, category: str) -> bool:
    return _matches(product.category, category) or any(_matches(tag, category) for tag in product.tags)

def _unique_category_groups(product: Product) -> set[str]:
    """Return the broad category slots occupied by a product.

    Known broad groups intentionally collapse labels such as "In-house
    sweet" and "outsourced Sweet" into "sweet". For a future catalog
    category that is not in the configured groups, its normalized category
    label remains its own slot instead of being ignored.
    """
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
    """Reward staying within [budget_min, budget_max]; penalize drifting
    outside on either side.

    No branch discards a total - falling outside the range only lowers the
    score. There is deliberately no hard cutoff.
    """
    if budget_min <= total <= budget_max:
        midpoint = (budget_min + budget_max) / 2
        span = (budget_max - budget_min) or 1
        return 100 - 10 * abs(total - midpoint) / span
    if total < budget_min:
        return 95 - 40 * (budget_min - total) / budget_min
    return 95 - 40 * (total - budget_max) / budget_max


def _resolve_mandatory(candidates: list[Product], requested: list[str]) -> set[int]:
    """Resolve each mandatory product name to exactly one catalog index.

    Unlike the lenient substring filters used elsewhere, a mandatory
    product must be unambiguous: it either names one product exactly, or
    substring-matches exactly one candidate. Anything else is a request
    error, since silently including zero or several products would break
    the caller's expectation of "this exact item is in every box."
    """
    resolved: set[int] = set()
    for wanted in requested:
        needle = wanted.strip().lower()
        exact = [i for i, product in enumerate(candidates) if product.name.strip().lower() == needle]
        matches = exact if exact else [i for i, product in enumerate(candidates) if _matches(product.name, wanted)]
        if len(matches) != 1:
            raise ValueError(f"Mandatory product '{wanted}' must match exactly one catalog item (found {len(matches)}).")
        resolved.add(matches[0])
    return resolved


