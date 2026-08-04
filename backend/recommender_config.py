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
