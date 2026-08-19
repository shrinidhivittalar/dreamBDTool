import { useState } from 'react'
import { SuggestDropdown } from './SuggestDropdown'

export function TagField({ tags, placeholder, suggestions = [], onAdd, onRemove }) {
  const [query, setQuery] = useState('')
  const selectedValues = tags.map(tag => tag.toLowerCase())

  const commit = value => {
    if (!value.trim()) return
    onAdd(value)
    setQuery('')
  }

  // Ticking a suggestion adds/removes it without clearing the search box,
  // so the dropdown stays open on the same query and multiple matches can
  // be ticked one after another.
  const togglePick = value => {
    const existing = tags.find(tag => tag.toLowerCase() === value.toLowerCase())
    if (existing) onRemove(existing)
    else onAdd(value)
  }

  return (
    <div className="tag-input-wrap">
      {tags.length > 0 && (
        <div className="tag-row">
          {tags.map(tag => (
            <span className="tag" key={tag}>
              {tag}
              <button type="button" onClick={() => onRemove(tag)}>×</button>
            </span>
          ))}
        </div>
      )}
      {/* Search box lives in its own fixed-position row, separate from the
          tag row above - if the input sat inline with the tags, adding a
          tag could wrap the input onto a new line and shift the dropdown
          out from under the user's next click. */}
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
