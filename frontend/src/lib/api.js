const API_BASE = import.meta.env.VITE_API_URL || 'http://127.0.0.1:2500'

export { API_BASE }

export async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      ...(options.body instanceof FormData ? {} : { 'Content-Type': 'application/json' }),
      ...(options.headers || {}),
    },
    ...options,
  })

  if (!response.ok) {
    const payload = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new Error(payload.detail || 'Request failed')
  }

  return response.json()
}
