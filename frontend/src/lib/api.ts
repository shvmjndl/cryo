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

  sendStream: (message: string, conversationId?: string, fileIds?: string[]) => {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' }
    if (token) headers['Authorization'] = `Bearer ${token}`

    return fetch(`${API_BASE}/chat/send`, {
      method: 'POST',
      headers,
      body: JSON.stringify({ message, conversation_id: conversationId, file_ids: fileIds?.length ? fileIds : undefined }),
    })
  },
}

// Uploads
export interface UploadRecord {
  id: string
  original_filename: string
  server_path: string
  file_size: number
  mime_type: string | null
  file_ext: string | null
  data_type: string | null
  suggested_command: string | null
  times_used: number
  created_at: string
}

export const uploads = {
  list: (): Promise<UploadRecord[]> => request('/uploads'),

  upload: (file: File, conversationId?: string, onProgress?: (pct: number) => void): Promise<UploadRecord> => {
    return new Promise((resolve, reject) => {
      const formData = new FormData()
      formData.append('file', file)
      const url = conversationId
        ? `${API_BASE}/uploads?conversation_id=${conversationId}`
        : `${API_BASE}/uploads`
      const xhr = new XMLHttpRequest()
      xhr.open('POST', url)
      if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
      xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress?.(Math.round(e.loaded / e.total * 100)) }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText))
        else reject(new Error(JSON.parse(xhr.responseText)?.detail || `HTTP ${xhr.status}`))
      }
      xhr.onerror = () => reject(new Error('Upload failed'))
      xhr.send(formData)
    })
  },

  remove: (id: string) => request(`/uploads/${id}`, { method: 'DELETE' }),
}

// Document Collections
export interface CollectionRecord {
  id: string
  name: string
  description: string | null
  file_count: number
  conversation_id: string | null
  created_at: string
}

export interface CollectionFileRecord {
  id: string
  collection_id: string
  original_filename: string
  original_path: string
  markdown_path: string | null
  file_size: number
  file_ext: string | null
  status: 'pending' | 'processing' | 'done' | 'error'
  error_message: string | null
  created_at: string
  processed_at: string | null
  collection: CollectionRecord
}

export const collections = {
  list: (conversationId?: string): Promise<CollectionRecord[]> =>
    request(`/collections${conversationId ? `?conversation_id=${conversationId}` : ''}`),

  listFiles: (conversationId?: string): Promise<CollectionFileRecord[]> =>
    collections.list(conversationId).then(async cols => {
      if (!cols.length) return []
      const col = await collections.get(cols[0].id)
      return col.files ?? []
    }),

  get: (id: string): Promise<CollectionRecord & { files: CollectionFileRecord[] }> =>
    request(`/collections/${id}`),

  create: (name: string, conversationId?: string): Promise<CollectionRecord> =>
    request(`/collections?name=${encodeURIComponent(name)}${conversationId ? `&conversation_id=${conversationId}` : ''}`, { method: 'POST' }),

  upload: (
    file: File,
    opts: { collectionId?: string; conversationId?: string; collectionName?: string },
    onProgress?: (pct: number) => void,
  ): Promise<CollectionFileRecord> => {
    return new Promise((resolve, reject) => {
      const formData = new FormData()
      formData.append('file', file)
      const params = new URLSearchParams()
      if (opts.collectionId) params.set('collection_id', opts.collectionId)
      if (opts.conversationId) params.set('conversation_id', opts.conversationId)
      if (opts.collectionName) params.set('collection_name', opts.collectionName)
      const url = `${API_BASE}/collections/upload?${params.toString()}`
      const xhr = new XMLHttpRequest()
      xhr.open('POST', url)
      const storedToken = localStorage.getItem('cryo_token')
      if (storedToken) xhr.setRequestHeader('Authorization', `Bearer ${storedToken}`)
      xhr.upload.onprogress = e => { if (e.lengthComputable) onProgress?.(Math.round(e.loaded / e.total * 100)) }
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) resolve(JSON.parse(xhr.responseText))
        else reject(new Error(JSON.parse(xhr.responseText)?.detail || `HTTP ${xhr.status}`))
      }
      xhr.onerror = () => reject(new Error('Upload failed'))
      xhr.send(formData)
    })
  },

  fileStatus: (collectionId: string, fileId: string): Promise<CollectionFileRecord & { markdown?: string }> =>
    request(`/collections/${collectionId}/files/${fileId}`),

  search: (collectionId: string, q: string, limit = 10) =>
    request(`/collections/${collectionId}/search?q=${encodeURIComponent(q)}&limit=${limit}`),
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
