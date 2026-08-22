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
    recs = recommend_hampers([CONTAINER], ITEMS, request)

    assert recs
    for rec in recs:
        assert rec.total_price <= 350


def test_recommend_hampers_returns_none_when_container_alone_exceeds_budget():
    request = HamperRequest(budget_min=10, budget_max=50, option_count=3)
    recs = recommend_hampers([CONTAINER], ITEMS, request)

    assert recs == []


def test_recommend_hampers_includes_mandatory_and_excludes_excluded():
    request = HamperRequest(
        budget_min=100,
        budget_max=500,
        option_count=3,
        mandatory_products=["Cookie Tin"],
        excluded_products=["Chocolate Pack"],
    )
    recs = recommend_hampers([CONTAINER], ITEMS, request)

    assert recs
    for rec in recs:
        item_names = {item.name for item in rec.items}
        assert "Cookie Tin" in item_names
        assert "Chocolate Pack" not in item_names


def test_recommend_hampers_rejects_oversized_combo_on_fit():
    tiny_container = HamperContainer(name="Tiny Box", price=10, length_in=1, breadth_in=1, height_in=1)
    request = HamperRequest(budget_min=10, budget_max=1000, option_count=3)

    recs = recommend_hampers([tiny_container], ITEMS, request)

    for rec in recs:
        assert rec.fit_status.fits
