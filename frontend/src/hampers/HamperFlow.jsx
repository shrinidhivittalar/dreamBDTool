import { useEffect, useState } from 'react'
import { HamperWizard } from './HamperWizard'
import { HamperResultsPanel } from './HamperResultsPanel'
import { initialHamperForm, hamperCategories } from '../config/hamper'
import { fetchHamperCatalogStatus, fetchHamperProducts, fetchHamperRecommendations, uploadHamperCatalog } from '../lib/hamperApi'

export function HamperFlow() {
  const [form, setForm] = useState(initialHamperForm)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [catalogStatus, setCatalogStatus] = useState(null)
  const [productNames, setProductNames] = useState([])
  const [uploading, setUploading] = useState(false)

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
    }
    try {
      const data = await fetchHamperRecommendations(payload)
      setResult(data)
      setMessage(data.message || '')
    } catch (error) {
      setMessage(error.message)
      setResult(null)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[minmax(0,560px)_1fr] xl:grid-cols-[600px_1fr]">
      <HamperWizard
        budgetInvalid={budgetInvalid}
        catalogStatus={catalogStatus}
        form={form}
        loading={loading}
        onGenerate={generate}
        onSet={set}
        onUploadCatalog={uploadCatalog}
        productNames={productNames}
        toggleCategory={toggleCategory}
        uploading={uploading}
      />
      <HamperResultsPanel loading={loading} message={message} result={result} />
    </div>
  )
}
