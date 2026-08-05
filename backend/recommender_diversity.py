from collections import Counter

try:
    from .models import Product
    from .recommender_config import MAX_PRODUCT_REPEAT, OVERLAP_LEVELS, QUALITY_FLOOR_RATIO
except ImportError:
    from models import Product
    from recommender_config import MAX_PRODUCT_REPEAT, OVERLAP_LEVELS, QUALITY_FLOOR_RATIO


def _pick_within_threshold(
    candidates: list[tuple[float, float, list[Product], Counter]],
    k: int,
    limit: int,
    threshold: float | None = None,
    max_repeat: int | None = None,
) -> tuple[list[tuple[float, float, list[Product]]], list[Counter]]:
    """Greedily take candidates (already score-sorted) up to `limit`,
    skipping any whose overlap with an already-picked combo exceeds
    `threshold`, and (when `max_repeat` is set) skipping any that would push
    a single product's appearance count across the picked set past
    `max_repeat`. `threshold=None` means no overlap-ratio constraint;
    `max_repeat=None` means no per-product frequency cap - either or both
    can be relaxed by the caller to guarantee `limit` results.
    """
    picked: list[tuple[float, float, list[Product]]] = []
    picked_ids: list[Counter] = []
    product_frequency: Counter = Counter()
    for score, total, combo, ids in candidates:
        if ids in picked_ids:
            continue
        if threshold is not None and k and any(sum((ids & other).values()) / k > threshold for other in picked_ids):
            continue
        if max_repeat is not None and any(product_frequency[key] + count > max_repeat for key, count in ids.items()):
            continue
        picked.append((score, total, combo))
        picked_ids.append(ids)
        product_frequency.update(ids)
        if len(picked) == limit:
            break
    return picked, picked_ids


def _select_diverse(scored: list[tuple[float, float, list[Product], Counter]], k: int, limit: int) -> list[tuple[float, float, list[Product]]]:
    """Pick up to `limit` results preferring low overlap with each other,
    without sacrificing quality *or* diversity wholesale to get there.

    Two guardrails, tried in order:
    1. Quality floor - only candidates within QUALITY_FLOOR_RATIO of the
       best score are eligible at all. Otherwise, hunting for a distinct
       option could drag in something dramatically worse just because it
       doesn't overlap with the good ones already picked.
    2. Graduated overlap + a per-product repeat cap (MAX_PRODUCT_REPEAT) -
       within that eligible set, try the strictest overlap allowance first
       (OVERLAP_LEVELS) while capping how many of the `limit` options any
       single product can appear in, so five options aren't just
       non-identical but actually spread across different products/
       categories. Both constraints only loosen (repeat cap first, then
       overlap ratio) if the stricter combination can't fill every slot,
       so real variety stays as high as the catalog allows rather than
       jumping straight to "ignore diversity entirely" the moment the
       strictest tier falls short.

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
    # Relax the repeat cap one step at a time (2, 3, 4, ... up to `limit`)
    # before ever dropping it altogether. Jumping straight from "cap=2" to
    # "no cap" the moment cap=2 can't fill every slot throws away real
    # variety that a slightly looser cap could still provide - e.g. a set
    # of 5 boxes that share a strong 4-item "core" only twice each (cap=3)
    # is far more diverse than 5 boxes with an uncapped, unlimited core.
    for repeat_cap in range(MAX_PRODUCT_REPEAT, limit + 1):
        for threshold in OVERLAP_LEVELS:
            picked, picked_ids = _pick_within_threshold(eligible, k, limit, threshold, repeat_cap)
            if len(picked) == limit:
                break
        if len(picked) == limit:
            break
        picked, picked_ids = _pick_within_threshold(eligible, k, limit, None, repeat_cap)
        if len(picked) == limit:
            break
    if len(picked) < limit:
        # Drop the repeat cap too, still within the quality floor.
        picked, picked_ids = _pick_within_threshold(eligible, k, limit)
    if len(picked) < limit:
        # Last resort: guarantee `limit` results even past the quality floor.
        picked, picked_ids = _pick_within_threshold(scored, k, limit)

    picked.sort(key=lambda entry: entry[0], reverse=True)
    return picked


