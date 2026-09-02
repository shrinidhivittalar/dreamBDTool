import { useState } from 'react'
import { App } from './App'
import { HamperFlow } from './hampers/HamperFlow'
import { Sidebar } from './Sidebar'

// Persistent sidebar replaces the old landing-page fork: Snack Box and
// Hamper are still separate flows/pipelines internally (matches the
// agreed architecture - see HamperFlow/App), just switched via nav instead
// of a full-page choice screen. Default flow is Snack Box, the original
// product; Hamper is reached via the sidebar like Snack Box always was.
export function Shell() {
  const [flow, setFlow] = useState('snackbox')

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar flow={flow} onSelect={setFlow} />

      <div className="dad-main">
        {flow === 'snackbox' ? (
          <div className="brand-dad min-h-screen">
            <App hideBrand />
          </div>
        ) : (
          <div className="brand-dad min-h-screen">
            <main className="mx-auto max-w-[1440px] px-6 py-4 lg:px-10 lg:py-5">
              <div className="mb-3 flex flex-col justify-between gap-3 md:flex-row md:items-end">
                <div>
                  <p className="mb-0.5 text-[11px] font-bold uppercase tracking-[.2em]" style={{ color: 'var(--dad-accent-strong)' }}>Corporate gifting / new brief</p>
                  <h1 className="serif text-xl leading-tight md:text-2xl" style={{ color: 'var(--dad-ink)' }}>
                    Build a thoughtful <span style={{ color: 'var(--dad-cta)' }}>hamper.</span>
                  </h1>
                </div>
                <div className="max-w-sm text-xs leading-5" style={{ color: 'var(--dad-ink-soft)' }}>
                  Set the budget once. We'll match containers to items and show you exactly how full and how within-budget each option is.
                </div>
              </div>

              <HamperFlow />
            </main>
          </div>
        )}
      </div>
    </div>
  )
}
