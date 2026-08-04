from backend.models import PackagingRequirement, Product, Recommendation, RecommendationRequest
from backend.validator import blocking_errors, validate_recommendation, validate_recommendations


def _rec(products, **overrides):
    data = {
        "products": products,
        "total_price": 100,
        "remaining_budget": 100,
        "score": 90,
        "packaging": [PackagingRequirement(name="Box"), PackagingRequirement(name="Tissue")],
    }
    data.update(overrides)
    return Recommendation(**data)


def test_budget_exceeded_is_warning_not_blocking():
    request = RecommendationRequest(budget_min=1, budget_max=90, item_count=1)
    rec = _rec([Product(name="Brownie", selling_price=100, category="Sweet")], remaining_budget=-10)

    issues = validate_recommendation(rec, request, 1)

    assert any(issue.code == "budget_exceeded" and issue.severity == "warning" for issue in issues)
    assert blocking_errors(issues) == []


def test_more_than_ten_items_is_error():
    products = [Product(name=f"Item {index}", selling_price=10, category="Sweet") for index in range(11)]
    request = RecommendationRequest(budget_min=1, budget_max=200, item_count=10)
    rec = _rec(products, total_price=110, remaining_budget=90)

    issues = validate_recommendation(rec, request, 1)

    assert any(issue.code == "too_many_items" and issue.severity == "error" for issue in issues)


def test_invalid_category_is_warning():
    request = RecommendationRequest(budget_min=1, budget_max=200, item_count=1)
    rec = _rec([Product(name="Mystery", selling_price=50)], total_price=50, remaining_budget=150)

    issues = validate_recommendation(rec, request, 1)

    assert any(issue.code == "invalid_category" and issue.severity == "warning" for issue in issues)


def test_two_ketchup_sachets_is_error():
    request = RecommendationRequest(budget_min=1, budget_max=200, item_count=1)
    rec = _rec(
        [Product(name="Samosa", selling_price=40, category="Savoury")],
        total_price=40,
        remaining_budget=160,
        packaging=[
            PackagingRequirement(name="Box"),
            PackagingRequirement(name="Tissue"),
            PackagingRequirement(name="Ketchup sachet"),
            PackagingRequirement(name="Ketchup sachet"),
        ],
    )

    issues = validate_recommendation(rec, request, 1)

    assert any(issue.code == "duplicate_ketchup" and issue.severity == "error" for issue in issues)


def test_disc_without_customization_opt_in_is_error():
    request = RecommendationRequest(budget_min=1, budget_max=200, item_count=1, include_themed_customised=False)
    rec = _rec(
        [Product(name="White Chocolate Disc with Edible Print", selling_price=50, category="Customisation")],
        total_price=50,
        remaining_budget=150,
    )

    issues = validate_recommendation(rec, request, 1)

    assert any(issue.code == "disc_customization_without_opt_in" and issue.severity == "error" for issue in issues)


def test_missing_required_category_is_error():
    request = RecommendationRequest(budget_min=1, budget_max=200, item_count=1, required_categories=["Healthy"])
    rec = _rec([Product(name="Brownie", selling_price=50, category="Sweet")], total_price=50, remaining_budget=150)

    issues = validate_recommendations([rec], request)

    assert any(issue.code == "missing_required_category" and issue.severity == "error" for issue in issues)
