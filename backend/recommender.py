from collections import Counter

try:
    from .models import Product, Recommendation, RecommendationRequest
    from .pricing import pricing_engine
    from .recommender_config import MAX_ITEM_COUNT
    from .recommender_constraints import active_filter_descriptions, build_candidate_context, find_customization_addon
    from .recommender_diversity import _select_diverse
    from .recommender_ranking import (
        ScoredCombination,
        append_budget_hint,
        mandatory_only_recommendation,
        recommendation_from_score,
        score_combination,
    )
    from .recommender_rules import _base_product_key, _bonus_value, _category_match, _closeness, _unique_category_groups
    from .recommender_search import _search_pool, _search_unique_pool, generate_combinations
except ImportError:
    from models import Product, Recommendation, RecommendationRequest
    from pricing import pricing_engine
    from recommender_config import MAX_ITEM_COUNT
    from recommender_constraints import active_filter_descriptions, build_candidate_context, find_customization_addon
    from recommender_diversity import _select_diverse
    from recommender_ranking import (
        ScoredCombination,
        append_budget_hint,
        mandatory_only_recommendation,
        recommendation_from_score,
        score_combination,
    )
    from recommender_rules import _base_product_key, _bonus_value, _category_match, _closeness, _unique_category_groups
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
    item_bucket = pricing_engine.price_bucket(item)
    item_required = tuple(_category_match(item, group) for group in group_keys)
    siblings = []
    for candidate in pool:
        if _base_product_key(candidate) in excluded_keys:
            continue
        if _unique_category_groups(candidate) != item_groups:
            continue
        if pricing_engine.price_bucket(candidate) != item_bucket:
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
    scored: list[ScoredCombination] = []
    generated = generate_combinations(
        context.pool,
        context.k,
        request.preferred_products,
        context.group_keys,
        context.quota_counts,
        context.unique_category_keys,
        allow_repeats=False,
        enforce_unique_categories=True,
    )
    if not generated and context.k > len(context.unique_category_keys):
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
    seen_key_sets: set[frozenset[str]] = set()

    def add_combo(pool_items: list[Product], bonus_sum: float) -> None:
        pool_keys = [_base_product_key(product) for product in pool_items]
        # Skip boxes that would carry two size/variant SKUs of the same
        # flavor (e.g. a "mini" and a full-size version of one brownie).
        if len(set(pool_keys)) != len(pool_keys) or mandatory_keys & set(pool_keys):
            return
        key_set = frozenset(pool_keys) | mandatory_keys
        if key_set in seen_key_sets:
            return
        seen_key_sets.add(key_set)
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
            )
        )

    combos = [([context.pool[i] for i in item_indices], bonus_sum) for bonus_sum, item_indices in generated]
    for pool_items, bonus_sum in combos:
        add_combo(pool_items, bonus_sum)

    # Sibling substitution: for each generated combo, try swapping each item
    # for a same-price-bucket, same-category alternative the DP's tie-
    # breaking discarded (see _sibling_candidates). Bounded by what the DP
    # already generated, so this stays proportional to search output, not
    # the whole catalog.
    for pool_items, bonus_sum in combos:
        existing_keys = {_base_product_key(product) for product in pool_items} | mandatory_keys
        for position, item in enumerate(pool_items):
            siblings = _sibling_candidates(context.pool, item, existing_keys, context.group_keys)
            for sibling in siblings:
                variant = list(pool_items)
                variant[position] = sibling
                variant_bonus = bonus_sum - _bonus_value(item, request.preferred_products) + _bonus_value(sibling, request.preferred_products)
                add_combo(variant, variant_bonus)

    scored.sort(key=lambda entry: entry.score, reverse=True)
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

    scored = _generate_scored_combinations(context, request, customization_addon)
    if messages is not None:
        append_budget_hint(scored, request, messages)

    selected = _select_diverse(
        [(entry.score, entry.total, entry.products, entry.identities) for entry in scored],
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
        scored.extend(_generate_scored_combinations(context, sized_request, customization_addon))

    if not considered_any_size:
        if messages is not None:
            messages.append(_too_few_candidates_message(0, 1, request))
        return []

    if not scored:
        if mandatory_only is not None and messages is not None:
            messages.append("Only the mandatory product(s) fit within the requested constraints.")
        return [recommendation_from_score(mandatory_only, request)][:limit] if mandatory_only else []

    scored.sort(key=lambda entry: entry.score, reverse=True)
    selected = _select_diverse(
        [(entry.score, entry.total, entry.products, entry.identities) for entry in scored],
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
