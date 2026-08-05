export function TagField({ tags, placeholder, onAdd, onRemove }) {
  return (
    <div className="tag-input input">
      {tags.map(tag => (
        <span className="tag" key={tag}>
          {tag}
          <button type="button" onClick={() => onRemove(tag)}>×</button>
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
        onBlur={e => {
          // Commits whatever's still sitting in the box uncommitted when
          // focus leaves it (e.g. clicking straight to "Generate
          // recommendations" without pressing Enter/comma first) - otherwise
          // that text is silently dropped and the rule it represents never
          // reaches the request at all.
          if (e.currentTarget.value.trim()) {
            onAdd(e.currentTarget.value)
            e.currentTarget.value = ''
          }
        }}
      />
    </div>
  )
}
