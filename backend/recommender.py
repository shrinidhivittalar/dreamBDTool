from collections import Counter

import numpy as np

try:
    from .models import Product, Recommendation, RecommendationRequest
except ImportError:
    from models import Product, Recommendation, RecommendationRequest


# Scoring weights and DP resolution cap — assumptions pending BD sign-off,
# see BUSINESS_RULE_ASSUMPTIONS.md.
IN_HOUSE_WEIGHT = 3
HEALTHY_WEIGHT = 2
PREFERRED_WEIGHT = 5
# Caps dp_history's (items, layers, price-buckets, quota-progress) cell
# count; float32 so this stays ~200MB at the cap. Exceeding it coarsens the
# price bucket width, not correctness — see _search_pool.
CELL_BUDGET = 50_000_000
OVERLAP_THRESHOLD = 0.5
# Number of *distinct* requested categories, not total slots — bounds the
# quota-progress dimension's multiplier the same way item_count<=20 bounds
# the price/count dimensions.
MAX_CATEGORY_GROUPS = 6


def _matches(value: str, requested: str) -> bool:
    return requested.strip().lower() in value.strip().lower()


def _category_match(product: Product, category: str) -> bool:
    return _matches(product.category, category) or any(_matches(tag, category) for tag in product.tags)


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


def _closeness(total: float, budget: float, target: float) -> float:
    """Reward staying under the buffered target; penalize drifting past it.

    No branch discards a total — going over the buffer, or even the raw
    budget, only lowers the score. There is deliberately no hard cutoff.
    """
    if total <= target:
        return 100 * total / target
    if total <= budget:
        return 100 - 15 * (total - target) / (budget - target)
    return 85 - 40 * (total - budget) / budget


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


def _search_pool(
    pool: list[Product],
    k: int,
    preferred: list[str],
    allow_repeats: bool = False,
    group_keys: tuple[str, ...] = (),
    quota_counts: tuple[int, ...] = (),
) -> list[tuple[float, list[int]]]:
    """Exhaustive knapsack DP: best bonus score for every reachable k-item
    total price that also satisfies every category quota, without
    enumerating combinations.

    dp_history[i][j][t][q1..qC] = max total bonus achievable using exactly
    j items from pool[:i] whose (bucketed) prices sum to t, having filled
    q_g slots of category group g so far. Every reachable t is kept —
    there is no "t <= budget" pruning — so combinations above the budget
    are still found and scored, just via the closeness curve, not
    excluded here. With no quota groups this degenerates to a plain 3D
    array, unchanged from the pre-quota implementation.

    A full per-item history is kept (not just the final table) because a
    single mutable table can't be reconstructed unambiguously: a cell's
    recorded "best predecessor" can be superseded later by a different
    item's turn without downstream cells knowing, which silently lets one
    physical item get picked twice across two layers of the same combo.
    Walking the history backward instead guarantees a consistent path.

    allow_repeats switches the per-item transition from 0/1 (each item
    usable once, sourced from the pre-item snapshot dp_history[i]) to
    unbounded (an item may repeat, sourced from its own layer's smaller-j
    row dp_history[i+1, j-1] so it can chain onto itself within one turn).
    Reconstruction mirrors this: item i-1 is "used again" (stay on i) as
    long as dp_history[i] differs from the pre-item baseline dp_history[i-1]
    at the current (j, t, q); once they match, that item is exhausted and i
    decrements. For 0/1, every use immediately decrements i.

    Each item offers a "free" transition (identical to the no-quota code —
    it never touches the quota axes, so it works unchanged whether or not
    quota axes exist) plus one "advance group g" transition per category
    it matches, which additionally shifts that group's progress axis by
    one. A single use of an item fills at most one quota slot.
    """
    n = len(pool)
    c = len(group_keys)
    prices = [product.selling_price for product in pool]
    bonuses = [_bonus_value(product, preferred) for product in pool]
    eligible = [[_category_match(product, key) for key in group_keys] for product in pool]

    bucket_width = 1
    while True:
        buckets = [max(1, round(price / bucket_width)) for price in prices]
        if allow_repeats:
            max_sum = k * max(buckets) if buckets else 0
        else:
            max_sum = sum(sorted(buckets, reverse=True)[:k])
        quota_cells = 1
        for count in quota_counts:
            quota_cells *= count + 1
        if (n + 1) * (k + 1) * (max_sum + 1) * quota_cells <= CELL_BUDGET or bucket_width >= 1000:
            break
        bucket_width *= 2

    quota_shape = tuple(count + 1 for count in quota_counts)
    dp_history = np.full((n + 1, k + 1, max_sum + 1) + quota_shape, -np.inf, dtype=np.float32)
    dp_history[(0, 0, 0) + (0,) * c] = 0.0

    def quota_slices(group: int) -> tuple[tuple, tuple]:
        count = quota_counts[group]
        src = tuple(slice(0, count) if h == group else slice(None) for h in range(c))
        dst = tuple(slice(1, count + 1) if h == group else slice(None) for h in range(c))
        return src, dst

    group_quota_slices = [quota_slices(g) for g in range(c)]

    for i in range(n):
        dp_history[i + 1] = dp_history[i]
        bucket, value = buckets[i], bonuses[i]
        if bucket > max_sum:
            continue
        width = max_sum + 1 - bucket

        def apply(src_layer_j, dst_j, src_quota: tuple = (), dst_quota: tuple = ()) -> None:
            src_price = slice(0, width)
            dst_price = slice(bucket, max_sum + 1)
            candidate = dp_history[(src_layer_j[0], src_layer_j[1], src_price) + src_quota] + value
            dest = dp_history[(i + 1, dst_j, dst_price) + dst_quota]
            mask = candidate > dest
            dest[mask] = candidate[mask]

        if allow_repeats:
            for j in range(1, k + 1):
                apply((i + 1, j - 1), j)
                for g in range(c):
                    if eligible[i][g]:
                        src_q, dst_q = group_quota_slices[g]
                        apply((i + 1, j - 1), j, src_q, dst_q)
        else:
            apply((i, slice(0, k)), slice(1, k + 1))
            for g in range(c):
                if eligible[i][g]:
                    src_q, dst_q = group_quota_slices[g]
                    apply((i, slice(0, k)), slice(1, k + 1), src_q, dst_q)

    def reconstruct(total: int) -> list[int]:
        items: list[int] = []
        i, j, remaining = n, k, total
        q = list(quota_counts)
        while i > 0 and j > 0:
            current = (i, j, remaining, *q)
            baseline = (i - 1, j, remaining, *q)
            if dp_history[current] == dp_history[baseline]:
                i -= 1
                continue
            item = i - 1
            bucket, value = buckets[item], bonuses[item]
            source_layer_i = i if allow_repeats else i - 1
            source_j, source_remaining = j - 1, remaining - bucket
            target = dp_history[current]

            free_value = dp_history[(source_layer_i, source_j, source_remaining, *q)] + value
            if free_value == target:
                items.append(item)
                remaining, j = source_remaining, j - 1
                if not allow_repeats:
                    i -= 1
                continue

            for g in range(c):
                if q[g] <= 0 or not eligible[item][g]:
                    continue
                source_q = q.copy()
                source_q[g] -= 1
                group_value = dp_history[(source_layer_i, source_j, source_remaining, *source_q)] + value
                if group_value == target:
                    items.append(item)
                    remaining, j, q = source_remaining, j - 1, source_q
                    if not allow_repeats:
                        i -= 1
                    break
            else:
                raise AssertionError("unreachable: DP cell has no matching predecessor transition")
        return items

    results: list[tuple[float, list[int]]] = []
    final_quota = tuple(quota_counts)
    for t in range(max_sum + 1):
        best = dp_history[(n, k, t) + final_quota]
        if best == -np.inf:
            continue
        results.append((float(best), reconstruct(t)))
    return results


def _select_diverse(scored: list[tuple[float, float, list[Product], Counter]], k: int, limit: int) -> list[tuple[float, float, list[Product]]]:
    picked: list[tuple[float, float, list[Product]]] = []
    picked_ids: list[Counter] = []
    for score, total, combo, ids in scored:
        if k and all(sum((ids & other).values()) / k <= OVERLAP_THRESHOLD for other in picked_ids):
            picked.append((score, total, combo))
            picked_ids.append(ids)
            if len(picked) == limit:
                return picked
    for score, total, combo, ids in scored:
        if ids in picked_ids:
            continue
        picked.append((score, total, combo))
        picked_ids.append(ids)
        if len(picked) == limit:
            break
    return picked


def recommend(
    products: list[Product],
    request: RecommendationRequest,
    limit: int = 5,
    messages: list[str] | None = None,
) -> list[Recommendation]:
    candidates = [product for product in products if not any(_matches(product.name, excluded) for excluded in request.excluded_products)]
    if request.preferred_categories:
        candidates = [product for product in candidates if any(_category_match(product, category) for category in request.preferred_categories)]
    if request.preferred_vendors:
        candidates = [product for product in candidates if any(_matches(product.vendor, vendor) for vendor in request.preferred_vendors)]

    mandatory_indices = _resolve_mandatory(candidates, request.mandatory_products)
    mandatory_items = [candidates[i] for i in sorted(mandatory_indices)]
    pool = [product for i, product in enumerate(candidates) if i not in mandatory_indices]

    k = request.item_count - len(mandatory_items)
    if k < 0:
        raise ValueError("Mandatory products exceed the requested item count.")
    if k > len(pool) and not request.allow_repeats:
        return []

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

    target = request.budget * (1 - request.buffer_percentage / 100)
    mandatory_total = sum(product.selling_price for product in mandatory_items)
    fixed_bonus = sum(_bonus_value(product, request.preferred_products) for product in mandatory_items)

    if k == 0:
        total = mandatory_total
        score = _closeness(total, request.budget, target) + fixed_bonus
        return [Recommendation(
            products=mandatory_items,
            total_price=round(total, 2),
            remaining_budget=round(request.budget - total, 2),
            score=round(score, 3),
        )][:limit]

    scored: list[tuple[float, float, list[Product], Counter]] = []
    for bonus_sum, item_indices in _search_pool(pool, k, request.preferred_products, request.allow_repeats, group_keys, quota_counts):
        pool_items = [pool[i] for i in item_indices]
        total = mandatory_total + sum(product.selling_price for product in pool_items)
        score = _closeness(total, request.budget, target) + fixed_bonus + bonus_sum
        scored.append((score, total, mandatory_items + pool_items, Counter(item_indices)))
    scored.sort(key=lambda entry: entry[0], reverse=True)

    if messages is not None and scored:
        max_achievable = max(total for _, total, _, _ in scored)
        if max_achievable < target * 0.95:
            messages.append(
                f"The priciest valid {request.item_count}-item combination for this brief comes to "
                f"₹{round(max_achievable)} — try raising the item count or enabling repeated products "
                f"to get closer to ₹{round(request.budget)}."
            )

    return [Recommendation(
        products=combo,
        total_price=round(total, 2),
        remaining_budget=round(request.budget - total, 2),
        score=round(score, 3),
    ) for score, total, combo in _select_diverse(scored, k, limit)]
