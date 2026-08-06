// The business's current catalog taxonomy - "Healthy Sweet" is left out
// because no catalog item is tagged that way yet.
export const categories = ['Savoury', 'Healthy Savoury', 'Sweet', 'FMCG']

// Replaces the old, separately-stored "Preference" segmented control - each
// preset is just a shortcut for a specific set of category chips, not an
// independent setting, so it can never disagree with what's actually
// checked below it. "Everything" (all 4) is the true no-restriction
// default - same behavior as today's default (no categories filter, no
// sweet_preference restriction).
export const categoryPresets = [
  { value: 'sweet_only', label: 'Sweet only', categories: ['Sweet'] },
  { value: 'savory_only', label: 'Savory only', categories: ['Savoury', 'Healthy Savoury', 'FMCG'] },
  { value: 'savory_and_sweet', label: 'Savory + Sweet', categories: ['Savoury', 'Healthy Savoury', 'Sweet'] },
  { value: 'everything', label: 'Everything', categories: [...categories] },
]

export const MAX_ITEM_COUNT = 10
// Mirrors backend/recommender_config.py::MAX_OPTION_COUNT - keep in sync.
export const MAX_OPTION_COUNT = 25

export const initialForm = {
  budget_min: 100,
  budget_max: 250,
  item_count: 5,
  // 8 by default - enough spread to see real variety without a huge wall
  // of cards; the stepper in the wizard still goes up to MAX_OPTION_COUNT.
  option_count: 8,
  // Defaults to every category checked - the "Everything" preset - which
  // is the true equivalent of today's unrestricted default, not just the
  // 3-category "Savory + Sweet" preset (that would silently exclude FMCG
  // by default, a real behavior change from today).
  preferred_categories: [...categories],
  // Each entry: { value: string, mode: 'must' | 'preferred' }. Replaces the
  // old separate mandatory_products/preferred_products/required_categories
  // UI fields - see lib/briefForm.js::splitMustInclude for how a single
  // entry gets routed back to those three backend request fields.
  must_include: [],
  excluded_products: '',
  include_themed_customised: false,
}

export const RUPEE = '₹'
