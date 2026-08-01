import { useEffect, useState } from 'react'
import { Field } from './components/Field'
import { MultiSelect } from './components/MultiSelect'
import { TagField } from './components/TagField'
import { RecommendationCard } from './components/RecommendationCard'
import { fetchProducts, fetchRecommendations } from './lib/api'

// Only categories that actually exist in the catalog's taxonomy ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â "Cookies"
// and "Cakes" were dropped because no product is ever categorized that way
// (cupcakes/cake-pops live under "In-house sweet" / "outsourced Sweet"),
// so those pills always returned zero matches.
const categories = ['Sweet', 'Savoury', 'Healthy']
const sweetOptions = [
  { value: 'any', label: 'No preference' },
  { value: 'sweet_only', label: 'Sweet only' },
  { value: 'no_sweet', label: 'No sweet' },
]

const initialForm = {
  budget_min: 800,
  budget_max: 1000,
  item_count: 4,
  preferred_categories: [],
  mandatory_products: '',
  preferred_products: '',
  excluded_products: '',
  sweet_preference: 'any',
  price_includes_gst: false,
  include_themed_customised: false,
  required_categories: '',
}

export function App() {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState(initialForm)
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [catalogSize, setCatalogSize] = useState(0)
  const [lastBrief, setLastBrief] = useState(null)
  const [catalogRange, setCatalogRange] = useState(null)

  useEffect(() => {
    fetchProducts()
      .then(products => {
        if (!products.length) return
        const prices = products.map(product => product.selling_price)
        setCatalogRange({ min: Math.min(...prices), max: Math.max(...prices) })
      })
      .catch(() => {})
  }, [])

  const set = (key, value) => setForm(current => ({ ...current, [key]: value }))
  const toggle = key => item => set(key, form[key].includes(item) ? form[key].filter(value => value !== item) : [...form[key], item])
  const budgetInvalid = form.budget_min > form.budget_max
  const maxPossibleTotal = catalogRange ? form.item_count * catalogRange.max : null
  const budgetTooHighForItems = !budgetInvalid && maxPossibleTotal !== null && maxPossibleTotal < form.budget_min
  const visibleCategories = form.sweet_preference === 'no_sweet' ? categories.filter(item => item !== 'Sweet') : categories
  const setSweetPreference = value => {
    set('sweet_preference', value)
    if (value === 'no_sweet') set('preferred_categories', form.preferred_categories.filter(item => item !== 'Sweet'))
  }
  const tagsFor = key => form[key].split(',').map(value => value.trim()).filter(Boolean)
  const addTag = (key, value) => set(key, [...new Set([...tagsFor(key), value.trim()])].filter(Boolean).join(', '))
  const removeTag = (key, tag) => set(key, tagsFor(key).filter(value => value !== tag).join(', '))
  const advancedCount = [
    tagsFor('required_categories').length > 0,
    tagsFor('preferred_products').length > 0,
    tagsFor('excluded_products').length > 0,
    form.include_themed_customised,
  ].filter(Boolean).length

  async function generate() {
    setLoading(true)
    setMessage('')
    const payload = {
      ...form,
      mandatory_products: form.mandatory_products.split(',').map(value => value.trim()).filter(Boolean),
      preferred_products: form.preferred_products.split(',').map(value => value.trim()).filter(Boolean),
      excluded_products: form.excluded_products.split(',').map(value => value.trim()).filter(Boolean),
      required_categories: form.required_categories.split(',').map(value => value.trim()).filter(Boolean),
    }
    try {
      const data = await fetchRecommendations(payload)
      setRecommendations(data.recommendations)
      setCatalogSize(data.catalog_size)
      setMessage(data.message || '')
      setLastBrief({
        mandatoryProducts: payload.mandatory_products,
        requiredCategories: payload.required_categories,
      })
    } catch (error) {
      setMessage(error.message)
      setRecommendations([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-[#e5dbd2] bg-[#f9f4ed]">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-3 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#bd285c] text-white serif text-lg">d</div>
            <div>
              <div className="serif text-[19px] leading-none text-[#352e2b]">dream a dozen</div>
              <div className="mt-1 text-[10px] font-bold uppercase tracking-[.18em] text-[#9b8f87]">BD toolkit</div>
            </div>
          </div>
          <div className="flex items-center gap-4 text-[13px] text-[#766b64]">
            <span className="hidden sm:inline">Internal use only</span>
            <span className="h-2 w-2 rounded-full bg-[#5d9c78]" />
            <span>Catalog ready</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-6 py-5 lg:px-10 lg:py-6">
        <div className="mb-5 flex flex-col justify-between gap-3 md:flex-row md:items-end">
          <div>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-[.2em] text-[#bd285c]">Corporate gifting / new brief</p>
            <h1 className="serif text-2xl leading-tight text-[#302a27] md:text-[28px]">
              Build a thoughtful <span className="text-[#bd285c]">gift box.</span>
            </h1>
          </div>
          <div className="max-w-sm text-xs leading-5 text-[#766b64]">
            Set the brief once. We'll surface combinations your client can actually use ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â priced with a little breathing room.
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,560px)_1fr] xl:grid-cols-[600px_1fr]">
          <aside className="card wizard-card h-fit p-5 sm:p-7">
            <div className="mb-7 flex items-center justify-between"><div><p className="wizard-kicker">New brief</p><h2 className="serif mt-1 text-2xl text-[#302a27]">Create a gift box</h2></div><span className="wizard-step-count">0{step} / 02</span></div>
            <div className="wizard-progress"><span style={{ width: `${step * 50}%` }} /></div>
            {step === 1 ? <div className="wizard-step"><div className="mb-6"><p className="text-sm font-semibold text-[#3a322e]">Let's set the basics</p><p className="mt-1 text-sm text-[#91857d]">Start with the shape and budget of the box.</p></div>
              <Field label="Budget range" hint={catalogRange ? `Catalog items ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹${Math.round(catalogRange.min)}ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹${Math.round(catalogRange.max)}` : undefined}><div className="budget-inputs">{[['budget_min', 'Minimum'], ['budget_max', 'Maximum']].map(([key, label]) => <label className="input flex items-center gap-1" key={key}><span>ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹</span><input aria-label={label} className="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none" type="number" value={form[key]} onChange={e => set(key, Math.max(0, Number(e.target.value)))} /></label>)}</div>{budgetInvalid && <p className="field-error">Minimum can't be greater than maximum.</p>}<label className="checkbox-row"><input type="checkbox" checked={form.price_includes_gst} onChange={e => set('price_includes_gst', e.target.checked)} /><span>Prices already include GST</span></label></Field>
              <Field label="Number of items"><div className="stepper"><button type="button" onClick={() => set('item_count', Math.max(1, form.item_count - 1))}>-</button><span>{form.item_count} <small>items</small></span><button type="button" onClick={() => set('item_count', Math.min(20, form.item_count + 1))}>+</button></div>{budgetTooHighForItems && <p className="field-note">Even {form.item_count} of the priciest catalog items (ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹{Math.round(catalogRange.max)} each) can't reach ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹{Math.round(form.budget_min).toLocaleString()}. Try raising the item count or enabling repeats.</p>}</Field>
              <Field label="Sweet preference"><div className="segmented-control">{sweetOptions.map(option => <button type="button" key={option.value} className={form.sweet_preference === option.value ? 'selected' : ''} onClick={() => setSweetPreference(option.value)}>{option.label}</button>)}</div></Field>
              <button type="button" className="wizard-next" onClick={() => { if (!budgetInvalid) setStep(2) }} disabled={budgetInvalid}>Continue <span>ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢</span></button>
            </div> : <div className="wizard-step"><div className="mb-6"><p className="text-sm font-semibold text-[#3a322e]">Shape the selection</p><p className="mt-1 text-sm text-[#91857d]">Tell us what should make it into the box.</p></div>
              <div className="recap-row"><span className="recap-label">Current brief</span><span className="recap-chip">ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹{form.budget_min.toLocaleString()}ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹{form.budget_max.toLocaleString()}</span><span className="recap-chip">{form.item_count} items</span><span className="recap-chip">{form.sweet_preference === 'any' ? 'No preference' : sweetOptions.find(option => option.value === form.sweet_preference)?.label}</span></div>
              <Field label="Categories"><MultiSelect items={visibleCategories} selected={form.preferred_categories} onToggle={toggle('preferred_categories')} /></Field>
              <Field label="Mandatory products" hint="press enter or use commas">
                <TagField tags={tagsFor('mandatory_products')} placeholder="e.g. Brownie" onAdd={value => addTag('mandatory_products', value)} onRemove={tag => removeTag('mandatory_products', tag)} />
              </Field>
              <details className="advanced-options">
                <summary><span>Advanced options{advancedCount ? ` Ãƒâ€šÃ‚Â· ${advancedCount} set` : ''}</span></summary>
                <div className="advanced-body">
                  <Field label="Required categories" hint="repeat one to require more than one, e.g. Cookie, Cookie">
                    <TagField tags={tagsFor('required_categories')} placeholder="e.g. Brownie" onAdd={value => addTag('required_categories', value)} onRemove={tag => removeTag('required_categories', tag)} />
                  </Field>
                  <Field label="Preferred products" hint="nice to have, not guaranteed">
                    <TagField tags={tagsFor('preferred_products')} placeholder="e.g. Cupcake" onAdd={value => addTag('preferred_products', value)} onRemove={tag => removeTag('preferred_products', tag)} />
                  </Field>
                  <Field label="Excluded products" hint="never include these">
                    <TagField tags={tagsFor('excluded_products')} placeholder="e.g. Samosa" onAdd={value => addTag('excluded_products', value)} onRemove={tag => removeTag('excluded_products', tag)} />
                  </Field>
                  <label className="checkbox-row"><input type="checkbox" checked={form.include_themed_customised} onChange={e => set('include_themed_customised', e.target.checked)} /><span>Include themed or customised items</span></label>
                </div>
              </details>
              <div className="summary-card"><div><span className="summary-label">Your brief</span><strong>ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹{form.budget_min.toLocaleString()} ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Å“ ÃƒÂ¢Ã¢â‚¬Å¡Ã‚Â¹{form.budget_max.toLocaleString()}</strong></div><span>{form.item_count} items</span><span>{form.preferred_categories.length ? form.preferred_categories.join(', ') : 'Any category'}</span><span>{form.sweet_preference === 'any' ? 'No sweet preference' : sweetOptions.find(option => option.value === form.sweet_preference)?.label}</span></div>
              <div className="wizard-actions"><button type="button" className="wizard-back" onClick={() => setStep(1)}>ÃƒÂ¢Ã¢â‚¬Â Ã‚Â Back</button><button onClick={generate} disabled={loading} className="wizard-next flex-1">{loading ? 'Finding a good fitÃƒÂ¢Ã¢â€šÂ¬Ã‚Â¦' : 'Generate recommendations'} <span>ÃƒÂ¢Ã¢â‚¬Â Ã¢â‚¬â„¢</span></button></div>
            </div>}
          </aside>          <section>
            <div className="mb-3 flex items-end justify-between">
              <div>
                <p className="mb-0.5 text-xs font-bold uppercase tracking-[.18em] text-[#9a8d84]">Recommendations</p>
                <h2 className="serif text-[20px]">A few good options</h2>
              </div>
              {recommendations.length > 0 && (
                <span className="text-xs text-[#8e8179]">{recommendations.length} options, {catalogSize} products checked</span>
              )}
            </div>

            {message && (
              <div className="mb-3 rounded-lg border border-[#eed3db] bg-[#fff4f6] px-4 py-2.5 text-sm text-[#a51f50]">{message}</div>
            )}

            {recommendations.length === 0 ? (
              <div className="flex min-h-[280px] items-center justify-center rounded-xl border border-dashed border-[#d8ccc2] bg-[#f9f4ed] px-8 text-center">
                <div className="max-w-sm">
                  <div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-[#f3dce3] text-xl text-[#bd285c]">ÃƒÂ°Ã…Â¸Ã…Â½Ã‚Â</div>
                  <h3 className="serif text-xl">Ready when you are</h3>
                  <p className="mt-2 text-sm leading-6 text-[#83776f]">Fill in the brief on the left and we'll search every valid combination in the catalog for five sensible boxes.</p>
                  <p className="mt-3 text-xs text-[#a39891]">Boxes inside your range rank first ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â nothing is ruled out for falling outside it.</p>
                </div>
              </div>
            ) : (
              <div className="grid gap-3 xl:grid-cols-2">
                {recommendations.map((recommendation, index) => (
                  <RecommendationCard
                    key={index}
                    recommendation={recommendation}
                    index={index}
                    mandatoryProducts={lastBrief?.mandatoryProducts ?? []}
                    requiredCategories={lastBrief?.requiredCategories ?? []}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="mx-auto max-w-[1440px] px-6 pb-4 text-xs text-[#a39891] lg:px-10">
        Dream a Dozen ÃƒÂ¢Ã¢â€šÂ¬Ã¢â‚¬Â Business development workspace
      </footer>
    </div>
  )
}







