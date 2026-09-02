"""Verifies the per-container item-eligibility rule (2026-09-03): the
catalog's "yes"/"no" columns say which containers a given item is curated
for, independent of physical fit. Off by default (recommend_hampers'
eligible_container_names param defaults to None) - only exercised here and
by the real API, which passes catalog.eligible_container_names through.
"""

from pathlib import Path

import pytest

from backend.hampers.catalog_loader import load_hamper_catalog
from backend.hampers.models import HamperRequest
from backend.hampers.recommender import GREETING_CARD_MANDATORY, recommend_hampers

DATA_PATH = Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"

pytestmark = pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")


@pytest.fixture(scope="module")
def catalog():
    return load_hamper_catalog(DATA_PATH)


def test_catalog_actually_has_eligibility_columns(catalog):
    # Guards against this silently going inert if the catalog is ever
    # swapped back to the old schema (no per-container columns).
    assert catalog.eligible_container_names


def test_eligibility_data_only_appears_on_items_with_a_yes_or_no(catalog):
    # The two carried-forward items (2x2 Handprinted Diya, Farmley Smoked
    # BBQ Nuts) have blank cells for every eligibility column - they must
    # come through as unconstrained (None), not as "allowed nowhere".
    carried_forward = [item for item in catalog.items if item.name in {"2x2 Handprinted Diya (Autistic)", "Farmley Smoked BBQ Nuts 22g"}]
    assert len(carried_forward) == 2
    for item in carried_forward:
        assert item.allowed_containers is None


def test_a_no_marked_item_is_excluded_from_that_container_but_not_others(catalog):
    # Real data: "Besan Laddoo Cookies Tin 100g" is "no" for the Bougenvilla
    # box but "yes" for the Blue box (per the source sheet).
    tin_item = next(item for item in catalog.items if item.name == "Besan Laddoo Cookies Tin 100g")
    bougenvilla = next(c for c in catalog.containers if c.name == "11 x 4.5 x 2.5 inch box - Bougenvilla")
    blue_box = next(c for c in catalog.containers if c.name == "13.5 x 7 x 3.5 inch box - Blue")

    assert tin_item.allowed_containers is not None
    assert bougenvilla.name not in tin_item.allowed_containers
    assert blue_box.name in tin_item.allowed_containers


def test_recommendations_never_place_a_no_marked_item_in_its_excluded_container(catalog):
    request = HamperRequest(budget_min=1, budget_max=5000, option_count=10)
    result = recommend_hampers(catalog.containers, catalog.items, request, catalog.eligible_container_names)

    for rec in result.recommendations:
        # Containers with no eligibility column at all (e.g. "10 x 10 x 3
        # w cavity - Jaipur palace") are exempt from this rule by design -
        # the filter only applies where the sheet actually has data.
        if rec.container.name not in catalog.eligible_container_names:
            continue
        for item in rec.items:
            if item.allowed_containers is None:
                continue
            assert rec.container.name in item.allowed_containers, (
                f"'{item.name}' is not curated for '{rec.container.name}' but was recommended there anyway."
            )


def test_container_with_no_eligibility_column_is_unaffected(catalog):
    # "10 x 10 x 3 w cavity - Jaipur palace" has no dedicated eligibility
    # column in the sheet at all - it must not be silently blocked from
    # every item as a result.
    gap_container_name = "10 x 10 x 3 w cavity - Jaipur palace"
    assert any(c.name == gap_container_name for c in catalog.containers)
    assert gap_container_name not in catalog.eligible_container_names


def test_without_eligibility_param_behavior_is_unchanged(catalog):
    # The default (no eligible_container_names passed) must behave exactly
    # as if this feature didn't exist - existing callers/tests are
    # unaffected by this change.
    request = HamperRequest(budget_min=1500, budget_max=2000, option_count=4)
    without_filter = recommend_hampers(catalog.containers, catalog.items, request)
    with_filter_off = recommend_hampers(catalog.containers, catalog.items, request, None)

    prices_without = sorted(rec.total_price for rec in without_filter.recommendations)
    prices_with = sorted(rec.total_price for rec in with_filter_off.recommendations)
    assert prices_without == prices_with


if GREETING_CARD_MANDATORY:
    def test_greeting_card_is_unaffected_by_eligibility_filter(catalog):
        # Greeting Card is "yes" for every container in the sheet, so the
        # mandate from earlier this week and this new rule don't conflict.
        card = next(item for item in catalog.items if item.name == "Greeting Card")
        if card.allowed_containers is not None:
            for container in catalog.containers:
                if container.name in catalog.eligible_container_names:
                    assert container.name in card.allowed_containers
