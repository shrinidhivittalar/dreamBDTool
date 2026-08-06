import numpy as np

try:
    from .models import Product
    from .pricing import pricing_engine
    from .recommender_config import CELL_BUDGET
    from .recommender_rules import _bonus_value, _category_bucket_match, _unique_category_groups
except ImportError:
    from models import Product
    from pricing import pricing_engine
    from recommender_config import CELL_BUDGET
    from recommender_rules import _bonus_value, _category_bucket_match, _unique_category_groups


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
    q_g slots of category group g so far. Every reachable t is kept -
    there is no "t <= budget" pruning - so combinations above the budget
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

    Each item offers a "free" transition (identical to the no-quota code -
    it never touches the quota axes, so it works unchanged whether or not
    quota axes exist) plus one "advance group g" transition per category
    it matches, which additionally shifts that group's progress axis by
    one. A single use of an item fills at most one quota slot.
    """
    n = len(pool)
    c = len(group_keys)
    prices = [pricing_engine.dad_selling_price(product) for product in pool]
    bonuses = [_bonus_value(product, preferred) for product in pool]
    eligible = [[_category_bucket_match(product, key) for key in group_keys] for product in pool]

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


# Category-unique search is defined before the diversity selector.
def _search_unique_pool(
    pool: list[Product],
    k: int,
    preferred: list[str],
    group_keys: tuple[str, ...],
    quota_counts: tuple[int, ...],
    unique_category_keys: tuple[str, ...],
    cap: int = 1,
) -> list[tuple[float, list[int]]]:
    """Find every reachable, product-unique box satisfying the category
    quotas, where no broad category group (`unique_category_keys` - e.g.
    sweet/savoury/healthy) supplies more than `cap` of the box's items.

    `cap=1` (the default, and the only value this used to support) is a
    hard "one item per broad category" rule - which by definition can never
    fill a box bigger than `len(unique_category_keys)` items. The caller
    raises `cap` for larger boxes (see recommender.py's
    `_max_category_repeat_cap`) so a 6-item box against 3 broad groups asks
    for "at most 2 per group" instead of silently giving up on spread
    entirely and letting one category (usually whichever scores best,
    e.g. all cupcakes) fill every remaining slot.

    The state stores its chosen items directly. That makes this separate
    constraint layer easy to change: edit UNIQUE_CATEGORY_GROUPS above,
    rather than the recommendation ranking or API contract.
    """
    positions = {key: position for position, key in enumerate(unique_category_keys)}
    product_groups = [
        tuple(sorted(positions[group] for group in _unique_category_groups(product)))
        for product in pool
    ]
    buckets = [pricing_engine.price_bucket(product) for product in pool]
    final_quota = tuple(quota_counts)
    empty_occupied = (0,) * len(unique_category_keys)
    # (item count, price bucket, quota progress, per-broad-group counts so far)
    states: dict[tuple[int, int, tuple[int, ...], tuple[int, ...]], tuple[float, tuple[int, ...]]] = {
        (0, 0, (0,) * len(group_keys), empty_occupied): (0.0, ())
    }

    for index, product in enumerate(pool):
        next_states = states.copy()  # Snapshot keeps this a 0/1 search.
        item_groups = product_groups[index]
        product_bonus = _bonus_value(product, preferred)
        matches = [group for group, key in enumerate(group_keys) if _category_bucket_match(product, key)]
        for (count, total, progress, occupied), (bonus, items) in states.items():
            if count == k or any(occupied[g] >= cap for g in item_groups):
                continue
            next_occupied = tuple(c + 1 if g in item_groups else c for g, c in enumerate(occupied))
            transitions = [progress]
            for group in matches:
                if progress[group] < quota_counts[group]:
                    advanced = list(progress)
                    advanced[group] += 1
                    transitions.append(tuple(advanced))
            for next_progress in transitions:
                state = (count + 1, total + buckets[index], next_progress, next_occupied)
                candidate = (bonus + product_bonus, items + (index,))
                current = next_states.get(state)
                if current is None or candidate[0] > current[0]:
                    next_states[state] = candidate
        states = next_states

    return [
        (bonus, list(items))
        for (count, _total, progress, _occupied), (bonus, items) in states.items()
        if count == k and progress == final_quota
    ]

def generate_combinations(
    pool: list[Product],
    k: int,
    preferred: list[str],
    group_keys: tuple[str, ...],
    quota_counts: tuple[int, ...],
    unique_category_keys: tuple[str, ...],
    allow_repeats: bool = False,
    enforce_unique_categories: bool = True,
    category_repeat_cap: int = 1,
) -> list[tuple[float, list[int]]]:
    """Generate candidate item indexes for a recommendation request.

    This is the search strategy seam. Ranking, budget scoring, and API
    shaping should not need to know whether candidates came from the
    product/category-unique search, the older DP search, or a future rule-
    specific generator.
    """
    if enforce_unique_categories and not allow_repeats:
        return _search_unique_pool(pool, k, preferred, group_keys, quota_counts, unique_category_keys, category_repeat_cap)
    return _search_pool(pool, k, preferred, allow_repeats, group_keys, quota_counts)

