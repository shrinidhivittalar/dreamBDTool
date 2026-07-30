import { money } from '../lib/format'
import { matchesAny, matchingCategory } from '../lib/match'

const ACCENT = '#bd285c'

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

function groupByProduct(products) {
  const groups = []
  const indexByName = new Map()
  for (const product of products) {
    if (indexByName.has(product.name)) {
      groups[indexByName.get(product.name)].count += 1
    } else {
      indexByName.set(product.name, groups.length)
      groups.push({ product, count: 1 })
    }
  }
  return groups
}

export function RecommendationCard({ recommendation, index, mandatoryProducts, requiredCategories, budgetMin, budgetMax }) {
  const inHouseCount = recommendation.products.filter(isInHouse).length
  const healthyCount = recommendation.products.filter(isHealthy).length
  const groupedProducts = groupByProduct(recommendation.products)
  const hasRepeats = groupedProducts.some(group => group.count > 1)
  const highlights = [
    describeFit(recommendation.total_price, budgetMin, budgetMax),
    inHouseCount > 0 ? `${inHouseCount} in-house` : null,
    healthyCount > 0 ? `${healthyCount} healthy` : null,
    hasRepeats ? 'repeats a product' : null,
  ].filter(Boolean).join(' · ')

  return (
    <article className="card option-card overflow-hidden" style={{ borderLeft: `4px solid ${ACCENT}` }}>
      <div className="flex items-center justify-between border-b border-[#eee5dd] px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#f7dce5] text-xs font-bold text-[#b32758]">
            {String(index + 1).padStart(2, '0')}
          </span>
          <div>
            <h3 className="text-sm font-bold text-[#3a322e]">Option {index + 1}</h3>
            {highlights && <p className="text-[11px] text-[#9a8d84]">{highlights}</p>}
          </div>
        </div>
        {index === 0 && (
          <span className="rounded-full bg-[#e8f3ec] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#4c8664]">Top pick</span>
        )}
      </div>
      <div className="px-4">
        {groupedProducts.map(({ product, count }) => {
          const isMandatory = matchesAny(product.name, mandatoryProducts)
          const matchedCategory = matchingCategory(product, requiredCategories)
          return (
            <div key={product.name} className="flex items-center justify-between gap-3 border-b border-[#f1eae4] py-1.5 last:border-0">
              <span className="flex flex-wrap items-center gap-1.5 pr-3 text-[13px] text-[#4b423d]">
                {product.name}
                {count > 1 && <span className="badge badge-repeat">×{count}</span>}
                {isMandatory && <span className="badge badge-mandatory">Mandatory</span>}
                {matchedCategory && <span className="badge badge-category">Required: {matchedCategory}</span>}
              </span>
              <span className="whitespace-nowrap text-[11px] text-[#9b8d84]">{product.vendor}</span>
            </div>
          )
        })}
      </div>
      <div className="bg-[#fcf8f3] px-4 py-2.5">
        <div className="text-[10px] font-bold uppercase tracking-wider text-[#9b8d84]">Total price</div>
        <div className="serif mt-0.5 text-lg text-[#302a27]">{money(recommendation.total_price)}</div>
      </div>
    </article>
  )
}

