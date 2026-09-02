const NAV_ITEMS = [
  { key: 'snackbox', label: 'Snack Box', icon: <GiftIcon /> },
  { key: 'hamper', label: 'Hamper', icon: <DiyaIcon /> },
]

function SparkleMark({ size = 34 }) {
  // The brand's diamond/sparkle emblem: four pointed shapes around a
  // central "D", per the Dream A Dozen style guide (logo mark variant).
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" aria-hidden="true">
      <path d="M20 1 L23.5 14 L20 20 L16.5 14 Z" fill="#f6ecf8" />
      <path d="M20 39 L23.5 26 L20 20 L16.5 26 Z" fill="#f6ecf8" />
      <path d="M1 20 L14 16.5 L20 20 L14 23.5 Z" fill="#f6ecf8" />
      <path d="M39 20 L26 16.5 L20 20 L26 23.5 Z" fill="#f6ecf8" />
      <circle cx="20" cy="20" r="8" fill="#f6ecf8" />
      <text x="20" y="24.5" textAnchor="middle" fontFamily="Lora, serif" fontSize="12" fontWeight="700" fill="#c22026">D</text>
    </svg>
  )
}

function GiftIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="9" width="18" height="11" rx="1.2" />
      <path d="M3 13h18" />
      <path d="M12 9v11" />
      <path d="M12 9c-1.8 0-4-1-4-3.2S9.8 3 11 4.2c1 1 1 2.6 1 4.8Z" />
      <path d="M12 9c1.8 0 4-1 4-3.2S14.2 3 13 4.2c-1 1-1 2.6-1 4.8Z" />
    </svg>
  )
}

function DiyaIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M12 4c1 1.4.6 2.4 0 3.2C11.4 6.4 11 5.4 12 4Z" />
      <path d="M3 13c1.5 3 4.5 5 9 5s7.5-2 9-5" />
      <path d="M3 13c0-1 .8-1.8 2-1.8h14c1.2 0 2 .8 2 1.8s-1 2-2 2H5c-1 0-2-1-2-2Z" />
    </svg>
  )
}

function RefreshIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M21 12a9 9 0 1 1-2.6-6.4" />
      <path d="M21 4v5h-5" />
    </svg>
  )
}

export function Sidebar({ flow, onSelect, footerNote, onRefresh }) {
  return (
    <nav className="dad-sidebar" aria-label="Recommendation type">
      <div className="dad-sidebar-logo">
        <SparkleMark />
        <div>
          <div className="dad-sidebar-wordmark">Dream A Dozen</div>
          <div className="dad-sidebar-subtitle">Indian Gourmet Gifting</div>
        </div>
      </div>

      <div className="dad-sidebar-nav">
        {NAV_ITEMS.map(item => (
          <button
            key={item.key}
            type="button"
            className={`dad-nav-item ${flow === item.key ? 'active' : ''}`}
            onClick={() => onSelect(item.key)}
          >
            <span className="dad-nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}
      </div>

      <div className="dad-sidebar-footer">
        {onRefresh && (
          <button type="button" className="dad-sidebar-refresh" onClick={onRefresh} title="Refresh catalog status">
            <RefreshIcon />
          </button>
        )}
        <span>{footerNote || 'Business development workspace'}</span>
      </div>
    </nav>
  )
}
