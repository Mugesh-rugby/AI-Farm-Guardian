import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import api from '../api/client'
import { useAuth } from './AuthContext'

const defaultFarmState = {
  farms: [],
  activeFarm: null,
  setActiveFarm: () => {},
  loading: false,
  fetchFarms: () => {},
}

const FarmContext = createContext(defaultFarmState)

export function FarmProvider({ children }) {
  const { user } = useAuth()
  const [farms, setFarms] = useState([])
  const [activeFarm, setActiveFarm] = useState(null)
  const [loading, setLoading] = useState(false)
  const requestVersion = useRef(0)

  const fetchFarms = useCallback(async () => {
    const version = ++requestVersion.current
    if (!user) {
      setFarms([])
      setActiveFarm(null)
      setLoading(false)
      return
    }
    setLoading(true)
    try {
      const res = await api.get('/farms/')
      if (version !== requestVersion.current) return
      setFarms(res.data)
      setActiveFarm((current) => res.data.find((farm) => farm.id === current?.id) || res.data[0] || null)
    } catch (err) {
      if (version === requestVersion.current) console.error('Failed to fetch farms', err)
    } finally {
      if (version === requestVersion.current) setLoading(false)
    }
  }, [user])

  useEffect(() => {
    setFarms([])
    setActiveFarm(null)
    fetchFarms()
    return () => { requestVersion.current += 1 }
  }, [fetchFarms])

  return (
    <FarmContext.Provider value={{ farms, activeFarm, setActiveFarm, loading, fetchFarms }}>
      {children}
    </FarmContext.Provider>
  )
}

export const useFarm = () => useContext(FarmContext) || defaultFarmState
