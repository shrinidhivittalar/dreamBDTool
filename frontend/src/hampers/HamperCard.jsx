import { money } from '../lib/format'

const ACCENT = '#bd285c'

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
  // Three states, deliberately no ambiguity: verified fits, unverifiable
  // (dimensions missing - not disproven), and does-not-fit. The engine
  // rejects does-not-fit candidates before they reach this UI, so that
  // branch is defensive, not an expected path.
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
      <span>Fit verified</span>
    </div>
  )
}

export function HamperCard({ recommendation, index }) {
  const { container, items, total_price, budget_utilisation, composition, fit_status } = recommendation
  const fillPct = fit_status.utilisation_ratio != null ? Math.round(fit_status.utilisation_ratio * 100) : null

  return (
    <article className="card option-card overflow-hidden" style={{ borderLeft: `4px solid ${ACCENT}` }}>
      <div className="flex items-center justify-between border-b border-[#eee5dd] px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#f7dce5] text-xs font-bold text-[#b32758]">
            {String(index + 1).padStart(2, '0')}
          </span>
          <h3 className="text-sm font-bold text-[#3a322e]">{container.name}</h3>
        </div>
        {index === 0 && (
          <span className="rounded-full bg-[#e8f3ec] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#4c8664]">Top pick</span>
        )}
      </div>

      <div className="px-4 pt-2">
        {items.map(item => (
          <div key={item.name} className="border-b border-[#f1eae4] py-1.5 last:border-0">
            <div className="flex items-center justify-between gap-3">
              <span className="flex flex-wrap items-center gap-1.5 pr-3 text-[13px] text-[#4b423d]">{item.name}</span>
              <span className="whitespace-nowrap text-[11px] text-[#9b8d84]">{money(item.price)}</span>
            </div>
          </div>
        ))}
      </div>

      <div className="bg-[#fcf8f3] px-4 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#9b8d84]">Total price</div>
            <div className="serif mt-0.5 text-lg text-[#302a27]">{money(total_price)}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#9b8d84]">Budget used</div>
            <div className="serif mt-0.5 text-lg text-[#302a27]">{Math.round(budget_utilisation * 100)}%</div>
          </div>
        </div>

        {fillPct != null && (
          <div className="mt-1.5 text-[11px] text-[#9b8d84]">
            <span className="font-semibold text-[#766b64]">Container space:</span> estimated fill {fillPct}%
          </div>
        )}

        <div className="mt-2 flex flex-col gap-1 border-t border-[#eee5dd] pt-2">
          <CategoryCoverage composition={composition} />
          <FitStatus fitStatus={fit_status} />
        </div>
      </div>
    </article>
  )
}
