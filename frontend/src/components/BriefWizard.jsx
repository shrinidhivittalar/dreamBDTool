import { Field } from './Field'
import { MultiSelect } from './MultiSelect'
import { MustIncludeField } from './MustIncludeField'
import { TagField } from './TagField'
import { MAX_ITEM_COUNT, RUPEE, categories, sweetOptions } from '../config/brief'
import { tagsFor } from '../lib/briefForm'

export function BriefWizard({
  budgetInvalid,
  budgetTooHighForItems,
  catalogRange,
  form,
  loading,
  onAddMustInclude,
  onAddTag,
  onGenerate,
  onRemoveMustInclude,
  onRemoveTag,
  onSet,
  onStepChange,
  onToggleMustIncludeMode,
  step,
  toggleCategory,
  visibleCategories,
}) {
  const itemCountLabel = `${form.item_count} items`

  return (
    <aside className="card wizard-card h-fit p-5 sm:p-7">
      <div className="mb-7 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {step === 2 && <button type="button" className="wizard-back-top" onClick={() => onStepChange(1)} aria-label="Back">&larr;</button>}
          <div><p className="wizard-kicker">New brief</p><h2 className="serif mt-1 text-2xl text-[#302a27]">Create a snack box</h2></div>
        </div>
        <span className="wizard-step-count">0{step} / 02</span>
      </div>
      <div className="wizard-progress"><span style={{ width: `${step * 50}%` }} /></div>
      {step === 1 ? <div className="wizard-step"><div className="mb-6"><p className="text-sm font-semibold text-[#3a322e]">Let's set the basics</p><p className="mt-1 text-sm text-[#91857d]">Start with the shape and budget of the box.</p></div>
        <Field label="Budget range" hint={catalogRange ? `Catalog items ${RUPEE}${Math.round(catalogRange.min)}-${RUPEE}${Math.round(catalogRange.max)}` : undefined}><div className="budget-inputs">{[['budget_min', 'Minimum'], ['budget_max', 'Maximum']].map(([key, label]) => <label className="input flex items-center gap-1" key={key}><span>{RUPEE}</span><input aria-label={label} className="min-w-0 flex-1 border-0 bg-transparent p-0 outline-none" type="number" value={form[key]} onChange={e => onSet(key, Math.max(0, Number(e.target.value)))} /></label>)}</div>{budgetInvalid && <p className="field-error">Minimum can't be greater than maximum.</p>}</Field>
        <Field label="Number of items" hint="up to 10">
          <div className="stepper">
            <button type="button" onClick={() => onSet('item_count', Math.max(1, form.item_count - 1))}>-</button>
            <span>{itemCountLabel}</span>
            <button type="button" onClick={() => onSet('item_count', Math.min(MAX_ITEM_COUNT, form.item_count + 1))}>+</button>
          </div>
          {budgetTooHighForItems && <p className="field-note">Even {form.item_count} of the priciest catalog items ({RUPEE}{Math.round(catalogRange.max)} each) can't reach {RUPEE}{Math.round(form.budget_min).toLocaleString()}. Try raising the item count.</p>}
        </Field>
        <Field label="Preference"><div className="segmented-control">{sweetOptions.map(option => <button type="button" key={option.value} className={form.sweet_preference === option.value ? 'selected' : ''} onClick={() => onSet('sweet_preference', option.value)}>{option.label}</button>)}</div></Field>
        <button type="button" className="wizard-next" onClick={() => { if (!budgetInvalid) onStepChange(2) }} disabled={budgetInvalid}>Continue <span>&rarr;</span></button>
      </div> : <div className="wizard-step"><div className="mb-6"><p className="text-sm font-semibold text-[#3a322e]">Shape the selection</p><p className="mt-1 text-sm text-[#91857d]">Tell us what should make it into the box.</p></div>
        <Field label="Categories"><MultiSelect items={visibleCategories} selected={form.preferred_categories} onToggle={toggleCategory} /></Field>
        <Field label="Must include" hint="press enter or use commas - tap Must/Preferred on a tag to set it">
          <MustIncludeField
            entries={form.must_include}
            placeholder="e.g. Brownie or Cookie"
            onAdd={onAddMustInclude}
            onRemove={onRemoveMustInclude}
            onToggleMode={onToggleMustIncludeMode}
          />
        </Field>
        <Field label="Exclude" hint="never include these">
          <TagField tags={tagsFor(form, 'excluded_products')} placeholder="e.g. Samosa" onAdd={value => onAddTag('excluded_products', value)} onRemove={tag => onRemoveTag('excluded_products', tag)} />
        </Field>
        <label className="checkbox-row"><input type="checkbox" checked={form.include_themed_customised} onChange={e => onSet('include_themed_customised', e.target.checked)} /><span>Include themed or customised items</span></label>
        <div className="summary-card"><div><span className="summary-label">Your brief</span><strong>{RUPEE}{form.budget_min.toLocaleString()} - {RUPEE}{form.budget_max.toLocaleString()}</strong></div><span>{itemCountLabel}</span><span>{form.preferred_categories.length ? form.preferred_categories.join(', ') : 'Any category'}</span><span>{sweetOptions.find(option => option.value === form.sweet_preference)?.label}</span></div>
        <div className="wizard-actions"><button onClick={() => onGenerate()} disabled={loading} className="wizard-next flex-1">{loading ? 'Finding a good fit...' : 'Generate recommendations'} <span>&rarr;</span></button></div>
      </div>}
    </aside>
  )
}
