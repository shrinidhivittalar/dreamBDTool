from collections import Counter

try:
    from .models import Product, Recommendation, RecommendationRequest
    from .pricing import pricing_engine
    from .recommender_config import MAX_ITEM_COUNT, MAX_SIBLINGS_PER_POSITION, MAX_SIBLING_BASE_COMBOS, SIBLING_PRICE_TOLERANCE
    from .recommender_constraints import CandidateContext, active_filter_descriptions, build_candidate_context, find_customization_addon
    from .recommender_diversity import _select_diverse
    from .recommender_ranking import (
        ScoredCombination,
        append_budget_hint,
        mandatory_only_recommendation,
        recommendation_from_score,
        score_combination,
    )
    from .recommender_rules import _base_product_key, _bonus_value, _category_match, _closeness, _max_category_repeat_cap, _product_type_key, _unique_category_groups
    from .recommender_search import _search_pool, _search_unique_pool, generate_combinations
except ImportError:
    from models import Product, Recommendation, RecommendationRequest
    from pricing import pricing_engine
    from recommender_config import MAX_ITEM_COUNT, MAX_SIBLINGS_PER_POSITION, MAX_SIBLING_BASE_COMBOS, SIBLING_PRICE_TOLERANCE
    from recommender_constraints import CandidateContext, active_filter_descriptions, build_candidate_context, find_customization_addon
    from recommender_diversity import _select_diverse
    from recommender_ranking import (
        ScoredCombination,
        append_budget_hint,
        mandatory_only_recommendation,
        recommendation_from_score,
        score_combination,
    )
    from recommender_rules import _base_product_key, _bonus_value, _category_match, _closeness, _max_category_repeat_cap, _product_type_key, _unique_category_groups
    from recommender_search import _search_pool, _search_unique_pool, generate_combinations


def _sibling_candidates(
    pool: list[Product],
    item: Product,
    excluded_keys: set[str],
    group_keys: tuple[str, ...],
) -> list[Product]:
    """Other pool products that are a budget/category-neutral swap for
    `item` - same price bucket (so scoring/budget impact is unchanged) and
    the same category footprint (so unique-category and required-category
    quotas stay satisfied). The DP search's tie-breaking keeps only one
    canonical item per (price, category) state, silently discarding true
    alternatives like this - this reintroduces them so the diversity
    selector has real variety to choose from instead of always seeing the
    same single "winner" for every tied slot (e.g. every FMCG item costs
    the same, so only one would ever appear without this).
    """
    item_groups = _unique_category_groups(item)
    # A direct rupee tolerance (SIBLING_PRICE_TOLERANCE), not price_bucket
    # equality - a fixed-width grid still splits two close-but-not-quite
    # identical prices into different buckets right at the grid line, which
    # left items like the catalog's cheapest Savoury product with no real
    # siblings at all (confirmed live: it appeared in every single returned
    # option because there was nothing else in its "bucket" to substitute).
    # The real total price is still what budget-closeness scoring judges
    # the final combo on, so a same-tier swap can't silently make a box
    # drift far off budget.
    item_price = pricing_engine.dad_selling_price(item)
    item_required = tuple(_category_match(item, group) for group in group_keys)
    siblings = []
    for candidate in pool:
        if _base_product_key(candidate) in excluded_keys:
            continue
        if _unique_category_groups(candidate) != item_groups:
            continue
        if abs(pricing_engine.dad_selling_price(candidate) - item_price) > SIBLING_PRICE_TOLERANCE:
            continue
        if tuple(_category_match(candidate, group) for group in group_keys) != item_required:
            continue
        siblings.append(candidate)
    return siblings


def _too_few_candidates_message(pool_size: int, k: int, request: RecommendationRequest) -> str:
    active_filters = active_filter_descriptions(request)
    if active_filters:
        return (
            f"Only {pool_size} catalog item(s) match {', '.join(active_filters)} - not enough to fill "
            f"{k} more slot(s) for a {request.item_count}-item box. Check for typos, or loosen these filters."
        )
    return (
        f"Only {pool_size} catalog item(s) are available - not enough to fill {k} more slot(s) "
        f"without repeats. Try enabling repeated products or lowering the item count."
    )


def _generate_scored_combinations(
    context,
    request: RecommendationRequest,
    customization_addon: Product | None = None,
) -> list[ScoredCombination]:
    def search(cap: int):
        return generate_combinations(
            context.pool,
            context.k,
            request.preferred_products,
            context.group_keys,
            context.quota_counts,
            context.unique_category_keys,
            allow_repeats=False,
            enforce_unique_categories=True,
            category_repeat_cap=cap,
        )

    # Tries the strictest per-box category-repeat cap first (1 - true
    # uniqueness), only loosening it if the box is bigger than the number of
    # broad category groups that exist at all (so cap=1 is mathematically
    # unsatisfiable), and even then only as far as the catalog forces -
    # mirrors the diversity selector's progressive relaxation
    # (recommender_diversity.py) rather than jumping straight from "1 per
    # category" to "anything goes" the moment a 4-item box can't fit into 3
    # categories. This is what stops a box from being, say, 3 cupcakes
    # (all "sweet") plus 1 savoury filler just because cupcakes score well -
    # each broad category is capped at a fair share of the box, not
    # unlimited once its minimum quota is met.
    # Bounded to at most two tries of the (comparatively expensive,
    # dict-state) capped search before falling back to the fast, uncapped
    # numpy DP - an escalating cap=1,2,3,...,k retry loop was briefly tried
    # here and was too slow in practice (each larger cap multiplies the
    # per-broad-group state space, and _recommend_any_count repeats this
    # whole search once per item size 1..10).
    if context.k <= len(context.unique_category_keys):
        generated = search(1)
    else:
        generated = search(_max_category_repeat_cap(context.k, context.unique_category_keys))
    if not generated:
        # Last resort: no category-repeat constraint at all, so a catalog
        # that can't otherwise fill this item count still returns something
        # rather than nothing.
        generated = generate_combinations(
            context.pool,
            context.k,
            request.preferred_products,
            context.group_keys,
            context.quota_counts,
            context.unique_category_keys,
            allow_repeats=False,
            enforce_unique_categories=False,
        )

    mandatory_keys = {_base_product_key(product) for product in context.mandatory_items}
    combos = [([context.pool[i] for i in item_indices], bonus_sum) for bonus_sum, item_indices in generated]

    # Sibling substitution: for each combo, try swapping each item for a
    # same-price-bucket, same-category alternative the search's tie-
    # breaking discarded (see _sibling_candidates) - without this, every
    # combo the search emits shares the same single best-bonus pick for any
    # tied slot (e.g. every FMCG item costs the same, so it's always
    # Frooti, never Lays), which is exactly the "same product in every
    # option" bug this exists to prevent, so it always runs.
    #
    # Sampled with an even stride across the full combo list, not "top N by
    # bonus_sum" - bonus_sum doesn't track final rank (that also depends on
    # budget closeness, computed later) and, worse, the highest-bonus combos
    # tend to be near-duplicates of each other (same core items, one tied
    # slot swapped), so substituting only those covers one box repeatedly
    # instead of spreading sibling alternatives across genuinely different
    # underlying boxes. An even stride is cheap and reaches across the
    # whole result space instead.
    all_candidates = list(combos)
    if len(combos) > MAX_SIBLING_BASE_COMBOS:
        stride = len(combos) // MAX_SIBLING_BASE_COMBOS
        combos_to_expand = combos[::stride][:MAX_SIBLING_BASE_COMBOS]
    else:
        combos_to_expand = combos
    for pool_items, bonus_sum in combos_to_expand:
        existing_keys = {_base_product_key(product) for product in pool_items} | mandatory_keys
        for position, item in enumerate(pool_items):
            # Capped per position too - without this, one combo's first,
            # sibling-rich position (a bread roll with a dozen near-
            # identical alternatives) could dominate that combo's share of
            # the work before ever reaching the position actually causing a
            # repeat (e.g. the one FMCG slot).
            siblings = _sibling_candidates(context.pool, item, existing_keys, context.group_keys)[:MAX_SIBLINGS_PER_POSITION]
            for sibling in siblings:
                variant = list(pool_items)
                variant[position] = sibling
                variant_bonus = bonus_sum - _bonus_value(item, request.preferred_products) + _bonus_value(sibling, request.preferred_products)
                all_candidates.append((variant, variant_bonus))

    mandatory_type_keys = {_product_type_key(product) for product in context.mandatory_items}
    deduped_candidates: list[tuple[list[Product], float, list[str], bool]] = []
    seen_key_sets: set[frozenset[str]] = set()
    for pool_items, bonus_sum in all_candidates:
        pool_keys = [_base_product_key(product) for product in pool_items]
        # Skip boxes that would carry two size/variant SKUs of the same
        # flavor (e.g. a "mini" and a full-size version of one brownie).
        if len(set(pool_keys)) != len(pool_keys) or mandatory_keys & set(pool_keys):
            continue
        key_set = frozenset(pool_keys) | mandatory_keys
        if key_set in seen_key_sets:
            continue
        seen_key_sets.add(key_set)
        type_keys = [_product_type_key(product) for product in pool_items]
        type_unique = len(set(type_keys)) == len(type_keys) and not (mandatory_type_keys & set(type_keys))
        deduped_candidates.append((pool_items, bonus_sum, pool_keys, type_unique))

    # Two different flavors of the same dish (e.g. "Blueberry Cupcake" and
    # "Chocolate buttercream Cupcake") pass the SKU-uniqueness check above
    # just fine - they're genuinely different products - but a box with
    # two cupcakes (or two juices) still reads as "the same item twice" to
    # whoever opens it. type_unique is carried on the combo itself rather
    # than filtered here - the caller (_recommend_fixed_count /
    # _recommend_any_count) decides whether to prefer type-unique combos,
    # since _recommend_any_count merges combos across every box size and
    # needs to make that call once on the *whole* merged pool, not per
    # size (a size with no clean combo shouldn't leak a duplicate-type box
    # into the merge when other sizes have plenty of clean alternatives).
    scored: list[ScoredCombination] = []
    for pool_items, bonus_sum, pool_keys, type_unique in deduped_candidates:
        scored.append(
            score_combination(
                context.mandatory_items,
                pool_items,
                bonus_sum,
                # Keyed on actual product identity (not pool position) so
                # overlap comparisons stay meaningful even across the
                # different pools _recommend_any_count builds per item size.
                Counter(pool_keys),
                request,
                customization_addon,
                type_unique,
            )
        )

    scored.sort(key=lambda entry: entry.score, reverse=True)
    return scored


def _prefer_type_unique(scored: list[ScoredCombination]) -> list[ScoredCombination]:
    # Applied once on the final merged pool (see _scored_combinations_across_rotations's
    # docstring for why not per-size): if any type-unique combo exists at
    # all, only those compete for a spot; duplicate-dish-type combos are
    # the fallback only when the whole pool has nothing else.
    type_unique = [entry for entry in scored if entry.type_unique]
    return type_unique if type_unique else scored


def _scored_combinations_across_rotations(
    products: list[Product],
    request: RecommendationRequest,
    context: CandidateContext,
    customization_addon: Product | None,
) -> list[ScoredCombination]:
    # A single call already covers the common case (category_rotation_count
    # == 1). When more categories are checked than fit in the box, rotating
    # which subset gets folded (see build_candidate_context) and merging
    # every rotation's combos means the diversity selector downstream has
    # options covering each checked category to choose from, instead of
    # only ever seeing boxes missing the same one category.
    scored = list(_generate_scored_combinations(context, request, customization_addon))
    for rotation in range(1, context.category_rotation_count):
        rotated_context = build_candidate_context(products, request, category_rotation=rotation)
        scored.extend(_generate_scored_combinations(rotated_context, request, customization_addon))
    return scored


def _recommend_fixed_count(
    products: list[Product],
    request: RecommendationRequest,
    limit: int,
    messages: list[str] | None,
) -> list[Recommendation]:
    customization_addon = find_customization_addon(products)
    context = build_candidate_context(products, request)
    if context.k > len(context.pool):
        if messages is not None:
            messages.append(_too_few_candidates_message(len(context.pool), context.k, request))
        return []

    if context.k == 0:
        return [mandatory_only_recommendation(context.mandatory_items, request, customization_addon)][:limit]

    scored = _prefer_type_unique(_scored_combinations_across_rotations(products, request, context, customization_addon))
    if messages is not None:
        append_budget_hint(scored, request, messages)

    selected = _select_diverse(
        [(entry.score, entry.total, entry.products, entry.identities, entry.vendor_identities) for entry in scored],
        context.k,
        limit,
    )
    return [
        recommendation_from_score(
            ScoredCombination(
                score=score,
                total=total,
                products=combo,
                identities=Counter(),
                breakdown=pricing_engine.breakdown(combo, request, customization_addon),
            ),
            request,
        )
        for score, total, combo in selected
    ]


def _recommend_any_count(
    products: list[Product],
    request: RecommendationRequest,
    limit: int,
    messages: list[str] | None,
) -> list[Recommendation]:
    """No item-count preference: try every size up to MAX_ITEM_COUNT and
    keep whichever combinations fit the budget and score best, regardless
    of how many items they contain.
    """
    customization_addon = find_customization_addon(products)
    scored: list[ScoredCombination] = []
    mandatory_only: ScoredCombination | None = None
    considered_any_size = False

    for size in range(1, MAX_ITEM_COUNT + 1):
        sized_request = request.model_copy(update={"item_count": size})
        try:
            context = build_candidate_context(products, sized_request)
        except ValueError:
            continue
        if context.k > len(context.pool):
            continue
        considered_any_size = True
        if context.k == 0:
            if mandatory_only is None:
                mandatory_only = score_combination(
                    context.mandatory_items, [], 0, Counter(), sized_request, customization_addon
                )
            continue
        scored.extend(_scored_combinations_across_rotations(products, sized_request, context, customization_addon))

    if not considered_any_size:
        if messages is not None:
            messages.append(_too_few_candidates_message(0, 1, request))
        return []

    if not scored:
        if mandatory_only is not None and messages is not None:
            messages.append("Only the mandatory product(s) fit within the requested constraints.")
        return [recommendation_from_score(mandatory_only, request)][:limit] if mandatory_only else []

    # Applied once here, after merging every box size's combos together -
    # a size where no clean (type-unique) combo existed must not leak a
    # duplicate-dish-type box into the merge just because other sizes had
    # plenty of clean options.
    scored = _prefer_type_unique(scored)
    scored.sort(key=lambda entry: entry.score, reverse=True)
    selected = _select_diverse(
        [(entry.score, entry.total, entry.products, entry.identities, entry.vendor_identities) for entry in scored],
        MAX_ITEM_COUNT,
        limit,
    )
    return [
        recommendation_from_score(
            ScoredCombination(
                score=score,
                total=total,
                products=combo,
                identities=Counter(),
                breakdown=pricing_engine.breakdown(combo, request, customization_addon),
            ),
            request,
        )
        for score, total, combo in selected
    ]


def recommend(
    products: list[Product],
    request: RecommendationRequest,
    limit: int = 5,
    messages: list[str] | None = None,
) -> list[Recommendation]:
    if request.item_count is None:
        return _recommend_any_count(products, request, limit, messages)
    return _recommend_fixed_count(products, request, limit, messages)
