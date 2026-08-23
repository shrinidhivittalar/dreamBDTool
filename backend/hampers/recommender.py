"""Basic hamper recommendation engine (Phase 3).

Deliberately simple: bounded combination search per candidate container,
a conservative volume-ratio fit check (no bin-packing), and a scoring pass
that rewards high budget utilisation and composition variety. This is a
starting point, not a final optimizer - see PHASE1_HAMPERS.md Phase 5 for
what's intentionally deferred (real packing, smarter container selection,
etc).
"""

import itertools
from dataclasses import dataclass

try:
    from .models import (
        HamperCompositionInfo,
        HamperContainer,
        HamperFitStatus,
        HamperItem,
        HamperRecommendation,
        HamperRequest,
        HamperSearchResult,
    )
except ImportError:
    from models import (
        HamperCompositionInfo,
        HamperContainer,
        HamperFitStatus,
        HamperItem,
        HamperRecommendation,
        HamperRequest,
        HamperSearchResult,
    )

# Conservative usable-capacity factor applied to a container's raw volume -
# accounts for packaging bulk, irregular item shapes, and gaps between items
# that a pure volume-ratio check can't see. Not a substitute for real
# packing/arrangement logic (see module docstring).
USABLE_CAPACITY_FACTOR = 0.75

MIN_ITEMS_PER_HAMPER = 1
MAX_ITEMS_PER_HAMPER = 6

# Bounds how many combinations are evaluated per container so the search
# stays fast even on a large item catalog. Generous enough for today's
# catalog size (~50 items); revisit if the catalog grows substantially.
MAX_COMBOS_PER_CONTAINER = 20_000

# Two recommendations that share this fraction (or more) of their items are
# treated as near-duplicates, regardless of whether they use the same
# container - a BD user doesn't consider "A+B+C+D" vs "A+B+C+E" meaningfully
# different just because the box differs.
DIVERSITY_OVERLAP_THRESHOLD = 0.6

# A given container may not be reused more than this many times across one
# batch of recommendations, so 5 requested options can't silently collapse
# into "the same box, five times."
MAX_CONTAINER_REPEATS = 2

# A hamper where the container itself eats most of the budget, leaving only
# a token amount for actual product, is technically valid but not a good
# recommendation. Require the item content to be worth at least this
# fraction of the container's price.
MIN_CONTENT_TO_CONTAINER_RATIO = 0.15

# Below this budget utilisation, a combination is deprioritised as "leaving
# too much budget on the table" - it's only surfaced if nothing better is
# available (see recommend_hampers' fallback pass).
MIN_BUDGET_UTILISATION = 0.5

# A hamper that occupies less than this share of usable container capacity
# is scored down (not rejected - some premium hampers legitimately look
# sparse), so a technically-valid but near-empty-looking box doesn't rank
# as well as a well-filled one.
MIN_FILL_RATIO = 0.3

# If one single item accounts for this much of the total item spend, the
# hamper reads as "one expensive thing plus filler" rather than a balanced
# selection - scored down, not rejected.
MAX_SINGLE_ITEM_SHARE = 0.75

# A hamper with 3+ items that are all the same category reads as
# repetitive/samey even though every item is distinct - scored down.
MIN_ITEMS_FOR_CATEGORY_CONCENTRATION_PENALTY = 3

# Currency amounts are rounded to paise before any comparison so that
# repeated float addition (e.g. many 60.72 + 69.84 + ...) can't cause a
# combination to be spuriously accepted or rejected right at the budget
# boundary.
CURRENCY_DECIMALS = 2


def _round_currency(value: float) -> float:
    return round(value, CURRENCY_DECIMALS)


@dataclass
class _Candidate:
    container: HamperContainer
    items: list[HamperItem]
    total_price: float


def _normalized(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _matches_any(item: HamperItem, names: set[str]) -> bool:
    return _normalized(item.name) in names


def _item_dims(entity: HamperContainer | HamperItem) -> tuple[float, float, float] | None:
    if entity.length_in is None or entity.breadth_in is None or entity.height_in is None:
        return None
    if entity.length_in <= 0 or entity.breadth_in <= 0 or entity.height_in <= 0:
        return None
    return (entity.length_in, entity.breadth_in, entity.height_in)


def _item_fits_container_individually(item: HamperItem, container: HamperContainer) -> bool | None:
    """Checks the item's own footprint against the container's, trying every
    axis rotation (6 orientations). Returns None (unknown) rather than
    guessing when dimensions are missing/invalid - callers must treat that
    as "not verified", never as "fits"."""

    item_dims = _item_dims(item)
    container_dims = _item_dims(container)
    if item_dims is None or container_dims is None:
        return None

    for rotation in itertools.permutations(item_dims):
        if all(dim <= max_dim for dim, max_dim in zip(rotation, container_dims)):
            return True
    return False


def _fit_status(container: HamperContainer, items: list[HamperItem]) -> HamperFitStatus:
    unresolved_individual = False
    for item in items:
        individual_fit = _item_fits_container_individually(item, container)
        if individual_fit is False:
            return HamperFitStatus(
                fits=False,
                container_volume_in3=container.usable_volume_in3,
                notes=f"'{item.name}' does not fit inside the container in any orientation.",
                fully_verified=False,
            )
        if individual_fit is None:
            unresolved_individual = True

    container_volume = container.usable_volume_in3
    if container_volume is None:
        return HamperFitStatus(
            fits=True,
            notes="Container dimensions missing; fit not verified.",
            fully_verified=False,
        )

    # An item with a missing/invalid dimension is excluded from the volume
    # sum rather than treated as contributing zero - HamperItem.volume_in3
    # already returns None for it (see models.py), so the resulting ratio is
    # a floor on real usage, never an inflated or falsely-precise number.
    resolved_volumes = [item.volume_in3 for item in items if item.volume_in3 is not None]
    excluded_items = any(item.volume_in3 is None for item in items)

    usable_volume = container_volume * USABLE_CAPACITY_FACTOR
    used_volume = sum(resolved_volumes)
    fits = used_volume <= usable_volume
    # If every item's volume was excluded, a "0%" floor would read as a real
    # measurement rather than "we know nothing" - suppress the ratio instead.
    ratio = (used_volume / usable_volume) if usable_volume > 0 and resolved_volumes else None

    if not fits:
        notes = "Estimated item volume exceeds usable container capacity."
    elif excluded_items and not resolved_volumes:
        notes = "No items in this hamper have usable dimensions; fit not verified."
    elif excluded_items:
        notes = "Fit not fully verified - one or more items have missing/invalid dimensions; the fill estimate below excludes them and is a floor, not a precise figure."
    elif unresolved_individual:
        notes = "Combined volume fits, but not every item's dimensions could be verified individually."
    else:
        notes = ""

    return HamperFitStatus(
        fits=fits,
        used_volume_in3=used_volume,
        container_volume_in3=container_volume,
        utilisation_ratio=ratio,
        notes=notes,
        fully_verified=not (unresolved_individual or excluded_items),
        fill_estimate_partial=excluded_items,
    )


def _composition(
    items: list[HamperItem],
    applicable_categories: set[str],
    is_fallback: bool,
) -> HamperCompositionInfo:
    counts: dict[str, int] = {}
    for item in items:
        key = item.category or "Uncategorised"
        counts[key] = counts.get(key, 0) + 1

    covered = {item.category for item in items if item.category}
    missing = sorted(applicable_categories - covered)
    return HamperCompositionInfo(
        category_counts=counts,
        applicable_categories=sorted(applicable_categories),
        missing_categories=missing,
        is_full_category_coverage=not missing,
        is_category_fallback=is_fallback,
    )


def _score(candidate: _Candidate, budget_max: float, fit_status: HamperFitStatus) -> float:
    utilisation = candidate.total_price / budget_max if budget_max > 0 else 0
    # Reward getting close to the budget cap without exceeding it.
    utilisation_score = utilisation * 10

    distinct_categories = len({item.category for item in candidate.items if item.category})
    diversity_score = distinct_categories * 2

    fit_confidence = 3 if fit_status.fits and fit_status.utilisation_ratio is not None else 1

    # Anti-bias: penalise a hamper where the item mix reads as "one
    # expensive thing plus filler" or "a pile of same-category filler",
    # even if the totals hit the budget target cleanly.
    composition_penalty = 0.0
    item_prices = [item.price for item in candidate.items]
    item_total = sum(item_prices)
    if item_total > 0 and item_prices:
        single_item_share = max(item_prices) / item_total
        if single_item_share > MAX_SINGLE_ITEM_SHARE:
            composition_penalty += 4
    if (
        len(candidate.items) >= MIN_ITEMS_FOR_CATEGORY_CONCENTRATION_PENALTY
        and distinct_categories <= 1
    ):
        composition_penalty += 3

    # Fill-ratio bonus/penalty: a near-empty-looking hamper (well under
    # MIN_FILL_RATIO of usable capacity) is scored down; a well-filled one
    # gets a small bonus. This is a soft preference, not a hard rejection -
    # some premium hampers legitimately have low physical fill.
    fill_adjustment = 0.0
    if fit_status.utilisation_ratio is not None:
        fill_adjustment = min(fit_status.utilisation_ratio, 1.0) * 2
        if fit_status.utilisation_ratio < MIN_FILL_RATIO:
            fill_adjustment -= 3

    return utilisation_score + diversity_score + fit_confidence + fill_adjustment - composition_penalty


def _explanation(
    candidate: _Candidate,
    budget_max: float,
    fit_status: HamperFitStatus,
    composition: HamperCompositionInfo,
) -> list[str]:
    utilisation = (candidate.total_price / budget_max * 100) if budget_max > 0 else 0
    distinct_categories = len(composition.category_counts)
    lines = [
        f"Rs {candidate.total_price:.2f} / Rs {budget_max:.2f} used ({utilisation:.1f}%)",
        f"{len(candidate.items)} item(s) across {distinct_categories} categor{'y' if distinct_categories == 1 else 'ies'}",
    ]
    if fit_status.utilisation_ratio is not None:
        lines.append(f"Estimated fit: {fit_status.utilisation_ratio * 100:.0f}% of usable container capacity")
    else:
        lines.append("Estimated fit: not calculable (dimensions missing)")
    lines.append("Dimensions verified" if fit_status.fully_verified else "Fit partially unverified - some dimensions were missing")

    total_categories = len(composition.applicable_categories)
    if total_categories:
        covered = total_categories - len(composition.missing_categories)
        status = "Complete" if composition.is_full_category_coverage else "Fallback"
        line = f"Category coverage: {covered}/{total_categories} - {status}"
        if composition.missing_categories:
            line += f" (missing: {', '.join(composition.missing_categories)})"
        lines.append(line)
    return lines


def _candidate_item_sets(candidate: _Candidate) -> frozenset[str]:
    return frozenset(_normalized(item.name) for item in candidate.items)


def _overlap_ratio(a: frozenset[str], b: frozenset[str]) -> float:
    smaller = min(len(a), len(b)) or 1
    return len(a & b) / smaller


def _is_diverse(candidate: _Candidate, chosen: list[_Candidate], container_use_count: dict[str, int]) -> bool:
    if container_use_count.get(candidate.container.name, 0) >= MAX_CONTAINER_REPEATS:
        return False

    candidate_names = _candidate_item_sets(candidate)
    for other in chosen:
        if _overlap_ratio(candidate_names, _candidate_item_sets(other)) >= DIVERSITY_OVERLAP_THRESHOLD:
            return False
    return True


def _generate_candidates_for_container(
    container: HamperContainer,
    items: list[HamperItem],
    request: HamperRequest,
    reasons: list[str],
) -> list[_Candidate]:
    if container.price > request.budget_max:
        return []

    mandatory_names = {_normalized(name) for name in request.mandatory_products}
    excluded_names = {_normalized(name) for name in request.excluded_products}

    conflicting = mandatory_names & excluded_names
    if conflicting:
        reasons.append(
            f"Must-include and exclude lists conflict on: {', '.join(sorted(conflicting))}."
        )
        return []

    catalog_names = {_normalized(item.name) for item in items}
    missing_mandatory = mandatory_names - catalog_names
    if missing_mandatory:
        reasons.append(
            f"Must-include item(s) not found in catalog: {', '.join(sorted(missing_mandatory))}."
        )
        return []

    mandatory_items = [item for item in items if _matches_any(item, mandatory_names)]
    for item in mandatory_items:
        if _item_fits_container_individually(item, container) is False:
            reasons.append(f"Must-include '{item.name}' does not fit in container '{container.name}'.")
            return []

    mandatory_total = _round_currency(sum(item.price for item in mandatory_items))
    if _round_currency(container.price + mandatory_total) > request.budget_max:
        reasons.append(
            f"Container '{container.name}' plus required item(s) exceeds the budget cap."
        )
        return []

    optional_pool = [
        item for item in items
        if not _matches_any(item, mandatory_names) and not _matches_any(item, excluded_names)
        and (not request.preferred_categories or item.category in request.preferred_categories)
        and _item_fits_container_individually(item, container) is not False
    ]

    remaining_budget = request.budget_max - container.price - mandatory_total
    min_content_value = container.price * MIN_CONTENT_TO_CONTAINER_RATIO

    candidates: list[_Candidate] = []
    seen_combos = 0

    max_optional = max(0, MAX_ITEMS_PER_HAMPER - len(mandatory_items))
    for size in range(0, max_optional + 1):
        if len(mandatory_items) + size < MIN_ITEMS_PER_HAMPER:
            continue
        for combo in itertools.combinations(optional_pool, size):
            seen_combos += 1
            if seen_combos > MAX_COMBOS_PER_CONTAINER:
                break

            combo_total = _round_currency(sum(item.price for item in combo))
            if combo_total > remaining_budget:
                continue

            content_value = mandatory_total + combo_total
            if content_value < min_content_value:
                continue

            all_items = mandatory_items + list(combo)
            total_price = _round_currency(container.price + content_value)
            if total_price > request.budget_max:
                continue
            candidates.append(_Candidate(container=container, items=all_items, total_price=total_price))
        if seen_combos > MAX_COMBOS_PER_CONTAINER:
            break

    return candidates


def _select_diverse(
    pool: list[tuple[_Candidate, HamperFitStatus, float]],
    limit: int,
) -> list[tuple[_Candidate, HamperFitStatus, float]]:
    return _select_diverse_continuing(pool, limit, [], {})


def _select_diverse_continuing(
    pool: list[tuple[_Candidate, HamperFitStatus, float]],
    limit: int,
    chosen: list[_Candidate],
    container_use_count: dict[str, int],
) -> list[tuple[_Candidate, HamperFitStatus, float]]:
    """Same greedy diversity selection as _select_diverse, but continues
    from an already-chosen set (used for the category-coverage fallback
    pass, so container-repeat caps and item-overlap checks stay consistent
    with what was already picked in the primary pass)."""

    picked: list[tuple[_Candidate, HamperFitStatus, float]] = []

    for candidate, fit_status, score in pool:
        if len(picked) >= limit:
            break
        if not _is_diverse(candidate, chosen, container_use_count):
            continue
        chosen.append(candidate)
        container_use_count[candidate.container.name] = container_use_count.get(candidate.container.name, 0) + 1
        picked.append((candidate, fit_status, score))

    return picked


def recommend_hampers(
    containers: list[HamperContainer],
    items: list[HamperItem],
    request: HamperRequest,
) -> HamperSearchResult:
    reasons: list[str] = []
    all_candidates: list[tuple[_Candidate, HamperFitStatus, float]] = []

    excluded_names = {_normalized(name) for name in request.excluded_products}
    eligible_for_categories = [
        item for item in items
        if not _matches_any(item, excluded_names)
        and (not request.preferred_categories or item.category in request.preferred_categories)
    ]
    applicable_categories = {item.category for item in eligible_for_categories if item.category}

    for container in containers:
        for candidate in _generate_candidates_for_container(container, items, request, reasons):
            fit_status = _fit_status(candidate.container, candidate.items)
            if not fit_status.fits:
                continue
            score = _score(candidate, request.budget_max, fit_status)
            all_candidates.append((candidate, fit_status, score))

    all_candidates.sort(key=lambda entry: entry[2], reverse=True)

    # Prefer combinations that make good use of the budget; only fall back
    # to lower-utilisation ones if nothing better exists, so cheap
    # combinations don't dominate just because they were found first.
    well_utilised = [
        entry for entry in all_candidates
        if request.budget_max <= 0 or entry[0].total_price / request.budget_max >= MIN_BUDGET_UTILISATION
    ]
    ranked_pool = well_utilised if well_utilised else all_candidates

    def covered_categories(candidate: _Candidate) -> set[str]:
        return {item.category for item in candidate.items if item.category}

    # Primary rule: require all applicable categories to be represented.
    # Only relax it (falling back to the best partial-coverage options) if
    # there aren't enough full-coverage results to satisfy option_count -
    # and that relaxation is recorded explicitly, not silently blended in.
    if applicable_categories:
        full_coverage_pool = [
            entry for entry in ranked_pool
            if applicable_categories <= covered_categories(entry[0])
        ]
    else:
        full_coverage_pool = ranked_pool

    picked = _select_diverse(full_coverage_pool, request.option_count)
    full_coverage_count = len(picked)

    if len(picked) < request.option_count:
        chosen_so_far = [entry[0] for entry in picked]
        container_counts: dict[str, int] = {}
        for candidate in chosen_so_far:
            container_counts[candidate.container.name] = container_counts.get(candidate.container.name, 0) + 1

        remaining_pool = [entry for entry in ranked_pool if entry not in picked]
        fallback_picked = _select_diverse_continuing(
            remaining_pool, request.option_count - len(picked), chosen_so_far, container_counts,
        )
        picked = picked + fallback_picked

    recommendations = []
    for index, (candidate, fit_status, score) in enumerate(picked):
        is_fallback = index >= full_coverage_count
        composition = _composition(candidate.items, applicable_categories, is_fallback)
        recommendations.append(HamperRecommendation(
            container=candidate.container,
            items=candidate.items,
            total_price=candidate.total_price,
            budget_utilisation=(candidate.total_price / request.budget_max) if request.budget_max else 0,
            composition=composition,
            fit_status=fit_status,
            score=score,
            explanation=_explanation(candidate, request.budget_max, fit_status, composition),
        ))

    message_parts: list[str] = []
    if not recommendations:
        message_parts.append(
            reasons[0] if reasons else "No valid hamper found within the given budget and constraints."
        )
    else:
        if len(recommendations) < request.option_count:
            message_parts.append(
                f"Only {len(recommendations)} valid, sufficiently distinct hamper option(s) found "
                f"(requested {request.option_count})."
            )
        if full_coverage_count < len(recommendations):
            message_parts.append(
                f"{full_coverage_count} option(s) cover all applicable categories; "
                f"{len(recommendations) - full_coverage_count} additional fallback option(s) with "
                f"partial category coverage included."
            )
    message = " ".join(message_parts) or None

    return HamperSearchResult(
        recommendations=recommendations,
        requested_count=request.option_count,
        message=message,
        reasons=reasons,
    )
