import { createContext, useContext, useEffect, useState } from 'react'
import api from '../api/client'
import toast from 'react-hot-toast'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    api.get('/auth/me')
      .then(({ data }) => setUser(data))
      .catch((error) => {
        setUser(null)
        if (error.response?.status !== 401) console.error('Could not validate the login session', error)
      })
      .finally(() => setLoading(false))
  }, [])

  const login = async (email, password) => {
    setLoading(true)
    try {
      const res = await api.post('/auth/login', { email, password })
      const { user: userData } = res.data
      setUser(userData)
      toast.success(`Welcome back, ${userData.name}! 🌾`)
      return { success: true }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Login failed'
      toast.error(msg)
      return { success: false, error: msg }
    } finally {
      setLoading(false)
    }
  }

  const register = async (name, email, password, phone) => {
    setLoading(true)
    try {
      const res = await api.post('/auth/register', { name, email, password, phone })
      const { user: userData } = res.data
      setUser(userData)
      toast.success(`Welcome to AI Farm Guardian, ${userData.name}! 🌱`)
      return { success: true }
    } catch (err) {
      const msg = err.response?.data?.detail || 'Registration failed'
      toast.error(msg)
      return { success: false, error: msg }
    } finally {
      setLoading(false)
    }
  }

  const logout = async () => {
    try {
      await api.post('/auth/logout')
    } catch {
      toast.error('Could not confirm logout with the server')
    }
    setUser(null)
    toast.success('Logged out successfully')
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => useContext(AuthContext)
