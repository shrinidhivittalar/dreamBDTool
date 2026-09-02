import { money } from '../lib/format'

function ProgressRow({ label, pct, note }) {
  const clamped = pct == null ? 0 : Math.max(0, Math.min(100, pct))
  return (
    <div className="dad-progress-row">
      <div className="dad-progress-label">
        <span>{label}</span>
        <strong>{pct == null ? '—' : `${note || ''}${Math.round(pct)}%`}</strong>
      </div>
      <div className="dad-progress-track">
        <span className="dad-progress-fill" style={{ width: `${clamped}%` }} />
      </div>
    </div>
  )
}

function CategoryCoverage({ composition }) {
  if (composition.is_full_category_coverage) {
    return (
      <div className="hamper-status-line hamper-status-ok">
        <span className="hamper-status-icon">✓</span>
        <span>{composition.applicable_categories.length}/{composition.applicable_categories.length} Categories — Complete</span>
      </div>
    )
  }
  return (
    <div className="hamper-status-line hamper-status-warn">
      <span className="hamper-status-icon">⚠</span>
      <span>
        {composition.applicable_categories.length - composition.missing_categories.length}/{composition.applicable_categories.length} Categories — Fallback
        {composition.missing_categories.length > 0 && ` · Missing: ${composition.missing_categories.join(', ')}`}
      </span>
    </div>
  )
}

function FitStatus({ fitStatus }) {
  // Three states, deliberately no ambiguity: dimension-compatible,
  // unverifiable (dimensions missing - not disproven), and does-not-fit.
  // The engine rejects does-not-fit candidates before they reach this UI,
  // so that branch is defensive, not an expected path.
  //
  // "Dimension compatible" (not "fit verified"): each item (or hexagon row)
  // is checked against the container's bounds independently, then combined
  // volume is bounded against the container's volume - there is no
  // arrangement/packing search proving every item simultaneously fits
  // without overlapping. Don't relabel this as "verified".
  if (!fitStatus.fits) {
    return (
      <div className="hamper-status-line hamper-status-bad">
        <span className="hamper-status-icon">✕</span>
        <span>Does not fit</span>
      </div>
    )
  }
  if (!fitStatus.fully_verified) {
    return (
      <div className="hamper-status-line hamper-status-warn">
        <span className="hamper-status-icon">⚠</span>
        <span>Fit not fully verified — dimensions missing</span>
      </div>
    )
  }
  return (
    <div className="hamper-status-line hamper-status-ok">
      <span className="hamper-status-icon">✓</span>
      <span>Dimension compatible</span>
    </div>
  )
}

export function HamperCard({ recommendation, index }) {
  const { container, items, total_price, budget_utilisation, composition, fit_status } = recommendation
  const fillPct = fit_status.utilisation_ratio != null ? Math.round(fit_status.utilisation_ratio * 100) : null

  return (
    <article className="card option-card overflow-hidden">
      <div className="flex items-center justify-between px-4 pt-3.5">
        <h3 className="serif text-base leading-tight" style={{ color: 'var(--dad-accent-strong, #302a27)' }}>{container.name}</h3>
        {index === 0 && (
          <span className="rounded-full bg-[#e8f3ec] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#4c8664]">Top pick</span>
        )}
      </div>

      <div className="px-4 pt-2">
        {items.slice(0, 3).map(item => (
          <div key={item.name} className="flex items-center gap-1.5 py-0.5 text-[13px]" style={{ color: 'var(--dad-ink-soft, #4b423d)' }}>
            <span aria-hidden="true">·</span>
            <span>{item.name}</span>
          </div>
        ))}
        {items.length > 3 && (
          <div className="pt-0.5 text-[12px] font-semibold" style={{ color: 'var(--dad-accent, #a5690a)' }}>+ {items.length - 3} more items</div>
        )}
      </div>

      <div className="mt-3 px-4 pb-3.5">
        <div className="serif text-xl" style={{ color: 'var(--dad-ink, #302a27)' }}>{money(total_price)}</div>

        <ProgressRow label="Budget used" pct={budget_utilisation * 100} />
        <ProgressRow
          label="Estimated container fill"
          pct={fillPct}
          note={fillPct != null && fit_status.fill_estimate_partial ? 'at least ' : ''}
        />
        {fillPct == null && (
          <p className="mt-1 text-[10px]" style={{ color: 'var(--dad-ink-soft, #9b8d84)' }}>Fill cannot be fully estimated - dimensions missing.</p>
        )}

        <div className="mt-2.5 flex flex-col gap-1 border-t pt-2.5" style={{ borderColor: 'var(--dad-border, #eee5dd)' }}>
          <FitStatus fitStatus={fit_status} />
          <CategoryCoverage composition={composition} />
        </div>

        {/* Static for now - expand-to-detail isn't wired up yet (known gap,
            tracked separately), so this is a label, not a clickable button. */}
        <div className="mt-2.5 text-right text-[11px] font-semibold" style={{ color: 'var(--dad-ink-soft, #9b8d84)' }}>
          View Details ⌄
        </div>
      </div>
    </article>
  )
}
