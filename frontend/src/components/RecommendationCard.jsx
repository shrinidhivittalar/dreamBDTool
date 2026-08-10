import { money } from '../lib/format'
import { isMandatoryProduct, matchingCategory } from '../lib/match'

const ACCENT = '#bd285c'

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

export function RecommendationCard({ recommendation, index, mandatoryProducts, requiredCategories, onToggleCustomization, repricing }) {
  const groupedProducts = groupByProduct(recommendation.products)
  const customizeProducts = recommendation.customizeProducts || []
  const boxProductNames = recommendation.products.map(product => product.name)

  return (
    <article className="card option-card overflow-hidden" style={{ borderLeft: `4px solid ${ACCENT}` }}>
      <div className="flex items-center justify-between border-b border-[#eee5dd] px-4 py-2.5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-6 w-6 items-center justify-center rounded-full bg-[#f7dce5] text-xs font-bold text-[#b32758]">
            {String(index + 1).padStart(2, '0')}
          </span>
          <h3 className="text-sm font-bold text-[#3a322e]">Option {index + 1}</h3>
        </div>
        {index === 0 && (
          <span className="rounded-full bg-[#e8f3ec] px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider text-[#4c8664]">Top pick</span>
        )}
      </div>
      <div className="px-4">
        {groupedProducts.map(({ product, count }) => {
          const isMandatory = isMandatoryProduct(product.name, mandatoryProducts, boxProductNames)
          const matchedCategory = matchingCategory(product, requiredCategories)
          const isCustomized = customizeProducts.includes(product.name)
          return (
            <div key={product.name} className="border-b border-[#f1eae4] py-1.5 last:border-0">
              <div className="flex items-center justify-between gap-3">
                <span className="flex flex-wrap items-center gap-1.5 pr-3 text-[13px] text-[#4b423d]">
                  {product.name}
                  {count > 1 && <span className="badge badge-repeat">×{count}</span>}
                  {isMandatory && <span className="badge badge-mandatory">Mandatory</span>}
                  {matchedCategory && <span className="badge badge-category">Required: {matchedCategory}</span>}
                </span>
                <span className="whitespace-nowrap text-[11px] text-[#9b8d84]">{product.vendor}</span>
              </div>
              {product.customization_eligible && onToggleCustomization && (
                <label className="mt-1 flex items-center gap-1.5 text-[11px] text-[#9b8d84]">
                  <input
                    type="checkbox"
                    checked={isCustomized}
                    disabled={repricing}
                    onChange={() => onToggleCustomization(index, product.name)}
                  />
                  <span>Add white chocolate disc customization +{'₹'}50</span>
                </label>
              )}
            </div>
          )
        })}
      </div>
      <div className="bg-[#fcf8f3] px-4 py-2.5">
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#9b8d84]">Recommended price</div>
            <div className="serif mt-0.5 text-lg text-[#302a27]">{money(recommendation.dad_selling_price)}</div>
          </div>
          <div className="text-right">
            <div className="text-[10px] font-bold uppercase tracking-wider text-[#9b8d84]">Floor price</div>
            <div className="serif mt-0.5 text-lg text-[#a5690a]">{money(recommendation.rock_bottom_price)}</div>
          </div>
        </div>
        {recommendation.packaging_cost > 0 && (
          <div className="mt-1 text-[11px] text-[#9b8d84]">+ {money(recommendation.packaging_cost)} packaging</div>
        )}
        {recommendation.customization_surcharge > 0 && (
          <div className="mt-0.5 text-[11px] text-[#9b8d84]">+ {money(recommendation.customization_surcharge)} customization</div>
        )}
        <div className="mt-1.5 flex items-center justify-between gap-3 border-t border-[#eee5dd] pt-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#9b8d84]">Total</span>
          <span className="text-sm font-bold text-[#302a27]">{money(recommendation.total_price)}</span>
        </div>
        {recommendation.over_budget && (
          <div className="mt-1.5 rounded-md bg-[#fff0ec] px-2 py-1 text-[11px] font-semibold text-[#b7472a]">
            Over budget by {money(-recommendation.remaining_budget)}
          </div>
        )}
      </div>
    </article>
  )
}

