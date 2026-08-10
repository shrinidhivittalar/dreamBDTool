import pytest

from backend.business_rules import BusinessRulesEngine
from backend.models import Product, RecommendationRequest
from backend.recommender import recommend


def test_business_rules_budget_total_excludes_gst():
    engine = BusinessRulesEngine()
    products = [Product(name="Brownie", selling_price=100), Product(name="Cookie", selling_price=50)]

    assert engine.budget_total(products) == 150


def test_business_rules_uses_selling_price_and_rock_bottom_price():
    engine = BusinessRulesEngine()
    products = [
        Product(name="Brownie", selling_price=100, rock_bottom_price=80),
        Product(name="Cookie", selling_price=50),
    ]

    assert engine.selling_total(products) == 150
    assert engine.rock_bottom_total(products) == 130


def test_business_rules_sweet_only_packaging_has_box_and_tissue():
    engine = BusinessRulesEngine()
    products = [Product(name="Brownie", selling_price=100, category="Sweet")]

    assert [item.name for item in engine.packaging_requirements(products)] == ["Box", "Tissue"]


def test_business_rules_savory_packaging_adds_ketchup():
    engine = BusinessRulesEngine()
    products = [Product(name="Samosa", selling_price=40, category="Savoury")]

    assert [item.name for item in engine.packaging_requirements(products)] == ["Box", "Tissue", "Ketchup sachet"]


def test_recommendation_output_charges_packaging_for_sweet_only_box():
    catalog = [Product(name="Brownie", selling_price=100, rock_bottom_price=80, category="Sweet")]
    request = RecommendationRequest(budget_min=80, budget_max=150, item_count=1, mandatory_products=["Brownie"])

    recommendation = recommend(catalog, request)[0]

    # Sweet-only boxes still get Box + Tissue, which carries the same flat
    # ₹20 packaging charge as a savory box's Box + Tissue + Ketchup - see
    # PACKAGING_COST.
    assert recommendation.packaging_cost == pytest.approx(20)
    assert recommendation.total_price == pytest.approx(120)
    assert [item.name for item in recommendation.packaging] == ["Box", "Tissue"]


def test_recommendation_output_includes_business_rule_prices_and_packaging():
    catalog = [Product(name="Samosa", selling_price=40, rock_bottom_price=30, category="Savoury")]
    request = RecommendationRequest(budget_min=30, budget_max=80, item_count=1, mandatory_products=["Samosa"])

    recommendation = recommend(catalog, request)[0]

    # A savory box always carries the flat ₹20 packaging add-on (Ketchup
    # sachet included) on top of the item total - see PACKAGING_SAVORY_COST.
    assert recommendation.packaging_cost == pytest.approx(20)
    assert recommendation.total_price == pytest.approx(60)
    assert recommendation.dad_selling_price == pytest.approx(40)
    assert recommendation.rock_bottom_price == pytest.approx(30)
    assert [item.name for item in recommendation.packaging] == ["Box", "Tissue", "Ketchup sachet"]
