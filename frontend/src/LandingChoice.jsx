export function LandingChoice({ onChoose }) {
  return (
    <main className="mx-auto max-w-[1440px] px-6 py-16 lg:px-10">
      <div className="mx-auto max-w-2xl text-center">
        <p className="mb-1 text-[11px] font-bold uppercase tracking-[.2em] text-[#bd285c]">Corporate gifting / new brief</p>
        <h1 className="serif text-2xl leading-tight text-[#302a27] md:text-[28px]">What are you building today?</h1>
        <p className="mt-3 text-sm leading-6 text-[#766b64]">Snack boxes and hampers use different logic and catalogs - pick one to start.</p>
      </div>

      <div className="mx-auto mt-10 grid max-w-2xl grid-cols-1 gap-4 sm:grid-cols-2">
        <button type="button" className="card landing-choice-card" onClick={() => onChoose('snackbox')}>
          <span className="landing-choice-icon">📦</span>
          <span className="serif text-xl text-[#302a27]">Snack Box</span>
          <span className="mt-1 text-sm text-[#83776f]">A single box of items, priced per box within a budget.</span>
        </button>
        <button type="button" className="card landing-choice-card" onClick={() => onChoose('hamper')}>
          <span className="landing-choice-icon">🎁</span>
          <span className="serif text-xl text-[#302a27]">Hamper</span>
          <span className="mt-1 text-sm text-[#83776f]">A container plus items, matched by budget, category and fit.</span>
        </button>
      </div>
    </main>
  )
}
