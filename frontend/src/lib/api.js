const API = ''

export async function fetchProducts() {
  const response = await fetch(`${API}/api/products`)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json()
}

export async function fetchRecommendations(payload) {
  let response
  try {
    response = await fetch(`${API}/api/recommendations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
  } catch {
    throw new Error('Backend is not connected yet. Start FastAPI to generate live recommendations.')
  }
  if (!response.ok) {
    let detail = null
    try {
      const body = await response.json()
      if (typeof body.detail === 'string') detail = body.detail
      else if (Array.isArray(body.detail)) detail = body.detail.map(item => item.msg).join('; ')
    } catch {}
    throw new Error(detail || 'Backend is not connected yet. Start FastAPI to generate live recommendations.')
  }
  return response.json()
}
