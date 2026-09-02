export function Field({ label, hint, children }) {
  return (
    <label className="block mb-1.5">
      <span className="flex flex-wrap justify-between gap-x-2 mb-0.5 text-[11px] font-semibold tracking-wide text-[#4c1f53] uppercase">
        <span className="min-w-0">{label}</span>
        {hint && <span className="min-w-0 font-normal normal-case tracking-normal text-[#6b5570]">{hint}</span>}
      </span>
      {children}
    </label>
  )
}
