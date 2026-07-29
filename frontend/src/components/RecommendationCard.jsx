import { money } from '../lib/format'
import { matchesAny, matchingCategory } from '../lib/match'

const ACCENTS = ['#bd285c', '#5d9c78']

function isInHouse(product) {
  return product.vendor === 'Dream a Dozen' || (product.sourcing || '').toLowerCase().includes('in-house')
}

function isHealthy(product) {
  return (product.tags || []).some(tag => tag.toLowerCase().includes('healthy'))
}

function describeFit(total, budgetMin, budgetMax) {
  if (!budgetMax) return null
  if (total < budgetMin) return `${money(budgetMin - total)} under range`
  if (total > budgetMax) return `${money(total - budgetMax)} over range`
  return 'Within range'
}

export function RecommendationCard({ recommendation, index, mandatoryProducts, requiredCategories, budgetMin, budgetMax }) {
  const inHouseCount = recommendation.products.filter(isInHouse).length
  const healthyCount = recommendation.products.filter(isHealthy).length
  const highlights = [
    describeFit(recommendation.total_price, budgetMin, budgetMax),
    inHouseCount > 0 ? `${inHouseCount} in-house` : null,
    healthyCount > 0 ? `${healthyCount} healthy` : null,
  ].filter(Boolean).join(' · ')

  return (
    <article className="card option-card overflow-hidden" style={{ borderLeft: `4px solid ${ACCENTS[index % ACCENTS.length]}` }}>
      <div className="flex items-center justify-between border-b border-[#eee5dd] px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-[#f7dce5] text-sm font-bold text-[#b32758]">
            {String(index + 1).padStart(2, '0')}
          </span>
          <div>
            <h3 className="font-bold text-[#3a322e]">Option {index + 1}</h3>
            {highlights && <p className="text-xs text-[#9a8d84]">{highlights}</p>}
          </div>
        </div>
        {index === 0 && (
          <span className="rounded-full bg-[#e8f3ec] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-[#4c8664]">Top pick</span>
        )}
      </div>
      <div className="px-5 py-2">
        {recommendation.products.map((product, productIndex) => {
          const isMandatory = matchesAny(product.name, mandatoryProducts)
          const matchedCategory = matchingCategory(product, requiredCategories)
          return (
            <div key={`${product.name}-${productIndex}`} className="flex items-center justify-between gap-3 border-b border-[#f1eae4] py-3 last:border-0">
              <span className="flex flex-wrap items-center gap-1.5 pr-3 text-sm text-[#4b423d]">
                {product.name}
                {isMandatory && <span className="badge badge-mandatory">Mandatory</span>}
                {matchedCategory && <span className="badge badge-category">Required: {matchedCategory}</span>}
              </span>
              <span className="whitespace-nowrap text-xs text-[#9b8d84]">{product.vendor}</span>
            </div>
          )
        })}
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
