const KEY = 'localsms.token'

export const getToken = () => {
  try { return localStorage.getItem(KEY) || '' } catch { return '' }
}
export const setToken = (t) => { try { localStorage.setItem(KEY, t) } catch { /* stockage indisponible */ } }
export const clearToken = () => { try { localStorage.removeItem(KEY) } catch { /* ignore */ } }

/** Le lanceur ouvre http://127.0.0.1:8765/#token=… ; on mémorise puis on efface le fragment. */
export function captureTokenFromHash() {
  const m = window.location.hash.match(/token=([\w-]+)/)
  if (m) {
    setToken(m[1])
    window.history.replaceState(null, '', window.location.pathname + window.location.search)
  }
}

export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', body, params } = {}) {
  const url = new URL('/api/v1' + path, window.location.origin)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v)
    }
  }
  let res
  try {
    res = await fetch(url, {
      method,
      headers: {
        Authorization: `Bearer ${getToken()}`,
        ...(body ? { 'Content-Type': 'application/json' } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Serveur LocalSMS injoignable.')
  }
  let data = null
  try { data = await res.json() } catch { /* corps vide */ }
  if (!res.ok) {
    let msg = data?.detail
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join(' ; ')
    throw new ApiError(res.status, msg || `Erreur ${res.status}`)
  }
  return data
}
