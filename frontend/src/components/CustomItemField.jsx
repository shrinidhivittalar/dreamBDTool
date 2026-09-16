import { useState } from 'react'

const RUPEE = '₹'

// A one-off product that doesn't exist in the catalog, added by a BD user
// for a single client's ask - forced into every generated box for that one
// request only, never saved anywhere. Shared between the Snack Box and
// Hamper wizards; `showDimensions` is the only real difference between the
// two (hamper items can optionally carry length/breadth/height for fit
// checking, snack-box items never need dimensions at all).
export function CustomItemField({ items, categories, showDimensions = false, onAdd, onRemove }) {
  const [open, setOpen] = useState(false)
  const [name, setName] = useState('')
  const [price, setPrice] = useState('')
  const [category, setCategory] = useState('')
  const [length, setLength] = useState('')
  const [breadth, setBreadth] = useState('')
  const [height, setHeight] = useState('')
  const [error, setError] = useState('')

  function reset() {
    setName('')
    setPrice('')
    setCategory('')
    setLength('')
    setBreadth('')
    setHeight('')
    setError('')
  }

  function handleAdd() {
    const missing = []
    if (name.trim().length === 0) missing.push('item name')
    if (!(Number(price) > 0)) missing.push('price')
    if (category.length === 0) missing.push('category')
    if (missing.length > 0) {
      setError(`Please add: ${missing.join(', ')}`)
      return
    }
    setError('')
    onAdd({
      name: name.trim(),
      price: Number(price),
      category,
      ...(showDimensions
        ? {
            length_in: length === '' ? null : Number(length),
            breadth_in: breadth === '' ? null : Number(breadth),
            height_in: height === '' ? null : Number(height),
          }
        : {}),
    })
    reset()
    setOpen(false)
  }

  return (
    <div className="custom-item-field">
      {items.length > 0 && (
        <div className="tag-row mb-2">
          {items.map((item, index) => (
            <span className="tag custom-item-tag" key={`${item.name}-${index}`}>
              {item.name} · {RUPEE}{item.price} · {item.category}
              <button type="button" onClick={() => onRemove(index)} aria-label={`Remove ${item.name}`}>×</button>
            </span>
          ))}
        </div>
      )}
      {!open ? (
        <button type="button" className="pill" onClick={() => setOpen(true)}>+ Add a one-off item</button>
      ) : (
        <div className="custom-item-form">
          <div className="custom-item-form-row">
            <input className="input" placeholder="Item name" value={name} onChange={e => setName(e.target.value)} />
            <label className="input flex items-center gap-1">
              <span>{RUPEE}</span>
              <input
                type="number"
                placeholder="Price"
                className="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none"
                value={price}
                onChange={e => setPrice(e.target.value)}
              />
            </label>
          </div>
          <div className="custom-item-category-picker">
            {categories.map(cat => (
              <button
                type="button"
                key={cat}
                className={`preset-pill ${category === cat ? 'matched' : ''}`}
                onClick={() => setCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
          {showDimensions && (
            <div className="custom-item-form-row">
              <input className="input" type="number" placeholder="Length, inches (optional)" value={length} onChange={e => setLength(e.target.value)} />
              <input className="input" type="number" placeholder="Breadth, inches (optional)" value={breadth} onChange={e => setBreadth(e.target.value)} />
              <input className="input" type="number" placeholder="Height, inches (optional)" value={height} onChange={e => setHeight(e.target.value)} />
            </div>
          )}
          {showDimensions && (
            <p className="field-note">Dimensions are in inches. Leave blank if you don't know them.</p>
          )}
          {error && <p className="field-error">{error}</p>}
          <div className="custom-item-form-actions">
            <button type="button" className="pill" onClick={() => { setOpen(false); reset() }}>Cancel</button>
            <button type="button" className="pill" onClick={handleAdd}>Add item</button>
          </div>
        </div>
      )}
    </div>
  )
}
