const API_BASE = '/api'

let token: string | null = localStorage.getItem('cryo_token')

export function setToken(t: string | null) {
  token = t
  if (t) localStorage.setItem('cryo_token', t)
  else localStorage.removeItem('cryo_token')
}

export function getToken(): string | null {
  return token
}

async function request(path: string, opts: RequestInit = {}) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(opts.headers as Record<string, string> || {}),
  }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${API_BASE}${path}`, { ...opts, headers })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

// Auth
export const auth = {
  signup: (data: { email: string; username: string; password: string; full_name?: string }) =>
    request('/auth/signup', { method: 'POST', body: JSON.stringify(data) }),
  login: (data: { email: string; password: string }) =>
    request('/auth/login', { method: 'POST', body: JSON.stringify(data) }),
  me: () => request('/auth/me'),
}

// Chat
export const chat = {
  conversations: () => request('/chat/conversations'),
  messages: (id: string) => request(`/chat/conversations/${id}/messages`),
  archive: (id: string) => request(`/chat/conversations/${id}`, { method: 'DELETE' }),
  tools: () => request('/chat/tools'),

  sendStream: (message: string, conversationId?: string) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    return fetch(`${API_BASE}/chat/send`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, conversation_id: conversationId }),
    })
  },
}

// Workspace
export const workspace = {
  list: () => request('/workspace/list'),
  get: (id: string) => request(`/workspace/${id}`),
  create: () => request('/workspace/create', { method: 'POST' }),
  save: (id: string, data: { nodes: any[]; edges: any[] }) =>
    request(`/workspace/${id}/save`, { method: 'POST', body: JSON.stringify(data) }),
  rename: (id: string, name: string) =>
    request(`/workspace/${id}?name=${encodeURIComponent(name)}`, { method: 'PATCH' }),
  remove: (id: string) => request(`/workspace/${id}`, { method: 'DELETE' }),
}
