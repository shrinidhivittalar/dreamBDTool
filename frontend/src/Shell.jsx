import { useState } from 'react'
import { App } from './App'
import { HamperFlow } from './hampers/HamperFlow'
import { LandingChoice } from './LandingChoice'

// Top-level fork, matching the agreed architecture: Snack Box and Hamper
// are separate flows/pipelines, not steps of one wizard. No router - the
// rest of the app already uses plain state for screen switching (see
// BriefWizard's step state), so this follows the same pattern.
export function Shell() {
  const [flow, setFlow] = useState('landing')

  if (flow === 'landing') return <LandingChoice onChoose={setFlow} />
  if (flow === 'snackbox') return <App onBackToLanding={() => setFlow('landing')} />

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
            <button type="button" className="pill" onClick={() => setFlow('landing')}>&larr; Switch flow</button>
            <span className="hidden sm:inline">Internal use only</span>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1440px] px-6 py-5 lg:px-10 lg:py-6">
        <div className="mb-5 flex flex-col justify-between gap-3 md:flex-row md:items-end">
          <div>
            <p className="mb-1 text-[11px] font-bold uppercase tracking-[.2em] text-[#bd285c]">Corporate gifting / new brief</p>
            <h1 className="serif text-2xl leading-tight text-[#302a27] md:text-[28px]">
              Build a thoughtful <span className="text-[#bd285c]">hamper.</span>
            </h1>
          </div>
          <div className="max-w-sm text-xs leading-5 text-[#766b64]">
            Set the budget once. We'll match containers to items and show you exactly how full and how within-budget each option is.
          </div>
        </div>

        <HamperFlow />
      </main>

      <footer className="mx-auto max-w-[1440px] px-6 pb-4 text-xs text-[#a39891] lg:px-10">
        Dream a Dozen - Business development workspace
      </footer>
    </div>
  )
}
