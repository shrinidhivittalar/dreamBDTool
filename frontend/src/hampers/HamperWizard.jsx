import { Field } from '../components/Field'
import { MultiSelect } from '../components/MultiSelect'
import { TagField } from '../components/TagField'
import { MAX_HAMPER_OPTION_COUNT, MAX_ITEMS_PER_BOX, RUPEE, hamperCategories } from '../config/hamper'

export function HamperWizard({
  budgetInvalid,
  catalogStatus,
  form,
  loading,
  onGenerate,
  onSet,
  onUploadCatalog,
  productNames,
  toggleCategory,
  uploading,
}) {
  return (
    <aside className="card wizard-card h-fit p-4 sm:p-5">
      <div className="mb-2.5 flex items-center justify-between">
        <div>
          <p className="wizard-kicker">New brief</p>
          <h2 className="serif mt-0.5 text-lg text-[#301736]">Create a hamper</h2>
        </div>
        {onUploadCatalog && (
          <label className="pill" style={{ cursor: uploading ? 'default' : 'pointer' }}>
            {uploading ? 'Uploading...' : 'Upload catalog'}
            <input type="file" accept=".xlsx,.xls,.csv" className="hidden" onChange={onUploadCatalog} disabled={uploading} />
          </label>
        )}
      </div>

      <Field label="Budget range" hint={catalogStatus ? `${catalogStatus.container_count} containers, ${catalogStatus.item_count} items in catalog` : undefined}>
        <div className="budget-inputs">
          {[['budget_min', 'Minimum'], ['budget_max', 'Maximum']].map(([key, label]) => (
            <label className="input flex items-center gap-1" key={key}>
              <span>{RUPEE}</span>
              <input
                aria-label={label}
                className="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none"
                type="number"
                value={form[key]}
                onChange={e => {
                  const raw = e.target.value
                  onSet(key, raw === '' ? '' : Math.max(0, Number(raw)))
                }}
                onBlur={e => { if (e.target.value === '') onSet(key, 0) }}
              />
            </label>
          ))}
        </div>
        {budgetInvalid && <p className="field-error">Minimum can't be greater than maximum.</p>}
      </Field>

      <Field label={`Number of options: ${form.option_count}`} hint={`up to ${MAX_HAMPER_OPTION_COUNT}`}>
        <div className="stepper">
          <button type="button" onClick={() => onSet('option_count', Math.max(1, form.option_count - 1))}>-</button>
          <span>{form.option_count}</span>
          <button type="button" onClick={() => onSet('option_count', Math.min(MAX_HAMPER_OPTION_COUNT, form.option_count + 1))}>+</button>
        </div>
      </Field>

      <Field label="Items per box" hint={form.items_per_box == null ? 'no constraint' : `up to ${MAX_ITEMS_PER_BOX}`}>
        <div className="flex items-center gap-3">
          <div className="stepper">
            <button
              type="button"
              onClick={() => onSet('items_per_box', form.items_per_box == null ? 1 : Math.max(1, form.items_per_box - 1))}
            >-</button>
            <span>{form.items_per_box == null ? 'Any' : form.items_per_box}</span>
            <button
              type="button"
              onClick={() => onSet('items_per_box', form.items_per_box == null ? 1 : Math.min(MAX_ITEMS_PER_BOX, form.items_per_box + 1))}
            >+</button>
          </div>
          {form.items_per_box != null && (
            <button
              type="button"
              className="text-xs font-semibold text-[#a5690a] underline"
              onClick={() => onSet('items_per_box', null)}
            >Clear</button>
          )}
        </div>
      </Field>

      <Field label="Preferred categories" hint="at least these should be present">
        <MultiSelect items={hamperCategories} selected={form.preferred_categories} onToggle={toggleCategory} />
        <p className="field-note">We'll cover every selected category when possible - fallbacks are clearly marked.</p>
      </Field>

      <Field label="Mandatory products (optional)" hint="these must be included">
        <TagField
          tags={form.mandatory_products}
          placeholder="Search by product name..."
          suggestions={productNames}
          onAdd={value => onSet('mandatory_products', [...new Set([...form.mandatory_products, value.trim()])].filter(Boolean))}
          onRemove={tag => onSet('mandatory_products', form.mandatory_products.filter(value => value !== tag))}
        />
      </Field>

      <Field label="Excluded products (optional)" hint="these will not be included">
        <TagField
          tags={form.excluded_products_list}
          placeholder="Search by product name..."
          suggestions={productNames}
          onAdd={value => onSet('excluded_products_list', [...new Set([...form.excluded_products_list, value.trim()])].filter(Boolean))}
          onRemove={tag => onSet('excluded_products_list', form.excluded_products_list.filter(value => value !== tag))}
        />
      </Field>

      <div className="wizard-actions">
        <button onClick={onGenerate} disabled={loading || budgetInvalid} className="wizard-next flex-1">
          {loading ? 'Finding a good fit...' : 'Generate recommendations'} <span>&rarr;</span>
        </button>
      </div>
    </aside>
  )
}
