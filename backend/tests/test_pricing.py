import pytest

from backend.models import Product, RecommendationRequest
from backend.pricing import PricingEngine


def test_pricing_engine_calculates_selling_and_rock_bottom_totals():
    engine = PricingEngine()
    products = [
        Product(name="Brownie", selling_price=100, rock_bottom_price=80),
        Product(name="Cookie", selling_price=50),
    ]

    assert engine.dad_selling_total(products) == 150
    assert engine.rock_bottom_total(products) == 130


def test_priced_total_matches_catalog_total():
    engine = PricingEngine()
    products = [Product(name="Brownie", selling_price=100)]
    request = RecommendationRequest(budget_min=90, budget_max=120, item_count=1)

    assert engine.priced_total(products, request) == pytest.approx(100)


def test_breakdown_has_future_pricing_rule_hooks():
    engine = PricingEngine()
    products = [Product(name="Brownie", selling_price=100, rock_bottom_price=80)]
    request = RecommendationRequest(budget_min=90, budget_max=120, item_count=1)

    breakdown = engine.breakdown(products, request)

    assert breakdown.dad_selling_price == 100
    assert breakdown.rock_bottom_price == 80
    assert breakdown.customization_surcharge == 0
    assert breakdown.packaging_cost == 0
    assert breakdown.discount == 0
    assert breakdown.total_price == pytest.approx(100)
