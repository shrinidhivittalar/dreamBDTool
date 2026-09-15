// Shown only on products that came from this request's "one-off item" list
// (see CustomItemField.jsx) - lets a BD user carry a client-requested item
// they liked forward into the real catalog for every future brief, on this
// deployed backend, for every user. See lib/api.js::promoteProduct /
// lib/hamperApi.js::promoteHamperItem for the actual call; the confirmation
// copy lives one level up (App.jsx / HamperFlow.jsx) so it can be shown
// before the call, not just after.
export function PromoteButton({ promoted, promoting, onClick }) {
  if (promoted) {
    return <span className="badge badge-promoted">✓ In catalog now</span>
  }
  return (
    <button type="button" className="promote-btn" disabled={promoting} onClick={onClick}>
      {promoting ? 'Adding...' : '+ Make permanent'}
    </button>
  )
}
