import { HamperCard } from './HamperCard'

export function HamperResultsPanel({ loading, message, result }) {
  const recommendations = result?.recommendations ?? []

  return (
    <section>
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <p className="mb-0.5 text-xs font-bold uppercase tracking-[.18em] text-[#9a8d84]">Recommendations</p>
          <h2 className="serif text-[20px]">Hamper options</h2>
        </div>
        <div className="flex items-center gap-3">
          {loading && (
            <span className="flex items-center gap-1.5 text-xs font-semibold text-[#844292]">
              <span className="results-spinner" aria-hidden="true" /> Finding hamper options...
            </span>
          )}
          {!loading && recommendations.length > 0 && (
            <span className="text-xs text-[#8e8179]">
              {recommendations.length} of {result.requested_count} requested options found
            </span>
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
            <p className="mt-2 text-sm leading-6 text-[#83776f]">Fill in the requirements on the left and we'll find the best container + item combinations for your budget.</p>
          </div>
        </div>
      ) : (
        <div className={`grid gap-3 xl:grid-cols-2 ${loading ? 'results-stale' : ''}`}>
          {recommendations.map((recommendation, index) => (
            <HamperCard key={index} recommendation={recommendation} index={index} />
          ))}
        </div>
      )}
    </section>
  )
}
