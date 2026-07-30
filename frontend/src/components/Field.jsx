export function Field({ label, hint, children }) {
  return (
    <label className="block mb-3">
      <span className="flex justify-between mb-1.5 text-[12px] font-semibold tracking-wide text-[#665d58] uppercase">
        <span>{label}</span>
        {hint && <span className="font-normal normal-case tracking-normal text-[#968b84]">{hint}</span>}
      </span>
      {children}
    </label>
  )
}
