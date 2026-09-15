import { useEffect, useState } from 'react'
import { CatalogPreviewDialog } from '../components/CatalogPreviewDialog'
import { HamperWizard } from './HamperWizard'
import { HamperResultsPanel } from './HamperResultsPanel'
import { initialHamperForm, hamperCategories } from '../config/hamper'
import { fetchHamperCatalogPreview, fetchHamperCatalogStatus, fetchHamperProducts, fetchHamperRecommendations, promoteHamperItem, uploadHamperCatalog } from '../lib/hamperApi'

export function HamperFlow() {
  const [form, setForm] = useState(initialHamperForm)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [catalogStatus, setCatalogStatus] = useState(null)
  const [productNames, setProductNames] = useState([])
  const [uploading, setUploading] = useState(false)
  const [catalogPreviewOpen, setCatalogPreviewOpen] = useState(false)
  const [lastCustomItems, setLastCustomItems] = useState([])
  const [pendingPromote, setPendingPromote] = useState(null)
  const [promoting, setPromoting] = useState(false)
  const [promotedNames, setPromotedNames] = useState(() => new Set())

  function refreshCatalogInfo() {
    fetchHamperCatalogStatus().then(setCatalogStatus).catch(() => {})
    fetchHamperProducts().then(setProductNames).catch(() => {})
  }

  useEffect(() => {
    refreshCatalogInfo()
  }, [])

  async function uploadCatalog(event) {
    const file = event.target.files?.[0]
    if (!file) return
    setUploading(true)
    try {
      await uploadHamperCatalog(file)
      refreshCatalogInfo()
    } catch (error) {
      setMessage(error.message)
    } finally {
      setUploading(false)
      event.target.value = ''
    }
  }

  const set = (key, value) => setForm(current => ({ ...current, [key]: value }))
  // Same guard as the snack-box wizard: an empty category selection means
  // "no restriction" on the backend, which would silently contradict a user
  // who thinks they've deselected everything.
  const toggleCategory = item => {
    const already = form.preferred_categories.includes(item)
    if (already && form.preferred_categories.length === 1) return
    set('preferred_categories', already
      ? form.preferred_categories.filter(value => value !== item)
      : [...form.preferred_categories, item])
  }
  // '' is a transient state while the user is mid-edit (backspacing the
  // field to retype it) - see HamperWizard's budget input onChange. Treated
  // as invalid here (not coerced to 0) so Generate stays disabled until a
  // real number is entered, rather than silently submitting budget_min=0.
  const budgetInvalid = form.budget_min === '' || form.budget_max === '' || form.budget_min > form.budget_max
  const addCustomItem = entry => set('custom_items', [...form.custom_items, entry])
  const removeCustomItem = index => set('custom_items', form.custom_items.filter((_, i) => i !== index))

  async function generate() {
    setLoading(true)
    setMessage('')
    const payload = {
      budget_min: form.budget_min,
      budget_max: form.budget_max,
      option_count: form.option_count,
      items_per_box: form.items_per_box,
      preferred_categories: form.preferred_categories.length === hamperCategories.length ? [] : form.preferred_categories,
      mandatory_products: form.mandatory_products,
      excluded_products: form.excluded_products_list,
      custom_items: form.custom_items,
    }
    try {
      const data = await fetchHamperRecommendations(payload)
      setResult(data)
      setMessage(data.message || '')
      setLastCustomItems(payload.custom_items)
    } catch (error) {
      setMessage(error.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  function requestPromote(entry) {
    setPendingPromote(entry)
  }

  function cancelPromote() {
    setPendingPromote(null)
  }

  async function confirmPromote() {
    if (!pendingPromote) return
    setPromoting(true)
    try {
      await promoteHamperItem(pendingPromote)
      setPromotedNames(current => new Set(current).add(pendingPromote.name))
    } catch (error) {
      if (String(error.message).toLowerCase().includes('already in the catalog')) {
        setPromotedNames(current => new Set(current).add(pendingPromote.name))
      } else {
        setMessage(error.message)
      }
    } finally {
      setPromoting(false)
      setPendingPromote(null)
    }
  }

  return (
    <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,560px)_1fr] xl:grid-cols-[600px_1fr]">
      <HamperWizard
        budgetInvalid={budgetInvalid}
        catalogStatus={catalogStatus}
        form={form}
        loading={loading}
        onAddCustomItem={addCustomItem}
        onGenerate={generate}
        onRemoveCustomItem={removeCustomItem}
        onSet={set}
        onUploadCatalog={uploadCatalog}
        onViewCatalog={() => setCatalogPreviewOpen(true)}
        productNames={productNames}
        toggleCategory={toggleCategory}
        uploading={uploading}
      />
      <HamperResultsPanel
        customItems={lastCustomItems}
        loading={loading}
        message={message}
        onPromote={requestPromote}
        promotedNames={promotedNames}
        promotingName={promoting ? pendingPromote?.name : null}
        result={result}
      />

      <CatalogPreviewDialog
        open={catalogPreviewOpen}
        onClose={() => setCatalogPreviewOpen(false)}
        title="Hamper catalog"
        fetcher={fetchHamperCatalogPreview}
      />

      {pendingPromote && (
        <div className="modal-backdrop" role="dialog" aria-modal="true">
          <div className="modal-card">
            <p className="modal-title">Add "{pendingPromote.name}" to the catalog?</p>
            <p className="modal-body">
              <span className="modal-conflict-line">This makes it a real catalog item - available to everyone using this tool, in every future brief, not just this one.</span>
              <span className="modal-conflict-line">It stays in the catalog until the next time this app is updated and redeployed - after that, you may need to add it again.</span>
            </p>
            <div className="modal-actions">
              <button type="button" className="pill" onClick={cancelPromote} disabled={promoting}>Cancel</button>
              <button type="button" className="wizard-next" onClick={confirmPromote} disabled={promoting}>
                {promoting ? 'Adding...' : 'Add to catalog'} <span>&rarr;</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
