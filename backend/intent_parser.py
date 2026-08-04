import re
from dataclasses import dataclass, field

try:
    from .models import IntentParseResponse, RecommendationRequest
except ImportError:
    from models import IntentParseResponse, RecommendationRequest


CATEGORY_KEYWORDS = {
    "Healthy": ("healthy", "better for you", "low calorie", "low-calorie"),
    "Savoury": ("savoury", "savory", "snack", "snacks", "namkeen", "samosa", "sandwich"),
    "Sweet": ("sweet", "dessert", "desserts", "brownie", "cupcake", "cookie", "cake"),
}

CUSTOMIZATION_KEYWORDS = ("custom", "customised", "customized", "personalised", "personalized", "logo", "theme", "themed")
NO_CUSTOMIZATION_KEYWORDS = ("no custom", "without custom", "no customization", "no customisation", "no logo", "plain")
SWEET_ONLY_KEYWORDS = ("sweet only", "only sweet", "dessert only")
SAVORY_ONLY_KEYWORDS = ("savoury only", "savory only", "only savoury", "only savory", "no sweet", "without sweet", "avoid sweet", "not sweet")


@dataclass(frozen=True)
class ParsedIntent:
    budget_min: float
    budget_max: float
    item_count: int | None
    preferred_categories: list[str] = field(default_factory=list)
    sweet_preference: str = "savory_and_sweet"
    include_themed_customised: bool = False
    preferred_products: list[str] = field(default_factory=list)
    required_categories: list[str] = field(default_factory=list)
    confidence: float = 0.35
    notes: list[str] = field(default_factory=list)

    def to_request(self) -> RecommendationRequest:
        return RecommendationRequest(
            budget_min=self.budget_min,
            budget_max=self.budget_max,
            item_count=self.item_count,
            preferred_categories=self.preferred_categories,
            preferred_products=self.preferred_products,
            required_categories=self.required_categories,
            sweet_preference=self.sweet_preference,
            include_themed_customised=self.include_themed_customised,
        )

    def filters(self) -> dict[str, object]:
        return {
            "budget": self.budget_max,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "item_count": self.item_count,
            "categories": self.preferred_categories,
            "preference": self.sweet_preference,
            "customization": self.include_themed_customised,
            "preferred_products": self.preferred_products,
            "required_categories": self.required_categories,
        }


def _normalized(text: str) -> str:
    return text.strip().lower().replace("?", " rs ")


def _parse_budget(text: str, default_min: float) -> tuple[float, float, list[str], float]:
    notes: list[str] = []
    confidence = 0.0
    patterns = [
        r"(?:under|below|less than|upto|up to|max|maximum|within)\s*(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)",
        r"(?:rs\.?|inr)\s*(\d+(?:\.\d+)?)\s*(?:or less|max|maximum)?",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            budget = float(match.group(1))
            return default_min, budget, notes, 0.25

    range_match = re.search(r"(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)\s*(?:-|to)\s*(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)", text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return min(low, high), max(low, high), notes, 0.3

    any_number = re.search(r"(?:rs\.?|inr)?\s*(\d+(?:\.\d+)?)", text)
    if any_number:
        budget = float(any_number.group(1))
        notes.append("Interpreted the first amount as the maximum budget.")
        return default_min, budget, notes, 0.15

    notes.append("No budget found; used the default budget range.")
    return default_min, 1000.0, notes, confidence


def _parse_item_count(text: str, default_item_count: int | None) -> tuple[int | None, float]:
    direct = re.search(r"(\d+)\s*(?:items?|pcs|pieces|products?|boxes|hampers?)", text)
    if direct:
        return max(1, min(10, int(direct.group(1)))), 0.15
    described = re.search(r"(\d+)(?:\s+\w+){0,4}\s+(?:items?|pcs|pieces|products?|boxes|hampers?)", text)
    if described:
        return max(1, min(10, int(described.group(1)))), 0.15
    if "hamper" in text or "box" in text:
        return default_item_count, 0.05
    return default_item_count, 0.0


def _parse_categories(text: str) -> tuple[list[str], float]:
    categories = [category for category, words in CATEGORY_KEYWORDS.items() if any(word in text for word in words)]
    return categories, 0.15 if categories else 0.0


def _parse_sweet_preference(text: str) -> tuple[str, float]:
    if any(keyword in text for keyword in SWEET_ONLY_KEYWORDS):
        return "sweet_only", 0.15
    if any(keyword in text for keyword in SAVORY_ONLY_KEYWORDS):
        return "savory_only", 0.15
    return "savory_and_sweet", 0.0


def _parse_customization(text: str) -> tuple[bool, float]:
    if any(keyword in text for keyword in NO_CUSTOMIZATION_KEYWORDS):
        return False, 0.1
    if any(keyword in text for keyword in CUSTOMIZATION_KEYWORDS):
        return True, 0.1
    return False, 0.0


def parse_intent(text: str, default_item_count: int | None = None, default_budget_min: float = 1) -> ParsedIntent:
    normalized = _normalized(text)
    budget_min, budget_max, notes, budget_confidence = _parse_budget(normalized, default_budget_min)
    item_count, item_confidence = _parse_item_count(normalized, default_item_count)
    categories, category_confidence = _parse_categories(normalized)
    sweet_preference, sweet_confidence = _parse_sweet_preference(normalized)
    include_custom, custom_confidence = _parse_customization(normalized)

    confidence = min(0.95, 0.25 + budget_confidence + item_confidence + category_confidence + sweet_confidence + custom_confidence)
    return ParsedIntent(
        budget_min=budget_min,
        budget_max=budget_max,
        item_count=item_count,
        preferred_categories=categories,
        sweet_preference=sweet_preference,
        include_themed_customised=include_custom,
        confidence=confidence,
        notes=notes,
    )


def parse_intent_response(text: str, default_item_count: int | None = None, default_budget_min: float = 1) -> IntentParseResponse:
    parsed = parse_intent(text, default_item_count=default_item_count, default_budget_min=default_budget_min)
    return IntentParseResponse(
        filters=parsed.filters(),
        recommendation_request=parsed.to_request(),
        confidence=parsed.confidence,
        notes=parsed.notes,
    )
