import { useState, useEffect, useCallback } from 'react'
import { auth as authApi, setToken, getToken } from '../lib/api'

interface User {
  id: string
  email: string
  username: string
  full_name: string | null
  role: string
  institution: string | null
}

export function useAuth() {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const t = getToken()
    if (t) {
      authApi.me()
        .then(u => setUser(u))
        .catch(() => { setToken(null); setUser(null) })
        .finally(() => setLoading(false))
    } else {
      setLoading(false)
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const res = await authApi.login({ email, password })
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const signup = useCallback(async (data: { email: string; username: string; password: string; full_name?: string }) => {
    const res = await authApi.signup(data)
    setToken(res.access_token)
    setUser(res.user)
  }, [])

  const logout = useCallback(() => {
    setToken(null)
    setUser(null)
  }, [])

  return { user, loading, login, signup, logout }
}
