import { useMemo } from 'react'

const MAX_SUGGESTIONS = 8

// Type-to-filter dropdown shown below a tag input's text box. Lets a user
// search the real catalog product list and click/tick multiple matches
// without the box closing between picks - each click adds a tag and the
// dropdown stays open on the same query so they can keep going.
export function SuggestDropdown({ query, suggestions, selectedValues, onPick }) {
  const normalizedQuery = query.trim().toLowerCase()
  const matches = useMemo(() => {
    if (!normalizedQuery) return []
    return suggestions
      .filter(name => name.toLowerCase().includes(normalizedQuery))
      .slice(0, MAX_SUGGESTIONS)
  }, [normalizedQuery, suggestions])

  if (!matches.length) return null

  return (
    <div className="suggest-dropdown">
      {matches.map(name => {
        const picked = selectedValues.includes(name.toLowerCase())
        return (
          <button
            type="button"
            key={name}
            className={`suggest-option ${picked ? 'picked' : ''}`}
            // preventDefault on mousedown (not the click handler itself) stops
            // the button from stealing focus, so the input never blurs. The
            // actual pick happens on click, not mousedown: picking on
            // mousedown re-renders the tag list synchronously before the
            // browser's mouseup for this same click completes, which can
            // shift a different element (e.g. the new tag's Must/Preferred
            // toggle) under the mouseup and make it register as a second,
            // unintended click.
            onMouseDown={e => e.preventDefault()}
            onClick={() => onPick(name)}
          >
            <span className={`suggest-check ${picked ? 'on' : ''}`}>{picked ? '✓' : ''}</span>
            {name}
          </button>
        )
      })}
    </div>
  )
}
