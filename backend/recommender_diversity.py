from collections import Counter

try:
    from .models import Product
    from .recommender_config import OVERLAP_LEVELS, QUALITY_FLOOR_RATIO
except ImportError:
    from models import Product
    from recommender_config import OVERLAP_LEVELS, QUALITY_FLOOR_RATIO


def _pick_within_threshold(
    candidates: list[tuple[float, float, list[Product], Counter]],
    k: int,
    limit: int,
    threshold: float | None = None,
) -> tuple[list[tuple[float, float, list[Product]]], list[Counter]]:
    """Greedily take candidates (already score-sorted) up to `limit`,
    skipping any whose overlap with an already-picked combo exceeds
    `threshold`. `threshold=None` means no overlap constraint at all -
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
    1. Quality floor - only candidates within QUALITY_FLOOR_RATIO of the
       best score are eligible at all. Otherwise, hunting for a distinct
       option could drag in something dramatically worse just because it
       doesn't overlap with the good ones already picked.
    2. Graduated overlap - within that eligible set, try the strictest
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


