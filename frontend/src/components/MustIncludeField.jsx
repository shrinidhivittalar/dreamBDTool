import { useState } from 'react'
import { SuggestDropdown } from './SuggestDropdown'

export function MustIncludeField({ entries, placeholder, suggestions = [], onAdd, onRemove, onToggleMode }) {
  const [query, setQuery] = useState('')
  const selectedValues = entries.map(entry => entry.value.toLowerCase())

  const commit = value => {
    if (!value.trim()) return
    onAdd(value)
    setQuery('')
  }

  // Ticking a suggestion adds/removes it without clearing the search box,
  // so the dropdown stays open on the same query and multiple matches can
  // be ticked one after another (e.g. all products matching "brownie").
  const togglePick = value => {
    const index = entries.findIndex(entry => entry.value.toLowerCase() === value.toLowerCase())
    if (index >= 0) onRemove(index)
    else onAdd(value)
  }

  return (
    <div className="tag-input-wrap">
      {entries.length > 0 && (
        <div className="tag-row">
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
        </div>
      )}
      {/* Search box lives in its own fixed-position row, separate from the
          tag row above - if the input sat inline with the tags, adding a
          tag could wrap the input onto a new line and shift the dropdown
          out from under the user's next click (see git history for the
          mis-click this caused when picking a second suggestion). */}
      <div className="tag-input input">
        <input
          placeholder={placeholder}
          value={query}
          onChange={e => setQuery(e.target.value)}
          onKeyDown={e => {
            if ((e.key === 'Enter' || e.key === ',') && e.currentTarget.value.trim()) {
              e.preventDefault()
              commit(e.currentTarget.value)
            }
          }}
          onBlur={e => {
            // Commits whatever's still sitting in the box uncommitted when
            // focus leaves it (e.g. clicking straight to "Generate
            // recommendations" without pressing Enter/comma first) - otherwise
            // that text is silently dropped and the rule it represents never
            // reaches the request at all.
            if (e.currentTarget.value.trim()) commit(e.currentTarget.value)
          }}
        />
      </div>
      <SuggestDropdown
        query={query}
        suggestions={suggestions}
        selectedValues={selectedValues}
        onPick={togglePick}
      />
    </div>
  )
}
