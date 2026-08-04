import { useEffect, useState } from 'react'
import { BriefWizard } from './components/BriefWizard'
import { ResultsPanel } from './components/ResultsPanel'
import { categories, initialForm } from './config/brief'
import { exportRecommendations, fetchProducts, fetchRecommendations, refreshProducts, uploadProducts } from './lib/api'
import { recommendationPayload, tagsFor } from './lib/briefForm'

export function App() {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState(initialForm)
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [catalogSize, setCatalogSize] = useState(0)
  const [lastBrief, setLastBrief] = useState(null)
  const [catalogRange, setCatalogRange] = useState(null)
  const [lastPayload, setLastPayload] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)

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
  const toggleCategory = item => set('preferred_categories', form.preferred_categories.includes(item) ? form.preferred_categories.filter(value => value !== item) : [...form.preferred_categories, item])
  const budgetInvalid = form.budget_min > form.budget_max
  const maxPossibleTotal = catalogRange && !form.no_item_count_preference ? form.item_count * catalogRange.max : null
  const budgetTooHighForItems = !budgetInvalid && maxPossibleTotal !== null && maxPossibleTotal < form.budget_min
  const visibleCategories = form.sweet_preference === 'sweet_only'
    ? categories.filter(item => item.toLowerCase().includes('sweet'))
    : form.sweet_preference === 'savory_only'
      ? categories.filter(item => !item.toLowerCase().includes('sweet'))
      : categories
  const addTag = (key, value) => set(key, [...new Set([...tagsFor(form, key), value.trim()])].filter(Boolean).join(', '))
  const removeTag = (key, tag) => set(key, tagsFor(form, key).filter(value => value !== tag).join(', '))
  const advancedCount = [
    tagsFor(form, 'required_categories').length > 0,
    tagsFor(form, 'preferred_products').length > 0,
    tagsFor(form, 'excluded_products').length > 0,
    form.include_themed_customised,
  ].filter(Boolean).length

  async function generate() {
    setLoading(true)
    setMessage('')
    const payload = recommendationPayload(form)
    try {
      const data = await fetchRecommendations(payload)
      setRecommendations(data.recommendations)
      setCatalogSize(data.catalog_size)
      setMessage(data.message || '')
      setLastBrief({
        mandatoryProducts: payload.mandatory_products,
        requiredCategories: payload.required_categories,
      })
      setLastPayload(payload)
    } catch (error) {
      setMessage(error.message)
      setRecommendations([])
    } finally {
      setLoading(false)
    }
  }

  async function exportCurrent(format, layout) {
    if (!lastPayload) return
    setExporting(true)
    try {
      const blob = await exportRecommendations(lastPayload, format, layout)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `dream-a-dozen-${layout}.${format}`
      link.click()
      URL.revokeObjectURL(url)
    } catch (error) {
      setMessage(error.message)
    } finally {
      setExporting(false)
    }
  }

  async function pullCatalogNow() {
    setRefreshing(true)
    try {
      await refreshProducts()
      const products = await fetchProducts()
      if (products.length) {
        const prices = products.map(product => product.selling_price)
        setCatalogRange({ min: Math.min(...prices), max: Math.max(...prices) })
      }
    } catch (error) {
      setMessage(error.message)
    } finally {
      setRefreshing(false)
    }
  }

  async function uploadCatalog(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setRefreshing(true)
    try {
      await uploadProducts(file)
      const products = await fetchProducts()
      if (products.length) {
        const prices = products.map(product => product.selling_price)
        setCatalogRange({ min: Math.min(...prices), max: Math.max(...prices) })
      }
    } catch (error) {
      setMessage(error.message)
    } finally {
      setRefreshing(false)
      event.target.value = ''
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
          <div className="flex items-center gap-3 text-[13px] text-[#766b64]">
            <span className="hidden sm:inline">Internal use only</span>
            <span className="h-2 w-2 rounded-full bg-[#5d9c78]" />
            <span>Catalog ready</span>
            <button type="button" className="pill" disabled={refreshing} onClick={pullCatalogNow}>{refreshing ? 'Pulling...' : 'Pull catalog now'}</button>
            <label className="pill" style={{ cursor: 'pointer' }}>
              Upload catalog
              <input type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={uploadCatalog} disabled={refreshing} />
            </label>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-6 py-5 lg:px-10 lg:py-6">
        <div className="mb-5 flex flex-col justify-between gap-3 md:flex-row md:items-end">
          <div>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-[.2em] text-[#bd285c]">Corporate gifting / new brief</p>
            <h1 className="serif text-2xl leading-tight text-[#302a27] md:text-[28px]">
              Build a thoughtful <span className="text-[#bd285c]">snack box.</span>
            </h1>
          </div>
          <div className="max-w-sm text-xs leading-5 text-[#766b64]">
            Set the brief once. We'll surface combinations your client can actually use - priced with a little breathing room.
          </div>
        </div>

        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[minmax(0,560px)_1fr] xl:grid-cols-[600px_1fr]">
          <BriefWizard
            advancedCount={advancedCount}
            budgetInvalid={budgetInvalid}
            budgetTooHighForItems={budgetTooHighForItems}
            catalogRange={catalogRange}
            form={form}
            loading={loading}
            onAddTag={addTag}
            onGenerate={generate}
            onRemoveTag={removeTag}
            onSet={set}
            onStepChange={setStep}
            step={step}
            toggleCategory={toggleCategory}
            visibleCategories={visibleCategories}
          />
          <ResultsPanel
            catalogSize={catalogSize}
            lastBrief={lastBrief}
            message={message}
            recommendations={recommendations}
            onExport={exportCurrent}
            exporting={exporting}
          />
        </div>
      </main>

      <footer className="mx-auto max-w-[1440px] px-6 pb-4 text-xs text-[#a39891] lg:px-10">
        Dream a Dozen - Business development workspace
      </footer>
    </div>
  )
}
