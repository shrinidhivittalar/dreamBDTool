import { useEffect, useState } from 'react'
import { BriefWizard } from './components/BriefWizard'
import { ResultsPanel } from './components/ResultsPanel'
import { categories, initialForm } from './config/brief'
import { exportRecommendations, fetchProducts, fetchRecommendations, repriceRecommendation, uploadProducts } from './lib/api'
import { findMandatoryCategoryConflicts, findMandatoryExcludedConflicts, recommendationPayload, tagsFor } from './lib/briefForm'

export function App() {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState(initialForm)
  const [recommendations, setRecommendations] = useState([])
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [catalogSize, setCatalogSize] = useState(0)
  const [lastBrief, setLastBrief] = useState(null)
  const [catalogRange, setCatalogRange] = useState(null)
  const [products, setProducts] = useState([])
  const [productNames, setProductNames] = useState([])
  const [pendingConflicts, setPendingConflicts] = useState([])
  const [lastPayload, setLastPayload] = useState(null)
  const [exporting, setExporting] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [repricingIndices, setRepricingIndices] = useState(() => new Set())

  useEffect(() => {
    fetchProducts()
      .then(products => {
        if (!products.length) return
        const prices = products.map(product => product.selling_price)
        setCatalogRange({ min: Math.min(...prices), max: Math.max(...prices) })
        setProductNames(products.map(product => product.name))
        setProducts(products)
      })
      .catch(() => {})
  }, [])

  const set = (key, value) => setForm(current => ({ ...current, [key]: value }))
  // Guards against ending up with zero categories checked - an empty
  // selection means "no restriction at all" on the backend, which would
  // silently contradict a user who thinks they've excluded everything.
  const toggleCategory = item => {
    const already = form.preferred_categories.includes(item)
    if (already && form.preferred_categories.length === 1) return
    set('preferred_categories', already
      ? form.preferred_categories.filter(value => value !== item)
      : [...form.preferred_categories, item])
  }
  const applyCategoryPreset = presetCategories => set('preferred_categories', [...presetCategories])
  const budgetInvalid = form.budget_min > form.budget_max
  const maxPossibleTotal = catalogRange ? form.item_count * catalogRange.max : null
  const budgetTooHighForItems = !budgetInvalid && maxPossibleTotal !== null && maxPossibleTotal < form.budget_min
  const addTag = (key, value) => set(key, [...new Set([...tagsFor(form, key), value.trim()])].filter(Boolean).join(', '))
  const removeTag = (key, tag) => set(key, tagsFor(form, key).filter(value => value !== tag).join(', '))
  const catalogNames = { productNames, categoryNames: categories }
  const addMustInclude = value => {
    const trimmed = value.trim()
    if (!trimmed) return
    if (form.must_include.some(entry => entry.value.toLowerCase() === trimmed.toLowerCase())) return
    set('must_include', [...form.must_include, { value: trimmed, mode: 'must' }])
  }
  const removeMustInclude = index => set('must_include', form.must_include.filter((_, i) => i !== index))
  const toggleMustIncludeMode = index => set('must_include', form.must_include.map((entry, i) =>
    i === index ? { ...entry, mode: entry.mode === 'preferred' ? 'must' : 'preferred' } : entry
  ))

  async function runGenerate() {
    setLoading(true)
    setMessage('')
    const payload = { ...recommendationPayload(form, catalogNames), customize_products: [] }
    try {
      const data = await fetchRecommendations(payload)
      // Each card tracks its own customization toggles locally - not part
      // of the shared brief, so a toggle on one card can't affect another.
      setRecommendations(data.recommendations.map(recommendation => ({ ...recommendation, customizeProducts: [] })))
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

  // A Must Include product outside every checked category (e.g. Samosa
  // with "Sweet only" selected) is a real decision the user should make
  // explicitly, not something the app silently resolves either way - stop
  // here and ask, rather than generating with a silent override or a
  // confusing "product not found" error.
  function generate() {
    const contradictions = findMandatoryExcludedConflicts(form)
    if (contradictions.length) {
      // A straight self-contradiction (same item in both Must Include and
      // Exclude) has no "proceed anyway" answer worth offering - unlike
      // the category conflict below, just point at it and stop.
      setMessage(contradictions.map(({ value }) => `"${value}" is in both Must Include and Exclude - remove it from one.`).join(' '))
      return
    }
    const conflicts = findMandatoryCategoryConflicts(form, products)
    if (conflicts.length) {
      setPendingConflicts(conflicts)
      return
    }
    runGenerate()
  }

  function confirmPendingConflicts() {
    setPendingConflicts([])
    runGenerate()
  }

  function cancelPendingConflicts() {
    setPendingConflicts([])
  }

  // Toggling a cupcake's customization re-prices only that one option's
  // fixed product list via /api/recommendations/reprice - it must NOT
  // re-run the search, so the other options and this option's own product
  // list stay exactly as generated.
  async function toggleCustomization(optionIndex, productName) {
    const target = recommendations[optionIndex]
    if (!target) return
    const currentList = target.customizeProducts || []
    const nextList = currentList.includes(productName)
      ? currentList.filter(name => name !== productName)
      : [...currentList, productName]

    setRepricingIndices(current => new Set(current).add(optionIndex))
    try {
      const pricing = await repriceRecommendation({
        products: target.products,
        customize_products: nextList,
        budget_max: form.budget_max,
      })
      setRecommendations(current => current.map((recommendation, index) =>
        index === optionIndex ? { ...recommendation, ...pricing, customizeProducts: nextList } : recommendation
      ))
    } catch (error) {
      setMessage(error.message)
    } finally {
      setRepricingIndices(current => {
        const next = new Set(current)
        next.delete(optionIndex)
        return next
      })
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
        setProductNames(products.map(product => product.name))
        setProducts(products)
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
            budgetInvalid={budgetInvalid}
            budgetTooHighForItems={budgetTooHighForItems}
            catalogRange={catalogRange}
            form={form}
            loading={loading}
            onAddMustInclude={addMustInclude}
            onAddTag={addTag}
            onApplyCategoryPreset={applyCategoryPreset}
            onGenerate={generate}
            onRemoveMustInclude={removeMustInclude}
            onRemoveTag={removeTag}
            onSet={set}
            onStepChange={setStep}
            onToggleMustIncludeMode={toggleMustIncludeMode}
            step={step}
            toggleCategory={toggleCategory}
          />
          <ResultsPanel
            catalogSize={catalogSize}
            lastBrief={lastBrief}
            message={message}
            recommendations={recommendations}
            onExport={exportCurrent}
            exporting={exporting}
            onToggleCustomization={toggleCustomization}
            repricingIndices={repricingIndices}
          />
        </div>
      </main>

      <footer className="mx-auto max-w-[1440px] px-6 pb-4 text-xs text-[#a39891] lg:px-10">
        Dream a Dozen - Business development workspace
      </footer>

      {pendingConflicts.length > 0 && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <p className="modal-title">Outside your selected categories</p>
            <p className="modal-body">
              {pendingConflicts.map(({ value, product }) => (
                <span key={value} className="modal-conflict-line">
                  <strong>{product.name}</strong> is {product.category ? `${product.category}, outside` : 'not in'} your selected categories ({form.preferred_categories.join(', ')}).
                </span>
              ))}
              Include {pendingConflicts.length === 1 ? 'it' : 'them'} anyway, since it's a Must Include item?
            </p>
            <div className="modal-actions">
              <button type="button" className="pill" onClick={cancelPendingConflicts}>Cancel, let me edit</button>
              <button type="button" className="wizard-next" onClick={confirmPendingConflicts}>Include anyway <span>&rarr;</span></button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
