"""System-level regression scenarios for the hamper engine, run against the
real giftbox_data catalog.

Purpose (per stakeholder review): once individual mechanisms (budget cap,
fit checks, category coverage, anti-bias scoring) are each independently
validated, the bigger ongoing risk is regressions and rule *interactions*
as the engine evolves - not another missing scoring rule. This file pins
down structural invariants across a matrix of budgets/option counts/
constraints so a future change to any one rule can't silently break the
others without a test failing here.

These are intentionally invariant-based (never exceed budget, no duplicate
items, etc.) rather than pinned to exact item picks - exact picks are
expected to shift as scoring is legitimately tuned; the invariants below
should not.
"""

from pathlib import Path

import pytest

from backend.hampers.catalog_loader import load_hamper_catalog
from backend.hampers.models import HamperRequest
from backend.hampers.recommender import recommend_hampers

DATA_PATH = Path(__file__).resolve().parents[2] / "giftbox_data" / "Input Data - Quotations Tool_Hampers.csv"

pytestmark = pytest.mark.skipif(not DATA_PATH.exists(), reason="real hamper catalog data not present")


@pytest.fixture(scope="module")
def catalog():
    return load_hamper_catalog(DATA_PATH)


def _assert_result_invariants(result, request: HamperRequest):
    assert result.found_count <= request.option_count

    for rec in result.recommendations:
        # Never exceed the hard budget cap, even by a paisa.
        assert rec.total_price <= request.budget_max + 1e-9

        # No item appears twice in the same hamper.
        item_names = [item.name for item in rec.items]
        assert len(item_names) == len(set(item_names))

        # Excluded products never appear.
        excluded = {name.lower() for name in request.excluded_products}
        assert not any(item.name.lower() in excluded for item in rec.items)

        # Mandatory products always appear when the request succeeded.
        mandatory = {name.lower() for name in request.mandatory_products}
        present = {item.name.lower() for item in rec.items}
        assert mandatory <= present

        # A candidate that failed physical fit should never surface.
        assert rec.fit_status.fits is True

        # Composition/coverage flags must be internally consistent.
        covered = {item.category for item in rec.items if item.category}
        missing = set(rec.composition.missing_categories)
        assert rec.composition.is_full_category_coverage == (not missing)
        if rec.composition.applicable_categories:
            assert missing == set(rec.composition.applicable_categories) - covered

        # Hard eligibility rule: every returned recommendation must cover
        # every applicable category - no partial-coverage fallback exists.
        assert rec.composition.is_full_category_coverage
        assert not rec.composition.missing_categories
        if rec.composition.applicable_categories:
            assert set(rec.composition.applicable_categories) <= covered

    # Container reuse cap respected across the whole batch.
    container_counts: dict[str, int] = {}
    for rec in result.recommendations:
        container_counts[rec.container.name] = container_counts.get(rec.container.name, 0) + 1
    assert all(count <= 2 for count in container_counts.values())

    # If fewer options were found than requested, that must be visible in
    # the message - never silent.
    if 0 < result.found_count < request.option_count:
        assert result.message


# --- 1. Budget matrix: low / medium / high / awkward boundary values ----

BUDGET_SCENARIOS = [
    pytest.param(1, 100, id="impossible-too-low-for-any-container"),
    pytest.param(1, 335, id="boundary-just-under-cheapest-container"),
    pytest.param(1, 336, id="boundary-exact-cheapest-container-price"),
    pytest.param(1, 700, id="low-medium"),
    pytest.param(1, 1500, id="medium"),
    pytest.param(1, 2500, id="high"),
    pytest.param(1, 5000, id="above-catalog-max-possible"),
]


@pytest.mark.parametrize("budget_min, budget_max", BUDGET_SCENARIOS)
def test_budget_matrix(catalog, budget_min, budget_max):
    request = HamperRequest(budget_min=budget_min, budget_max=budget_max, option_count=5)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)

    if budget_max < 336:
        # Below the cheapest container's price - nothing can ever be valid.
        assert result.found_count == 0
        assert result.message


# --- 2. Option-count variation ------------------------------------------

@pytest.mark.parametrize("option_count", [1, 3, 5, 10])
def test_option_count_variation(catalog, option_count):
    request = HamperRequest(budget_min=1, budget_max=1500, option_count=option_count)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)
    assert result.found_count > 0


# --- 2b. Items-per-box customizer ----------------------------------------

@pytest.mark.parametrize("items_per_box", [3, 4])
def test_items_per_box_forces_exact_item_count(catalog, items_per_box):
    request = HamperRequest(
        budget_min=1, budget_max=2500, option_count=5, items_per_box=items_per_box,
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)
    assert result.found_count > 0
    for rec in result.recommendations:
        assert len(rec.items) == items_per_box


@pytest.mark.parametrize("items_per_box", [1, 2])
def test_items_per_box_below_real_catalog_category_count_is_structurally_impossible(catalog, items_per_box):
    # The real catalog has 3 categories (Food, Merchandise, Gourmet item) -
    # 1 or 2 items per box can never cover all 3, so this must be reported
    # as structurally impossible, not silently return zero with no reason.
    request = HamperRequest(
        budget_min=1, budget_max=2500, option_count=5, items_per_box=items_per_box,
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.recommendations == []
    assert result.message and "structurally impossible" in result.message


def test_items_per_box_none_is_unconstrained(catalog):
    request = HamperRequest(budget_min=1, budget_max=1500, option_count=5, items_per_box=None)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)
    assert result.found_count > 0
    # Without the constraint, item counts are free to vary across options.
    assert len({len(rec.items) for rec in result.recommendations}) >= 1


def test_items_per_box_rejects_when_mandatory_alone_exceeds_it(catalog):
    request = HamperRequest(
        budget_min=1,
        budget_max=2500,
        option_count=5,
        items_per_box=1,
        mandatory_products=["Baked Mathri Hexagon 70g", "Craft Lantern"],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 0
    assert any("exceed the requested" in reason for reason in result.reasons)


# --- 3. Mandatory + excluded combined ------------------------------------

def test_mandatory_and_excluded_together(catalog):
    # Against the real catalog, every container the mandatory tin physically
    # fits in tops out around ~56% fill for this combination - below the
    # 70% hard floor (MIN_REQUIRED_FILL_RATIO) - so this now legitimately
    # returns zero recommendations rather than some. This pins that as
    # expected, not a regression: confirmed via direct inspection that no
    # candidate across any valid container reaches 0.70.
    request = HamperRequest(
        budget_min=1,
        budget_max=1500,
        option_count=3,
        mandatory_products=["Nawabi Nuts Tin100g"],
        excluded_products=["Lasercut Metal Lantern", "Auspicious Lasercut Lantern"],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)
    assert result.found_count == 0


def test_multiple_mandatory_products_together(catalog):
    request = HamperRequest(
        budget_min=1,
        budget_max=2000,
        option_count=2,
        mandatory_products=["Baked Mathri Hexagon 70g", "Craft Lantern"],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)
    assert result.found_count > 0


# --- 4. Impossible requests ----------------------------------------------

def test_impossible_mandatory_product_not_in_catalog(catalog):
    request = HamperRequest(
        budget_min=1, budget_max=1500, option_count=3,
        mandatory_products=["Product That Does Not Exist In Catalog"],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 0
    assert result.message and "not found" in result.message.lower()


def test_impossible_conflicting_mandatory_and_excluded(catalog):
    request = HamperRequest(
        budget_min=1, budget_max=1500, option_count=3,
        mandatory_products=["Nawabi Nuts Tin100g"],
        excluded_products=["Nawabi Nuts Tin100g"],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 0
    assert result.message and "conflict" in result.message.lower()


def test_impossible_mandatory_items_alone_exceed_budget(catalog):
    request = HamperRequest(
        budget_min=1, budget_max=100, option_count=3,
        mandatory_products=["Nawabi Nuts Tin100g"],
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 0
    assert result.message


# --- 6. Pinned snapshot scenarios -----------------------------------------
#
# A small number of specific, previously-verified-live results pinned to
# concrete values (not just invariants), so an unintentional scoring
# regression on these known-good scenarios is caught immediately. If a
# future deliberate scoring change legitimately shifts these, update the
# pinned values in the same commit as the scoring change - don't just
# delete the assertion.

def test_snapshot_1500_budget_top_option_favours_container_fill(catalog):
    # Fill-ratio scoring weight was raised on 2026-08-24 per stakeholder
    # feedback ("container space needs to be fully filled") - the top
    # option now favours a well-filled container over squeezing out the
    # last few % of budget, so this asserts fill rather than budget-max.
    # Only 4 (not 5) full-coverage combinations at this budget clear the
    # 70% hard fill floor added later - confirmed deterministic via direct
    # inspection, not a flaky/partial result.
    request = HamperRequest(budget_min=1, budget_max=1500, option_count=5)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 4
    top = result.recommendations[0]
    assert top.fit_status.utilisation_ratio >= 0.9
    assert top.total_price <= 1500

    # Recommendations are ranked by score (which blends utilisation, fill,
    # and composition), not raw price - so only the score ordering is a
    # guaranteed invariant, not a price ordering.
    scores = [rec.score for rec in result.recommendations]
    assert scores == sorted(scores, reverse=True)


def test_snapshot_2500_budget_four_options_all_full_category_coverage(catalog):
    request = HamperRequest(budget_min=1, budget_max=2500, option_count=4)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 4
    assert all(rec.composition.is_full_category_coverage for rec in result.recommendations)
    assert all(set(rec.composition.applicable_categories) == {"Food", "Merchandise", "Gourmet item"}
               for rec in result.recommendations)
