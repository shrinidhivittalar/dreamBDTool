from collections import Counter
from dataclasses import dataclass

try:
    from .models import Product, RecommendationRequest
    from .recommender_config import MAX_CATEGORY_GROUPS, MAX_UNIQUE_CATEGORY_GROUPS
    from .recommender_rules import (
        _category_match,
        _is_explicitly_mandatory,
        _is_themed_or_customised,
        _matches,
        _resolve_mandatory,
        _unique_category_groups,
    )
except ImportError:
    from models import Product, RecommendationRequest
    from recommender_config import MAX_CATEGORY_GROUPS, MAX_UNIQUE_CATEGORY_GROUPS
    from recommender_rules import (
        _category_match,
        _is_explicitly_mandatory,
        _is_themed_or_customised,
        _matches,
        _resolve_mandatory,
        _unique_category_groups,
    )


@dataclass(frozen=True)
class CandidateContext:
    mandatory_items: list[Product]
    pool: list[Product]
    k: int
    group_keys: tuple[str, ...]
    quota_counts: tuple[int, ...]
    unique_category_keys: tuple[str, ...]


def active_filter_descriptions(request: RecommendationRequest) -> list[str]:
    active_filters: list[str] = []
    if request.excluded_products:
        active_filters.append(f"excluded products ({', '.join(request.excluded_products)})")
    if request.preferred_categories:
        active_filters.append(f"categories ({', '.join(request.preferred_categories)})")
    if request.preferred_vendors:
        active_filters.append(f"vendors ({', '.join(request.preferred_vendors)})")
    if request.sweet_preference != "savory_and_sweet":
        active_filters.append(f"sweet preference ({request.sweet_preference.replace('_', ' ')})")
    return active_filters


def apply_catalog_filters(products: list[Product], request: RecommendationRequest) -> list[Product]:
    candidates = [
        product for product in products
        if not any(_matches(product.name, excluded) for excluded in request.excluded_products)
    ]
    if not request.include_themed_customised:
        candidates = [
            product for product in candidates
            if not _is_themed_or_customised(product)
            or _is_explicitly_mandatory(product, request.mandatory_products)
        ]
    if request.preferred_categories:
        candidates = [
            product for product in candidates
            if any(_category_match(product, category) for category in request.preferred_categories)
        ]
    if request.preferred_vendors:
        candidates = [
            product for product in candidates
            if any(_matches(product.vendor, vendor) for vendor in request.preferred_vendors)
        ]
    if request.sweet_preference == "sweet_only":
        candidates = [product for product in candidates if _category_match(product, "sweet")]
    elif request.sweet_preference == "savory_only":
        candidates = [product for product in candidates if not _category_match(product, "sweet")]
    # "savory_and_sweet" applies no extra filtering - both are allowed.
    return candidates


def _category_mask(product: Product, category_positions: dict[str, int]) -> int:
    return sum(1 << category_positions[group] for group in _unique_category_groups(product))


def build_candidate_context(products: list[Product], request: RecommendationRequest) -> CandidateContext:
    candidates = apply_catalog_filters(products, request)
    mandatory_indices = _resolve_mandatory(candidates, request.mandatory_products)
    mandatory_items = [candidates[i] for i in sorted(mandatory_indices)]
    pool = [product for i, product in enumerate(candidates) if i not in mandatory_indices]

    unique_category_keys = tuple(sorted({group for product in candidates for group in _unique_category_groups(product)}))
    if len(unique_category_keys) > MAX_UNIQUE_CATEGORY_GROUPS:
        raise ValueError(
            f"The catalog has {len(unique_category_keys)} category groups after filtering; "
            f"at most {MAX_UNIQUE_CATEGORY_GROUPS} are supported."
        )

    category_positions = {key: position for position, key in enumerate(unique_category_keys)}
    mandatory_mask = 0
    for product in mandatory_items:
        product_mask = _category_mask(product, category_positions)
        if mandatory_mask & product_mask:
            raise ValueError("Mandatory products must be from different categories.")
        mandatory_mask |= product_mask

    pool = [product for product in pool if not (mandatory_mask & _category_mask(product, category_positions))]
    k = request.item_count - len(mandatory_items)
    if k < 0:
        raise ValueError("Mandatory products exceed the requested item count.")

    category_counts = Counter(category.strip().lower() for category in request.required_categories if category.strip())
    group_keys = tuple(category_counts.keys())
    quota_counts = tuple(category_counts.values())
    if len(group_keys) > MAX_CATEGORY_GROUPS:
        raise ValueError(f"At most {MAX_CATEGORY_GROUPS} distinct required categories are supported (requested {len(group_keys)}).")
    if sum(quota_counts) > k:
        raise ValueError("Mandatory products and required categories exceed the requested item count.")
    for group in group_keys:
        if not any(_category_match(product, group) for product in pool):
            raise ValueError(f"Required category '{group}' has no matching catalog items.")

    return CandidateContext(
        mandatory_items=mandatory_items,
        pool=pool,
        k=k,
        group_keys=group_keys,
        quota_counts=quota_counts,
        unique_category_keys=unique_category_keys,
    )
