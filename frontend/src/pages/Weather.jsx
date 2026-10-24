import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import { CloudRain, CloudSun, Droplets, MapPin, RefreshCw, Thermometer, Wind } from 'lucide-react'

const display = (value, unit = '') => value == null || !Number.isFinite(Number(value))
  ? 'Unavailable'
  : `${Math.round(Number(value) * 10) / 10}${unit}`

const formatForecastTime = (value) => {
  if (!value) return 'Time unavailable'
  const date = new Date(value.replace(' ', 'T') + (value.includes('Z') ? '' : 'Z'))
  return Number.isNaN(date.getTime())
    ? value
    : date.toLocaleString(undefined, { weekday: 'short', hour: 'numeric' })
}

export default function Weather() {
  const [farms, setFarms] = useState([])
  const [farmId, setFarmId] = useState('')
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')

  const loadWeather = useCallback(async (id, quiet = false) => {
    if (!id) return
    if (quiet) setRefreshing(true)
    else setLoading(true)
    try {
      const response = await api.get('/weather', { params: { farm_id: id } })
      setData(response.data.data)
      setError(response.data.connected ? '' : response.data.reason || 'Weather data is unavailable.')
    } catch (requestError) {
      setData(null)
      setError(requestError.response?.data?.detail || 'Could not retrieve current weather.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    api.get('/farms')
      .then(({ data: rows }) => {
        if (cancelled) return
        setFarms(rows)
        const selected = rows[0]?.id
        setFarmId(selected ? String(selected) : '')
        if (!selected) {
          setLoading(false)
          setError('Add a farm to view its weather.')
        }
      })
      .catch((requestError) => {
        if (cancelled) return
        setLoading(false)
        setError(requestError.response?.data?.detail || 'Could not load your farms.')
      })
    return () => { cancelled = true }
  }, [])

  useEffect(() => {
    if (!farmId) return undefined
    let cancelled = false
    const refresh = async (quiet) => {
      if (!quiet) setLoading(true)
      else setRefreshing(true)
      try {
        const response = await api.get('/weather', { params: { farm_id: farmId } })
        if (cancelled) return
        setData(response.data.data)
        setError(response.data.connected ? '' : response.data.reason || 'Weather data is unavailable.')
      } catch (requestError) {
        if (!cancelled) {
          setData(null)
          setError(requestError.response?.data?.detail || 'Could not retrieve current weather.')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
          setRefreshing(false)
        }
      }
    }
    refresh(false)
    const timer = window.setInterval(() => refresh(true), 10 * 60 * 1000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [farmId])

  const selectedFarm = farms.find((farm) => String(farm.id) === farmId)

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="eyebrow">Farm conditions</p>
          <h1 className="section-title">Weather</h1>
          <p className="section-subtitle">Current conditions and forecast from OpenWeather for a saved farm location.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label htmlFor="weather-farm" className="sr-only">Choose farm</label>
          <select
            id="weather-farm"
            className="farm-input min-w-48"
            value={farmId}
            onChange={(event) => setFarmId(event.target.value)}
            disabled={!farms.length}
          >
            {farms.length ? farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>) : <option value="">No farms</option>}
          </select>
          <button
            type="button"
            onClick={() => loadWeather(farmId, true)}
            disabled={!farmId || loading || refreshing}
            className="btn-secondary"
          >
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>
      </header>

      {loading && (
        <div className="metric-card flex min-h-48 items-center justify-center" role="status">
          <div className="text-center">
            <span className="spinner mx-auto mb-3 block border-emerald-700 border-t-transparent" />
            <p className="text-sm text-gray-600">Loading weather data…</p>
          </div>
        </div>
      )}

      {!loading && error && (
        <div className="metric-card border-amber-200 bg-amber-50" role="status">
          <div className="flex items-start gap-3">
            <CloudSun className="mt-0.5 text-amber-700" size={20} />
            <div>
              <h2 className="font-semibold text-amber-950">Weather unavailable</h2>
              <p className="mt-1 text-sm text-amber-900">{error}</p>
              {selectedFarm && (selectedFarm.latitude == null || selectedFarm.longitude == null) && (
                <Link className="mt-3 inline-flex text-sm font-semibold text-emerald-800 underline" to="/farms">Add farm coordinates</Link>
              )}
            </div>
          </div>
        </div>
      )}

      {!loading && data && (
        <>
          <section className="metric-card overflow-hidden p-0">
            <div className="grid gap-6 bg-gradient-to-br from-emerald-950 to-emerald-800 p-6 text-white md:grid-cols-[1fr_auto] md:items-center">
              <div>
                <div className="flex items-center gap-2 text-sm text-emerald-100">
                  <MapPin size={15} />
                  {selectedFarm?.name || data.location_name || 'Saved farm'}
                </div>
                <div className="mt-3 flex flex-wrap items-end gap-x-4 gap-y-1">
                  <p className="text-5xl font-bold tracking-tight">{display(data.temperature, '°C')}</p>
                  <p className="pb-1 text-lg text-emerald-100">{data.description || data.condition || 'Condition unavailable'}</p>
                </div>
                <p className="mt-3 text-xs text-emerald-200">
                  Source: {data.source || 'OpenWeather'}
                  {data.updated_at && <> · Updated {new Date(data.updated_at).toLocaleString()}</>}
                </p>
              </div>
              <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  { label: 'Feels like', value: display(data.feels_like, '°C'), icon: Thermometer },
                  { label: 'Humidity', value: display(data.humidity, '%'), icon: Droplets },
                  { label: 'Wind', value: display(data.wind_speed_kmh, ' km/h'), icon: Wind },
                  { label: 'Rain chance', value: display(data.rain_probability, '%'), icon: CloudRain },
                ].map(({ label, value, icon: Icon }) => (
                  <div key={label} className="min-w-24 rounded-xl border border-white/15 bg-white/10 p-3">
                    <Icon size={16} className="mb-2 text-emerald-100" />
                    <p className="text-xs text-emerald-100">{label}</p>
                    <p className="mt-1 text-sm font-semibold">{value}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="grid gap-4 p-5 sm:grid-cols-2">
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Observed rainfall (last hour)</p>
                <p className="mt-2 text-xl font-semibold text-slate-900">{display(data.rainfall_mm, ' mm')}</p>
              </div>
              <div className="rounded-xl bg-slate-50 p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">Farm coordinates</p>
                <p className="mt-2 text-sm font-semibold text-slate-900">
                  {selectedFarm?.latitude == null || selectedFarm?.longitude == null
                    ? 'Not recorded'
                    : `${selectedFarm.latitude}, ${selectedFarm.longitude}`}
                </p>
              </div>
            </div>
          </section>

          {data.forecast?.length > 0 && (
            <section className="metric-card space-y-4">
              <div>
                <h2 className="text-base font-semibold text-slate-900">Forecast</h2>
                <p className="text-sm text-slate-500">Forecast intervals supplied by OpenWeather; unavailable values are not inferred.</p>
              </div>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                {data.forecast.map((item, index) => (
                  <article key={`${item.time || 'forecast'}-${index}`} className="rounded-xl border border-slate-200 bg-white p-4">
                    <p className="text-xs font-semibold text-slate-500">{formatForecastTime(item.time)}</p>
                    <p className="mt-3 flex items-center gap-2 text-xl font-semibold text-slate-900">
                      <Thermometer size={17} className="text-emerald-700" />{display(item.temperature, '°C')}
                    </p>
                    <p className="mt-2 flex items-center gap-2 text-sm text-slate-600">
                      <Droplets size={15} className="text-sky-700" />Humidity {display(item.humidity, '%')}
                    </p>
                    <p className="mt-1 flex items-center gap-2 text-sm text-slate-600">
                      <CloudRain size={15} className="text-sky-700" />Rain {display(item.rain_probability, '%')}
                    </p>
                  </article>
                ))}
              </div>
            </section>
          )}

          {data.advisories?.length > 0 && (
            <section className="metric-card space-y-3">
              <div className="flex items-center gap-2">
                <CloudSun size={18} className="text-emerald-700" />
                <h2 className="text-base font-semibold text-slate-900">Weather advisories</h2>
              </div>
              <ul className="space-y-2">
                {data.advisories.map((advisory) => (
                  <li key={advisory} className="rounded-lg bg-emerald-50 px-4 py-3 text-sm text-emerald-950">{advisory}</li>
                ))}
              </ul>
            </section>
          )}
        </>
      )}
    </div>
  )
}
