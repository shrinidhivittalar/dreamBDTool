import difflib
import re

try:
    from .models import Product
    from .recommender_config import (
        HEALTHY_WEIGHT,
        IN_HOUSE_WEIGHT,
        PREFERRED_WEIGHT,
        THEMED_CUSTOMISED_CATEGORY_MARKERS,
        THEMED_CUSTOMISED_PRODUCT_MARKERS,
        UNIQUE_CATEGORY_GROUPS,
    )
except ImportError:
    from models import Product
    from recommender_config import (
        HEALTHY_WEIGHT,
        IN_HOUSE_WEIGHT,
        PREFERRED_WEIGHT,
        THEMED_CUSTOMISED_CATEGORY_MARKERS,
        THEMED_CUSTOMISED_PRODUCT_MARKERS,
        UNIQUE_CATEGORY_GROUPS,
    )


def _normalized_text(value: str) -> str:
    # Collapses "-", "/" and repeated whitespace to a single space so
    # catalog punctuation quirks (e.g. "Healthy - Savoury" vs a "Healthy
    # Savoury" filter) don't silently zero out an otherwise-valid match.
    return " ".join(re.sub(r"[-/]", " ", value).split()).lower()


def _matches(value: str, requested: str) -> bool:
    return _normalized_text(requested) in _normalized_text(value)


FUZZY_CUTOFF = 0.75


# Whole-string similarity (not the per-word scoring _suggest_names below
# uses for "did you mean" ranking) - a single typo anywhere in a short
# product/category name shouldn't sink the ratio, but this is deliberately
# looser than a real spellcheck: it's for catching that two *already-typed*
# fields likely refer to the same thing (e.g. Must Include "Samsoa" vs
# Exclude "Samosa"), not for silently resolving a name to a catalog item -
# that resolution still goes through the exact/substring-first
# _resolve_mandatory below.
def _fuzzy_matches(value: str, requested: str, cutoff: float = FUZZY_CUTOFF) -> bool:
    return difflib.SequenceMatcher(None, _normalized_text(value), _normalized_text(requested)).ratio() >= cutoff


# Strips a trailing size/variant qualifier (with or without a leading dash)
# so "Fudgy walnut brownie - mini" and "Fudgy Walnut brownie" resolve to the
# same base product - a box shouldn't carry two sizes of the same flavor.
_VARIANT_SUFFIX_RE = re.compile(
    r"\s*-?\s*\b(mini|half|small|large|full|single|double|regular)\b\s*$",
    re.IGNORECASE,
)


def _base_product_key(product: Product) -> str:
    name = product.name.strip().lower()
    while True:
        stripped = _VARIANT_SUFFIX_RE.sub("", name).strip()
        if stripped == name:
            return name
        name = stripped


# Two-word product "types" - a plain last-word split would collapse these
# into a meaningless "pop"/"pita" bucket rather than the actual dish name.
_COMPOUND_PRODUCT_TYPES = ("cake pop",)
_BRACKET_SUFFIX_RE = re.compile(r"\s*[\[(][^\])]*[\])]\s*$")

# Brand-name products (mostly FMCG) don't follow the catalog's usual
# "<flavor/variant> <type>" naming, so the last-word heuristic below sees
# "Frooti", "Maaza" and "Paper Boat - Swing" as three unrelated one-word
# types and would happily put two juice brands in the same box. They're
# all beverages, so this maps them there explicitly. Lays is chips, not a
# drink, so it's deliberately left out - pairing a drink with a bag of
# chips is a normal box, two juices is not. Keyed on the variant-stripped
# base name (lowercase), same normalization _product_type_key already
# does before falling through to the last-word heuristic.
_PRODUCT_TYPE_OVERRIDES = {
    "frooti": "beverage",
    "maaza": "beverage",
    "paper boat - swing": "beverage",
}


def _product_type_key(product: Product) -> str:
    """The dish "type" a product belongs to (Cupcake, Brownie, Bun, Puff,
    Roll, Sandwich, beverage...), independent of flavor/brand -
    "Blueberry Cupcake" and "Chocolate buttercream Cupcake" are different
    products (different `_base_product_key`) but the same type, and so are
    "Frooti" and "Maaza" (see _PRODUCT_TYPE_OVERRIDES).

    The catalog's naming convention is consistently "<flavor/variant> <type>"
    (a handful of two-word types like "cake pop" aside), so the last
    word(s) of the variant-stripped, bracket-stripped name is a reliable
    signal for most products without needing a hand-maintained mapping;
    brand-name products that don't fit that pattern get an explicit
    override instead. Used to stop a box from carrying two different
    flavors/brands of what a recipient would perceive as "the same item
    twice" (e.g. two cupcakes, two juices) - unlike _base_product_key,
    which only catches an exact flavor repeated at a different size.
    """
    override = _PRODUCT_TYPE_OVERRIDES.get(_base_product_key(product))
    if override:
        return override
    name = _BRACKET_SUFFIX_RE.sub("", _base_product_key(product)).strip()
    for compound in _COMPOUND_PRODUCT_TYPES:
        if name.endswith(compound):
            return compound
    words = name.split()
    return words[-1] if words else name


def _category_match(product: Product, category: str) -> bool:
    return _matches(product.category, category) or any(_matches(tag, category) for tag in product.tags)


def _category_bucket_match(product: Product, category: str) -> bool:
    """Matches against the discrete category-picker taxonomy (Savoury,
    Healthy Savoury, Sweet, FMCG) as mutually exclusive buckets, unlike
    _category_match's plain substring "contains" check.

    _category_match is deliberately broad elsewhere - e.g. business_rules'
    packaging rule needs a "Healthy - Savoury" item to still count as
    savory for the ketchup-sachet rule, and the diversity/cap logic needs
    it to occupy both the "savoury" and "healthy" broad slots at once. But
    when a user picks the "Savoury" category (not "Healthy Savoury") from
    the UI, they mean the plain-savoury bucket specifically - a "Healthy -
    Savoury" item satisfying it too, just because "savoury" is textually
    contained in "healthy savoury", made the two categories impossible to
    tell apart. This is used wherever a request's preferred/required
    category needs to match one specific taxonomy bucket: the category
    pool filter, the per-category quota search, and the validator's
    missing-category checks.
    """
    matched = _category_match(product, category)
    if not matched:
        return False
    target = _normalized_text(category)
    if target in ("savoury", "savory") and _category_match(product, "healthy"):
        return False
    return True


def _max_category_repeat_cap(k: int, unique_category_keys: tuple[str, ...]) -> int:
    # Only `len(unique_category_keys)` broad groups (sweet/savoury/healthy,
    # plus whatever else the catalog defines) exist at all, so a box bigger
    # than that count can never have every item in a distinct category -
    # e.g. a 4-item box against 3 groups always needs at least one repeat.
    # Spreading that repeat as evenly as the box size allows (ceil(k /
    # groups)) is what stops "1 required item per category, then 3 more
    # cupcakes on top" from passing, while still being satisfiable. Shared
    # between recommender.py (the search's own cap) and
    # recommender_constraints.py (the mandatory-item pool pre-filter, which
    # used to hard-block *any* shared category regardless of box size -
    # see build_candidate_context) so both agree on the same cap for the
    # same box.
    groups = max(1, len(unique_category_keys))
    return max(1, -(-k // groups))


def _unique_category_groups(product: Product) -> set[str]:
    """Return the broad category slots occupied by a product.

    Known broad groups intentionally collapse labels such as "In-house
    sweet" and "outsourced Sweet" into "sweet". For a future catalog
    category that is not in the configured groups, its normalized category
    label remains its own slot instead of being ignored.
    """
    groups = {group for group in UNIQUE_CATEGORY_GROUPS if _category_match(product, group)}
    if groups:
        return groups
    fallback = product.category.strip().lower()
    return {fallback} if fallback else set()



def _is_themed_or_customised(product: Product) -> bool:
    return (
        any(_matches(product.name, marker) for marker in THEMED_CUSTOMISED_PRODUCT_MARKERS)
        or any(_matches(product.category, marker) for marker in THEMED_CUSTOMISED_CATEGORY_MARKERS)
        or any(any(_matches(tag, marker) for marker in THEMED_CUSTOMISED_CATEGORY_MARKERS) for tag in product.tags)
    )


def _is_explicitly_mandatory(product: Product, mandatory_products: list[str]) -> bool:
    return any(_matches(product.name, wanted) for wanted in mandatory_products)

def _is_in_house(product: Product) -> bool:
    return "in-house" in product.sourcing.lower() or "dream a dozen" in product.vendor.lower()


def _is_healthy(product: Product) -> bool:
    return any("healthy" in tag.lower() for tag in product.tags)


def _is_preferred(product: Product, preferred: list[str]) -> bool:
    return any(_matches(product.name, wanted) for wanted in preferred)


def _bonus_value(product: Product, preferred: list[str]) -> float:
    return (
        IN_HOUSE_WEIGHT * _is_in_house(product)
        + HEALTHY_WEIGHT * _is_healthy(product)
        + PREFERRED_WEIGHT * _is_preferred(product, preferred)
    )


def _closeness(total: float, budget_min: float, budget_max: float) -> float:
    """Reward staying within [budget_min, budget_max]; penalize drifting
    outside on either side.

    No branch discards a total - falling outside the range only lowers the
    score. There is deliberately no hard cutoff.
    """
    if budget_min <= total <= budget_max:
        midpoint = (budget_min + budget_max) / 2
        span = (budget_max - budget_min) or 1
        return 100 - 10 * abs(total - midpoint) / span
    if total < budget_min:
        return 95 - 40 * (budget_min - total) / budget_min
    return 95 - 40 * (total - budget_max) / budget_max


def _suggest_names(wanted: str, names: list[str], limit: int = 3, cutoff: float = 0.6) -> list[str]:
    """Suggest catalog names close to `wanted`, matching on individual words
    too (not just whole-string similarity) since catalog names are often
    multi-word ("Fudgy Walnut brownie") while a typo'd request is usually
    just one misspelled word ("Brwonie").
    """
    whole = difflib.get_close_matches(wanted, names, n=limit, cutoff=cutoff)
    if whole:
        return whole
    scored: list[tuple[float, str]] = []
    for name in names:
        best = max(
            (difflib.SequenceMatcher(None, wanted.lower(), word.lower()).ratio() for word in name.split()),
            default=0.0,
        )
        if best >= cutoff:
            scored.append((best, name))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    seen: list[str] = []
    for _, name in scored:
        if name not in seen:
            seen.append(name)
        if len(seen) == limit:
            break
    return seen


def _resolve_mandatory(candidates: list[Product], requested: list[str]) -> set[int]:
    """Resolve each mandatory product name to exactly one catalog index.

    Unlike the lenient substring filters used elsewhere, a mandatory
    product must be unambiguous: it either names one product exactly, or
    substring-matches exactly one candidate. Anything else is a request
    error, since silently including zero or several products would break
    the caller's expectation of "this exact item is in every box."
    """
    resolved: set[int] = set()
    for wanted in requested:
        needle = wanted.strip().lower()
        exact = [i for i, product in enumerate(candidates) if product.name.strip().lower() == needle]
        matches = exact if exact else [i for i, product in enumerate(candidates) if _matches(product.name, wanted)]
        if len(matches) != 1:
            if not matches:
                names = [product.name for product in candidates]
                suggestions = _suggest_names(wanted, names)
                if suggestions:
                    raise ValueError(
                        f"Mandatory product '{wanted}' did not match any catalog item. "
                        f"Did you mean: {', '.join(suggestions)}?"
                    )
            raise ValueError(f"Mandatory product '{wanted}' must match exactly one catalog item (found {len(matches)}).")
        resolved.add(matches[0])
    return resolved


