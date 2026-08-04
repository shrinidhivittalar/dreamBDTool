// The business's current catalog taxonomy - "Healthy Sweet" is left out
// because no catalog item is tagged that way yet.
export const categories = ['Savoury', 'Healthy Savoury', 'Sweet', 'FMCG']

export const sweetOptions = [
  { value: 'sweet_only', label: 'Sweet only' },
  { value: 'savory_only', label: 'Savory only' },
  { value: 'savory_and_sweet', label: 'Savory + Sweet' },
]

export const MAX_ITEM_COUNT = 10

export const initialForm = {
  budget_min: 100,
  budget_max: 250,
  item_count: 4,
  no_item_count_preference: false,
  preferred_categories: [],
  mandatory_products: '',
  preferred_products: '',
  excluded_products: '',
  sweet_preference: 'savory_and_sweet',
  include_themed_customised: false,
  required_categories: '',
}

export const RUPEE = '\u20b9'
