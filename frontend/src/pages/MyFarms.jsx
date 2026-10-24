import { useState, useEffect } from 'react'
import api from '../api/client'
import { useFarm } from '../context/FarmContext'
import FarmMap from '../components/FarmMap'
import toast from 'react-hot-toast'
import {
  Sprout, Plus, Trash2, MapPin, Calendar, Leaf, ChevronDown,
  ChevronUp, Crosshair, Globe, Check, Layers
} from 'lucide-react'

const STAGE_OPTIONS = ['seedling', 'vegetative', 'flowering', 'maturity']

export default function MyFarms() {
  const { farms, fetchFarms, setActiveFarm, activeFarm } = useFarm()
  const [showAddFarm, setShowAddFarm] = useState(false)
  const [expandedFarm, setExpandedFarm] = useState(null)
  const [showAddField, setShowAddField] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [locating, setLocating] = useState(false)

  // Farm Form
  const [farmForm, setFarmForm] = useState({
    name: '',
    latitude: null,
    longitude: null,
    area_acres: null,
  })

  // Field Form
  const [fieldForm, setFieldForm] = useState({
    name: '',
    crop: '',
    growth_stage: '',
    size_acres: null,
  })

  // Auto-detect browser GPS coordinates
  const handleDetectLocation = () => {
    if (!navigator.geolocation) {
      toast.error('Geolocation is not supported by your browser')
      return
    }
    setLocating(true)
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setFarmForm(prev => ({
          ...prev,
          latitude: parseFloat(pos.coords.latitude.toFixed(4)),
          longitude: parseFloat(pos.coords.longitude.toFixed(4)),
        }))
        toast.success(`📍 Coordinates captured: ${pos.coords.latitude.toFixed(4)}, ${pos.coords.longitude.toFixed(4)}`)
        setLocating(false)
      },
      () => {
        toast.error('Unable to retrieve location. Check browser location permissions.')
        setLocating(false)
      },
      { timeout: 10000, enableHighAccuracy: true }
    )
  }

  const handleAddFarm = async (e) => {
    e.preventDefault()
    const cleanName = farmForm.name.trim()
    if (!cleanName) {
      toast.error('Please enter a farm name')
      return
    }

    setSubmitting(true)
    try {
      const payload = {
        name: cleanName,
        latitude: farmForm.latitude,
        longitude: farmForm.longitude,
        area_acres: farmForm.area_acres || null,
      }
      await api.post('/farms/', payload)
      toast.success(`Farm "${cleanName}" registered`)
      setShowAddFarm(false)
      setFarmForm({ name: '', latitude: null, longitude: null, area_acres: null })
      fetchFarms()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to create farm')
    } finally { 
      setSubmitting(false) 
    }
  }

  const handleAddField = async (e, farmId) => {
    e.preventDefault()
    const cleanFieldName = fieldForm.name.trim()
    if (!cleanFieldName) {
      toast.error('Please enter a field name')
      return
    }

    const currentFarm = farms.find(f => f.id === farmId)
    if (currentFarm?.fields?.some(f => f.name.toLowerCase() === cleanFieldName.toLowerCase())) {
      toast.error(`Field "${cleanFieldName}" already exists in this farm. Choose a unique field name.`)
      return
    }

    setSubmitting(true)
    try {
      await api.post('/fields/', {
        name: cleanFieldName,
        farm_id: farmId,
        crop: fieldForm.crop,
        growth_stage: fieldForm.growth_stage,
        size_acres: fieldForm.size_acres || null,
      })
      toast.success(`Field "${cleanFieldName}" added to farm!`)
      setShowAddField(null)
      setFieldForm({ 
        name: '',
        crop: '',
        growth_stage: '',
        size_acres: null,
      })
      fetchFarms()
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add field')
    } finally { 
      setSubmitting(false) 
    }
  }

  const handleDeleteFarm = async (id, name) => {
    if (!confirm(`Are you sure you want to delete farm "${name}"? All associated fields, scans, and priority issues will be removed.`)) return
    try {
      await api.delete(`/farms/${id}`)
      toast.success(`Farm "${name}" deleted`)
      fetchFarms()
    } catch { 
      toast.error('Failed to delete farm') 
    }
  }

  return (
    <div className="p-5 animate-fade-up space-y-5">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="section-title">🌿 Farms & Fields</h1>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-300">
              Your farm records
            </span>
          </div>
          <p className="section-subtitle">Manage farms, coordinates, and crop fields</p>
        </div>
        <button onClick={() => setShowAddFarm(!showAddFarm)} className="btn-primary self-start">
          <Plus size={16} /> Add Farm
        </button>
      </div>

      {/* Streamlined Add Farm Modal / Form */}
      {showAddFarm && (
        <div className="metric-card bg-white border-2 border-emerald-300 shadow-xl animate-fade-up">
          <div className="flex items-center justify-between pb-3 border-b border-gray-100 mb-4">
            <div>
              <div className="text-sm font-bold text-gray-900 flex items-center gap-2">
                <Sprout size={16} className="text-emerald-600" /> Create Unique Farm Territory
              </div>
              <div className="text-xs text-gray-400">Enter your farm's real details. Coordinates are optional.</div>
            </div>
            <button onClick={() => setShowAddFarm(false)} className="text-gray-400 hover:text-gray-600 font-bold">✕</button>
          </div>

          <form onSubmit={handleAddFarm} className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-bold text-gray-700 mb-1 block">Farm Name *</label>
                <input 
                  required 
                  value={farmForm.name} 
                  onChange={e => setFarmForm({...farmForm, name: e.target.value})}
                  placeholder="e.g. Green Valley Farm or Krishna River Plot" 
                  className="farm-input" 
                />
              </div>

              <div>
                <label className="text-xs font-bold text-gray-700 mb-1 block">Total Farm Area (Acres)</label>
                <input 
                  type="number" min="0.1" step="0.5" 
                  value={farmForm.area_acres ?? ''}
                  onChange={e => setFarmForm({...farmForm, area_acres: e.target.value ? parseFloat(e.target.value) : null})} 
                  className="farm-input" 
                />
              </div>

              {/* GPS Coordinates with 1-Click Detect */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="text-xs font-bold text-gray-700">GPS Coordinates</label>
                  <button
                    type="button"
                    onClick={handleDetectLocation}
                    disabled={locating}
                    className="text-[11px] font-bold text-emerald-700 hover:text-emerald-900 flex items-center gap-1 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200"
                  >
                    <Crosshair size={11} className={locating ? 'animate-spin' : ''} />
                    {locating ? 'Locating...' : 'Auto-Detect My GPS'}
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <input 
                    type="number" step="0.0001" placeholder="Latitude"
                    value={farmForm.latitude ?? ''}
                    onChange={e => setFarmForm({...farmForm, latitude: e.target.value ? parseFloat(e.target.value) : null})} 
                    className="farm-input text-xs py-1.5" 
                  />
                  <input 
                    type="number" step="0.0001" placeholder="Longitude"
                    value={farmForm.longitude ?? ''}
                    onChange={e => setFarmForm({...farmForm, longitude: e.target.value ? parseFloat(e.target.value) : null})} 
                    className="farm-input text-xs py-1.5" 
                  />
                </div>
              </div>
            </div>

            {/* Quick Regional Presets */}
            <div>
              <p className="text-[11px] text-gray-500">Use GPS or enter coordinates. No default location is added.</p>
            </div>

            <div className="flex gap-3 pt-2">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? <span className="spinner" /> : <Plus size={15} />} Save Farm
              </button>
              <button type="button" onClick={() => setShowAddFarm(false)} className="btn-secondary">
                Cancel
              </button>
            </div>
          </form>
        </div>
      )}

      <section className="metric-card space-y-3">
        <div>
          <h2 className="text-sm font-bold text-gray-900">Farm locations</h2>
          <p className="text-xs text-gray-500">Enter coordinates or use GPS to open the map, then click to adjust the location. Saved farm and field markers use recorded coordinates.</p>
        </div>
        <FarmMap
          farms={farms}
          selectedLocation={farmForm.latitude != null && farmForm.longitude != null
            ? { latitude: farmForm.latitude, longitude: farmForm.longitude }
            : null}
          onSelect={({ latitude, longitude }) => setFarmForm((current) => ({
            ...current,
            latitude: Number(latitude.toFixed(6)),
            longitude: Number(longitude.toFixed(6)),
          }))}
        />
      </section>

      {/* Farm overview */}
      {farms.length > 0 && (
        <div className="metric-card p-5">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-wider text-emerald-700 flex items-center gap-1.5">
                <Globe size={14} /> Farm overview
              </div>
              <div className="text-base font-black text-gray-900 mt-0.5">
                {farms.length} {farms.length === 1 ? 'farm' : 'farms'} registered
              </div>
            </div>
            <div className="text-xs text-gray-600">
              Recorded area: <strong className="text-gray-900">{farms.every(farm => farm.area_acres != null)
                ? `${farms.reduce((total, farm) => total + Number(farm.area_acres), 0)} acres`
                : 'incomplete'}</strong> ·
              Fields: <strong className="text-gray-900">{farms.reduce((acc, f) => acc + (f.fields?.length || 0), 0)}</strong>
            </div>
          </div>

          {/* Farm selector */}
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {farms.map((farm) => {
              const isActive = activeFarm?.id === farm.id

              return (
                <div
                  key={farm.id}
                  onClick={() => setActiveFarm(farm)}
                  className={`p-3.5 rounded-2xl cursor-pointer transition-all border ${
                    isActive 
                      ? 'bg-emerald-50 border-emerald-400 shadow-sm ring-1 ring-emerald-200' 
                      : 'bg-white border-gray-200 hover:bg-gray-50 hover:border-emerald-300'
                  }`}
                >
                  <div className="flex items-start justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-xl bg-emerald-700 flex items-center justify-center text-white shadow-sm">
                        <Sprout size={16} />
                      </div>
                      <div>
                        <div className="text-xs font-bold text-gray-900 truncate max-w-[130px]">{farm.name}</div>
                        <div className="text-[10px] text-gray-500 font-mono">Farm {farm.id}</div>
                      </div>
                    </div>

                    {isActive ? (
                      <span className="text-[9px] px-2 py-0.5 rounded-full font-bold bg-emerald-400 text-emerald-950 flex items-center gap-1">
                        <Check size={10} /> ACTIVE
                      </span>
                    ) : (
                      <button 
                        onClick={(e) => { e.stopPropagation(); setActiveFarm(farm) }}
                        className="text-[9px] px-2 py-0.5 rounded-full font-bold bg-emerald-50 text-emerald-800 border border-emerald-200 hover:bg-emerald-100 transition-colors"
                      >
                        Set Active
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-[10px] text-gray-600 pt-2 border-t border-gray-200">
                    <div>📐 {farm.area_acres ?? '—'} Acres</div>
                    <div>🌱 {farm.fields?.length || 0} Fields</div>
                    <div className="truncate">📍 {farm.latitude != null && farm.longitude != null ? `${farm.latitude.toFixed(4)}, ${farm.longitude.toFixed(4)}` : 'Coordinates not set'}</div>
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Main Farm Cards List */}
      {farms.length === 0 ? (
        <div className="empty-state metric-card p-12 text-center bg-white rounded-2xl border border-emerald-100">
          <div className="w-16 h-16 rounded-2xl bg-emerald-50 mx-auto mb-3 flex items-center justify-center">
            <Sprout size={36} className="text-emerald-500" />
          </div>
          <h2 className="text-lg font-bold text-gray-800 mb-1">No farms added yet</h2>
          <p className="text-gray-400 text-xs max-w-sm mx-auto mb-5">
            Add a farm and field before recording crop scans or weather observations.
          </p>
          <button onClick={() => setShowAddFarm(true)} className="btn-primary text-xs">
            <Plus size={15} /> Add Your First Farm
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="text-xs font-bold text-gray-500 uppercase tracking-wider">
            Detailed Farm Management ({farms.length})
          </div>

          {farms.map((farm) => {
            const isExpanded = expandedFarm === farm.id
            const isActive = activeFarm?.id === farm.id

            return (
              <div 
                key={farm.id} 
                className={`metric-card transition-all border-2 ${
                  isActive 
                    ? 'border-emerald-400 ring-2 ring-emerald-400 shadow-md' 
                    : 'border-gray-100 hover:border-emerald-200'
                }`}
              >
                {/* Farm Header */}
                <div
                  className="flex items-start gap-3 cursor-pointer"
                  onClick={() => setExpandedFarm(isExpanded ? null : farm.id)}
                >
                  <div className="w-11 h-11 rounded-2xl bg-emerald-700 flex items-center justify-center flex-shrink-0 text-white shadow-sm">
                    <Sprout size={20} />
                  </div>

                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <div className="text-sm font-bold text-gray-900">{farm.name}</div>
                      
                      {isActive && (
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-emerald-600 text-white font-bold flex items-center gap-1 shadow-sm">
                          <Check size={10} /> ACTIVE
                        </span>
                      )}
                    </div>

                    <div className="flex items-center gap-4 mt-1.5 flex-wrap text-xs text-gray-500">
                      <span className="flex items-center gap-1">
                        <MapPin size={12} className="text-emerald-600" />
                        {farm.latitude != null && farm.longitude != null
                          ? <a href={`https://www.openstreetmap.org/?mlat=${farm.latitude}&mlon=${farm.longitude}#map=14/${farm.latitude}/${farm.longitude}`} target="_blank" rel="noreferrer" onClick={event => event.stopPropagation()}>Open farm coordinates in OpenStreetMap</a>
                          : 'Coordinates not set'}
                      </span>
                      <span>📐 {farm.area_acres ?? '—'} acres</span>
                      <span>🌱 {farm.fields?.length || 0} fields</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {!isActive && (
                      <button
                        onClick={e => { e.stopPropagation(); setActiveFarm(farm) }}
                        className="text-xs px-2.5 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-lg hover:bg-emerald-100 font-bold transition-colors"
                      >
                        Set Active
                      </button>
                    )}
                    <button
                      onClick={e => { e.stopPropagation(); handleDeleteFarm(farm.id, farm.name) }}
                      className="p-1.5 text-gray-300 hover:text-red-500 transition-colors"
                      title="Delete Farm"
                    >
                      <Trash2 size={15} />
                    </button>
                    {isExpanded ? <ChevronUp size={18} className="text-gray-400" /> : <ChevronDown size={18} className="text-gray-400" />}
                  </div>
                </div>

                {/* Expanded Fields Panel */}
                {isExpanded && (
                  <div className="mt-4 pt-4 border-t border-gray-100 animate-fade-up space-y-3">
                    <div className="flex items-center justify-between">
                      <div className="text-xs font-bold text-gray-700 flex items-center gap-1.5">
                        <Layers size={14} className="text-emerald-600" />
                        Crop Fields in {farm.name} ({farm.fields?.length || 0})
                      </div>
                      <button
                        onClick={() => setShowAddField(showAddField === farm.id ? null : farm.id)}
                        className="btn-primary text-xs py-1 px-3"
                      >
                        <Plus size={12} /> Add Field Plot
                      </button>
                    </div>

                    {/* Add Field Form */}
                    {showAddField === farm.id && (
                      <form onSubmit={e => handleAddField(e, farm.id)} className="bg-emerald-50/70 border border-emerald-200 rounded-xl p-4 space-y-3 animate-fade-up">
                        <div className="text-xs font-bold text-emerald-900 mb-1">Add Field Plot to {farm.name}</div>
                        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                          <div>
                            <label className="text-[10px] font-bold text-gray-700 mb-0.5 block">Field Plot Name *</label>
                            <input 
                              required 
                              value={fieldForm.name} 
                              onChange={e => setFieldForm({...fieldForm, name: e.target.value})}
                              placeholder="e.g. Field Alpha" 
                              className="farm-input text-xs py-1.5" 
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-gray-700 mb-0.5 block">Crop type *</label>
                            <input
                              required
                              value={fieldForm.crop} 
                              onChange={e => setFieldForm({...fieldForm, crop: e.target.value})}
                              placeholder="Enter crop type"
                              className="farm-input text-xs py-1.5"
                            />
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-gray-700 mb-0.5 block">Growth stage *</label>
                            <select 
                              required
                              value={fieldForm.growth_stage} 
                              onChange={e => setFieldForm({...fieldForm, growth_stage: e.target.value})} 
                              className="farm-input text-xs py-1.5"
                            >
                              <option value="" disabled>Select stage</option>
                              {STAGE_OPTIONS.map(stage => (
                                <option key={stage} value={stage}>
                                  {stage.charAt(0).toUpperCase() + stage.slice(1)}
                                </option>
                              ))}
                            </select>
                          </div>
                          <div>
                            <label className="text-[10px] font-bold text-gray-700 mb-0.5 block">Plot Area (Acres)</label>
                            <input 
                              type="number" min="0.05" step="0.1" 
                              value={fieldForm.size_acres ?? ''}
                              onChange={e => setFieldForm({...fieldForm, size_acres: e.target.value ? parseFloat(e.target.value) : null})} 
                              className="farm-input text-xs py-1.5" 
                            />
                          </div>
                        </div>

                        <div className="flex gap-2 pt-1">
                          <button type="submit" disabled={submitting} className="btn-primary text-xs py-1.5 px-3">
                            {submitting ? <span className="spinner w-3 h-3" /> : null} Add Field
                          </button>
                          <button type="button" onClick={() => setShowAddField(null)} className="btn-secondary text-xs py-1.5 px-3">
                            Cancel
                          </button>
                        </div>
                      </form>
                    )}

                    {/* Field Cards */}
                    {farm.fields?.length === 0 ? (
                      <div className="text-xs text-gray-400 text-center py-4 bg-gray-50 rounded-xl">
                        No field plots configured yet. Click "Add Field Plot" above to register your crop zones.
                      </div>
                    ) : (
                      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5">
                        {farm.fields.map(field => (
                          <div key={field.id} className="p-3 bg-white rounded-xl border border-emerald-100 hover:border-emerald-300 transition-colors shadow-2xs">
                            <div className="flex items-center justify-between mb-1">
                              <div className="flex items-center gap-1.5">
                                <Leaf size={14} className="text-emerald-600" />
                                <span className="text-xs font-bold text-gray-800">{field.name}</span>
                              </div>
                              <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-50 text-emerald-700 font-bold">
                                {field.area ?? '—'} ac
                              </span>
                            </div>
                            <div className="text-xs font-bold text-emerald-800">{field.crop_type}</div>
                            <div className="text-[10px] text-gray-400 mt-0.5 flex items-center justify-between">
                              <span>Stage: {field.growth_stage}</span>
                              {field.planting_date && (
                                <span className="flex items-center gap-0.5"><Calendar size={9} /> {field.planting_date}</span>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
