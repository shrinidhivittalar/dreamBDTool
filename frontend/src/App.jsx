import { useState } from 'react'
import { Field } from './components/Field'
import { MultiSelect } from './components/MultiSelect'
import { RecommendationCard } from './components/RecommendationCard'
import { fetchRecommendations } from './lib/api'

const categories = ['Sweet', 'Savoury', 'Healthy', 'Cookies', 'Cakes']
const vendors = ['Dream a Dozen', 'HealthyChef']
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
  preferred_vendors: [],
  sweet_preference: 'any',
  price_includes_gst: false,
  allow_repeats: false,
  required_categories: '',
}

export function App() {
  const [form, setForm] = useState(initialForm)
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [catalogSize, setCatalogSize] = useState(0)
  const [lastBrief, setLastBrief] = useState(null)

  const set = (key, value) => setForm(current => ({ ...current, [key]: value }))
  const toggle = key => item => set(key, form[key].includes(item) ? form[key].filter(value => value !== item) : [...form[key], item])

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
        budgetMin: payload.budget_min,
        budgetMax: payload.budget_max,
      })
    } catch (error) {
      setMessage('Backend is not connected yet. Start FastAPI to generate live recommendations.')
      setRecommendations([])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-[#e5dbd2] bg-[#f9f4ed]">
        <div className="mx-auto flex max-w-[1440px] items-center justify-between px-6 py-5 lg:px-10">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-[#bd285c] text-white serif text-xl">d</div>
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

      <main className="mx-auto max-w-[1440px] px-6 py-9 lg:px-10 lg:py-12">
        <div className="mb-9 flex flex-col justify-between gap-5 md:flex-row md:items-end">
          <div>
            <p className="mb-3 text-[11px] font-bold uppercase tracking-[.2em] text-[#bd285c]">Corporate gifting / new brief</p>
            <h1 className="serif text-4xl leading-tight text-[#302a27] md:text-[48px]">
              Build a thoughtful<br /><span className="text-[#bd285c]">gift box.</span>
            </h1>
          </div>
          <div className="max-w-sm text-sm leading-6 text-[#766b64]">
            Set the brief once. We'll surface combinations your client can actually use — priced with a little breathing room.
          </div>
        </div>

        <div className="grid gap-8 lg:grid-cols-[350px_1fr] xl:grid-cols-[390px_1fr]">
          <aside className="card h-fit p-6 shadow-[0_8px_30px_#5134240a]">
            <div className="mb-6 flex items-center justify-between border-b border-[#eee5dd] pb-5">
              <div>
                <h2 className="serif text-[22px]">The brief</h2>
                <p className="mt-1 text-xs text-[#91857d]">What are we putting together?</p>
              </div>
              <span className="rounded-full bg-[#fbedf1] px-3 py-1 text-[11px] font-bold text-[#b32758]">MVP</span>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <Field label="Budget min">
                <div className="input flex items-center gap-1">
                  <span className="text-[#958980]">₹</span>
                  <input className="flex-1 border-0 bg-transparent p-0 outline-none" type="number" value={form.budget_min} onChange={e => set('budget_min', Number(e.target.value))} />
                </div>
              </Field>
              <Field label="Budget max">
                <div className="input flex items-center gap-1">
                  <span className="text-[#958980]">₹</span>
                  <input className="flex-1 border-0 bg-transparent p-0 outline-none" type="number" value={form.budget_max} onChange={e => set('budget_max', Number(e.target.value))} />
                </div>
              </Field>
            </div>

            <Field label="Items">
              <input className="input" type="number" min="1" max="20" value={form.item_count} onChange={e => set('item_count', Number(e.target.value))} />
            </Field>

            <Field label="Sweet preference">
              <div className="flex flex-wrap gap-2">
                {sweetOptions.map(option => (
                  <button
                    type="button"
                    key={option.value}
                    className={`pill ${form.sweet_preference === option.value ? 'active' : ''}`}
                    onClick={() => set('sweet_preference', option.value)}
                  >
                    {form.sweet_preference === option.value ? '✓ ' : ''}{option.label}
                  </button>
                ))}
              </div>
            </Field>

            <Field label="Categories">
              <MultiSelect items={categories} selected={form.preferred_categories} onToggle={toggle('preferred_categories')} />
            </Field>

            <Field label="Mandatory products" hint="comma separated — client asked for these">
              <input className="input" placeholder="e.g. Brownie" value={form.mandatory_products} onChange={e => set('mandatory_products', e.target.value)} />
            </Field>

            <Field label="Required categories" hint="repeat a name for multiple slots — e.g. Brownie, Cookie, Cookie">
              <input className="input" placeholder="e.g. Brownie, Cookie" value={form.required_categories} onChange={e => set('required_categories', e.target.value)} />
            </Field>

            <Field label="Preferred products" hint="comma separated — nice to have">
              <input className="input" placeholder="e.g. Cookie" value={form.preferred_products} onChange={e => set('preferred_products', e.target.value)} />
            </Field>

            <Field label="Avoid products" hint="comma separated">
              <input className="input" placeholder="e.g. Samosa" value={form.excluded_products} onChange={e => set('excluded_products', e.target.value)} />
            </Field>

            <Field label="Preferred vendors">
              <MultiSelect items={vendors} selected={form.preferred_vendors} onToggle={toggle('preferred_vendors')} />
            </Field>

            <Field label="Repeats" hint="fills budget when the price ceiling is low">
              <label className="flex items-center gap-2 text-sm text-[#4b423d]">
                <input type="checkbox" className="h-4 w-4 accent-[#bd285c]" checked={form.allow_repeats} onChange={e => set('allow_repeats', e.target.checked)} />
                Allow repeated products
              </label>
            </Field>

            <Field label="GST" hint="unconfirmed — flip if this is wrong">
              <label className="flex items-center gap-2 text-sm text-[#4b423d]">
                <input type="checkbox" className="h-4 w-4 accent-[#bd285c]" checked={form.price_includes_gst} onChange={e => set('price_includes_gst', e.target.checked)} />
                Selling prices already include GST
              </label>
            </Field>

            <button
              onClick={generate}
              disabled={loading}
              className="mt-1 w-full rounded-lg bg-[#bd285c] px-4 py-3.5 text-sm font-bold text-white shadow-[0_5px_12px_#bd285c35] transition hover:bg-[#a71e4f] disabled:cursor-wait disabled:opacity-60"
            >
              {loading ? 'Finding a good fit…' : 'Generate gift boxes →'}
            </button>
          </aside>

          <section>
            <div className="mb-5 flex items-end justify-between">
              <div>
                <p className="mb-1 text-xs font-bold uppercase tracking-[.18em] text-[#9a8d84]">Recommendations</p>
                <h2 className="serif text-[30px]">A few good options</h2>
              </div>
              {recommendations.length > 0 && (
                <span className="text-xs text-[#8e8179]">{recommendations.length} options, {catalogSize} products checked</span>
              )}
            </div>

            {message && (
              <div className="mb-5 rounded-lg border border-[#eed3db] bg-[#fff4f6] px-4 py-3 text-sm text-[#a51f50]">{message}</div>
            )}

            {recommendations.length === 0 ? (
              <div className="flex min-h-[420px] items-center justify-center rounded-xl border border-dashed border-[#d8ccc2] bg-[#f9f4ed] px-8 text-center">
                <div className="max-w-sm">
                  <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-full bg-[#f3dce3] text-2xl text-[#bd285c]">🎁</div>
                  <h3 className="serif text-2xl">Ready when you are</h3>
                  <p className="mt-2 text-sm leading-6 text-[#83776f]">Fill in the brief on the left and we'll search every valid combination in the catalog for five sensible boxes.</p>
                  <p className="mt-5 text-xs text-[#a39891]">Boxes inside your range rank first — nothing is ruled out for falling outside it.</p>
                </div>
              </div>
            ) : (
              <div className="grid gap-4 xl:grid-cols-2">
                {recommendations.map((recommendation, index) => (
                  <RecommendationCard
                    key={index}
                    recommendation={recommendation}
                    index={index}
                    mandatoryProducts={lastBrief?.mandatoryProducts ?? []}
                    requiredCategories={lastBrief?.requiredCategories ?? []}
                    budgetMin={lastBrief?.budgetMin ?? 0}
                    budgetMax={lastBrief?.budgetMax ?? 0}
                  />
                ))}
              </div>
            )}
          </section>
        </div>
      </main>

      <footer className="mx-auto max-w-[1440px] px-6 pb-8 text-xs text-[#a39891] lg:px-10">
        Dream a Dozen — Business development workspace
      </footer>
    </div>
  )
}
