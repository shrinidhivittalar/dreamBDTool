import { bestFuzzyMatch, findProductByName, FUZZY_CUTOFF, matchingCategory, textOverlaps } from './match'

export function tagsFor(form, key) {
  return form[key].split(',').map(value => value.trim()).filter(Boolean)
}

function normalize(value) {
  return value.trim().toLowerCase().replace(/[-/]/g, ' ').replace(/\s+/g, ' ')
}

// Auto-detects whether a "Must include" entry matches a known catalog
// category or product name, so the BD user typing into one consolidated
// field never has to know which backend bucket it belongs in. Tries an
// exact (case/whitespace/dash-insensitive) match first, then falls back to
// a fuzzy match (see lib/match.js::bestFuzzyMatch) so a typo'd category/
// product name still routes correctly (mirrors the backend's
// difflib-based typo suggestions for mandatory products/required
// categories). If neither matches, it's still accepted as free text (same
// fallback behavior as today) rather than blocking entry.
export function classifyMustInclude(value, { productNames = [], categoryNames = [] } = {}) {
  const target = normalize(value)
  if (categoryNames.some(name => normalize(name) === target)) return 'category'
  if (productNames.some(name => normalize(name) === target)) return 'product'
  if (bestFuzzyMatch(target, categoryNames) >= FUZZY_CUTOFF) return 'category'
  if (bestFuzzyMatch(target, productNames) >= FUZZY_CUTOFF) return 'product'
  return 'product'
}

// Splits the single "Must include" field back into the three request
// fields the backend still expects: a "must" entry becomes a
// mandatory_product or required_category depending on classification;
// a "preferred" entry always becomes a preferred_product - the backend has
// no "preferred category" concept, so a category typed as Preferred is
// still routed there rather than silently dropped.
export function splitMustInclude(mustInclude, catalogNames) {
  const mandatory_products = []
  const required_categories = []
  const preferred_products = []
  for (const entry of mustInclude) {
    if (!entry.value.trim()) continue
    if (entry.mode === 'preferred') {
      preferred_products.push(entry.value)
      continue
    }
    const kind = classifyMustInclude(entry.value, catalogNames)
    if (kind === 'category') required_categories.push(entry.value)
    else mandatory_products.push(entry.value)
  }
  return { mandatory_products, required_categories, preferred_products }
}

// Which preset (if any) the current category selection exactly matches -
// used to highlight the matching shortcut pill, or show "Custom mix" when
// the user has hand-picked something that doesn't line up with a shortcut.
// Order-independent, so checking chips in any sequence still matches.
export function matchedCategoryPreset(selectedCategories, presets) {
  const selected = new Set(selectedCategories)
  const preset = presets.find(candidate => (
    candidate.categories.length === selected.size && candidate.categories.every(category => selected.has(category))
  ))
  return preset ? preset.value : null
}

// Catches the "Sweet only + Must Include a Savoury product" conflict
// *before* the request goes out, so the user gets an actual yes/no
// decision instead of either a request that silently overrides their
// category preference or a confusing "did not match any catalog item"
// error (the product exists, it just isn't in the checked categories -
// see recommender_constraints.py::apply_catalog_filters for the backend
// side of this same override, which validator.py now also surfaces as a
// warning after the fact). Asking up front is the more honest version of
// that: the user decides whether Must Include should win, rather than
// finding out after generating.
export function findMandatoryCategoryConflicts(form, products) {
  if (!form.preferred_categories.length || !products.length) return []
  const conflicts = []
  for (const entry of form.must_include) {
    if (entry.mode !== 'must' || !entry.value.trim()) continue
    const product = findProductByName(entry.value, products)
    if (!product) continue // Might be a category name, not a product - nothing to conflict with here.
    if (!matchingCategory(product, form.preferred_categories)) {
      conflicts.push({ value: entry.value, product })
    }
  }
  return conflicts
}

// The direct self-contradiction case: the same item typed into both Must
// Include and Exclude. Unlike the category conflict above, there's no
// "which one wins" question worth asking about - it's just a mistake to
// point out and let the user fix, mirroring the backend's hard error
// (recommender_constraints.py::build_candidate_context) rather than a
// confirm-and-proceed dialog.
export function findMandatoryExcludedConflicts(form) {
  const excluded = tagsFor(form, 'excluded_products')
  if (!excluded.length) return []
  const conflicts = []
  for (const entry of form.must_include) {
    if (entry.mode !== 'must' || !entry.value.trim()) continue
    const hit = excluded.find(value => textOverlaps(entry.value, value))
    if (hit) conflicts.push({ value: entry.value, excluded: hit })
  }
  return conflicts
}

export function recommendationPayload(form, catalogNames) {
  const { mandatory_products, required_categories, preferred_products } = splitMustInclude(form.must_include, catalogNames)
  const { must_include, ...rest } = form
  return {
    ...rest,
    mandatory_products,
    required_categories,
    preferred_products,
    excluded_products: tagsFor(form, 'excluded_products'),
  }
}
