import { money } from '../lib/format'

export function RecommendationCard({ recommendation, index }) {
  return (
    <article className="card overflow-hidden">
      <div className="flex items-center justify-between border-b border-[#eee5dd] px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f7dce5] text-sm font-bold text-[#b32758]">
            {String(index + 1).padStart(2, '0')}
          </span>
          <div>
            <h3 className="font-bold text-[#3a322e]">Option {index + 1}</h3>
            <p className="text-xs text-[#9a8d84]">{recommendation.products.length} items, thoughtfully balanced</p>
          </div>
        </div>
        {index === 0
          ? <span className="rounded-full bg-[#e8f3ec] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[#4c8664]">Closest fit</span>
          : <span className="text-xs text-[#9a8d84]">Within brief</span>}
      </div>
      <div className="px-5 py-2">
        {recommendation.products.map(product => (
          <div key={product.name} className="flex items-center justify-between border-b border-[#f1eae4] py-3 last:border-0">
            <span className="pr-3 text-sm text-[#4b423d]">{product.name}</span>
            <span className="whitespace-nowrap text-xs text-[#9b8d84]">{product.vendor}</span>
          </div>
        ))}
      </div>
      <div className="flex items-end justify-between bg-[#fcf8f3] px-5 py-4">
        <div>
          <div className="text-[11px] font-bold uppercase tracking-wider text-[#9b8d84]">Total price</div>
          <div className="serif mt-1 text-2xl text-[#302a27]">{money(recommendation.total_price)}</div>
        </div>
        <div className="text-right">
          <div className="text-[11px] font-bold uppercase tracking-wider text-[#9b8d84]">Remaining</div>
          <div className="mt-1 text-sm font-semibold text-[#bd285c]">{money(recommendation.remaining_budget)}</div>
        </div>
      </div>
    </article>
  )
}
