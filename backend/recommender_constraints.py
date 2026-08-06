from collections import Counter
from dataclasses import dataclass

try:
    from .models import Product, RecommendationRequest
    from .recommender_config import MAX_CATEGORY_GROUPS, MAX_UNIQUE_CATEGORY_GROUPS
    from .recommender_rules import (
        _category_bucket_match,
        _category_match,
        _fuzzy_matches,
        _is_explicitly_mandatory,
        _is_themed_or_customised,
        _matches,
        _max_category_repeat_cap,
        _resolve_mandatory,
        _suggest_names,
        _unique_category_groups,
    )
except ImportError:
    from models import Product, RecommendationRequest
    from recommender_config import MAX_CATEGORY_GROUPS, MAX_UNIQUE_CATEGORY_GROUPS
    from recommender_rules import (
        _category_bucket_match,
        _category_match,
        _fuzzy_matches,
        _is_explicitly_mandatory,
        _is_themed_or_customised,
        _matches,
        _max_category_repeat_cap,
        _resolve_mandatory,
        _suggest_names,
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
    # How many distinct rotations of "which checked categories get folded
    # into a quota" exist for this request - 1 unless more categories are
    # checked than there are item slots to guarantee them in, in which case
    # it equals the number of eligible checked categories. See
    # build_candidate_context's `category_rotation` param.
    category_rotation_count: int = 1


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


def find_customization_addon(products: list[Product]) -> Product | None:
    return next((product for product in products if product.is_customization_addon), None)


def apply_catalog_filters(products: list[Product], request: RecommendationRequest) -> list[Product]:
    # Customization add-ons (the White Chocolate Disc) are never a standalone
    # box item, under any setting - not include_themed_customised, not even
    # an explicit mandatory_products request. They only apply as a surcharge
    # via request.customize_products, handled in pricing.py.
    candidates = [product for product in products if not product.is_customization_addon]
    candidates = [
        product for product in candidates
        if not any(_matches(product.name, excluded) for excluded in request.excluded_products)
    ]
    if not request.include_themed_customised:
        candidates = [
            product for product in candidates
            if not _is_themed_or_customised(product)
            or _is_explicitly_mandatory(product, request.mandatory_products)
        ]
    # Categories/vendors/sweet-preference are soft filters that narrow the
    # pool - a "Must include" product is a stronger, explicit instruction
    # (the same reasoning as the themed/customised bypass above), so it's
    # exempted from all three the same way. Without this, checking "Sweet
    # only" while must-including a Savoury product like Samosa filtered the
    # candidate list down *before* mandatory-product resolution ran, so
    # `_resolve_mandatory` (recommender_rules.py) found zero matches and
    # raised "did not match any catalog item" - a flatly false error, since
    # Samosa is right there in the catalog; it just isn't Sweet. The real
    # conflict is "you asked for this exact item and a category that
    # excludes it," and the right resolution is honoring the more specific,
    # explicit instruction (the exact product), same as Must Include
    # already overrides "hide themed/customised items by default."
    if request.preferred_categories:
        candidates = [
            product for product in candidates
            if any(_category_bucket_match(product, category) for category in request.preferred_categories)
            or _is_explicitly_mandatory(product, request.mandatory_products)
        ]
    if request.preferred_vendors:
        candidates = [
            product for product in candidates
            if any(_matches(product.vendor, vendor) for vendor in request.preferred_vendors)
            or _is_explicitly_mandatory(product, request.mandatory_products)
        ]
    if request.sweet_preference == "sweet_only":
        candidates = [
            product for product in candidates
            if _category_match(product, "sweet") or _is_explicitly_mandatory(product, request.mandatory_products)
        ]
    elif request.sweet_preference == "savory_only":
        candidates = [
            product for product in candidates
            if not _category_match(product, "sweet") or _is_explicitly_mandatory(product, request.mandatory_products)
        ]
    # "savory_and_sweet" applies no extra filtering - both are allowed.
    return candidates


def _category_mask(product: Product, category_positions: dict[str, int]) -> int:
    return sum(1 << category_positions[group] for group in _unique_category_groups(product))


def build_candidate_context(products: list[Product], request: RecommendationRequest, category_rotation: int = 0) -> CandidateContext:
    # A direct self-contradiction (the same product named in both Must
    # Include and Exclude) needs to be caught here, before
    # apply_catalog_filters removes it from the pool - otherwise Exclude
    # silently wins (the product vanishes from `candidates`) and
    # _resolve_mandatory below reports the misleading "did not match any
    # catalog item", as if the name were mistyped rather than deliberately
    # excluded. Unlike the soft-preference overrides above (categories,
    # vendor, sweet-only), Exclude and Must Include are both explicit,
    # equally-strong instructions - there's no principled way to silently
    # prefer one, so this is a hard error asking the user to resolve it,
    # not an override.
    for mandatory in request.mandatory_products:
        conflicting = next(
            (
                excluded for excluded in request.excluded_products
                if _matches(mandatory, excluded) or _matches(excluded, mandatory) or _fuzzy_matches(mandatory, excluded)
            ),
            None,
        )
        if conflicting is not None:
            raise ValueError(f"'{mandatory}' is in both Must Include and Exclude - remove it from one of the two.")
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

    # Mandatory items don't get an unconditional "no other product may ever
    # share my category" veto anymore - that was a leftover from before
    # category_repeat_cap existed (recommender.py/recommender_search.py),
    # and it hard-blocked *every* pool product sharing a broad category
    # with a mandatory item regardless of box size. For a 3-item box
    # against 3 categories that's the same as cap=1 anyway, but for a
    # 6-item box the search elsewhere would allow up to 2 items per
    # category - the pool needs to allow that many too, or a mandatory
    # item can make an otherwise-satisfiable box (e.g. "Samosa" plus
    # HealthyChef's Savoury/Healthy items) come back with an empty pool
    # for no real reason. Only exclude a pool product once mandatory items
    # alone have already used up its category's fair share of the box.
    category_repeat_cap = _max_category_repeat_cap(request.item_count, unique_category_keys)
    mandatory_group_counts = Counter(group for product in mandatory_items for group in _unique_category_groups(product))
    pool = [
        product for product in pool
        if all(mandatory_group_counts[group] < category_repeat_cap for group in _unique_category_groups(product))
    ]
    k = request.item_count - len(mandatory_items)
    if k < 0:
        raise ValueError("Mandatory products exceed the requested item count.")

    category_counts = Counter(category.strip().lower() for category in request.required_categories if category.strip())
    explicit_required_groups = set(category_counts.keys())
    if sum(category_counts.values()) > k:
        raise ValueError("Mandatory products and required categories exceed the requested item count.")
    # The "Categories" picker (request.preferred_categories) used to only
    # narrow the candidate pool (apply_catalog_filters) without guaranteeing
    # any of the checked categories actually made it into a given box - a
    # box could satisfy "every item is Sweet, Savoury, or Healthy Savoury"
    # while still being 100% Sweet. Folding each checked category in here
    # too (at a minimum quota of 1, same mechanism as an explicit "Must
    # include" category) makes checking a category an actual guarantee
    # instead of a soft filter. Unlike an explicit "Must include" category,
    # this is a *soft* preference: it only claims a slot if one is actually
    # left after mandatory items and explicit required categories, and
    # silently stops folding once slots run out rather than hard-erroring -
    # e.g. a 3-item box with all 4 category chips checked (the wizard's
    # default) folds 3 of them and leaves the 4th as a soft "not
    # guaranteed" preference instead of a 400. The validator's
    # preferred_category_missing warning still flags whichever category(s)
    # didn't make it in, so the user isn't left in the dark about it - it's
    # just a warning, not a blocking error, same as any other unmet
    # preference. A picked category with zero catalog matches (typo, or a
    # category the current catalog just doesn't have) is left out of the
    # quota the same way - apply_catalog_filters already narrowed the pool
    # to nothing in that case, so the normal "too few candidates" message
    # below handles it; only an explicit "Must include" category gets the
    # hard, typo-suggesting error, same as before this change.
    #
    # If more categories are checked than there are slots left to guarantee
    # them all, folding always the same subset (e.g. always the first 3 of
    # 4 in list order) means one category - always the same one - never
    # appears in *any* returned option. `category_rotation` rotates which
    # subset gets folded instead, so calling this once per rotation and
    # merging the results (see recommender.py) spreads which category
    # drops across different options, and every checked category shows up
    # in at least some of them rather than always the same one being
    # silently excluded from the entire result set.
    remaining = k - sum(category_counts.values())
    eligible_preferred: list[str] = []
    seen_preferred: set[str] = set()
    for category in request.preferred_categories:
        key = category.strip().lower()
        if key and key not in category_counts and key not in seen_preferred and any(_category_bucket_match(product, key) for product in pool):
            eligible_preferred.append(key)
            seen_preferred.add(key)
    rotation_count = 1
    if eligible_preferred and remaining > 0:
        take = min(remaining, len(eligible_preferred))
        rotation_count = len(eligible_preferred) if take < len(eligible_preferred) else 1
        offset = category_rotation % len(eligible_preferred)
        rotated = eligible_preferred[offset:] + eligible_preferred[:offset]
        for key in rotated[:take]:
            category_counts[key] = 1
    group_keys = tuple(category_counts.keys())
    quota_counts = tuple(category_counts.values())
    if len(group_keys) > MAX_CATEGORY_GROUPS:
        raise ValueError(f"At most {MAX_CATEGORY_GROUPS} distinct required/preferred categories are supported (requested {len(group_keys)}).")
    for group in explicit_required_groups:
        if not any(_category_bucket_match(product, group) for product in pool):
            available = sorted({group for product in pool for group in _unique_category_groups(product)})
            suggestions = _suggest_names(group, available)
            if suggestions:
                raise ValueError(
                    f"Required category '{group}' has no matching catalog items. "
                    f"Did you mean: {', '.join(suggestions)}?"
                )
            raise ValueError(f"Required category '{group}' has no matching catalog items.")

    return CandidateContext(
        mandatory_items=mandatory_items,
        pool=pool,
        k=k,
        group_keys=group_keys,
        quota_counts=quota_counts,
        unique_category_keys=unique_category_keys,
        category_rotation_count=rotation_count,
    )
