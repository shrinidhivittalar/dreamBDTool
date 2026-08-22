import pytest

from backend.hampers.models import HamperContainer, HamperItem, HamperRequest
from backend.hampers.recommender import recommend_hampers

CONTAINER = HamperContainer(name="Small Box", price=100, length_in=10, breadth_in=10, height_in=5)

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
    container = HamperContainer(name="Exact Box", price=100, length_in=20, breadth_in=20, height_in=20)
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
    container = HamperContainer(name="Box", price=10, length_in=3, breadth_in=10, height_in=4)
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


def test_container_is_not_reused_beyond_repeat_cap():
    big_container = HamperContainer(name="Roomy Box", price=10, length_in=50, breadth_in=50, height_in=50)
    many_items = [
        HamperItem(name=f"Item {i}", price=10 + i, length_in=1, breadth_in=1, height_in=1)
        for i in range(10)
    ]
    request = HamperRequest(budget_min=1, budget_max=100, option_count=10)

    result = recommend_hampers([big_container], many_items, request)

    container_counts: dict[str, int] = {}
    for rec in result.recommendations:
        container_counts[rec.container.name] = container_counts.get(rec.container.name, 0) + 1
    assert all(count <= 2 for count in container_counts.values())


def test_container_eating_most_of_budget_is_deprioritised():
    expensive_container = HamperContainer(name="Pricey Box", price=990, length_in=50, breadth_in=50, height_in=50)
    cheap_container = HamperContainer(name="Reasonable Box", price=100, length_in=50, breadth_in=50, height_in=50)
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
