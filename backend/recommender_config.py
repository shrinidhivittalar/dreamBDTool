# Scoring weights and DP resolution cap - assumptions pending BD/finance
# sign-off, see BUSINESS_RULE_ASSUMPTIONS.md.
IN_HOUSE_WEIGHT = 3
HEALTHY_WEIGHT = 2
PREFERRED_WEIGHT = 5
# Item count is capped at 10; when the caller has no preference the
# recommender tries every size from 1 to this cap and keeps the best fits.
MAX_ITEM_COUNT = 10
# Caller-facing cap on RecommendationRequest.option_count ("show as many
# options as possible" is a real request, not literally unbounded - each
# extra option is another slot the diversity selector has to fill from an
# already-scored candidate pool, and result cards have to render on one
# screen). 25 is generous for a 4-10 item box against this catalog's size
# without letting a request ask for hundreds.
MAX_OPTION_COUNT = 25
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
# Tried strictest-first, same escalation pattern as OVERLAP_LEVELS/the
# repeat-cap ladder below: a strong per-item scoring bonus (e.g.
# IN_HOUSE_WEIGHT) can mean every genuinely different alternative to the
# single best-scoring item in a category falls outside a single fixed 0.85
# floor, so the selector never even considers them for diversity and falls
# straight through to "drop the repeat cap" instead - the exact "same top
# item in every option" complaint this ladder exists to prevent. Loosening
# the floor step by step (still trying the strictest repeat-cap-respecting
# tier at each floor before moving on) pulls in real alternatives before
# giving up on variety, at the cost of a few options being further from
# the best score than 0.85 once the catalog forces it.
QUALITY_FLOOR_RATIO = 0.85
QUALITY_FLOOR_LEVELS = (0.85, 0.65, 0.45, 0.25)
# Across the final `limit` (usually 5) options, no single non-mandatory
# product may appear in more than this many of them - keeps the result set
# from being "5 non-identical boxes that all secretly share the same 2-3
# products" and forces real spread across the catalog/categories.
MAX_PRODUCT_REPEAT = 2
# Same idea, one level up: no single vendor may appear in more than this
# many of the final options, so a vendor that happens to score well (or is
# the only source for a required category) doesn't quietly show up in
# every single option. Looser than MAX_PRODUCT_REPEAT since a vendor
# legitimately supplying several distinct good products is normal; this
# only kicks in once one vendor is dominating the *result set*, not the
# catalog. Same graduated relaxation as the product cap applies, so this
# never blocks a box from being returned when a vendor genuinely has no
# alternative (e.g. HealthyChef is the catalog's only Healthy Savoury
# source) - it only spreads picks when an alternative exists.
MAX_VENDOR_REPEAT = 3
# Sibling substitution (recommender.py's _generate_scored_combinations)
# reintroduces same-price-bucket/same-category alternatives that the
# search's tie-breaking silently discards (e.g. every FMCG item costs the
# same, so the search only ever emits its single best-bonus pick - Frooti,
# say - never Lays or Maaza - unless this step swaps one in). Running it
# is not optional: skipping it once the search returns "enough" combos
# (tried once, briefly) still left every one of those combos sharing that
# same narrow FMCG/etc pick, which is exactly the "same product in every
# option" bug this exists to prevent.
#
# Bounded to an even stride sample of this many base combos (see
# recommender.py for why an even stride, not "top N by score") - the
# category-unique search can already emit thousands of combos for a single
# item count, and _recommend_any_count re-runs this whole step once per
# item size (1..10), so substituting every position of every combo isn't
# viable (measured 20+ seconds across all 10 sizes without this cap).
MAX_SIBLING_BASE_COMBOS = 60
# Also capped per (combo, position) - without this, a single position with
# many same-price-bucket/same-category siblings (a bread roll with a dozen
# near-identical options, say) can dominate that one combo's share of the
# work before ever reaching the position actually causing a repeat (e.g.
# the FMCG slot).
MAX_SIBLINGS_PER_POSITION = 3
# Sibling substitution used to match on price_bucket(width=1) - i.e. the
# *exact* rounded rupee price. Most catalog items have a genuinely unique
# price (see e.g. Savoury: 22, 28.6, 48.4, 55...), so the cheapest item in
# a category (often the DP's natural pick, since it leaves more budget for
# everything else) frequently had *zero* same-price siblings - confirmed
# live: "Bombay Khari" (Rs.22) and "Fudgy walnut brownie - mini" (a cheap
# Sweet) both appeared in every single returned option because there was
# nothing to substitute in. A fixed-width bucket doesn't fix this either -
# it just moves the problem to the bucket edges (Rs.22 and Rs.28.6 land in
# *different* width-15 buckets despite being Rs.6.6 apart, purely because
# they straddle a grid line). A direct rupee tolerance has no such edges:
# any two items within SIBLING_PRICE_TOLERANCE of each other are
# considered budget-neutral swaps, however their prices happen to fall.
# The real total price is still what budget-closeness scoring judges the
# final combo on, so a same-tier swap can't silently make a box drift far
# off budget.
SIBLING_PRICE_TOLERANCE = 15.0
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
