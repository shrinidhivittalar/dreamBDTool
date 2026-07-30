from collections import Counter

import numpy as np

try:
    from .models import Product, Recommendation, RecommendationRequest
except ImportError:
    from models import Product, Recommendation, RecommendationRequest


# Scoring weights, GST rate, and DP resolution cap — assumptions pending
# BD/finance sign-off, see BUSINESS_RULE_ASSUMPTIONS.md.
IN_HOUSE_WEIGHT = 3
HEALTHY_WEIGHT = 2
PREFERRED_WEIGHT = 5
# DaD Selling Price is GST-exclusive; this is added on top before comparing
# a combination's total against the client's budget range.
GST_RATE = 0.05
# Caps dp_history's (items, layers, price-buckets, quota-progress) cell
# count; float32 so this stays ~200MB at the cap. Exceeding it coarsens the
# price bucket width, not correctness — see _search_pool.
CELL_BUDGET = 50_000_000
# Tried strictest-first: only fall back to a looser overlap allowance once
# the stricter one can't fill every slot, so repeats across options stay as
# rare as the catalog allows rather than jumping straight to "anything goes".
OVERLAP_LEVELS = (0.25, 0.4, 0.55, 0.7)
# A candidate only competes on diversity if its score is within this
# fraction of the best score — keeps a hunt for variety from dragging in a
# dramatically worse fit just because it doesn't overlap with the rest.
QUALITY_FLOOR_RATIO = 0.85
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


def _closeness(total: float, budget_min: float, budget_max: float) -> float:
    """Reward staying within [budget_min, budget_max]; penalize drifting
    outside on either side.

    No branch discards a total — falling outside the range only lowers the
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


def _pick_within_threshold(
    candidates: list[tuple[float, float, list[Product], Counter]],
    k: int,
    limit: int,
    threshold: float | None = None,
) -> tuple[list[tuple[float, float, list[Product]]], list[Counter]]:
    """Greedily take candidates (already score-sorted) up to `limit`,
    skipping any whose overlap with an already-picked combo exceeds
    `threshold`. `threshold=None` means no overlap constraint at all —
    just take the next-best distinct combos.
    """
    picked: list[tuple[float, float, list[Product]]] = []
    picked_ids: list[Counter] = []
    for score, total, combo, ids in candidates:
        if ids in picked_ids:
            continue
        if threshold is None or not k or all(sum((ids & other).values()) / k <= threshold for other in picked_ids):
            picked.append((score, total, combo))
            picked_ids.append(ids)
            if len(picked) == limit:
                break
    return picked, picked_ids


def _select_diverse(scored: list[tuple[float, float, list[Product], Counter]], k: int, limit: int) -> list[tuple[float, float, list[Product]]]:
    """Pick up to `limit` results preferring low overlap with each other,
    without sacrificing quality *or* diversity wholesale to get there.

    Two guardrails, tried in order:
    1. Quality floor — only candidates within QUALITY_FLOOR_RATIO of the
       best score are eligible at all. Otherwise, hunting for a distinct
       option could drag in something dramatically worse just because it
       doesn't overlap with the good ones already picked.
    2. Graduated overlap — within that eligible set, try the strictest
       overlap allowance first (OVERLAP_LEVELS) and only loosen it if that
       can't fill every slot, so repeats across options stay as rare as
       the catalog allows rather than jumping straight to "ignore overlap
       entirely" the moment the strict threshold falls short.

    Only if the eligible set itself is smaller than `limit` do we reach
    past the quality floor into the full candidate list, to guarantee up
    to `limit` results whenever that many valid combinations exist at all.
    `scored` is already sorted descending; re-sorting the final picks
    restores that order since callers (and the UI) expect index 0 to be
    the best.
    """
    if not scored:
        return []
    best_score = scored[0][0]
    quality_floor = best_score * QUALITY_FLOOR_RATIO if best_score > 0 else best_score
    eligible = [entry for entry in scored if entry[0] >= quality_floor]

    picked: list[tuple[float, float, list[Product]]] = []
    picked_ids: list[Counter] = []
    for threshold in OVERLAP_LEVELS:
        picked, picked_ids = _pick_within_threshold(eligible, k, limit, threshold)
        if len(picked) == limit:
            break
    if len(picked) < limit:
        picked, picked_ids = _pick_within_threshold(eligible, k, limit)
    if len(picked) < limit:
        picked, picked_ids = _pick_within_threshold(scored, k, limit)

    picked.sort(key=lambda entry: entry[0], reverse=True)
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
    if request.sweet_preference == "sweet_only":
        candidates = [product for product in candidates if _category_match(product, "sweet")]
    elif request.sweet_preference == "no_sweet":
        candidates = [product for product in candidates if not _category_match(product, "sweet")]

    mandatory_indices = _resolve_mandatory(candidates, request.mandatory_products)
    mandatory_items = [candidates[i] for i in sorted(mandatory_indices)]
    pool = [product for i, product in enumerate(candidates) if i not in mandatory_indices]

    k = request.item_count - len(mandatory_items)
    if k < 0:
        raise ValueError("Mandatory products exceed the requested item count.")
    if k > len(pool) and not request.allow_repeats:
        if messages is not None:
            active_filters = []
            if request.excluded_products:
                active_filters.append(f"excluded products ({', '.join(request.excluded_products)})")
            if request.preferred_categories:
                active_filters.append(f"categories ({', '.join(request.preferred_categories)})")
            if request.preferred_vendors:
                active_filters.append(f"vendors ({', '.join(request.preferred_vendors)})")
            if request.sweet_preference != "any":
                active_filters.append(f"sweet preference ({request.sweet_preference.replace('_', ' ')})")
            if active_filters:
                messages.append(
                    f"Only {len(pool)} catalog item(s) match {', '.join(active_filters)} — not enough to fill "
                    f"{k} more slot(s) for a {request.item_count}-item box. Check for typos, or loosen these filters."
                )
            else:
                messages.append(
                    f"Only {len(pool)} catalog item(s) are available — not enough to fill {k} more slot(s) "
                    f"without repeats. Try enabling repeated products or lowering the item count."
                )
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

    mandatory_total = sum(product.selling_price for product in mandatory_items)
    fixed_bonus = sum(_bonus_value(product, request.preferred_products) for product in mandatory_items)
    # If the catalog price already includes GST, nothing is added on top;
    # otherwise GST_RATE is added before comparing against the budget range.
    gst_multiplier = 1.0 if request.price_includes_gst else 1 + GST_RATE

    if k == 0:
        total = mandatory_total * gst_multiplier
        score = _closeness(total, request.budget_min, request.budget_max) + fixed_bonus
        return [Recommendation(
            products=mandatory_items,
            total_price=round(total, 2),
            remaining_budget=round(request.budget_max - total, 2),
            score=round(score, 3),
        )][:limit]

    scored: list[tuple[float, float, list[Product], Counter]] = []
    for bonus_sum, item_indices in _search_pool(pool, k, request.preferred_products, request.allow_repeats, group_keys, quota_counts):
        pool_items = [pool[i] for i in item_indices]
        raw_total = mandatory_total + sum(product.selling_price for product in pool_items)
        total = raw_total * gst_multiplier
        score = _closeness(total, request.budget_min, request.budget_max) + fixed_bonus + bonus_sum
        scored.append((score, total, mandatory_items + pool_items, Counter(item_indices)))
    scored.sort(key=lambda entry: entry[0], reverse=True)

    if messages is not None and scored:
        max_achievable = max(total for _, total, _, _ in scored)
        min_achievable = min(total for _, total, _, _ in scored)
        gst_note = "" if request.price_includes_gst else " (incl. GST)"
        if max_achievable < request.budget_min * 0.95:
            messages.append(
                f"The priciest valid {request.item_count}-item combination for this brief comes to "
                f"₹{round(max_achievable)}{gst_note} — try raising the item count or enabling repeated "
                f"products to get closer to your ₹{round(request.budget_min)}–₹{round(request.budget_max)} range."
            )
        elif min_achievable > request.budget_max * 1.05:
            messages.append(
                f"The cheapest valid {request.item_count}-item combination for this brief comes to "
                f"₹{round(min_achievable)}{gst_note} — try lowering the item count or raising your "
                f"₹{round(request.budget_min)}–₹{round(request.budget_max)} range to get within budget."
            )

    return [Recommendation(
        products=combo,
        total_price=round(total, 2),
        remaining_budget=round(request.budget_max - total, 2),
        score=round(score, 3),
    ) for score, total, combo in _select_diverse(scored, k, limit)]
