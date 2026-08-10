// Mirrors backend/recommender.py's _matches: case-insensitive substring check.
function matches(value, requested) {
  return value.trim().toLowerCase().includes(requested.trim().toLowerCase())
}

// For the "Mandatory" badge specifically: mirrors the
// backend's exact-match-first preference (recommender_rules.py's
// _resolve_mandatory / _resolve_mandatory_exemptions) so a Must Include of
// "Samosa" only badges the exact "Samosa" product, not every other item in
// the same box whose name happens to contain "Samosa" (e.g. "Baked
// Vegetable Samosa"). Falls back to a substring match only when no product
// in this box is an exact match for that Must Include entry.
export function isMandatoryProduct(productName, mandatoryProducts, boxProductNames) {
  const target = productName.trim().toLowerCase()
  return mandatoryProducts.some(wanted => {
    const needle = wanted.trim().toLowerCase()
    if (target === needle) return true
    const hasExactInBox = boxProductNames.some(name => name.trim().toLowerCase() === needle)
    return !hasExactInBox && matches(productName, wanted)
  })
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

export const FUZZY_CUTOFF = 0.75

export function bestFuzzyMatch(target, names) {
  let best = 0
  for (const name of names) {
    const score = similarity(normalize(target), normalize(name))
    if (score > best) best = score
  }
  return best
}

// Whole-string fuzzy equality (mirrors backend/recommender_rules.py's
// _fuzzy_matches) - for "do these two typed-in fields likely refer to the
// same thing" (e.g. Must Include "Samsoa" vs Exclude "Samosa"), not for
// resolving free text to a catalog item (that stays exact/substring-first).
export function fuzzyTextMatches(a, b, cutoff = FUZZY_CUTOFF) {
  return similarity(normalize(a), normalize(b)) >= cutoff
}

// Two typed-in text fields "overlap" if either is a substring of the other,
// or they're a near-identical typo of each other - same either-direction
// check the backend uses (recommender_constraints.py) to catch e.g.
// "Samosa" (Must Include) vs "Samosa" (Exclude), "Samosa" vs "Samosa Roll",
// or "Samsoa" (typo) vs "Samosa".
export function textOverlaps(a, b) {
  return matches(a, b) || matches(b, a) || fuzzyTextMatches(a, b)
}

// Mirrors backend/recommender.py's _category_match: category or any tag.
export function matchingCategory(product, categories) {
  return categories.find(category => matches(product.category, category) || product.tags.some(tag => matches(tag, category))) ?? null
}

// Best-effort resolution of a "Must include" entry's typed text to one
// catalog product - exact name match first, then substring, then a fuzzy
// typo-tolerant match, mirroring the backend's _resolve_mandatory
// (recommender_rules.py) closely enough for a pre-flight check (the
// backend remains the source of truth if this picks the wrong product for
// an ambiguous substring/fuzzy match - this is only used to warn, never to
// silently decide what goes in the box).
export function findProductByName(name, products) {
  const target = name.trim().toLowerCase()
  return products.find(product => product.name.trim().toLowerCase() === target)
    ?? products.find(product => matches(product.name, name))
    ?? products.find(product => fuzzyTextMatches(product.name, name))
    ?? null
}
