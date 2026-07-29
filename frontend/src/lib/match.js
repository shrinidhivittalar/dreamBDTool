// Mirrors backend/recommender.py's _matches: case-insensitive substring check.
function matches(value, requested) {
  return value.trim().toLowerCase().includes(requested.trim().toLowerCase())
}

export function matchesAny(value, list) {
  return list.some(entry => matches(value, entry))
}

// Mirrors backend/recommender.py's _category_match: category or any tag.
export function matchingCategory(product, categories) {
  return categories.find(category => matches(product.category, category) || product.tags.some(tag => matches(tag, category))) ?? null
}
