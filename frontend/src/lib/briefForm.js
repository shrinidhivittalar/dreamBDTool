export function tagsFor(form, key) {
  return form[key].split(',').map(value => value.trim()).filter(Boolean)
}

function normalize(value) {
  return value.trim().toLowerCase().replace(/[-/]/g, ' ').replace(/\s+/g, ' ')
}

// Auto-detects whether a "Must include" entry matches a known catalog
// category or product name, so the BD user typing into one consolidated
// field never has to know which backend bucket it belongs in. Falls back
// to treating it as a product (same as today's free-text behavior) when it
// matches neither - this keeps typos/unlisted items from being blocked.
export function classifyMustInclude(value, { productNames = [], categoryNames = [] } = {}) {
  const target = normalize(value)
  if (categoryNames.some(name => normalize(name) === target)) return 'category'
  if (productNames.some(name => normalize(name) === target)) return 'product'
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
