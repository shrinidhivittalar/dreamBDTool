export function tagsFor(form, key) {
  return form[key].split(',').map(value => value.trim()).filter(Boolean)
}

export function recommendationPayload(form) {
  return {
    ...form,
    mandatory_products: tagsFor(form, 'mandatory_products'),
    preferred_products: tagsFor(form, 'preferred_products'),
    excluded_products: tagsFor(form, 'excluded_products'),
    required_categories: tagsFor(form, 'required_categories'),
  }
}
