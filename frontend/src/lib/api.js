// In local dev, Vite's proxy forwards /api to the backend, so '' (relative)
// works. In production the frontend and backend are separate Render
// services on different hosts, so VITE_API_URL must point at the backend.
const API = import.meta.env.VITE_API_URL || ''

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

export async function exportRecommendations(payload, format, layout = 'summary') {
  const response = await fetch(`${API}/api/recommendations/export/${format}?layout=${layout}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(`Export failed (${response.status})`)
  return response.blob()
}

export async function fetchProductStatus() {
  const response = await fetch(`${API}/api/products/status`)
  if (!response.ok) throw new Error(`Request failed (${response.status})`)
  return response.json()
}

export async function refreshProducts() {
  const response = await fetch(`${API}/api/products/refresh`, { method: 'POST' })
  if (!response.ok) throw new Error(`Refresh failed (${response.status})`)
  return response.json()
}

export async function uploadProducts(file) {
  const response = await fetch(`${API}/api/products/upload`, {
    method: 'POST',
    headers: { 'x-filename': file.name },
    body: await file.arrayBuffer(),
  })
  if (!response.ok) throw new Error(`Upload failed (${response.status})`)
  return response.json()
}
