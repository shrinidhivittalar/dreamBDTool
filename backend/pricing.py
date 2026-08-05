from dataclasses import dataclass

try:
    from .models import Product, RecommendationRequest
    from .recommender_config import PACKAGING_SAVORY_COST
    from .recommender_rules import _category_match, _normalized_text
except ImportError:
    from models import Product, RecommendationRequest
    from recommender_config import PACKAGING_SAVORY_COST
    from recommender_rules import _category_match, _normalized_text


def _is_savory(product: Product) -> bool:
    return _category_match(product, "savory") or _category_match(product, "savoury")


@dataclass(frozen=True)
class PricingBreakdown:
    dad_selling_price: float
    rock_bottom_price: float
    customization_surcharge: float = 0.0
    packaging_cost: float = 0.0
    discount: float = 0.0

    @property
    def total_price(self) -> float:
        # customization_surcharge is informational only (for the UI's "+ ₹50
        # customization" line) - it's already folded into dad_selling_price
        # by dad_selling_total(), so it must NOT be added again here.
        return self.dad_selling_price + self.packaging_cost - self.discount


class PricingEngine:
    """Single home for catalog, budget, surcharge, and discount math."""

    def dad_selling_price(self, product: Product) -> float:
        return product.selling_price

    def rock_bottom_price(self, product: Product) -> float:
        return product.rock_bottom_price if product.rock_bottom_price is not None else product.selling_price

    def dad_selling_total(
        self,
        products: list[Product],
        request: RecommendationRequest | None = None,
        customization_addon: Product | None = None,
    ) -> float:
        base = sum(self.dad_selling_price(product) for product in products)
        matches = self._customized_products(products, request)
        if not matches or customization_addon is None:
            return base
        # Same scope as rock_bottom_total(): the disc is a real addition to
        # this box once selected, so the "recommended price" must include it
        # too - otherwise it can read lower than the floor price, which
        # already includes it (a floor can never exceed the recommended
        # price for the same box).
        return base + len(matches) * self.dad_selling_price(customization_addon)

    def rock_bottom_total(
        self,
        products: list[Product],
        request: RecommendationRequest | None = None,
        customization_addon: Product | None = None,
    ) -> float:
        base = sum(self.rock_bottom_price(product) for product in products)
        matches = self._customized_products(products, request)
        if not matches or customization_addon is None:
            return base
        # Keeps rock_bottom_price consistent with total_price: the disc's
        # own floor price (₹39) is a real cost of the box once selected,
        # not something that should vanish from the floor estimate.
        return base + len(matches) * self.rock_bottom_price(customization_addon)

    def _customized_products(
        self,
        products: list[Product],
        request: RecommendationRequest | None,
    ) -> list[Product]:
        if not request or not request.customize_products:
            return []
        wanted = {_normalized_text(name) for name in request.customize_products}
        return [
            product for product in products
            if product.customization_eligible and _normalized_text(product.name) in wanted
        ]

    def customization_surcharge(
        self,
        products: list[Product],
        request: RecommendationRequest | None = None,
        customization_addon: Product | None = None,
    ) -> float:
        if customization_addon is None:
            return 0.0
        matches = self._customized_products(products, request)
        return len(matches) * customization_addon.selling_price

    def packaging_cost(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        # Flat charge, once per box, whenever the box's packaging requires a
        # Ketchup sachet (i.e. any savory item present) - mirrors the same
        # any()-per-box rule as business_rules.packaging_requirements(), not
        # summed per savory item.
        return PACKAGING_SAVORY_COST if any(_is_savory(product) for product in products) else 0.0

    def discount(self, products: list[Product], request: RecommendationRequest | None = None) -> float:
        return 0.0

    def budget_total(
        self,
        products: list[Product],
        request: RecommendationRequest | None = None,
        customization_addon: Product | None = None,
    ) -> float:
        subtotal = self.dad_selling_total(products, request, customization_addon)
        if request is None:
            return subtotal
        return subtotal + self.packaging_cost(products, request) - self.discount(products, request)

    def priced_total(
        self,
        products: list[Product],
        request: RecommendationRequest,
        customization_addon: Product | None = None,
    ) -> float:
        return self.breakdown(products, request, customization_addon).total_price

    def remaining_budget(
        self,
        budget_max: float,
        products: list[Product],
        request: RecommendationRequest | None = None,
        customization_addon: Product | None = None,
    ) -> float:
        total = (
            self.budget_total(products, request, customization_addon)
            if request is None
            else self.priced_total(products, request, customization_addon)
        )
        return budget_max - total

    def remaining_after_total(self, budget_max: float, total: float) -> float:
        return budget_max - total

    def price_bucket(self, product: Product, bucket_width: int = 1) -> int:
        return max(1, round(self.dad_selling_price(product) / bucket_width))

    def breakdown(
        self,
        products: list[Product],
        request: RecommendationRequest,
        customization_addon: Product | None = None,
    ) -> PricingBreakdown:
        return PricingBreakdown(
            dad_selling_price=self.dad_selling_total(products, request, customization_addon),
            rock_bottom_price=self.rock_bottom_total(products, request, customization_addon),
            customization_surcharge=self.customization_surcharge(products, request, customization_addon),
            packaging_cost=self.packaging_cost(products, request),
            discount=self.discount(products, request),
        )


pricing_engine = PricingEngine()
