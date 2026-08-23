// Mirrors backend/hampers/catalog_loader.py's "Tag" column values - the
// real per-item categories (distinct from the CSV's "Category" column,
// which only distinguishes container vs item rows).
export const hamperCategories = ['Food', 'Gourmet item', 'Merchandise']

export const MAX_HAMPER_OPTION_COUNT = 10 // mirrors HamperRequest.option_count le=10

export const initialHamperForm = {
  budget_min: 2500,
  budget_max: 2500,
  option_count: 4,
  preferred_categories: [...hamperCategories],
  // Flat string lists - unlike the snack-box wizard's must/preferred split,
  // HamperRequest has no such distinction (mandatory_products is a plain list).
  mandatory_products: [],
  excluded_products_list: [],
}

export const RUPEE = '₹'
