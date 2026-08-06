from collections import Counter

try:
    from .business_rules import business_rules, _category_bucket_match, _category_match, _is_themed_or_customised
    from .models import Recommendation, RecommendationRequest, ValidationIssue
    from .recommender_rules import _is_explicitly_mandatory
except ImportError:
    from business_rules import business_rules, _category_bucket_match, _category_match, _is_themed_or_customised
    from models import Recommendation, RecommendationRequest, ValidationIssue
    from recommender_rules import _is_explicitly_mandatory


MAX_DISPLAY_ITEMS = 10
DISC_MARKERS = ("disc", "edible print")


def _issue(severity: str, code: str, message: str, option_index: int | None = None) -> ValidationIssue:
    return ValidationIssue(severity=severity, code=code, message=message, option_index=option_index)


def _has_disc_product(recommendation: Recommendation) -> bool:
    return any(any(marker in product.name.lower() for marker in DISC_MARKERS) for product in recommendation.products)


def validate_recommendation(recommendation: Recommendation, request: RecommendationRequest, option_index: int) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    products = recommendation.products

    if len(products) > MAX_DISPLAY_ITEMS:
        issues.append(_issue(
            "error",
            "too_many_items",
            f"Recommendation has {len(products)} items; maximum displayable item count is {MAX_DISPLAY_ITEMS}.",
            option_index,
        ))

    if recommendation.total_price > request.budget_max:
        issues.append(_issue(
            "warning",
            "budget_exceeded",
            f"Recommendation total {recommendation.total_price} exceeds budget max {request.budget_max}.",
            option_index,
        ))

    if recommendation.remaining_budget != round(request.budget_max - recommendation.total_price, 2):
        issues.append(_issue(
            "error",
            "remaining_budget_mismatch",
            "Remaining budget does not match budget max minus total price.",
            option_index,
        ))

    if request.mandatory_products:
        for wanted in request.mandatory_products:
            if not any(wanted.strip().lower() in product.name.strip().lower() for product in products):
                issues.append(_issue("error", "missing_mandatory_product", f"Mandatory product '{wanted}' is missing.", option_index))

    for excluded in request.excluded_products:
        if any(excluded.strip().lower() in product.name.strip().lower() for product in products):
            issues.append(_issue("error", "excluded_product_present", f"Excluded product '{excluded}' is present.", option_index))

    # A product that violates sweet_preference/preferred_categories but was
    # explicitly named in Must Include isn't a bug to block on - apply_catalog_filters
    # (recommender_constraints.py) deliberately lets Must Include override
    # these soft preferences, the same way it already overrides the
    # themed/customised default. What the user does need to see is *that*
    # the override happened, since it's not obvious from the box alone why
    # a "Sweet only" brief contains a Savoury item - hence the warning
    # instead of either silently saying nothing or hard-blocking the result.
    non_sweet_present = [product for product in products if not _category_match(product, "sweet")]
    sweet_present = [product for product in products if _category_match(product, "sweet")]
    if request.sweet_preference == "sweet_only" and non_sweet_present:
        overridden = [p for p in non_sweet_present if _is_explicitly_mandatory(p, request.mandatory_products)]
        if len(overridden) == len(non_sweet_present):
            names = ", ".join(p.name for p in overridden)
            issues.append(_issue("warning", "mandatory_overrides_preference", f"'{names}' isn't Sweet, but was kept because it's a Must Include item.", option_index))
        else:
            issues.append(_issue("error", "non_sweet_product_present", "Non-sweet product present despite sweet-only preference.", option_index))
    if request.sweet_preference == "savory_only" and sweet_present:
        overridden = [p for p in sweet_present if _is_explicitly_mandatory(p, request.mandatory_products)]
        if len(overridden) == len(sweet_present):
            names = ", ".join(p.name for p in overridden)
            issues.append(_issue("warning", "mandatory_overrides_preference", f"'{names}' is Sweet, but was kept because it's a Must Include item.", option_index))
        else:
            issues.append(_issue("error", "sweet_product_present", "Sweet product present despite savory-only preference.", option_index))

    for required_category in request.required_categories:
        if not any(_category_bucket_match(product, required_category) for product in products):
            issues.append(_issue("error", "missing_required_category", f"Required category '{required_category}' is missing.", option_index))

    for preferred_category in request.preferred_categories:
        if products and not any(_category_bucket_match(product, preferred_category) for product in products):
            issues.append(_issue("warning", "preferred_category_missing", f"Preferred category '{preferred_category}' is not represented.", option_index))

    if request.preferred_categories:
        off_category_mandatory = [
            product for product in products
            if _is_explicitly_mandatory(product, request.mandatory_products)
            and not any(_category_bucket_match(product, category) for category in request.preferred_categories)
        ]
        if off_category_mandatory:
            names = ", ".join(product.name for product in off_category_mandatory)
            issues.append(_issue(
                "warning",
                "mandatory_overrides_preference",
                f"'{names}' doesn't match your selected categories, but was kept because it's a Must Include item.",
                option_index,
            ))

    empty_category_products = [product.name for product in products if not product.category and not product.tags]
    if empty_category_products:
        issues.append(_issue(
            "warning",
            "invalid_category",
            f"Product(s) lack category/tag data: {', '.join(empty_category_products)}.",
            option_index,
        ))

    packaging_counts = Counter(item.name for item in recommendation.packaging)
    if packaging_counts["Ketchup sachet"] > 1:
        issues.append(_issue("error", "duplicate_ketchup", "More than one ketchup sachet was applied.", option_index))

    expected_packaging = business_rules.packaging_requirements(products)
    if Counter(item.name for item in expected_packaging) != packaging_counts:
        issues.append(_issue("error", "packaging_mismatch", "Packaging does not match selected products.", option_index))

    if _has_disc_product(recommendation) and not request.include_themed_customised:
        issues.append(_issue("error", "disc_customization_without_opt_in", "Disc/edible-print customization appears without customization opt-in.", option_index))

    if not request.include_themed_customised and any(_is_themed_or_customised(product) for product in products):
        issues.append(_issue("error", "customization_without_opt_in", "Customised product appears without customization opt-in.", option_index))

    return issues


def validate_recommendations(recommendations: list[Recommendation], request: RecommendationRequest) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    for index, recommendation in enumerate(recommendations, start=1):
        issues.extend(validate_recommendation(recommendation, request, index))
    return issues


def blocking_errors(issues: list[ValidationIssue]) -> list[ValidationIssue]:
    return [issue for issue in issues if issue.severity == "error"]
