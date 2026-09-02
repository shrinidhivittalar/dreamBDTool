"""Verifies the greeting-card mandate (2026-09-02 stakeholder rule): every
hamper recommendation must include a Greeting Card, and its price counts
toward the budget cap like any normal item - the total never exceeds
budget_max. Run against the real giftbox_data catalog, which has a real
"Greeting Card" item (Merchandise, ~Rs 12).

Unrelated unit tests in test_hamper_recommender.py use synthetic catalogs
without a Greeting Card item and neutralize the mandate via an autouse
fixture there - this file is where the mandate itself is actually tested.
"""

from pathlib import Path

import pytest

from backend.hampers.catalog_loader import load_hamper_catalog
from backend.hampers.models import HamperRequest
from backend.hampers.recommender import GREETING_CARD_ITEM_NAME, GREETING_CARD_MANDATORY, recommend_hampers

DATA_PATH = Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"

pytestmark = pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")


@pytest.fixture(scope="module")
def catalog():
    return load_hamper_catalog(DATA_PATH)


def test_mandate_is_turned_on():
    # Guards against this silently reverting to the old "stubbed, off by
    # default" state from before the business decision was made.
    assert GREETING_CARD_MANDATORY is True


def test_every_recommendation_includes_greeting_card(catalog):
    request = HamperRequest(budget_min=1500, budget_max=2000, option_count=4)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.recommendations
    for rec in result.recommendations:
        names = [item.name.strip().lower() for item in rec.items]
        assert GREETING_CARD_ITEM_NAME.lower() in names


def test_greeting_card_price_counts_toward_budget_cap(catalog):
    request = HamperRequest(budget_min=1500, budget_max=2000, option_count=4)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.recommendations
    for rec in result.recommendations:
        card = next(item for item in rec.items if item.name.strip().lower() == GREETING_CARD_ITEM_NAME.lower())
        assert card.price > 0
        # The mandate must never push a hamper over budget - Greeting
        # Card's cost is included in the same mandatory-item budget check
        # every other must-include item goes through.
        assert rec.total_price <= request.budget_max + 1e-9


def test_greeting_card_conflicts_with_being_excluded(catalog):
    # Excluding the one item that's also unconditionally mandatory is a
    # real self-contradiction - it should be rejected with a clear reason,
    # not silently resolved either way.
    request = HamperRequest(
        budget_min=1500,
        budget_max=2000,
        option_count=4,
        excluded_products=[GREETING_CARD_ITEM_NAME],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 0
    assert any("conflict" in reason.lower() for reason in result.reasons)
