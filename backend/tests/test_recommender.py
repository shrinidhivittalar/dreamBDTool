from itertools import combinations, combinations_with_replacement

import pytest

from backend.models import Product, RecommendationRequest
from backend.recommender import GST_RATE, _bonus_value, _category_match, _closeness, recommend


def _catalog() -> list[Product]:
    return [
        Product(name="Brownie", selling_price=120, vendor="Dream a Dozen", tags=["sweet"], sourcing="In-house"),
        Product(name="Cake Pop", selling_price=45, vendor="Dream a Dozen", tags=["sweet"], sourcing="In-house"),
        Product(name="Sandwich", selling_price=88, vendor="HealthyChef", tags=["Healthy", "Savoury"], sourcing="Outsourced"),
        Product(name="Samosa", selling_price=28.6, vendor="Cakewala", tags=["Savoury"], sourcing="Outsourced"),
        Product(name="Cupcake", selling_price=60, vendor="Dream a Dozen", tags=["sweet"], sourcing="In-house"),
        Product(name="Cookie", selling_price=35, vendor="HealthyChef", tags=["Healthy"], sourcing="Outsourced"),
        Product(name="Muffin", selling_price=52, vendor="Cakewala", tags=["sweet"], sourcing="Outsourced"),
    ]


def test_mandatory_present_in_every_result():
    request = RecommendationRequest(budget_min=150, budget_max=300, item_count=3, mandatory_products=["Brownie"])
    recommendations = recommend(_catalog(), request)
    assert recommendations
    for rec in recommendations:
        assert any(product.name == "Brownie" for product in rec.products)


def test_ambiguous_mandatory_raises():
    catalog = [
        Product(name="Choco Brownie Deluxe", selling_price=120),
        Product(name="Nutty Brownie Deluxe", selling_price=150),
    ]
    request = RecommendationRequest(budget_min=150, budget_max=250, item_count=1, mandatory_products=["Deluxe"])
    with pytest.raises(ValueError):
        recommend(catalog, request)


def test_unmatched_mandatory_raises():
    request = RecommendationRequest(budget_min=150, budget_max=250, item_count=1, mandatory_products=["Nonexistent"])
    with pytest.raises(ValueError):
        recommend(_catalog(), request)


def test_mandatory_exceeds_item_count_raises():
    request = RecommendationRequest(budget_min=500, budget_max=1000, item_count=1, mandatory_products=["Brownie", "Cookie"])
    with pytest.raises(ValueError):
        recommend(_catalog(), request)


def test_budget_max_below_min_raises():
    with pytest.raises(ValueError):
        RecommendationRequest(budget_min=300, budget_max=200, item_count=2)


def test_preferred_not_required_for_results():
    # Preferred matches nothing in the catalog; it must not block results.
    request = RecommendationRequest(budget_min=150, budget_max=300, item_count=3, preferred_products=["Nonexistent Sweet"])
    assert recommend(_catalog(), request)


def test_preferred_increases_score():
    # A soft nudge, not a filter: it raises a product's bonus value, but
    # (unlike mandatory) never forces the search toward it.
    cookie = next(product for product in _catalog() if product.name == "Cookie")
    assert _bonus_value(cookie, ["Cookie"]) > _bonus_value(cookie, [])


def test_outside_range_combos_are_ranked_not_dropped():
    request = RecommendationRequest(budget_min=150, budget_max=200, item_count=3, mandatory_products=["Brownie"])
    recommendations = recommend(_catalog(), request, limit=10)
    totals = [rec.total_price for rec in recommendations]
    scores = [rec.score for rec in recommendations]
    assert len(recommendations) == 10
    assert max(totals) > request.budget_max  # combos above the range still surfaced, not filtered out
    assert scores == sorted(scores, reverse=True)  # ranked, never a hard cutoff


def test_no_duplicate_products_and_correct_size():
    request = RecommendationRequest(budget_min=200, budget_max=350, item_count=4)
    for rec in recommend(_catalog(), request):
        names = [product.name for product in rec.products]
        assert len(names) == request.item_count
        assert len(set(names)) == len(names)


def test_no_duplicate_items_with_tied_prices_and_bonuses():
    # Regression: many items sharing a price (so DP cells tie) plus a
    # preferred bonus that creates further ties used to let the naive
    # single-predecessor DP reconstruction pick the same physical item
    # at two different layers of one combination.
    catalog = [Product(name=f"Sandwich {i}", selling_price=price, tags=["Healthy"], sourcing="Outsourced")
               for i, price in enumerate([77, 77, 88, 88, 88, 35, 35, 52, 52, 60, 60, 45, 45, 28.6, 28.6] * 3)]
    request = RecommendationRequest(budget_min=400, budget_max=1200, item_count=6, mandatory_products=["Sandwich 0"], preferred_products=["Sandwich"])
    for rec in recommend(catalog, request, limit=20):
        names = [product.name for product in rec.products]
        assert len(names) == len(set(names))


def test_item_count_exceeds_pool_returns_empty():
    request = RecommendationRequest(budget_min=500, budget_max=1500, item_count=20)
    assert recommend(_catalog(), request) == []


def test_gst_added_on_top_of_selling_price():
    catalog = [Product(name="Brownie", selling_price=100)]
    request = RecommendationRequest(budget_min=90, budget_max=120, item_count=1, mandatory_products=["Brownie"])
    rec = recommend(catalog, request)[0]
    assert rec.total_price == pytest.approx(100 * (1 + GST_RATE), abs=0.01)


def test_price_includes_gst_adds_nothing_on_top():
    catalog = [Product(name="Brownie", selling_price=100)]
    request = RecommendationRequest(budget_min=90, budget_max=120, item_count=1, mandatory_products=["Brownie"], price_includes_gst=True)
    rec = recommend(catalog, request)[0]
    assert rec.total_price == pytest.approx(100, abs=0.01)


def test_sweet_only_filters_to_sweet_products():
    request = RecommendationRequest(budget_min=50, budget_max=150, item_count=2, sweet_preference="sweet_only")
    recommendations = recommend(_catalog(), request, limit=10)
    assert recommendations
    for rec in recommendations:
        assert all(_category_match(product, "sweet") for product in rec.products)


def test_no_sweet_excludes_sweet_products():
    request = RecommendationRequest(budget_min=50, budget_max=200, item_count=2, sweet_preference="no_sweet")
    recommendations = recommend(_catalog(), request, limit=10)
    assert recommendations
    for rec in recommendations:
        assert all(not _category_match(product, "sweet") for product in rec.products)


def test_dp_matches_brute_force_optimum():
    catalog = _catalog()
    request = RecommendationRequest(budget_min=150, budget_max=180, item_count=3)
    best = recommend(catalog, request, limit=1)[0].score

    brute_best = max(
        _closeness(sum(p.selling_price for p in combo) * (1 + GST_RATE), request.budget_min, request.budget_max)
        + sum(3 for p in combo if "in-house" in p.sourcing.lower() or "dream a dozen" in p.vendor.lower())
        + sum(2 for p in combo if any("healthy" in tag.lower() for tag in p.tags))
        for combo in combinations(catalog, request.item_count)
    )
    assert best == pytest.approx(brute_best, abs=0.01)


def _quota_feasible(combo: tuple[int, ...], group_keys: tuple[str, ...], quota_counts: tuple[int, ...], pool: list[Product]) -> bool:
    """Bipartite-matching feasibility check: can every quota slot be filled
    by a distinct unit of `combo` (each unit filling at most one slot)?
    Mirrors the DP's own semantics — a naive per-category tally would let
    one item double-count toward two categories it happens to match.
    """
    slots = [group for group, count in zip(group_keys, quota_counts) for _ in range(count)]
    adjacency = [[unit for unit, item in enumerate(combo) if _category_match(pool[item], group)] for group in slots]
    match_of_unit = [-1] * len(combo)

    def try_match(slot: int, seen: list[bool]) -> bool:
        for unit in adjacency[slot]:
            if not seen[unit]:
                seen[unit] = True
                if match_of_unit[unit] == -1 or try_match(match_of_unit[unit], seen):
                    match_of_unit[unit] = slot
                    return True
        return False

    matched = sum(try_match(slot, [False] * len(combo)) for slot in range(len(slots)))
    return matched == len(slots)


def test_repeats_dp_matches_brute_force_optimum():
    catalog = [
        Product(name="A", selling_price=50, tags=["Healthy"], sourcing="In-house"),
        Product(name="B", selling_price=30, vendor="Dream a Dozen"),
        Product(name="C", selling_price=70, tags=["Healthy"]),
        Product(name="D", selling_price=20),
    ]
    request = RecommendationRequest(budget_min=200, budget_max=250, item_count=4, allow_repeats=True)
    recommendations = recommend(catalog, request, limit=1)
    best = recommendations[0].score

    brute_best = max(
        _closeness(sum(p.selling_price for p in combo) * (1 + GST_RATE), request.budget_min, request.budget_max)
        + sum(_bonus_value(p, []) for p in combo)
        for combo in combinations_with_replacement(catalog, request.item_count)
    )
    assert best == pytest.approx(brute_best, abs=0.01)


def test_repeats_result_self_consistent_with_tied_prices():
    # Same tied-price/bonus setup that broke the naive 0/1 reconstruction —
    # repeats mode must independently reproduce reported total/score from
    # the (possibly repeated) products it actually returns.
    catalog = [Product(name=f"Sandwich {i}", selling_price=price, tags=["Healthy"], sourcing="Outsourced")
               for i, price in enumerate([77, 77, 88, 88, 88, 35, 35, 52, 52, 60, 60, 45, 45, 28.6, 28.6])]
    request = RecommendationRequest(budget_min=500, budget_max=1200, item_count=6, preferred_products=["Sandwich"], allow_repeats=True)
    for rec in recommend(catalog, request, limit=20):
        names = [product.name for product in rec.products]
        assert len(names) == request.item_count
        by_name = {product.name: product for product in catalog}
        recomputed_total = sum(by_name[name].selling_price for name in names) * (1 + GST_RATE)
        recomputed_bonus = sum(_bonus_value(by_name[name], request.preferred_products) for name in names)
        expected_score = _closeness(recomputed_total, request.budget_min, request.budget_max) + recomputed_bonus
        assert rec.total_price == pytest.approx(recomputed_total, abs=0.01)
        assert rec.score == pytest.approx(expected_score, abs=0.01)


def test_repeats_score_is_at_least_as_good_as_without():
    request_no_repeats = RecommendationRequest(budget_min=500, budget_max=1200, item_count=4)
    request_repeats = RecommendationRequest(budget_min=500, budget_max=1200, item_count=4, allow_repeats=True)
    without = recommend(_catalog(), request_no_repeats, limit=1)[0].score
    with_repeats = recommend(_catalog(), request_repeats, limit=1)[0].score
    assert with_repeats >= without


def test_required_category_present_in_every_result():
    catalog = [
        Product(name="Brownie A", selling_price=50, category="Brownie"),
        Product(name="Brownie B", selling_price=70, category="Brownie"),
        Product(name="Cookie A", selling_price=30, category="Cookie"),
        Product(name="Cookie B", selling_price=40, category="Cookie"),
        Product(name="Sandwich A", selling_price=90, category="Savoury"),
        Product(name="Cake", selling_price=100, category="Cake"),
    ]
    request = RecommendationRequest(budget_min=200, budget_max=350, item_count=4, required_categories=["Brownie", "Cookie"])
    recommendations = recommend(catalog, request, limit=10)
    assert recommendations
    for rec in recommendations:
        assert any(_category_match(product, "Brownie") for product in rec.products)
        assert any(_category_match(product, "Cookie") for product in rec.products)


def test_required_category_no_match_raises():
    request = RecommendationRequest(budget_min=200, budget_max=350, item_count=3, required_categories=["Nonexistent Category"])
    with pytest.raises(ValueError):
        recommend(_catalog(), request)


def test_required_categories_plus_mandatory_exceed_item_count_raises():
    catalog = [
        Product(name="Brownie A", selling_price=50, category="Brownie"),
        Product(name="Cookie A", selling_price=30, category="Cookie"),
        Product(name="Cake", selling_price=100, category="Cake"),
    ]
    request = RecommendationRequest(budget_min=200, budget_max=350, item_count=2, mandatory_products=["Cake"], required_categories=["Brownie", "Cookie"])
    with pytest.raises(ValueError):
        recommend(catalog, request)


def test_repeats_and_category_quota_combined_matches_brute_force():
    catalog = [
        Product(name="Brownie A", selling_price=50, category="Brownie", tags=["Sweet"]),
        Product(name="Healthy Brownie", selling_price=65, category="Brownie", tags=["Healthy"]),
        Product(name="Cookie A", selling_price=30, category="Cookie", tags=["Sweet"]),
        Product(name="Cookie B", selling_price=40, category="Cookie", tags=["Healthy"]),
        Product(name="Sandwich A", selling_price=90, category="Savoury"),
        Product(name="Cake", selling_price=45, category="Cake"),
    ]
    request = RecommendationRequest(
        budget_min=350, budget_max=450, item_count=5, allow_repeats=True,
        preferred_products=["Cake"], required_categories=["Brownie", "Cookie", "Cookie", "Healthy"],
    )
    recommendations = recommend(catalog, request, limit=50)
    assert recommendations

    group_keys = ("brownie", "cookie", "healthy")
    quota_counts = (1, 2, 1)
    name_to_index = {product.name: i for i, product in enumerate(catalog)}
    for rec in recommendations:
        assert len(rec.products) == request.item_count
        combo = tuple(name_to_index[product.name] for product in rec.products)
        assert _quota_feasible(combo, group_keys, quota_counts, catalog)

    brute_best = max(
        _closeness(sum(catalog[i].selling_price for i in combo) * (1 + GST_RATE), request.budget_min, request.budget_max)
        + sum(_bonus_value(catalog[i], request.preferred_products) for i in combo)
        for combo in combinations_with_replacement(range(len(catalog)), request.item_count)
        if _quota_feasible(combo, group_keys, quota_counts, catalog)
    )
    assert recommendations[0].score == pytest.approx(brute_best, abs=0.01)


def test_achievable_max_hint_when_catalog_price_ceiling_is_low():
    catalog = [
        Product(name="Small Item", selling_price=20),
        Product(name="Medium Item", selling_price=35),
    ]
    request = RecommendationRequest(budget_min=800, budget_max=1000, item_count=2)
    messages: list[str] = []
    recommendations = recommend(catalog, request, messages=messages)
    assert recommendations
    assert messages
    assert "priciest" in messages[0].lower()


def test_no_hint_when_budget_is_reachable():
    request = RecommendationRequest(budget_min=100, budget_max=250, item_count=3)
    messages: list[str] = []
    recommend(_catalog(), request, messages=messages)
    assert messages == []


def test_achievable_min_hint_when_catalog_price_floor_is_high():
    catalog = [
        Product(name="Deluxe Hamper", selling_price=500),
        Product(name="Premium Box", selling_price=600),
    ]
    request = RecommendationRequest(budget_min=50, budget_max=100, item_count=2)
    messages: list[str] = []
    recommendations = recommend(catalog, request, messages=messages)
    assert recommendations
    assert messages
    assert "cheapest" in messages[0].lower()


def test_message_when_filters_leave_too_few_candidates():
    request = RecommendationRequest(
        budget_min=150, budget_max=300, item_count=3, preferred_categories=["Nonexistent Category"],
    )
    messages: list[str] = []
    recommendations = recommend(_catalog(), request, messages=messages)
    assert recommendations == []
    assert messages
    assert "categories" in messages[0].lower()
    assert "check for typos" in messages[0].lower()
