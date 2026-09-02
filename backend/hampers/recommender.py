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
import math
import re
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

# Each returned recommendation must use a different container - a repeated
# box (even with different contents) reduces the variety a BD user sees.
# If fewer unique containers can produce a valid recommendation than were
# requested, fewer options are returned rather than reusing one.
MAX_CONTAINER_REPEATS = 1

# Category tags that are not part of the hard "one of each category"
# coverage requirement - carved out by explicit stakeholder rule (2026-08-31:
# "one of each category, and if budget allows, then nuts"), not derived from
# catalog data. Any category NOT in this set is still hard-required, exactly
# as before - this only removes these two from that requirement.
OPTIONAL_CATEGORIES = {"Nuts", "Gourmet item"}

# Of the optional categories above, which get a ranking preference (chosen
# over a Nuts-free candidate when the budget allows) rather than being
# merely allowed. Per the stakeholder rule, that's Nuts only - Gourmet item
# (tea) is optional with no preference either way.
PREFERRED_OPTIONAL_CATEGORIES = {"Nuts"}

# "If budget allows, then nuts": how close (in percentage points of
# budget_max) a candidate's utilisation must be to the best utilisation
# achievable by any hard-valid candidate for it to be considered "close
# enough" for the Nuts preference to apply (see _rank_key). 2026-09-01
# stakeholder-set threshold - deliberately NOT implemented as an additive
# score bonus: a flat bonus competes against utilisation_score's quadratic
# curve, whose slope varies with baseline utilisation, so no single bonus
# value reliably corresponds to "a small percentage-point gap" across all
# utilisation levels. Expressing the preference directly in percentage-point
# terms instead gives a fixed, predictable crossover regardless of baseline.
NUTS_UTILISATION_TOLERANCE = 0.03

# 2026-09-02 stakeholder rule, resolved: every hamper must include a
# greeting card, no exceptions, and it counts toward price/budget/fill like
# any other item - the total (container + items, greeting card included)
# still cannot exceed budget_max. Routed through the existing
# mandatory-item pipeline (see mandatory_names below), which already
# enforces exactly that: mandatory items' cost is added to the budget
# check before any optional items are chosen, so the cap is never
# exceeded. "Greeting Card" is a real catalog item (Merchandise, ~Rs 12).
GREETING_CARD_MANDATORY = True
GREETING_CARD_ITEM_NAME = "Greeting Card"

# A hamper where the container itself eats most of the budget, leaving only
# a token amount for actual product, is technically valid but not a good
# recommendation. Require the item content to be worth at least this
# fraction of the container's price.
MIN_CONTENT_TO_CONTAINER_RATIO = 0.15

# Hard eligibility floor: a hamper whose calculated fill (or, when some
# item dimensions are missing, the minimum known/floor fill) is below this
# share of usable container capacity is not returned at all - not scored
# down, rejected outright (see _fit_status). A ratio of None (nothing
# resolvable at all) is not a "known" fill below the floor, so it is not
# rejected on this basis alone.
MIN_REQUIRED_FILL_RATIO = 0.70

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

# Packaging-field keyword that generically identifies an item as a tin,
# same convention as HEXAGON_PACKAGING_KEYWORD above (2026-09-02 stakeholder
# rule: "if a box already contains a hexagon box of an item, do not add a
# tin of that same item" - see _base_product_key / _has_variant_clash).
TIN_PACKAGING_KEYWORD = "tin"

# Strips packaging-format words (hexagon/tin, optionally followed by a
# weight like "70g") and weight-only tokens from a product name so that
# "Achari Aam Crackers Hexagon 70g" and "Achari Aam Crackers Tin 100g"
# reduce to the same base product key. Order matters: the packaging-word
# pattern runs first (it also consumes a trailing weight), then the
# standalone-weight pattern mops up any weight left over (e.g. "Tin100g"
# with no space, or a weight with no packaging word at all).
_PACKAGING_WORD_RE = re.compile(r"\b(?:hexagon|tin)\s*\d*\s*g?\b", re.IGNORECASE)
_WEIGHT_RE = re.compile(r"\b\d+\s*g\b", re.IGNORECASE)


def _base_product_key(name: str) -> str:
    text = name.lower()
    text = _PACKAGING_WORD_RE.sub(" ", text)
    text = _WEIGHT_RE.sub(" ", text)
    return " ".join(text.split())


def _is_tin(item: HamperItem) -> bool:
    """Same generic, packaging-field-driven convention as _is_hexagonal_box -
    never by product name."""
    packaging = f"{item.primary_packaging} {item.secondary_packaging}".lower()
    return TIN_PACKAGING_KEYWORD in packaging


def _has_variant_clash(items: list[HamperItem]) -> bool:
    """True if the candidate contains both a hexagonal-box SKU and a tin SKU
    of the same underlying product (2026-09-02 stakeholder rule). Matched by
    base product name after stripping the packaging-format word and any
    weight, not by an explicit pair list, so it applies uniformly as the
    catalog grows."""
    by_key: dict[str, set[str]] = {}
    for item in items:
        if not (_is_hexagonal_box(item) or _is_tin(item)):
            continue
        key = _base_product_key(item.name)
        formats = by_key.setdefault(key, set())
        formats.add("hexagon" if _is_hexagonal_box(item) else "tin")
    return any(formats == {"hexagon", "tin"} for formats in by_key.values())


def _has_duplicate_item(items: list[HamperItem]) -> bool:
    """True if the exact same catalog item (by normalized name) appears more
    than once in the candidate (2026-09-02 stakeholder rule for Merchandise,
    applied generically - the catalog has at least one literal duplicate row
    ["Khara Cookies 20g Pouch" appears twice with different prices], so this
    also closes a real gap, not just the Merchandise case that prompted it).
    Pairing different Merchandise items, or Merchandise with candles, is
    unaffected - only an exact repeat of the same item is rejected."""
    names = [_normalized(item.name) for item in items]
    return len(names) != len(set(names))


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
        if ratio is not None and ratio < MIN_REQUIRED_FILL_RATIO:
            return HamperFitStatus(
                fits=False,
                used_volume_in3=used_volume,
                container_volume_in3=container_volume,
                utilisation_ratio=ratio,
                notes=(
                    f"Minimum known fill ({ratio * 100:.0f}%, excluding items with missing dimensions) "
                    f"is below the required {MIN_REQUIRED_FILL_RATIO * 100:.0f}%."
                ),
                fully_verified=False,
                fill_estimate_partial=True,
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

    if ratio is not None and ratio < MIN_REQUIRED_FILL_RATIO:
        return HamperFitStatus(
            fits=False,
            used_volume_in3=used_volume,
            container_volume_in3=container_volume,
            utilisation_ratio=ratio,
            notes=f"Calculated fill ({ratio * 100:.0f}%) is below the required {MIN_REQUIRED_FILL_RATIO * 100:.0f}%.",
            fully_verified=True,
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
    # Reward getting close to the budget cap without exceeding it. Squared
    # (like fill below) so the pull toward the cap strengthens as it's
    # approached, without being a hard 100% requirement - a combination at
    # 95% budget use still scores close to one at 100%, but meaningfully
    # ahead of one at 60%. This is now the dominant scoring term: budget
    # utilisation should generally win the ranking among otherwise-eligible
    # candidates, with fill acting as a secondary quality factor (see below).
    utilisation_score = (utilisation ** 2) * 40

    distinct_categories = len({item.category for item in candidate.items if item.category})
    # Nuts is excluded from the diversity count on purpose: it already has
    # its own dedicated preference channel (_rank_key's utilisation-gated
    # nuts_priority), and letting it also earn generic diversity credit here
    # would double-count that preference (stacking a second, unbounded
    # advantage on top of the gated one) - see 2026-09-01 stakeholder
    # decision. Other categories, including the still-optional-but-not-
    # preferred Gourmet item, keep counting normally. distinct_categories
    # itself (all categories, Nuts included) is kept as-is for the
    # composition_penalty concentration check below - that penalty is about
    # samey/repetitive item mixes, unrelated to the Nuts preference.
    diversity_categories = {
        item.category for item in candidate.items
        if item.category and item.category not in PREFERRED_OPTIONAL_CATEGORIES
    }
    diversity_score = len(diversity_categories) * 2

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

    # Fill-ratio bonus: candidates below MIN_REQUIRED_FILL_RATIO are already
    # hard-rejected in _fit_status and never reach scoring - every candidate
    # here already clears the 70% floor. This is now a secondary quality
    # factor, not the dominant ranking signal: its ceiling is deliberately
    # smaller than utilisation_score's so budget utilisation wins the
    # ranking first, with fill only breaking ties/near-ties between
    # otherwise similar budget usage (2026-08-25 stakeholder feedback:
    # "should fill 100%, or at least 98%" is now expressed via the 70%
    # hard floor plus this smaller tiebreaker, not via ranking dominance).
    fill_adjustment = 0.0
    if fit_status.utilisation_ratio is not None:
        capped_ratio = min(fit_status.utilisation_ratio, 1.0)
        fill_adjustment = (capped_ratio ** 2) * 10

    # The Nuts preference ("if budget allows, then nuts") is deliberately
    # NOT a term in this score - it's expressed separately in _rank_key()
    # as a utilisation-gated lexicographic tie-break, not an additive bonus.
    # See _rank_key's docstring for why.
    return utilisation_score + diversity_score + fit_confidence + fill_adjustment - composition_penalty


def _has_preferred_optional(candidate: _Candidate) -> bool:
    return any(item.category in PREFERRED_OPTIONAL_CATEGORIES for item in candidate.items)


def _rank_key(
    entry: tuple[_Candidate, HamperFitStatus, float],
    budget_max: float,
    best_utilisation: float,
) -> tuple[int, float]:
    """Ranking key implementing "if budget allows, then nuts" as a gated
    tie-break rather than an additive score bonus (see NUTS_UTILISATION_TOLERANCE
    for why an additive bonus can't reliably express "small percentage-point
    gap" across different baseline utilisation levels).

    A candidate's utilisation must be within NUTS_UTILISATION_TOLERANCE of
    best_utilisation (the best utilisation achieved by any hard-valid
    candidate for this request) for containing Nuts to count at all. Inside
    that band, any Nuts-containing candidate outranks any candidate without
    one, regardless of the (small, by construction) utilisation difference
    between them. Outside the band, Nuts contributes nothing here - ranking
    falls through to plain `score`, which is utilisation-dominant, so a
    candidate trailing the best by more than the tolerance can never win
    just for containing Nuts.

    When no candidate in the pool contains Nuts at all, `nuts_priority` is 0
    for every entry, and this key reduces to plain `score` - identical to
    ranking before this preference existed.
    """
    candidate, _fit_status, score = entry
    utilisation = candidate.total_price / budget_max if budget_max > 0 else 0
    in_band = utilisation >= best_utilisation - NUTS_UTILISATION_TOLERANCE
    nuts_priority = 1 if (in_band and _has_preferred_optional(candidate)) else 0
    return (nuts_priority, score)


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


def _generation_orderings(
    optional_pool: list[HamperItem],
    size: int,
    remaining_budget: float,
) -> list[list[HamperItem]]:
    """Deterministic pool orderings used to sample combinations for one
    item count, each biased toward a different region of the price
    spectrum. Catalog row order alone (the only ordering used previously)
    systematically hid higher-priced valid combinations whenever the true
    combination count for a size vastly exceeds its generation budget -
    the first N combinations in catalog order are not remotely
    representative of what's achievable. All orderings are `sorted()`
    (stable), so equal-price ties preserve original catalog order -
    everything here is fully deterministic and reproducible, no randomness.
    `remaining_budget` must already be net of mandatory-item cost, and
    `size` is the number of OPTIONAL slots being filled (mandatory items
    are added separately in the caller) - the per-item target below is
    remaining_budget / size, not remaining_budget / items_per_box.
    """
    target_price = remaining_budget / size if size > 0 else 0.0
    return [
        optional_pool,  # catalog order - baseline/diversity, unchanged from before
        sorted(optional_pool, key=lambda item: -item.price),  # price descending - surfaces high-value combos
        sorted(optional_pool, key=lambda item: item.price),  # price ascending - supports lower-budget combos
        sorted(optional_pool, key=lambda item: abs(item.price - target_price)),  # budget-balanced
    ]


def _generate_candidates_for_container(
    container: HamperContainer,
    items: list[HamperItem],
    request: HamperRequest,
    reasons: list[str],
) -> list[_Candidate]:
    if container.price > request.budget_max:
        return []

    mandatory_names = {_normalized(name) for name in request.mandatory_products}
    if GREETING_CARD_MANDATORY:
        mandatory_names = mandatory_names | {_normalized(GREETING_CARD_ITEM_NAME)}
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
    if _has_duplicate_item(mandatory_items) or _has_variant_clash(mandatory_items):
        reasons.append("Must-include items conflict with each other (duplicate item, or a hexagon/tin of the same product).")
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
        optional_sizes = [
            size for size in range(0, max_optional + 1)
            if len(mandatory_items) + size >= MIN_ITEMS_PER_HAMPER
        ]

    # Deterministic per-size combo budget: when several item counts are all
    # allowed (items_per_box is None), MAX_COMBOS_PER_CONTAINER is split
    # evenly across them up front, rather than spent in ascending-size order
    # until it runs out. Without this, a large optional pool means size-4
    # combos alone exceed the whole budget, and sizes 5/6 are never even
    # attempted - "any item count" silently degenerating into "4 items".
    # No randomness: each size gets a fixed, equal, deterministic share
    # (itertools.combinations already enumerates in a fixed lexicographic
    # order, so which combos are seen within a size's share is reproducible).
    per_size_budget = max(1, MAX_COMBOS_PER_CONTAINER // len(optional_sizes)) if optional_sizes else 0

    for size in optional_sizes:
        pool_size = len(optional_pool)
        total_combos_for_size = math.comb(pool_size, size) if size <= pool_size else 0

        # Only bother with multiple orderings when the true combination
        # count actually exceeds this size's budget - otherwise a single
        # exhaustive pass already sees every possible combo, and running
        # multiple orderings would just re-examine the same combos.
        if total_combos_for_size <= per_size_budget:
            orderings = [optional_pool]
            strategy_budgets = [per_size_budget]
        else:
            orderings = _generation_orderings(optional_pool, size, remaining_budget)
            # Split this size's fixed budget evenly across strategies, with
            # any remainder assigned to the earliest strategies - still
            # fully deterministic, and the total across strategies never
            # exceeds per_size_budget, so MAX_COMBOS_PER_CONTAINER is not
            # increased, only redistributed within each size.
            base_share, remainder = divmod(per_size_budget, len(orderings))
            strategy_budgets = [
                base_share + (1 if i < remainder else 0)
                for i in range(len(orderings))
            ]

        seen_item_sets: set[frozenset[int]] = set()

        for pool_ordering, strategy_budget in zip(orderings, strategy_budgets):
            seen_for_strategy = 0
            for combo in itertools.combinations(pool_ordering, size):
                seen_for_strategy += 1
                if seen_for_strategy > strategy_budget:
                    break

                combo_key = frozenset(id(item) for item in combo)
                if combo_key in seen_item_sets:
                    continue
                seen_item_sets.add(combo_key)

                combo_total = _round_currency(sum(item.price for item in combo))
                if combo_total > remaining_budget:
                    continue

                content_value = mandatory_total + combo_total
                if content_value < min_content_value:
                    continue

                all_items = mandatory_items + list(combo)
                if _has_duplicate_item(all_items) or _has_variant_clash(all_items):
                    continue
                total_price = _round_currency(container.price + content_value)
                if total_price > request.budget_max:
                    continue
                candidates.append(_Candidate(container=container, items=all_items, total_price=total_price))

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
    # OPTIONAL_CATEGORIES are excluded from the hard "one of each category"
    # requirement below - required_categories is the actual coverage
    # yardstick everywhere it's used (hard gate, composition reporting,
    # messaging).
    required_categories = applicable_categories - OPTIONAL_CATEGORIES

    for container in containers:
        for candidate in _generate_candidates_for_container(container, items, request, reasons):
            fit_status = _fit_status(candidate.container, candidate.items)
            if not fit_status.fits:
                continue
            score = _score(candidate, request.budget_max, fit_status)
            all_candidates.append((candidate, fit_status, score))

    all_candidates.sort(key=lambda entry: entry[2], reverse=True)

    def covered_categories(candidate: _Candidate) -> set[str]:
        return {item.category for item in candidate.items if item.category}

    # Hard eligibility rule: a candidate is not a valid recommendation at all
    # unless it covers every applicable category. This must be applied
    # before the budget-utilisation preference below, not after - otherwise
    # a full-coverage candidate could be silently excluded just because
    # some higher-utilisation, partial-coverage candidate exists, even
    # though partial coverage is supposed to never be returned at all.
    if required_categories:
        full_coverage_candidates = [
            entry for entry in all_candidates
            if required_categories <= covered_categories(entry[0])
        ]
    else:
        full_coverage_candidates = all_candidates

    # Budget utilisation is no longer a separate hard pre-filter here - it's
    # baked into _score() (the dominant scoring term) instead, so the greedy
    # diverse-selection below already prefers higher-utilisation candidates
    # first. A binary "must clear 50% utilisation or be dropped entirely"
    # gate previously applied here caused a real problem: a container whose
    # best achievable full-coverage combo landed just under the threshold
    # (e.g. 48%) was wholly excluded, even when it was a perfectly valid,
    # decent option and the only way to reach more unique containers -
    # actively fighting the unique-container requirement below.
    full_coverage_pool = full_coverage_candidates

    # best_utilisation is the ceiling _rank_key's Nuts-preference band is
    # measured against - computed globally across every hard-valid
    # (required-category-covered, fit/budget/fill-eligible) candidate for
    # this request, before diverse-selection narrows the pool down.
    best_utilisation = max(
        (entry[0].total_price / request.budget_max if request.budget_max else 0 for entry in full_coverage_pool),
        default=0.0,
    )
    full_coverage_pool = sorted(
        full_coverage_pool,
        key=lambda entry: _rank_key(entry, request.budget_max, best_utilisation),
        reverse=True,
    )

    picked = _select_diverse(full_coverage_pool, request.option_count)

    recommendations = []
    for candidate, fit_status, score in picked:
        composition = _composition(candidate.items, required_categories)
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
        if required_categories and request.items_per_box is not None and request.items_per_box < len(required_categories):
            message_parts.append(
                f"Requested {request.items_per_box} item(s) per box, but {len(required_categories)} "
                f"categor{'y' if len(required_categories) == 1 else 'ies'} must each be represented - "
                f"full category coverage is structurally impossible with that item count."
            )
        elif required_categories and all_candidates:
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
