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
    )
except ImportError:
    from models import (
        HamperCompositionInfo,
        HamperContainer,
        HamperFitStatus,
        HamperItem,
        HamperRecommendation,
        HamperRequest,
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


@dataclass
class _Candidate:
    container: HamperContainer
    items: list[HamperItem]
    total_price: float


def _normalized(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _matches_any(item: HamperItem, names: set[str]) -> bool:
    return _normalized(item.name) in names


def _fit_status(container: HamperContainer, items: list[HamperItem]) -> HamperFitStatus:
    container_volume = container.usable_volume_in3
    item_volumes = [item.volume_in3 for item in items]
    if container_volume is None or any(volume is None for volume in item_volumes):
        return HamperFitStatus(
            fits=True,
            notes="Dimensions missing for container or item(s); fit not verified.",
        )

    used_volume = sum(volume for volume in item_volumes if volume is not None)
    usable_volume = container_volume * USABLE_CAPACITY_FACTOR
    fits = used_volume <= usable_volume
    ratio = (used_volume / usable_volume) if usable_volume > 0 else None
    return HamperFitStatus(
        fits=fits,
        used_volume_in3=used_volume,
        container_volume_in3=container_volume,
        utilisation_ratio=ratio,
        notes="" if fits else "Estimated item volume exceeds usable container capacity.",
    )


def _composition(items: list[HamperItem]) -> HamperCompositionInfo:
    counts: dict[str, int] = {}
    for item in items:
        key = item.category or "Uncategorised"
        counts[key] = counts.get(key, 0) + 1
    return HamperCompositionInfo(category_counts=counts)


def _score(candidate: _Candidate, budget_max: float, fit_status: HamperFitStatus) -> float:
    utilisation = candidate.total_price / budget_max if budget_max > 0 else 0
    # Reward getting close to the budget cap without exceeding it.
    utilisation_score = utilisation * 10

    distinct_categories = len({item.category for item in candidate.items if item.category})
    diversity_score = distinct_categories * 2

    fit_confidence = 3 if fit_status.fits and fit_status.utilisation_ratio is not None else 1

    return utilisation_score + diversity_score + fit_confidence


def _candidate_item_sets(candidate: _Candidate) -> frozenset[str]:
    return frozenset(_normalized(item.name) for item in candidate.items)


def _is_diverse(candidate: _Candidate, chosen: list[_Candidate]) -> bool:
    candidate_names = _candidate_item_sets(candidate)
    for other in chosen:
        other_names = _candidate_item_sets(other)
        overlap = len(candidate_names & other_names)
        smaller = min(len(candidate_names), len(other_names)) or 1
        if candidate.container.name == other.container.name and overlap / smaller >= 0.7:
            return False
    return True


def _generate_candidates_for_container(
    container: HamperContainer,
    items: list[HamperItem],
    request: HamperRequest,
) -> list[_Candidate]:
    if container.price > request.budget_max:
        return []

    mandatory_names = {_normalized(name) for name in request.mandatory_products}
    excluded_names = {_normalized(name) for name in request.excluded_products}

    mandatory_items = [item for item in items if _matches_any(item, mandatory_names)]
    mandatory_total = sum(item.price for item in mandatory_items)
    if container.price + mandatory_total > request.budget_max:
        return []

    optional_pool = [
        item for item in items
        if not _matches_any(item, mandatory_names) and not _matches_any(item, excluded_names)
        and (not request.preferred_categories or item.category in request.preferred_categories)
    ]

    remaining_budget = request.budget_max - container.price - mandatory_total
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

            combo_total = sum(item.price for item in combo)
            if combo_total > remaining_budget:
                continue

            all_items = mandatory_items + list(combo)
            total_price = container.price + mandatory_total + combo_total
            candidates.append(_Candidate(container=container, items=all_items, total_price=total_price))
        if seen_combos > MAX_COMBOS_PER_CONTAINER:
            break

    return candidates


def recommend_hampers(
    containers: list[HamperContainer],
    items: list[HamperItem],
    request: HamperRequest,
) -> list[HamperRecommendation]:
    all_candidates: list[tuple[_Candidate, HamperFitStatus, float]] = []

    for container in containers:
        for candidate in _generate_candidates_for_container(container, items, request):
            fit_status = _fit_status(candidate.container, candidate.items)
            if not fit_status.fits:
                continue
            score = _score(candidate, request.budget_max, fit_status)
            all_candidates.append((candidate, fit_status, score))

    all_candidates.sort(key=lambda entry: entry[2], reverse=True)

    chosen: list[_Candidate] = []
    recommendations: list[HamperRecommendation] = []
    for candidate, fit_status, score in all_candidates:
        if len(recommendations) >= request.option_count:
            break
        if not _is_diverse(candidate, chosen):
            continue
        chosen.append(candidate)
        recommendations.append(HamperRecommendation(
            container=candidate.container,
            items=candidate.items,
            total_price=candidate.total_price,
            budget_utilisation=(candidate.total_price / request.budget_max) if request.budget_max else 0,
            composition=_composition(candidate.items),
            fit_status=fit_status,
            score=score,
        ))

    return recommendations
