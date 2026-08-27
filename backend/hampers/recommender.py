"""Basic hamper recommendation engine (Phase 3).

Bounded combination search per candidate container, a rule-based physical
fit check (per-item bounding-box orientation check, plus a dedicated
row-capacity rule for items generically classified as hexagonal boxes -
see _is_hexagonal_box / _hexagonal_box_fits), and a scoring pass that
rewards high budget utilisation and composition variety. This is a
starting point, not a final optimizer - see PHASE1_HAMPERS.md Phase 5 for
what's intentionally deferred (smarter container selection, etc).
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

# Packaging-field keyword that generically identifies an item as a
# hexagonal box, driven entirely by the catalog's Primary/Secondary
# Packaging columns (see catalog_loader.py) - never by product name.
HEXAGON_PACKAGING_KEYWORD = "hexagon"


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
    """Checks the item's own footprint against the container's. Freely
    rotatable items try every axis rotation (6 orientations). Items flagged
    `upright_only` (candles, liquids, anything that can't be laid on its
    side) only try yaw rotations that keep their own height as height -
    2 orientations instead of 6. Returns None (unknown) rather than
    guessing when dimensions are missing/invalid - callers must treat that
    as "not verified", never as "fits"."""

    item_dims = _item_dims(item)
    container_dims = _item_dims(container)
    if item_dims is None or container_dims is None:
        return None

    length, breadth, height = item_dims
    rotations = (
        [(length, breadth, height), (breadth, length, height)]
        if getattr(item, "upright_only", False)
        else list(itertools.permutations(item_dims))
    )
    for rotation in rotations:
        if all(dim <= max_dim for dim, max_dim in zip(rotation, container_dims)):
            return True
    return False


def _is_hexagonal_box(item: HamperItem) -> bool:
    """Generic classification driven by the catalog's packaging fields -
    never by product name. An item is a hexagonal box if either its
    primary or secondary packaging text mentions "hexagon"."""
    packaging = f"{item.primary_packaging} {item.secondary_packaging}".lower()
    return HEXAGON_PACKAGING_KEYWORD in packaging


def _hexagonal_box_fits(container: HamperContainer, item: HamperItem) -> bool | None:
    """Fit check for a generically-classified hexagonal box item, using a
    fixed orientation mapping (not a rotation search) because a hexagonal
    box's footprint is not axis-symmetric the way a rectangular carton is:

        hamper.length_in  <-> hexagon.length_in
        hamper.breadth_in <-> hexagon.height_in
        hamper.height_in  <-> hexagon.breadth_in

    Returns None (unknown) if either set of dimensions is missing/invalid."""
    item_dims = _item_dims(item)
    container_dims = _item_dims(container)
    if item_dims is None or container_dims is None:
        return None

    item_length, item_breadth, item_height = item_dims
    container_length, container_breadth, container_height = container_dims
    return (
        item_length <= container_length
        and item_height <= container_breadth
        and item_breadth <= container_height
    )


def _individually_fits(item: HamperItem, container: HamperContainer) -> bool | None:
    """Dispatches to the hexagonal-box rule for items generically
    classified as hexagonal boxes, and the general bounding-box rotation
    check for everything else. Single entry point so every caller applies
    the same rule consistently."""
    if _is_hexagonal_box(item):
        return _hexagonal_box_fits(container, item)
    return _item_fits_container_individually(item, container)


def _hexagonal_row_length(item: HamperItem) -> float | None:
    """The length_in a hexagonal box occupies along the hamper's shared
    row. Returns None if dimensions are missing/invalid."""
    item_dims = _item_dims(item)
    if item_dims is None:
        return None
    return item_dims[0]


def _fit_status(container: HamperContainer, items: list[HamperItem]) -> HamperFitStatus:
    hexagon_items = [item for item in items if _is_hexagonal_box(item)]
    other_items = [item for item in items if not _is_hexagonal_box(item)]

    for item in hexagon_items:
        hex_fit = _hexagonal_box_fits(container, item)
        if hex_fit is False:
            return HamperFitStatus(
                fits=False,
                container_volume_in3=container.usable_volume_in3,
                notes=f"'{item.name}' (hexagonal box) does not fit the container's length/breadth/height.",
                fully_verified=False,
            )

    if hexagon_items:
        # Combined-length row check: every hexagonal box in the candidate
        # shares one row along the hamper's length, so what matters is
        # their combined length_in, not each item's own individual row
        # capacity. For identical hexagon lengths this reduces to the same
        # result as floor(hamper.length_in / hexagon.length_in), but it
        # also correctly handles a mix of different hexagon lengths.
        row_lengths = [_hexagonal_row_length(item) for item in hexagon_items]
        container_length = _item_dims(container)
        if all(length is not None for length in row_lengths) and container_length is not None:
            total_row_length = sum(row_lengths)
            if total_row_length > container_length[0]:
                return HamperFitStatus(
                    fits=False,
                    container_volume_in3=container.usable_volume_in3,
                    notes="Hexagonal box items' combined length exceeds the container's length.",
                    fully_verified=True,
                )

    for item in other_items:
        individual_fit = _item_fits_container_individually(item, container)
        if individual_fit is False:
            return HamperFitStatus(
                fits=False,
                container_volume_in3=container.usable_volume_in3,
                notes=f"'{item.name}' does not fit inside the container in any orientation.",
                fully_verified=False,
            )

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
    used_volume = sum(resolved_volumes)
    # utilisation_ratio is a fill ESTIMATE for scoring/display only - it does
    # not gate physical fit (that's the per-item bounding-box check above and
    # the hexagonal-box row-capacity rule). No 0.75 capacity-factor fudge:
    # this is raw used volume over raw container volume, nothing more.
    ratio = (used_volume / container_volume) if container_volume > 0 and resolved_volumes else None

    # The only volume-based rejection that's a genuine necessary condition
    # (not an arbitrary threshold): if the items' combined volume alone
    # exceeds the container's raw volume, no arrangement can possibly exist,
    # full stop - no need to run the geometric search at all.
    if used_volume > container_volume:
        return HamperFitStatus(
            fits=False,
            used_volume_in3=used_volume,
            container_volume_in3=container_volume,
            utilisation_ratio=ratio,
            notes="Combined item volume exceeds the container's volume.",
            fully_verified=not excluded_items,
            fill_estimate_partial=excluded_items,
        )

    if excluded_items:
        # Can't run the geometric search without every item's real
        # dimensions - fall back to "not verified" rather than asserting a
        # geometry result that can't actually be checked.
        notes = (
            "No items in this hamper have usable dimensions; fit not verified."
            if not resolved_volumes
            else "Fit not fully verified - one or more items have missing/invalid dimensions; the fill estimate below excludes them and is a floor, not a precise figure."
        )
        return HamperFitStatus(
            fits=True,
            used_volume_in3=used_volume,
            container_volume_in3=container_volume,
            utilisation_ratio=ratio,
            notes=notes,
            fully_verified=False,
            fill_estimate_partial=True,
        )

    # All individual per-item checks (bounding-box for regular items,
    # length/breadth/height + row-capacity for hexagonal boxes) and the
    # combined-volume check above have passed - the fit is accepted.
    return HamperFitStatus(
        fits=True,
        used_volume_in3=used_volume,
        container_volume_in3=container_volume,
        utilisation_ratio=ratio,
        notes="",
        fully_verified=True,
    )


def _composition(
    items: list[HamperItem],
    applicable_categories: set[str],
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
    # gets a strong bonus. Squared so fill dominates the ranking near 100%
    # (2026-08-25 stakeholder feedback: "should fill 100%, or at least 98%")
    # - still a soft preference, not a hard rejection, since some premium
    # hampers legitimately have low physical fill and shouldn't be excluded
    # outright.
    fill_adjustment = 0.0
    if fit_status.utilisation_ratio is not None:
        capped_ratio = min(fit_status.utilisation_ratio, 1.0)
        fill_adjustment = (capped_ratio ** 2) * 30
        if fit_status.utilisation_ratio < MIN_FILL_RATIO:
            fill_adjustment -= 15

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
    # "Dimension compatible" (not "fit verified"/"arrangement verified"): the
    # check behind this is per-item bounding-box/hexagon-row compatibility
    # plus a combined-volume bound, not a proof that all items simultaneously
    # arrange inside the container without overlapping - don't overstate it.
    lines.append("Dimension compatible" if fit_status.fully_verified else "Fit partially unverified - some dimensions were missing")

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
        if _individually_fits(item, container) is False:
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
        and _individually_fits(item, container) is not False
    ]

    remaining_budget = request.budget_max - container.price - mandatory_total
    min_content_value = container.price * MIN_CONTENT_TO_CONTAINER_RATIO

    candidates: list[_Candidate] = []
    seen_combos = 0

    # When the user has requested an exact items-per-box count, that
    # replaces the engine's own MIN/MAX_ITEMS_PER_HAMPER range - only that
    # one combo size is considered, not "up to" it.
    if request.items_per_box is not None:
        if len(mandatory_items) > request.items_per_box:
            reasons.append(
                f"Must-include item(s) for container '{container.name}' exceed the requested "
                f"{request.items_per_box} item(s) per box."
            )
            return []
        optional_sizes = [request.items_per_box - len(mandatory_items)]
    else:
        max_optional = max(0, MAX_ITEMS_PER_HAMPER - len(mandatory_items))
        optional_sizes = range(0, max_optional + 1)

    for size in optional_sizes:
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

    # Hard eligibility rule: a candidate is not a valid recommendation at all
    # unless it covers every applicable category. There is no fallback to
    # partial-coverage candidates - if full coverage can't be achieved, the
    # engine returns fewer (or zero) recommendations rather than topping up
    # with ones missing a category.
    if applicable_categories:
        full_coverage_pool = [
            entry for entry in ranked_pool
            if applicable_categories <= covered_categories(entry[0])
        ]
    else:
        full_coverage_pool = ranked_pool

    picked = _select_diverse(full_coverage_pool, request.option_count)

    recommendations = []
    for candidate, fit_status, score in picked:
        composition = _composition(candidate.items, applicable_categories)
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
        if applicable_categories and request.items_per_box is not None and request.items_per_box < len(applicable_categories):
            message_parts.append(
                f"Requested {request.items_per_box} item(s) per box, but {len(applicable_categories)} "
                f"categor{'y' if len(applicable_categories) == 1 else 'ies'} must each be represented - "
                f"full category coverage is structurally impossible with that item count."
            )
        elif applicable_categories and all_candidates:
            message_parts.append(
                "No hamper covering every applicable category could be found within the budget and "
                "other constraints (must-include items, exclusions, or dimension compatibility)."
            )
        else:
            message_parts.append(
                reasons[0] if reasons else "No valid hamper found within the given budget and constraints."
            )
    else:
        if len(recommendations) < request.option_count:
            message_parts.append(
                f"Only {len(recommendations)} valid, sufficiently distinct hamper option(s) covering every "
                f"applicable category could be found (requested {request.option_count})."
            )
    message = " ".join(message_parts) or None

    return HamperSearchResult(
        recommendations=recommendations,
        requested_count=request.option_count,
        message=message,
        reasons=reasons,
    )
