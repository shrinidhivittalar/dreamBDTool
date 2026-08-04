export function tagsFor(form, key) {
  return form[key].split(',').map(value => value.trim()).filter(Boolean)
}

export function recommendationPayload(form) {
  const { no_item_count_preference, ...rest } = form
  return {
    ...rest,
    item_count: no_item_count_preference ? null : form.item_count,
    mandatory_products: tagsFor(form, 'mandatory_products'),
    preferred_products: tagsFor(form, 'preferred_products'),
    excluded_products: tagsFor(form, 'excluded_products'),
    required_categories: tagsFor(form, 'required_categories'),
  }
}
