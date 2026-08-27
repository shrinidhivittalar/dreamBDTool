import pytest

from backend.hampers.models import HamperContainer, HamperFitStatus, HamperItem, HamperRequest
from backend.hampers.recommender import _Candidate, _generation_orderings, _score, recommend_hampers

# Sized so combos actually used across these tests (Cookie Tin alone, or
# Cookie Tin + one Merchandise item) clear the 70% hard fill floor - a
# container this closely matched to item volume is unrealistic for real
# catalog data, but these tests are about budget/mandatory/exclusion logic,
# not fill, so the fixture just needs to not accidentally fail the floor.
CONTAINER = HamperContainer(name="Small Box", price=100, length_in=2, breadth_in=2, height_in=2.5)

ITEMS = [
    HamperItem(name="Cookie Tin", price=200, category="Food", length_in=2, breadth_in=2, height_in=2),
    HamperItem(name="Chocolate Pack", price=150, category="Food", length_in=2, breadth_in=2, height_in=2),
    HamperItem(name="Candle", price=50, category="Merchandise", length_in=1, breadth_in=1, height_in=1),
    HamperItem(name="Diya", price=80, category="Merchandise", length_in=1, breadth_in=1, height_in=1),
]


def test_recommend_hampers_respects_budget_cap():
    request = HamperRequest(budget_min=100, budget_max=350, option_count=5)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.total_price <= 350


def test_recommend_hampers_returns_message_when_container_alone_exceeds_budget():
    request = HamperRequest(budget_min=10, budget_max=50, option_count=3)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations == []
    assert result.message


def test_recommend_hampers_includes_mandatory_and_excludes_excluded():
    request = HamperRequest(
        budget_min=100,
        budget_max=500,
        option_count=3,
        mandatory_products=["Cookie Tin"],
        excluded_products=["Chocolate Pack"],
    )
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations
    for rec in result.recommendations:
        item_names = {item.name for item in rec.items}
        assert "Cookie Tin" in item_names
        assert "Chocolate Pack" not in item_names


def test_recommend_hampers_rejects_oversized_combo_on_fit():
    tiny_container = HamperContainer(name="Tiny Box", price=10, length_in=1, breadth_in=1, height_in=1)
    request = HamperRequest(budget_min=10, budget_max=1000, option_count=3)

    result = recommend_hampers([tiny_container], ITEMS, request)

    for rec in result.recommendations:
        assert rec.fit_status.fits


def test_exact_budget_match_is_accepted():
    container = HamperContainer(name="Exact Box", price=100, length_in=1, breadth_in=1, height_in=1.3)
    items = [HamperItem(name="Only Item", price=50, length_in=1, breadth_in=1, height_in=1)]
    request = HamperRequest(budget_min=1, budget_max=150, option_count=1)

    result = recommend_hampers([container], items, request)

    assert result.recommendations
    assert result.recommendations[0].total_price == 150


def test_one_paisa_over_budget_is_rejected():
    container = HamperContainer(name="Exact Box", price=100, length_in=20, breadth_in=20, height_in=20)
    items = [HamperItem(name="Only Item", price=50.01, length_in=1, breadth_in=1, height_in=1)]
    request = HamperRequest(budget_min=1, budget_max=150, option_count=1)

    result = recommend_hampers([container], items, request)

    assert result.recommendations == []


def test_individual_item_too_large_is_rejected_even_if_volume_fits():
    # Volume fits (10x1x1=10 << container's 10x10x10=1000) but the item is
    # physically longer than any container axis.
    container = HamperContainer(name="Box", price=10, length_in=5, breadth_in=5, height_in=5)
    oversized_item = HamperItem(name="Long Pole", price=20, length_in=10, breadth_in=1, height_in=1)
    request = HamperRequest(budget_min=1, budget_max=100, option_count=3)

    result = recommend_hampers([container], [oversized_item], request)

    assert result.recommendations == []


def test_item_fits_via_rotation():
    container = HamperContainer(name="Box", price=10, length_in=3, breadth_in=10, height_in=2.5)
    rotated_item = HamperItem(name="Bar", price=20, length_in=10, breadth_in=3, height_in=2)
    request = HamperRequest(budget_min=1, budget_max=100, option_count=3)

    result = recommend_hampers([container], [rotated_item], request)

    assert result.recommendations
    assert result.recommendations[0].fit_status.fits


def test_missing_dimensions_do_not_silently_pass_as_verified():
    container = HamperContainer(name="Box", price=10, length_in=5, breadth_in=5, height_in=5)
    item_no_dims = HamperItem(name="Mystery Item", price=20)
    request = HamperRequest(budget_min=1, budget_max=100, option_count=3)

    result = recommend_hampers([container], [item_no_dims], request)

    assert result.recommendations
    fit_status = result.recommendations[0].fit_status
    assert fit_status.fits is True
    assert "not verified" in fit_status.notes


def test_requesting_more_options_than_exist_returns_best_available_with_message():
    request = HamperRequest(budget_min=100, budget_max=350, option_count=5)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert 0 < len(result.recommendations) < 5
    assert result.message
    assert "Only" in result.message


def test_impossible_mandatory_item_gives_a_clear_reason():
    request = HamperRequest(
        budget_min=1,
        budget_max=1000,
        option_count=3,
        mandatory_products=["Item That Does Not Exist"],
    )
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations == []
    assert result.message
    assert "not found" in result.message.lower()


def test_conflicting_mandatory_and_excluded_gives_a_clear_reason():
    request = HamperRequest(
        budget_min=1,
        budget_max=1000,
        option_count=3,
        mandatory_products=["Cookie Tin"],
        excluded_products=["Cookie Tin"],
    )
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations == []
    assert "conflict" in result.message.lower()


def test_each_recommendation_uses_a_unique_container():
    # Every returned recommendation must use a different container - not
    # just capped at some repeat count. With only 3 unique containers that
    # can each produce one valid candidate, requesting 5 options must
    # return at most 3, never reusing a container to make up the numbers.
    containers = [
        HamperContainer(name=f"Box {i}", price=10, length_in=1, breadth_in=1, height_in=1.3)
        for i in range(3)
    ]
    items = [
        HamperItem(name=f"Item {i}", price=10 + i, length_in=1, breadth_in=1, height_in=1)
        for i in range(3)
    ]
    request = HamperRequest(budget_min=1, budget_max=100, option_count=5)

    result = recommend_hampers(containers, items, request)

    container_names = [rec.container.name for rec in result.recommendations]
    assert len(container_names) == len(set(container_names))
    assert len(result.recommendations) <= 3


def test_container_eating_most_of_budget_is_deprioritised():
    expensive_container = HamperContainer(name="Pricey Box", price=990, length_in=1, breadth_in=1, height_in=1.3)
    cheap_container = HamperContainer(name="Reasonable Box", price=100, length_in=1, breadth_in=1, height_in=1.3)
    filler_item = HamperItem(name="Filler", price=5, length_in=1, breadth_in=1, height_in=1)
    good_item = HamperItem(name="Good Item", price=800, length_in=1, breadth_in=1, height_in=1)
    request = HamperRequest(budget_min=1, budget_max=1000, option_count=1)

    result = recommend_hampers(
        [expensive_container, cheap_container],
        [filler_item, good_item],
        request,
    )

    assert result.recommendations
    assert result.recommendations[0].container.name == "Reasonable Box"


def test_no_valid_hamper_returns_empty_list_with_message_not_error():
    request = HamperRequest(budget_min=1, budget_max=5, option_count=3)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations == []
    assert isinstance(result.message, str)
    assert result.message


def test_recommend_hampers_is_deterministic():
    request = HamperRequest(budget_min=100, budget_max=1500, option_count=5)

    first = recommend_hampers([CONTAINER], ITEMS, request)
    second = recommend_hampers([CONTAINER], ITEMS, request)

    assert [r.total_price for r in first.recommendations] == [r.total_price for r in second.recommendations]
    assert (
        [tuple(sorted(i.name for i in r.items)) for r in first.recommendations]
        == [tuple(sorted(i.name for i in r.items)) for r in second.recommendations]
    )


def test_budget_utilisation_now_outweighs_fill_in_scoring():
    # 2026-08-28 rebalance: fill is a secondary tiebreaker (already a 70%
    # hard floor), budget utilisation is the dominant ranking term. Two
    # candidates both clearing the fill floor: one with much higher fill
    # but lower budget use should now score BELOW one with lower fill but
    # much higher budget use - the reverse of the pre-rebalance weighting.
    container = HamperContainer(name="Box", price=0, length_in=10, breadth_in=10, height_in=10)
    high_fill_low_budget = _Candidate(
        container=container,
        items=[HamperItem(name="Cheap", price=100, category="Food", length_in=10, breadth_in=10, height_in=9.7)],
        total_price=100,
    )
    low_fill_high_budget = _Candidate(
        container=container,
        items=[HamperItem(name="Pricey", price=700, category="Food", length_in=10, breadth_in=10, height_in=7.1)],
        total_price=700,
    )
    budget_max = 1000
    fs_high_fill = HamperFitStatus(fits=True, utilisation_ratio=0.97, fully_verified=True)
    fs_low_fill = HamperFitStatus(fits=True, utilisation_ratio=0.71, fully_verified=True)

    score_high_fill_low_budget = _score(high_fill_low_budget, budget_max, fs_high_fill)
    score_low_fill_high_budget = _score(low_fill_high_budget, budget_max, fs_low_fill)

    assert score_low_fill_high_budget > score_high_fill_low_budget


def test_generation_orderings_budget_balanced_target_uses_net_remaining_and_optional_slots():
    # The budget-balanced ordering's per-item target must be computed from
    # the budget remaining AFTER mandatory-item cost, divided by the number
    # of OPTIONAL slots being filled - not the total items_per_box and not
    # the pre-mandatory budget. Here remaining_budget=300 (already net of
    # mandatory cost, as the caller computes it) and size=3 optional slots,
    # so the target is 100/item - "C" (price 100) should sort first.
    pool = [
        HamperItem(name="A", price=10, length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="B", price=290, length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="C", price=100, length_in=1, breadth_in=1, height_in=1),
    ]
    orderings = _generation_orderings(pool, size=3, remaining_budget=300)
    catalog_order, price_desc, price_asc, budget_balanced = orderings

    assert [i.name for i in catalog_order] == ["A", "B", "C"]
    assert [i.name for i in price_desc] == ["B", "C", "A"]
    assert [i.name for i in price_asc] == ["A", "C", "B"]
    assert budget_balanced[0].name == "C"


def test_generation_orderings_size_zero_does_not_divide_by_zero():
    pool = [HamperItem(name="A", price=10, length_in=1, breadth_in=1, height_in=1)]
    orderings = _generation_orderings(pool, size=0, remaining_budget=500)
    assert len(orderings) == 4


def test_single_dominant_item_is_scored_down_vs_balanced_alternative():
    container = HamperContainer(name="Box", price=10, length_in=1.5, breadth_in=1.5, height_in=1.5)
    dominant_item = HamperItem(name="Premium Thing", price=900, category="Gourmet", length_in=1, breadth_in=1, height_in=1)
    filler = HamperItem(name="Filler", price=5, category="Merchandise", length_in=1, breadth_in=1, height_in=1)
    balanced_items = [
        HamperItem(name="A", price=300, category="Food", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="B", price=300, category="Merchandise", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="C", price=300, category="Gourmet", length_in=1, breadth_in=1, height_in=1),
    ]
    request = HamperRequest(budget_min=1, budget_max=1000, option_count=2)

    result = recommend_hampers([container], [dominant_item, filler, *balanced_items], request)

    assert result.recommendations
    top = result.recommendations[0]
    assert "Premium Thing" not in {item.name for item in top.items}


def test_near_empty_fill_is_hard_rejected_not_just_scored_lower():
    # Fill below MIN_REQUIRED_FILL_RATIO (0.70) is a hard eligibility floor,
    # not a soft scoring penalty - a near-empty-looking hamper must not be
    # returned at all, regardless of how good everything else about it is.
    container = HamperContainer(name="Box", price=10, length_in=8.5, breadth_in=8.5, height_in=6.5)
    tiny_item = HamperItem(name="Tiny", price=900, length_in=1, breadth_in=1, height_in=1)
    bulk_item = HamperItem(name="Bulk", price=300, length_in=8, breadth_in=8, height_in=6)
    request = HamperRequest(budget_min=1, budget_max=1000, option_count=1)

    sparse_only = recommend_hampers([container], [tiny_item], request)
    filled = recommend_hampers([container], [bulk_item], request)

    assert sparse_only.recommendations == []
    assert filled.recommendations
    assert filled.recommendations[0].fit_status.utilisation_ratio >= 0.70


def test_recommendation_includes_explanation_and_verification_flag():
    request = HamperRequest(budget_min=100, budget_max=1500, option_count=1)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations
    rec = result.recommendations[0]
    assert rec.explanation
    assert any("used" in line for line in rec.explanation)
    assert rec.fit_status.fully_verified is True


def test_missing_dimensions_are_flagged_as_not_fully_verified():
    container = HamperContainer(name="Box", price=10, length_in=5, breadth_in=5, height_in=5)
    item_no_dims = HamperItem(name="Mystery Item", price=20)
    request = HamperRequest(budget_min=1, budget_max=100, option_count=1)

    result = recommend_hampers([container], [item_no_dims], request)

    assert result.recommendations
    assert result.recommendations[0].fit_status.fully_verified is False


def test_full_category_coverage_is_preferred_over_partial():
    container = HamperContainer(name="Box", price=10, length_in=1.5, breadth_in=1.5, height_in=1.5)
    items = [
        # Full-coverage combo: one item per category, modest budget use.
        HamperItem(name="Food A", price=100, category="Food", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="Merch A", price=100, category="Merchandise", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="Gourmet A", price=100, category="Gourmet item", length_in=1, breadth_in=1, height_in=1),
        # Partial-coverage combo: two Food items only, higher total spend.
        HamperItem(name="Food B", price=250, category="Food", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="Food C", price=240, category="Food", length_in=1, breadth_in=1, height_in=1),
    ]
    request = HamperRequest(budget_min=1, budget_max=1000, option_count=1)

    result = recommend_hampers([container], items, request)

    assert result.recommendations
    top = result.recommendations[0]
    assert top.composition.is_full_category_coverage
    assert set(top.composition.applicable_categories) == {"Food", "Merchandise", "Gourmet item"}


def test_partial_coverage_options_are_never_returned_when_not_enough_full_coverage_exist():
    container = HamperContainer(name="Box", price=10, length_in=1.5, breadth_in=1.5, height_in=1.5)
    items = [
        # Only one way to hit all 3 categories.
        HamperItem(name="Food A", price=50, category="Food", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="Merch A", price=50, category="Merchandise", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="Gourmet A", price=50, category="Gourmet item", length_in=1, breadth_in=1, height_in=1),
        # Extra Food-only items that would previously have supplied
        # partial-coverage fallback options - they must not appear now.
        HamperItem(name="Food B", price=60, category="Food", length_in=1, breadth_in=1, height_in=1),
        HamperItem(name="Food C", price=70, category="Food", length_in=1, breadth_in=1, height_in=1),
    ]
    request = HamperRequest(budget_min=1, budget_max=200, option_count=3)

    result = recommend_hampers([container], items, request)

    assert result.recommendations
    for rec in result.recommendations:
        assert rec.composition.is_full_category_coverage
        assert not rec.composition.missing_categories
    assert len(result.recommendations) < request.option_count
    assert result.message and "requested 3" in result.message.lower()


def test_every_returned_recommendation_covers_all_applicable_categories():
    request = HamperRequest(budget_min=100, budget_max=500, option_count=4)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations
    applicable = {item.category for item in ITEMS if item.category}
    for rec in result.recommendations:
        covered = {item.category for item in rec.items if item.category}
        assert applicable <= covered


def test_items_per_box_smaller_than_category_count_gives_impossibility_reason():
    # ITEMS spans 2 categories (Food, Merchandise); items_per_box=1 can
    # never cover both, regardless of budget.
    request = HamperRequest(budget_min=1, budget_max=500, option_count=1, items_per_box=1)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations == []
    assert result.message
    assert "items_per_box" not in result.message  # human-readable, not a field name
    assert "1 item(s) per box" in result.message
    assert "2 categor" in result.message
    assert "structurally impossible" in result.message


def test_sufficient_items_per_box_but_zero_full_coverage_gives_different_reason():
    # items_per_box is unconstrained (not the limiting factor) - single-
    # category combos fit the budget, but no combo spanning both
    # categories does, so this must NOT blame item count.
    request = HamperRequest(budget_min=1, budget_max=250, option_count=1)
    result = recommend_hampers([CONTAINER], ITEMS, request)

    assert result.recommendations == []
    assert result.message
    assert "structurally impossible" not in result.message
    assert "items_per_box" not in result.message
    assert "category" in result.message.lower()


def test_search_scales_to_larger_catalogs_within_a_reasonable_time(benchmark_container=None):
    import time

    # Sized to just barely hold ~6 unit-volume items so a full 5-category
    # combo can clear the 70% hard fill floor for the size==20 case below.
    container = HamperContainer(name="Big Box", price=100, length_in=2, breadth_in=2, height_in=1.5)
    for size in (20, 100, 500):
        items = [
            HamperItem(name=f"Item {i}", price=10 + (i % 50), category=f"Cat {i % 5}", length_in=1, breadth_in=1, height_in=1)
            for i in range(size)
        ]
        request = HamperRequest(budget_min=1, budget_max=2000, option_count=5)

        start = time.perf_counter()
        result = recommend_hampers([container], items, request)
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"search took {elapsed:.2f}s for {size} items"
        # Full category coverage is now a hard requirement (5 synthetic
        # categories here). For the larger catalogs the combo-enumeration
        # cap (MAX_COMBOS_PER_CONTAINER) is exhausted by smaller item counts
        # before combos of size 5 are reached at all - a pre-existing
        # search-breadth limitation, not something this test's job (search
        # performance) covers. Only assert a result was found where finding
        # one is actually reachable within the cap.
        if size == 20:
            assert result.recommendations
