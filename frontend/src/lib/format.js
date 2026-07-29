export function money(value) {
  return `₹${Math.round(value).toLocaleString('en-IN')}`
}
