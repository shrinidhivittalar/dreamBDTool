from collections import Counter

try:
    from .models import Product
    from .recommender_config import MAX_PRODUCT_REPEAT, MAX_VENDOR_REPEAT, OVERLAP_LEVELS, QUALITY_FLOOR_LEVELS
except ImportError:
    from models import Product
    from recommender_config import MAX_PRODUCT_REPEAT, MAX_VENDOR_REPEAT, OVERLAP_LEVELS, QUALITY_FLOOR_LEVELS


def _pick_within_threshold(
    candidates: list[tuple[float, float, list[Product], Counter, Counter]],
    k: int,
    limit: int,
    threshold: float | None = None,
    max_repeat: int | None = None,
    max_vendor_repeat: int | None = None,
) -> tuple[list[tuple[float, float, list[Product]]], list[Counter]]:
    """Greedily take candidates (already score-sorted) up to `limit`,
    skipping any whose overlap with an already-picked combo exceeds
    `threshold`, and (when `max_repeat`/`max_vendor_repeat` is set) skipping
    any that would push a single product's, or a single vendor's,
    appearance count across the picked set past that cap. `None` for any of
    the three means that constraint is off - all three can be relaxed by
    the caller to guarantee `limit` results.
    """
    picked: list[tuple[float, float, list[Product]]] = []
    picked_ids: list[Counter] = []
    product_frequency: Counter = Counter()
    vendor_frequency: Counter = Counter()
    for score, total, combo, ids, vendor_ids in candidates:
        if ids in picked_ids:
            continue
        if threshold is not None and k and any(sum((ids & other).values()) / k > threshold for other in picked_ids):
            continue
        if max_repeat is not None and any(product_frequency[key] + count > max_repeat for key, count in ids.items()):
            continue
        if max_vendor_repeat is not None and any(vendor_frequency[vendor] + count > max_vendor_repeat for vendor, count in vendor_ids.items()):
            continue
        picked.append((score, total, combo))
        picked_ids.append(ids)
        product_frequency.update(ids)
        vendor_frequency.update(vendor_ids)
        if len(picked) == limit:
            break
    return picked, picked_ids


def _select_diverse(scored: list[tuple[float, float, list[Product], Counter, Counter]], k: int, limit: int) -> list[tuple[float, float, list[Product]]]:
    """Pick up to `limit` results preferring low overlap with each other,
    without sacrificing quality *or* diversity wholesale to get there.

    Two guardrails, tried together in a nested ladder, strictest first:
    1. Quality floor (QUALITY_FLOOR_LEVELS) - only candidates within a
       given fraction of the best score are eligible at all. Otherwise,
       hunting for a distinct option could drag in something dramatically
       worse just because it doesn't overlap with the good ones already
       picked.
    2. Graduated overlap + a per-product/per-vendor repeat cap
       (MAX_PRODUCT_REPEAT/MAX_VENDOR_REPEAT) - within the eligible set,
       try the strictest overlap allowance first (OVERLAP_LEVELS) while
       capping how many of the `limit` options any single product or
       vendor can appear in, so options aren't just non-identical but
       actually spread across different products/categories/vendors.

    The repeat-cap ladder is tried *in full* at each quality floor before
    that floor is loosened - a strong per-item scoring bonus (e.g.
    IN_HOUSE_WEIGHT) can mean every genuine alternative to the single
    best-scoring item in a category scores just outside a fixed 0.85
    floor, so without this nesting the selector would exhaust the repeat
    cap within that narrow floor and give up on diversity entirely (the
    exact "same top item in every option" symptom) instead of ever
    considering those alternatives. Only after every floor level has been
    tried at every repeat cap do the caps get dropped, and only past that
    does the quality floor get ignored entirely - both are last resorts to
    guarantee `limit` results whenever that many valid combinations exist
    at all. `scored` is already sorted descending; re-sorting the final
    picks restores that order since callers (and the UI) expect index 0 to
    be the best.
    """
    if not scored:
        return []
    best_score = scored[0][0]

    picked: list[tuple[float, float, list[Product]]] = []
    picked_ids: list[Counter] = []
    eligible: list[tuple[float, float, list[Product], Counter, Counter]] = []
    for floor_ratio in QUALITY_FLOOR_LEVELS:
        quality_floor = best_score * floor_ratio if best_score > 0 else best_score
        eligible = [entry for entry in scored if entry[0] >= quality_floor]
        # Relax the repeat cap one step at a time (2, 3, 4, ... up to
        # `limit`) before ever dropping it altogether. Jumping straight
        # from "cap=2" to "no cap" the moment cap=2 can't fill every slot
        # throws away real variety that a slightly looser cap could still
        # provide - e.g. a set of 5 boxes that share a strong 4-item "core"
        # only twice each (cap=3) is far more diverse than 5 boxes with an
        # uncapped, unlimited core.
        for repeat_cap in range(MAX_PRODUCT_REPEAT, limit + 1):
            # Vendor cap escalates in lockstep with the product cap, but
            # never below MAX_VENDOR_REPEAT - a vendor that's the sole
            # source for a required category (e.g. HealthyChef for Healthy
            # Savoury) still gets picked every time via this same
            # relaxation, it's just never squeezed tighter than a real
            # product repeat needs to be.
            vendor_cap = max(MAX_VENDOR_REPEAT, repeat_cap)
            for threshold in OVERLAP_LEVELS:
                picked, picked_ids = _pick_within_threshold(eligible, k, limit, threshold, repeat_cap, vendor_cap)
                if len(picked) == limit:
                    break
            if len(picked) == limit:
                break
            picked, picked_ids = _pick_within_threshold(eligible, k, limit, None, repeat_cap, vendor_cap)
            if len(picked) == limit:
                break
        if len(picked) == limit:
            break
    if len(picked) < limit:
        # Drop the repeat caps too, within the loosest quality floor tried.
        picked, picked_ids = _pick_within_threshold(eligible, k, limit)
    if len(picked) < limit:
        # Last resort: guarantee `limit` results even past every quality floor.
        picked, picked_ids = _pick_within_threshold(scored, k, limit)

    picked.sort(key=lambda entry: entry[0], reverse=True)
    return picked


