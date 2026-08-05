# Scoring weights and DP resolution cap - assumptions pending BD/finance
# sign-off, see BUSINESS_RULE_ASSUMPTIONS.md.
IN_HOUSE_WEIGHT = 3
HEALTHY_WEIGHT = 2
PREFERRED_WEIGHT = 5
# Item count is capped at 10; when the caller has no preference the
# recommender tries every size from 1 to this cap and keeps the best fits.
MAX_ITEM_COUNT = 10
# Caps dp_history's (items, layers, price-buckets, quota-progress) cell
# count; float32 so this stays ~200MB at the cap. Exceeding it coarsens the
# price bucket width, not correctness - see _search_pool.
CELL_BUDGET = 50_000_000
# Tried strictest-first: only fall back to a looser overlap allowance once
# the stricter one can't fill every slot, so repeats across options stay as
# rare as the catalog allows rather than jumping straight to "anything goes".
OVERLAP_LEVELS = (0.25, 0.4, 0.55, 0.7)
# A candidate only competes on diversity if its score is within this
# fraction of the best score - keeps a hunt for variety from dragging in a
# dramatically worse fit just because it doesn't overlap with the rest.
QUALITY_FLOOR_RATIO = 0.85
# Across the final `limit` (usually 5) options, no single non-mandatory
# product may appear in more than this many of them - keeps the result set
# from being "5 non-identical boxes that all secretly share the same 2-3
# products" and forces real spread across the catalog/categories.
MAX_PRODUCT_REPEAT = 2
# Number of *distinct* requested categories, not total slots - bounds the
# quota-progress dimension's multiplier the same way item_count<=20 bounds
# the price/count dimensions.
MAX_CATEGORY_GROUPS = 6
# Categories are deliberately defined in one place so the business can
# revise the grouping without changing the search algorithm. A product can
# belong to more than one group: "Healthy - Savoury", for example, consumes
# both the healthy and savoury slots in a box.
UNIQUE_CATEGORY_GROUPS = ("sweet", "savoury", "healthy")
MAX_UNIQUE_CATEGORY_GROUPS = 8
# These items are client-facing customisation choices, not default box items.
# Keep this list explicit so future opt-in catalog items are easy to add.
THEMED_CUSTOMISED_PRODUCT_MARKERS = ("theme cupcake",)
THEMED_CUSTOMISED_CATEGORY_MARKERS = ("customisation",)

# Flat packaging add-on charged once per box whenever the box's packaging
# requires a Ketchup sachet (i.e. any savory item is present) - see
# CSV column "Unnamed: 6" (Box + tissue + ketchup, 20) for where this
# number comes from. Applied via the same any()-per-box rule as
# business_rules.packaging_requirements(), not summed per savory item.
PACKAGING_SAVORY_COST = 20.0

# Exact allowlist of catalog products eligible for the White Chocolate Disc
# surcharge - the 6 base cupcake flavors, explicitly excluding Theme Cupcake.
# An allowlist (not "any cupcake") so a future themed/seasonal cupcake SKU
# doesn't silently become customizable. Matched against a whitespace/case
# -normalized product name; both spellings of "Chocolate truffle" are
# listed since the catalog row is misspelled "Chcolate truffle Cupcake".
CUSTOMIZATION_ELIGIBLE_PRODUCT_NAMES = (
    "vanilla buttercream cupcake",
    "blueberry cupcake",
    "chocolate buttercream cupcake",
    "chocolate truffle cupcake",
    "chcolate truffle cupcake",
    "red velvet cupcake",
    "choco caramel cupcake",
)
