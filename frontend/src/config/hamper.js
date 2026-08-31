// Mirrors backend/hampers/catalog_loader.py's "Tag" column values - the
// real per-item categories (distinct from the CSV's "Category" column,
// which only distinguishes container vs item rows).
export const hamperCategories = ['Food', 'Gourmet item', 'Merchandise', 'Nuts']

export const MAX_HAMPER_OPTION_COUNT = 10 // mirrors HamperRequest.option_count le=10
export const MAX_ITEMS_PER_BOX = 6 // mirrors HamperRequest.items_per_box le=6

export const initialHamperForm = {
  budget_min: 2500,
  budget_max: 2500,
  option_count: 4,
  // null = no constraint, let the engine pick the best size for the budget
  // (matches HamperRequest.items_per_box's default of None on the backend).
  items_per_box: null,
  preferred_categories: [...hamperCategories],
  // Flat string lists - unlike the snack-box wizard's must/preferred split,
  // HamperRequest has no such distinction (mandatory_products is a plain list).
  mandatory_products: [],
  excluded_products_list: [],
}

export const RUPEE = '₹'
