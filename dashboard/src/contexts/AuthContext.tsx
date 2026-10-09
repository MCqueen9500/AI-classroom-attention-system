// src/contexts/AuthContext.tsx
// Provides authentication state across the entire app.

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import { useNavigate } from 'react-router-dom'

export interface AuthUser {
  token: string
  username: string
  name: string
  is_admin: boolean
  subject?: string
  division?: string
}

interface AuthContextValue {
  user: AuthUser | null
  loading: boolean
  login: (token: string, user: Omit<AuthUser, 'token'>) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

// @ts-ignore
const API = (import.meta.env.VITE_API_URL || '') + '/api'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  // Restore session on mount
  useEffect(() => {
    const token = localStorage.getItem('token')
    if (!token) {
      setLoading(false)
      return
    }

    fetch(`${API}/auth/me`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
    })
      .then(res => {
        if (!res.ok) throw new Error('Session expired')
        return res.json()
      })
      .then((data: Omit<AuthUser, 'token'>) => {
        setUser({ token, ...data })
      })
      .catch(() => {
        localStorage.removeItem('token')
      })
      .finally(() => setLoading(false))
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const login = useCallback(
    (token: string, userInfo: Omit<AuthUser, 'token'>) => {
      localStorage.setItem('token', token)
      const fullUser: AuthUser = { token, ...userInfo }
      setUser(fullUser)
    },
    []
  )

  const logout = useCallback(() => {
    localStorage.removeItem('token')
    setUser(null)
    navigate('/login')
  }, [navigate])

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>')
  return ctx
}
