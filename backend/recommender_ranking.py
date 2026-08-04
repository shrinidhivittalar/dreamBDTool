from collections import Counter
from dataclasses import dataclass

try:
    from .business_rules import business_rules
    from .models import Product, Recommendation, RecommendationRequest
    from .pricing import PricingBreakdown, pricing_engine
    from .recommender_rules import _bonus_value, _closeness
except ImportError:
    from business_rules import business_rules
    from models import Product, Recommendation, RecommendationRequest
    from pricing import PricingBreakdown, pricing_engine
    from recommender_rules import _bonus_value, _closeness


@dataclass(frozen=True)
class ScoredCombination:
    score: float
    total: float
    products: list[Product]
    identities: Counter
    breakdown: PricingBreakdown


def score_combination(
    mandatory_items: list[Product],
    pool_items: list[Product],
    bonus_sum: float,
    identities: Counter,
    request: RecommendationRequest,
) -> ScoredCombination:
    products = mandatory_items + pool_items
    breakdown = pricing_engine.breakdown(products, request)
    total = breakdown.total_price
    fixed_bonus = sum(_bonus_value(product, request.preferred_products) for product in mandatory_items)
    score = _closeness(total, request.budget_min, request.budget_max) + fixed_bonus + bonus_sum
    return ScoredCombination(score=score, total=total, products=products, identities=identities, breakdown=breakdown)


def recommendation_from_score(scored: ScoredCombination, request: RecommendationRequest) -> Recommendation:
    return Recommendation(
        products=scored.products,
        total_price=round(scored.total, 2),
        remaining_budget=round(pricing_engine.remaining_after_total(request.budget_max, scored.total), 2),
        score=round(scored.score, 3),
        dad_selling_price=round(scored.breakdown.dad_selling_price, 2),
        rock_bottom_price=round(scored.breakdown.rock_bottom_price, 2),
        customization_surcharge=round(scored.breakdown.customization_surcharge, 2),
        packaging_cost=round(scored.breakdown.packaging_cost, 2),
        discount=round(scored.breakdown.discount, 2),
        packaging=business_rules.packaging_requirements(scored.products),
    )


def mandatory_only_recommendation(mandatory_items: list[Product], request: RecommendationRequest) -> Recommendation:
    breakdown = pricing_engine.breakdown(mandatory_items, request)
    total = breakdown.total_price
    fixed_bonus = sum(_bonus_value(product, request.preferred_products) for product in mandatory_items)
    score = _closeness(total, request.budget_min, request.budget_max) + fixed_bonus
    return Recommendation(
        products=mandatory_items,
        total_price=round(total, 2),
        remaining_budget=round(pricing_engine.remaining_after_total(request.budget_max, total), 2),
        score=round(score, 3),
        dad_selling_price=round(breakdown.dad_selling_price, 2),
        rock_bottom_price=round(breakdown.rock_bottom_price, 2),
        customization_surcharge=round(breakdown.customization_surcharge, 2),
        packaging_cost=round(breakdown.packaging_cost, 2),
        discount=round(breakdown.discount, 2),
        packaging=business_rules.packaging_requirements(mandatory_items),
    )


def append_budget_hint(scored: list[ScoredCombination], request: RecommendationRequest, messages: list[str]) -> None:
    if not scored:
        messages.append(
            "No valid combination has enough distinct product categories for this item count. Try lowering the item count."
        )
        return

    max_achievable = max(entry.total for entry in scored)
    min_achievable = min(entry.total for entry in scored)
    rupee = "\u20b9"
    if max_achievable < request.budget_min * 0.95:
        messages.append(
            f"The priciest valid {request.item_count}-item combination for this brief comes to "
            f"{rupee}{round(max_achievable)} - try raising the item count to get closer to your "
            f"{rupee}{round(request.budget_min)}-{rupee}{round(request.budget_max)} range."
        )
    elif min_achievable > request.budget_max * 1.05:
        messages.append(
            f"The cheapest valid {request.item_count}-item combination for this brief comes to "
            f"{rupee}{round(min_achievable)} - try lowering the item count or raising your "
            f"{rupee}{round(request.budget_min)}-{rupee}{round(request.budget_max)} range to get within budget."
        )
