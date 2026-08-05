export function MustIncludeField({ entries, placeholder, onAdd, onRemove, onToggleMode }) {
  return (
    <div className="tag-input input">
      {entries.map((entry, index) => (
        <span className="tag must-include-tag" key={`${entry.value}-${index}`}>
          {entry.value}
          <button
            type="button"
            className={`must-mode-toggle must-mode-${entry.mode}`}
            onClick={() => onToggleMode(index)}
            aria-label={`Toggle ${entry.value} between Must and Preferred`}
          >
            {entry.mode === 'preferred' ? 'Preferred' : 'Must'}
          </button>
          <button type="button" onClick={() => onRemove(index)} aria-label={`Remove ${entry.value}`}>×</button>
        </span>
      ))}
      <input
        placeholder={placeholder}
        onKeyDown={e => {
          if ((e.key === 'Enter' || e.key === ',') && e.currentTarget.value.trim()) {
            e.preventDefault()
            onAdd(e.currentTarget.value)
            e.currentTarget.value = ''
          }
        }}
      />
    </div>
  )
}
