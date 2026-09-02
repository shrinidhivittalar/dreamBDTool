import { RecommendationCard } from './RecommendationCard'

export function ResultsPanel({ catalogSize, lastBrief, loading, message, recommendations, onExport, exporting, onToggleCustomization, repricingIndices }) {
  return (
    <section>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="mb-0.5 text-xs font-bold uppercase tracking-[.18em] text-[#8a7690]">Recommendations</p>
          <h2 className="serif text-[20px]">A few good options</h2>
        </div>
        <div className="flex items-center gap-3">
          {loading && (
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[#c0264f]">
              <span className="results-spinner" aria-hidden="true" /> Updating your options...
            </span>
          )}
          {!loading && recommendations.length > 0 && (
            <span className="text-xs text-[#8a7690]">{recommendations.length} options, {catalogSize} products checked</span>
          )}
          {recommendations.length > 0 && onExport && (
            <div className="flex items-center gap-1.5">
              <button type="button" className="pill" disabled={exporting} onClick={() => onExport('xlsx', 'summary')}>Export (per box)</button>
              <button type="button" className="pill" disabled={exporting} onClick={() => onExport('xlsx', 'itemized')}>Export (row-wise)</button>
            </div>
          )}
        </div>
      </div>

      {message && (
        <div className="mb-3 rounded-lg border border-[#f0c9cf] bg-[#fdf0f1] px-4 py-2.5 text-sm text-[#c0264f]">{message}</div>
      )}

      {recommendations.length === 0 ? (
        <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-[#d9c3de] bg-[#f5ebf4] px-8 text-center">
          <div className="max-w-sm">
            <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[#f3e8f6] text-xl text-[#844292]">?</div>
            <h3 className="serif text-xl">Ready when you are</h3>
            <p className="mt-2 text-sm leading-6 text-[#6b5570]">Fill in the brief on the left and we'll search every valid combination in the catalog for five sensible boxes.</p>
            <p className="mt-3 text-xs text-[#8a7690]">Boxes inside your range rank first - nothing is ruled out for falling outside it.</p>
          </div>
        </div>
      ) : (
        <div className={`grid gap-3 xl:grid-cols-2 ${loading ? 'results-stale' : ''}`}>
          {recommendations.map((recommendation, index) => (
            <RecommendationCard
              key={index}
              recommendation={recommendation}
              index={index}
              mandatoryProducts={lastBrief?.mandatoryProducts ?? []}
              requiredCategories={lastBrief?.requiredCategories ?? []}
              onToggleCustomization={onToggleCustomization}
              repricing={repricingIndices?.has(index) ?? false}
            />
          ))}
        </div>
      )}
    </section>
  )
}
