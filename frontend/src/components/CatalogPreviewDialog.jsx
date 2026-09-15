import { useEffect, useState } from 'react'

const RUPEE = '₹'

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]))
}

function buildPreviewHtml(title, sections) {
  const sectionsHtml = sections
    .map(
      section => `
    <h2>${escapeHtml(section.label)} (${section.rows.length})</h2>
    <table>
      <thead><tr><th>Item</th><th>DaD selling price</th></tr></thead>
      <tbody>
        ${section.rows
          .map(row => `<tr><td>${escapeHtml(row.name)}</td><td>${RUPEE}${Number(row.dad_selling_price).toFixed(2)}</td></tr>`)
          .join('')}
      </tbody>
    </table>`
    )
    .join('')

  return `<!doctype html>
<html>
<head>
<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<style>
  body { font-family: 'Raleway', Arial, sans-serif; background: #f5ebf4; color: #301736; margin: 0; padding: 32px; }
  h1 { font-family: 'Lora', Georgia, serif; font-size: 22px; margin-bottom: 4px; }
  h2 { font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: #4c1f53; margin-top: 28px; }
  table { width: 100%; border-collapse: collapse; background: #fff; border-radius: 10px; overflow: hidden; box-shadow: 0 1px 2px rgba(0,0,0,.05); margin-top: 8px; }
  th, td { text-align: left; padding: 10px 14px; border-bottom: 1px solid #e6d6ea; font-size: 13px; }
  th { background: #f3e8f6; color: #4c1f53; font-weight: 700; }
  tr:last-child td { border-bottom: none; }
</style>
</head>
<body>
  <h1>${escapeHtml(title)}</h1>
  ${sectionsHtml}
</body>
</html>`
}

// Normalizes either shape a fetcher can return: a flat array (snack box -
// one "Items" section) or {items, containers} (hamper - two sections).
// Empty sections are dropped so, e.g., a container-less catalog doesn't
// render an empty "Containers" heading.
function normalize(data) {
  const raw = Array.isArray(data)
    ? [{ label: 'Items', rows: data }]
    : [
        { label: 'Items', rows: data.items || [] },
        { label: 'Containers', rows: data.containers || [] },
      ]
  return raw.filter(section => section.rows.length > 0)
}

export function CatalogPreviewDialog({ open, onClose, title, fetcher }) {
  const [status, setStatus] = useState('idle')
  const [sections, setSections] = useState([])
  const [error, setError] = useState('')
  const [fullscreen, setFullscreen] = useState(false)
  const [query, setQuery] = useState('')

  useEffect(() => {
    if (!open) return
    setFullscreen(false)
    setQuery('')
    setStatus('loading')
    setError('')
    fetcher()
      .then(data => {
        setSections(normalize(data))
        setStatus('ready')
      })
      .catch(err => {
        setError(err.message || 'Could not load the catalog.')
        setStatus('error')
      })
  }, [open, fetcher])

  if (!open) return null

  const trimmedQuery = query.trim().toLowerCase()
  const filteredSections = trimmedQuery
    ? sections.map(section => ({ ...section, rows: section.rows.filter(row => row.name.toLowerCase().includes(trimmedQuery)) }))
    : sections
  const totalCount = sections.reduce((sum, section) => sum + section.rows.length, 0)
  const visibleCount = filteredSections.reduce((sum, section) => sum + section.rows.length, 0)

  function openInNewTab() {
    const win = window.open('', '_blank')
    if (!win) return
    win.document.write(buildPreviewHtml(title, sections))
    win.document.close()
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true" onMouseDown={e => { if (e.target === e.currentTarget) onClose() }}>
      <div className={`catalog-preview-card${fullscreen ? ' fullscreen' : ''}`}>
        <div className="catalog-preview-header">
          <div>
            <p className="wizard-kicker">Catalog</p>
            <h3 className="serif catalog-preview-title">{title}</h3>
          </div>
          <div className="catalog-preview-actions">
            <button type="button" className="pill" onClick={() => setFullscreen(f => !f)}>
              {fullscreen ? 'Exit full screen' : 'Full screen'}
            </button>
            <button type="button" className="pill" onClick={openInNewTab} disabled={status !== 'ready'}>
              Open in new tab
            </button>
            <button type="button" className="pill" onClick={onClose} aria-label="Close preview">
              Close
            </button>
          </div>
        </div>

        {status === 'ready' && (
          <input
            className="input catalog-preview-search"
            type="text"
            placeholder="Search items..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
        )}

        <div className="catalog-preview-body">
          {status === 'loading' && <p className="field-note">Loading catalog...</p>}
          {status === 'error' && <p className="field-error">{error}</p>}
          {status === 'ready' && visibleCount === 0 && (
            <p className="field-note">No items match "{query}".</p>
          )}
          {status === 'ready' &&
            filteredSections.map(section => (
              <div key={section.label} className="catalog-preview-section">
                {sections.length > 1 && (
                  <p className="catalog-preview-section-label">
                    {section.label} ({section.rows.length})
                  </p>
                )}
                <table className="catalog-preview-table">
                  <thead>
                    <tr><th>Item</th><th>DaD selling price</th></tr>
                  </thead>
                  <tbody>
                    {section.rows.map(row => (
                      <tr key={row.name}>
                        <td>{row.name}</td>
                        <td>{RUPEE}{Number(row.dad_selling_price).toFixed(2)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
        </div>

        {status === 'ready' && (
          <p className="catalog-preview-count">
            {totalCount} item{totalCount === 1 ? '' : 's'} in the catalog
          </p>
        )}
      </div>
    </div>
  )
}
