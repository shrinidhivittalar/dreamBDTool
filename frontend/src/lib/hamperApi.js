const API = import.meta.env.VITE_API_URL || ''

export async function fetchHamperCatalogStatus() {
  const response = await fetch(`${API}/api/hampers/catalog/status`)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json()
}

export async function fetchHamperRecommendations(payload) {
  let response
  try {
    response = await fetch(`${API}/api/hampers/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch (err) {
    if (err instanceof TypeError && !(err.message || '').toLowerCase().includes('fetch')) throw err
    throw new Error('Backend is not connected yet. Start FastAPI to generate live hamper recommendations.')
  }
  if (!response.ok) {
    let detail = null
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map(item => item.msg).join('; ')
    } catch {}
    throw new Error(detail || 'Backend is not connected yet. Start FastAPI to generate live hamper recommendations.')
  }
  return response.json()
}
