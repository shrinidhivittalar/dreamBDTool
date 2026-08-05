export function tagsFor(form, key) {
  return form[key].split(',').map(value => value.trim()).filter(Boolean)
}

function normalize(value) {
  return value.trim().toLowerCase().replace(/[-/]/g, ' ').replace(/\s+/g, ' ')
}

function levenshtein(a, b) {
  const rows = a.length + 1
  const cols = b.length + 1
  const dp = Array.from({ length: rows }, () => new Array(cols).fill(0))
  for (let i = 0; i < rows; i++) dp[i][0] = i
  for (let j = 0; j < cols; j++) dp[0][j] = j
  for (let i = 1; i < rows; i++) {
    for (let j = 1; j < cols; j++) {
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1]
        : 1 + Math.min(dp[i - 1][j - 1], dp[i - 1][j], dp[i][j - 1])
    }
  }
  return dp[rows - 1][cols - 1]
}

// 1 = identical, 0 = completely different - lets a single-letter typo
// ("Healthy Savory" vs catalog's "Healthy Savoury") still classify
// correctly instead of silently falling through to the product bucket.
function similarity(a, b) {
  const longer = Math.max(a.length, b.length)
  if (longer === 0) return 1
  return (longer - levenshtein(a, b)) / longer
}

const FUZZY_CUTOFF = 0.75

function bestFuzzyMatch(target, names) {
  let best = 0
  for (const name of names) {
    const score = similarity(target, normalize(name))
    if (score > best) best = score
  }
  return best
}

// Auto-detects whether a "Must include" entry matches a known catalog
// category or product name, so the BD user typing into one consolidated
// field never has to know which backend bucket it belongs in. Tries an
// exact (case/whitespace/dash-insensitive) match first, then falls back to
// a fuzzy match so a typo'd category/product name still routes correctly
// (mirrors the backend's difflib-based typo suggestions for mandatory
// products/required categories). If neither matches, it's still accepted
// as free text (same fallback behavior as today) rather than blocking entry.
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
