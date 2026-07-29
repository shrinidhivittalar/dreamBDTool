const API = ''

export async function fetchRecommendations(payload) {
  const response = await fetch(`${API}/api/recommendations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error('Could not reach the recommendation service')
  return response.json()
}
