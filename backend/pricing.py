from dataclasses import dataclass

try:
    from .models import Product, RecommendationRequest
except ImportError:
    from models import Product, RecommendationRequest


@dataclass(frozen=True)
class PricingBreakdown:
    dad_selling_price: float
    rock_bottom_price: float
    customization_surcharge: float = 0.0
    packaging_cost: float = 0.0
    discount: float = 0.0

    @property
    def total_price(self) -> float:
        return self.dad_selling_price + self.customization_surcharge + self.packaging_cost - self.discount


class PricingEngine:
    """Single home for catalog, budget, surcharge, and discount math."""

    def dad_selling_price(self, product: Product) -> float:
        return product.selling_price

    def rock_bottom_price(self, product: Product) -> float:
        return product.rock_bottom_price if product.rock_bottom_price is not None else product.selling_price

    def dad_selling_total(self, products: list[Product]) -> float:
        return sum(self.dad_selling_price(product) for product in products)

    def rock_bottom_total(self, products: list[Product]) -> float:
        return sum(self.rock_bottom_price(product) for product in products)

    def customization_surcharge(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        return 0.0

    def packaging_cost(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        return 0.0

    def discount(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        return 0.0

    def budget_total(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        subtotal = self.dad_selling_total(products)
        if request is None:
            return subtotal
        return subtotal + self.customization_surcharge(products, request) + self.packaging_cost(products, request) - self.discount(products, request)

    def priced_total(self, products: list[Product], request: RecommendationRequest) -> float:
        return self.breakdown(products, request).total_price

    def remaining_budget(self, budget_max: float, products: list[Product], request: RecommendationRequest | None = None) -> float:
        total = self.budget_total(products, request) if request is None else self.priced_total(products, request)
        return budget_max - total

    def remaining_after_total(self, budget_max: float, total: float) -> float:
        return budget_max - total

    def price_bucket(self, product: Product, bucket_width: int = 1) -> int:
        return max(1, round(self.dad_selling_price(product) / bucket_width))

    def breakdown(self, products: list[Product], request: RecommendationRequest) -> PricingBreakdown:
        return PricingBreakdown(
            dad_selling_price=self.dad_selling_total(products),
            rock_bottom_price=self.rock_bottom_total(products),
            customization_surcharge=self.customization_surcharge(products, request),
            packaging_cost=self.packaging_cost(products, request),
            discount=self.discount(products, request),
        )


pricing_engine = PricingEngine()
