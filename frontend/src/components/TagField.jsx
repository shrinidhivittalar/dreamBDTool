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
      />
    </div>
  )
}
