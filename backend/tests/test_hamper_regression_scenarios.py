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

    # Every recommendation in a batch must use a different container.
    container_names = [rec.container.name for rec in result.recommendations]
    assert len(container_names) == len(set(container_names))

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


@pytest.mark.parametrize("items_per_box", [1])
def test_items_per_box_below_real_catalog_category_count_is_structurally_impossible(catalog, items_per_box):
    # The real catalog has 4 Tag values (Food, Merchandise, Gourmet item,
    # Nuts), but Gourmet item and Nuts are carved out of the hard "one of
    # each category" requirement (OPTIONAL_CATEGORIES in recommender.py) per
    # the 2026-08-31 stakeholder rule "one of each category, and if budget
    # allows, then nuts" - only Food and Merchandise are hard-required. 1
    # item per box can never cover both, so this must be reported as
    # structurally impossible, not silently return zero with no reason.
    request = HamperRequest(
        budget_min=1, budget_max=2500, option_count=5, items_per_box=items_per_box,
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.recommendations == []
    assert result.message and "raise 'Items per box'" in result.message


def test_items_per_box_at_real_catalog_required_category_count_is_not_structurally_impossible(catalog):
    # 2 items per box can structurally cover the 2 hard-required categories
    # (Food, Merchandise) even though it's below the total Tag-value count -
    # this is the behavior change from the "Nuts is optional" rule. Real
    # containers may still reject 2-item combos on other grounds (the 70%
    # fill floor, budget), so this only asserts the category-count gate
    # itself no longer blocks it "structurally impossible" the way 1 item
    # does.
    request = HamperRequest(
        budget_min=1, budget_max=2500, option_count=5, items_per_box=2,
    )
    result = recommend_hampers(catalog.containers, catalog.items, request)

    if not result.recommendations:
        assert result.message and "raise 'Items per box'" not in result.message
    for rec in result.recommendations:
        assert rec.composition.is_full_category_coverage


def test_items_per_box_none_is_unconstrained(catalog):
    request = HamperRequest(budget_min=1, budget_max=1500, option_count=5, items_per_box=None)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    _assert_result_invariants(result, request)
    assert result.found_count > 0
    # Without the constraint, item counts are free to vary across options.
    assert len({len(rec.items) for rec in result.recommendations}) >= 1


def test_items_per_box_none_actually_generates_5_and_6_item_candidates(catalog):
    # Regression pin for a real bug (2026-08-28): itertools.combinations was
    # enumerated in ascending size order against one shared
    # MAX_COMBOS_PER_CONTAINER budget, so for most real containers the
    # 4-item combo count alone exceeded the whole budget and sizes 5/6 were
    # never generated at all - "Any" silently behaved like "4". The fix
    # splits the combo budget evenly per allowed size up front, so every
    # size gets a guaranteed, deterministic share.
    from backend.hampers.recommender import _generate_candidates_for_container

    request = HamperRequest(budget_min=1, budget_max=2500, option_count=5, items_per_box=None)
    sizes_seen: set[int] = set()
    for container in catalog.containers:
        reasons: list[str] = []
        for candidate in _generate_candidates_for_container(container, catalog.items, request, reasons):
            sizes_seen.add(len(candidate.items))

    assert 5 in sizes_seen
    assert 6 in sizes_seen


def test_generation_ordering_bias_no_longer_hides_high_value_combos(catalog):
    # Regression pin for a real bug (2026-08-28): a single catalog-row-order
    # pass over itertools.combinations means the first ~N combos examined
    # for a given size are not remotely representative once the true combo
    # count vastly exceeds the per-size budget - so combinations built from
    # pricier, later-in-the-catalog items were never generated at all, not
    # legitimately excluded by any rule. At a Rs2000 budget, the top
    # recommendation for Bougenvilla used to top out around Rs1197 (only
    # ~60% budget) even though a valid Rs1968+ (98%+) combination exists
    # and passes every hard rule. Confirmed via direct inspection that the
    # fix (catalog/price-desc/price-asc/budget-balanced orderings sharing
    # the fixed per-size budget) actually finds it now.
    request = HamperRequest(budget_min=1, budget_max=2000, option_count=5, items_per_box=None)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.recommendations
    assert any(rec.budget_utilisation >= 0.9 for rec in result.recommendations)


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

def test_snapshot_1500_budget_top_option_favours_budget_utilisation(catalog):
    # Scoring was rebalanced on 2026-08-28 so budget utilisation is the
    # dominant ranking term and fill (already a 70% hard floor) is only a
    # secondary tiebreaker - the top option now favours using more of the
    # budget over maximising fill, the reverse of the old 2026-08-24
    # weighting this test used to assert. 3 unique containers (not 2) can
    # now produce a valid, full-coverage, >=70%-fill combination at this
    # budget - the fixed per-item-count combo generation budget (see
    # _generate_candidates_for_container) means item counts up to 6 are now
    # actually considered, surfacing options this catalog always had.
    # Confirmed deterministic via direct inspection.
    #
    # 2026-09-02: dropped from 3 to 2 after GREETING_CARD_MANDATORY was
    # turned on - Greeting Card now occupies one item slot and ~Rs 12 of
    # budget in every candidate, which pushed one previously-70%+-fill
    # container below the floor at this budget. Expected consequence of the
    # business rule, not a regression - re-confirmed live.
    request = HamperRequest(budget_min=1, budget_max=1500, option_count=5)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 2
    container_names = [rec.container.name for rec in result.recommendations]
    assert len(container_names) == len(set(container_names))
    top = result.recommendations[0]
    assert top.budget_utilisation >= 0.9
    assert top.fit_status.utilisation_ratio >= 0.70
    assert top.total_price <= 1500

    # Recommendations are ranked by score (which blends utilisation, fill,
    # and composition), not raw price - so only the score ordering is a
    # guaranteed invariant, not a price ordering. Score is no longer a
    # *strictly* monotonic ordering by itself (2026-09-01): the Nuts
    # preference (_rank_key) can place a lower-scored Nuts-inclusive
    # recommendation above a higher-scored Nuts-free one, when the two are
    # within NUTS_UTILISATION_TOLERANCE of each other's utilisation - so any
    # score increase between consecutive recommendations must be explained
    # by exactly that (earlier has Nuts, later doesn't), never by anything
    # else.
    for earlier, later in zip(result.recommendations, result.recommendations[1:]):
        if earlier.score < later.score:
            assert "Nuts" in earlier.composition.category_counts
            assert "Nuts" not in later.composition.category_counts


def test_snapshot_2500_budget_unique_containers_all_full_category_coverage(catalog):
    # All 4 requested unique containers can produce a valid, full-coverage,
    # >=70%-fill combination at this budget. This rose from 3 (2026-08-28,
    # single catalog-order generation pass) to 4 after fixing a real
    # candidate-generation sampling bias: itertools.combinations only ever
    # examined the first N combos in catalog row order, which for large
    # item counts is a tiny, unrepresentative fraction of the true space -
    # so higher-value combos for some containers (e.g. Jaipur palace
    # variants) were never even generated, not legitimately excluded.
    # Fixed via multiple deterministic pool orderings (catalog/price-desc/
    # price-asc/budget-balanced) sharing the same fixed per-size budget.
    # Confirmed deterministic via direct inspection.
    #
    # 2026-09-02: dropped from 4 to 3 after GREETING_CARD_MANDATORY was
    # turned on - same reasoning as the 1500-budget snapshot above.
    request = HamperRequest(budget_min=1, budget_max=2500, option_count=4)
    result = recommend_hampers(catalog.containers, catalog.items, request)

    assert result.found_count == 3
    container_names = [rec.container.name for rec in result.recommendations]
    assert len(container_names) == len(set(container_names))
    assert all(rec.composition.is_full_category_coverage for rec in result.recommendations)
    # Gourmet item and Nuts are optional (OPTIONAL_CATEGORIES in
    # recommender.py) - only Food and Merchandise are hard-required, so
    # that's what composition.applicable_categories (the coverage yardstick)
    # reports here.
    assert all(set(rec.composition.applicable_categories) == {"Food", "Merchandise"}
               for rec in result.recommendations)
