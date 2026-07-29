export function MultiSelect({ items, selected, onToggle }) {
  return (
    <div className="flex flex-wrap gap-2">
      {items.map(item => (
        <button
          type="button"
          key={item}
          className={`pill ${selected.includes(item) ? 'active' : ''}`}
          onClick={() => onToggle(item)}
        >
          {selected.includes(item) ? '✓ ' : ''}{item}
        </button>
      ))}
    </div>
  )
}
