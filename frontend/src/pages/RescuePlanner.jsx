import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'
import EmptyState from '../components/EmptyState'
import { useFarm } from '../context/FarmContext'
import toast from 'react-hot-toast'
import { 
  Sparkles, AlertTriangle, Leaf, FlaskConical, Droplets, Clock, 
  ShieldCheck, CloudSun, CheckCircle2, Database, 
  Layers, ShieldAlert, ThermometerSun
} from 'lucide-react'

export default function RescuePlanner() {
  const { scanId } = useParams()
  const navigate = useNavigate()
  const { farms } = useFarm()
  const [priorities, setPriorities] = useState([])
  const [selected, setSelected] = useState(scanId ? Number(scanId) : null)
  const [plan, setPlan] = useState(null)
  const [facts, setFacts] = useState(null)
  const [source, setSource] = useState('')
  const [unavailableReason, setUnavailableReason] = useState('')
  const [retryCount, setRetryCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [listLoading, setListLoading] = useState(true)
  const [deploying, setDeploying] = useState(false)
  const [activeTab, setActiveTab] = useState('all') // 'all', 'organic', 'chemical'
  const [actionType, setActionType] = useState('organic')
  const [treatmentAction, setTreatmentAction] = useState('')

  useEffect(() => {
    let cancelled = false
    client.get('/scans?limit=100').then((res) => {
      if (cancelled) return
      const fieldsById = new Map(
        farms.flatMap((farm) => (farm.fields || []).map((field) => [field.id, { ...field, farm_name: farm.name }]))
      )
      const scans = res.data
        .filter((scan) => scan.status !== 'resolved')
        .map((scan) => {
          const field = fieldsById.get(scan.field_id)
          return {
            ...scan,
            scan_id: scan.id,
            disease_name: scan.disease_name || 'Unclassified crop image',
            field_name: field?.name || `Field ${scan.field_id}`,
            farm_name: field?.farm_name || 'Farm',
            crop: field?.crop_type || field?.crop || 'Crop not specified',
            growth_stage: field?.growth_stage,
          }
        })
      setPriorities(scans)
      setSelected((current) => {
        if (scanId && scans.some((scan) => scan.id === Number(scanId))) return Number(scanId)
        if (current && scans.some((scan) => scan.id === current)) return current
        return scans[0]?.id || null
      })
    }).catch(() => {
      if (!cancelled) toast.error('Could not load saved crop scans')
    }).finally(() => {
      if (!cancelled) setListLoading(false)
    })
    return () => { cancelled = true }
  }, [farms, scanId])

  useEffect(() => {
    if (!selected) return
    let cancelled = false
    setLoading(true)
    setPlan(null)
    setFacts(null)
    setUnavailableReason('')
    client.get(`/rescue/${selected}`, { timeout: 90_000 }).then((res) => {
      if (cancelled) return
      setPlan(res.data.plan)
      setFacts(res.data.facts)
      setSource(res.data.source || 'General AI guidance')
      if (!res.data.plan) {
        setUnavailableReason(res.data.reason || 'The AI provider did not return a diagnosis.')
      }
    }).catch((err) => {
      console.error(err)
      if (cancelled) return
      const message = err.response?.data?.detail
        || (err.code === 'ECONNABORTED'
          ? 'Diagnosis timed out. Check the backend and AI provider, then retry.'
          : typeof err.response?.data === 'string' && err.response.data.trim()
            ? err.response.data
            : err.response?.status
              ? `Diagnosis request failed (HTTP ${err.response.status}). Please retry or check the backend logs.`
              : err.message || 'Could not load crop diagnosis.')
      setUnavailableReason(message)
    }).finally(() => {
      if (!cancelled) setLoading(false)
    })
    return () => { cancelled = true }
  }, [selected, retryCount])

  const handleDeployTreatment = async (event) => {
    event.preventDefault()
    if (!selected || !plan || treatmentAction.trim().length < 10) return
    setDeploying(true)
    try {
      await client.post(`/rescue/${selected}/deploy`, {
        action_type: actionType,
        custom_notes: treatmentAction.trim()
      })
      toast.success('Your treatment plan was added to the Treatment Tracker.')
      setTimeout(() => {
        navigate('/treatments')
      }, 1200)
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to add treatment')
    } finally {
      setDeploying(false)
    }
  }

  if (listLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-farm-600 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-sm text-earth-800/60 font-medium">Loading active farm threats...</p>
        </div>
      </div>
    )
  }

  if (priorities.length === 0) {
    return (
      <EmptyState
        icon={Sparkles}
        title="No saved crop scans yet"
        message="Scan a crop first. Its saved image assessment will be available here for AI-assisted diagnosis and rescue guidance."
        action={<a href="/scanner" className="btn-primary">Go to Crop Scanner</a>}
      />
    )
  }

  const current = priorities.find((p) => p.id === selected)

  return (
    <div className="space-y-6 animate-fade-up">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-extrabold text-[#1e4f2b] flex items-center gap-2">
              <Sparkles className="w-7 h-7 text-emerald-600" /> Diagnosis and Rescue Guidance
            </h1>
            <span className="text-[11px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-800 border border-emerald-200 flex items-center gap-1">
              <Database size={11} /> AI-assisted
            </span>
          </div>
          <p className="text-xs sm:text-sm text-[#4a3826]/70 mt-1">
            The saved crop photo is checked against the model prediction. Treat the result as AI-assisted guidance, not a confirmed diagnosis.
          </p>
        </div>
      </div>

      {/* Threat Selector Bar */}
      <div className="flex gap-2 overflow-x-auto pb-2 scrollbar-none">
        {priorities.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            className={`shrink-0 px-4 py-2.5 rounded-xl text-xs sm:text-sm font-semibold border transition-all flex items-center gap-2 ${
              selected === p.id 
                ? 'bg-[#226431] text-white border-[#226431] shadow-md shadow-emerald-900/10 scale-[1.02]' 
                : 'bg-white border-gray-200 text-gray-700 hover:border-gray-300 hover:bg-gray-50'
            }`}
          >
            <span>{p.disease_name}</span>
            <span className={`text-[10px] px-1.5 py-0.5 rounded font-bold capitalize ${
              selected === p.id ? 'bg-white/15 text-white' : 'bg-gray-100 text-gray-600'
            }`}>
              {p.severity || 'unassessed'}
            </span>
          </button>
        ))}
      </div>

      {/* Selected Threat Diagnostic Context Card */}
      {current && (
        <div className="bg-white rounded-2xl p-5 border border-gray-100 shadow-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="w-12 h-12 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center shrink-0 font-bold text-lg">
                <Layers className="w-6 h-6 text-emerald-700" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-lg font-bold text-[#1e4f2b]">
                    <span className="mr-1 text-xs font-semibold uppercase tracking-wide text-gray-500">Model prediction:</span>
                    {current.disease_name.replace(/_/g, ' ')}
                  </h3>
                  <span className="rounded-full bg-gray-100 px-2 py-1 text-xs font-semibold capitalize text-gray-600">
                    {current.severity || 'unassessed'}
                  </span>
                </div>
                <p className="text-xs text-gray-500 mt-0.5">
                  Field: <strong className="text-gray-700">{current.field_name}</strong> · Crop:                   <strong className="text-gray-700">{current.crop}</strong> ({current.growth_stage || 'stage not recorded'}) · Farm: <strong className="text-gray-700">{current.farm_name}</strong>
                </p>
                <div className="flex flex-wrap items-center gap-3 mt-2 text-[11px] text-gray-600">
                  <span className="bg-gray-100 px-2 py-0.5 rounded font-medium">{current.confidence == null ? 'Confidence not recorded' : <>AI confidence estimate: <strong>{current.confidence}%</strong></>}</span>
                  <span className="bg-gray-100 px-2 py-0.5 rounded font-medium">{current.affected_area_pct == null ? 'Affected area not recorded' : <>Affected area: <strong>{current.affected_area_pct}%</strong></>}</span>
                  <span className="bg-gray-100 px-2 py-0.5 rounded font-medium text-emerald-700 font-semibold">{current.suggested_timeframe}</span>
                </div>
              </div>
            </div>

            {facts?.weather && (
              <div className="bg-sky-50 border border-sky-100 rounded-xl p-3 text-xs text-sky-900 flex items-center gap-3">
                <ThermometerSun className="w-6 h-6 text-sky-600 shrink-0" />
                <div>
                  <p className="font-bold text-[11px] text-sky-950 uppercase tracking-wide">Live Microclimate</p>
                  <p className="text-xs mt-0.5">
                    {facts.weather.temperature}°C · {facts.weather.humidity}% RH · {facts.weather.rain_probability}% Rain Risk
                  </p>
                </div>
              </div>
            )}
          </div>

          {plan?.evidence_summary && (
            <div className="mt-3 pt-3 border-t border-gray-100 text-xs text-gray-600 flex items-center gap-1.5">
              <CheckCircle2 size={13} className="text-emerald-600 shrink-0" />
              <span><strong>AI guidance notice:</strong> {plan.evidence_summary}</span>
            </div>
          )}
        </div>
      )}

      {loading && (
        <div className="bg-white rounded-2xl p-10 border border-gray-100 text-center space-y-3">
          <div className="w-10 h-10 border-3 border-emerald-600 border-t-transparent rounded-full animate-spin mx-auto" />
          <p className="text-sm font-semibold text-gray-700">Requesting general crop guidance…</p>
          <p className="text-xs text-gray-400">No product-specific dosage or treatment is generated.</p>
        </div>
      )}
      {!loading && !plan && unavailableReason && (
        <div role="status" className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <span>{unavailableReason}</span>
          <button
            type="button"
            className="rounded-lg border border-amber-300 bg-white px-3 py-1.5 font-semibold text-amber-900 hover:bg-amber-100"
            onClick={() => setRetryCount((count) => count + 1)}
          >
            Retry diagnosis
          </button>
        </div>
      )}

      {/* The 7 Plan Cards */}
      {!loading && plan && (
        <div className="space-y-4">
          <section className="grid gap-4 sm:grid-cols-2">
            <article className="rounded-2xl border border-emerald-100 bg-white p-5 shadow-sm sm:col-span-2">
              <h3 className="text-base font-bold text-gray-900">Image-based crop diagnosis</h3>
              <p className="mt-2 text-sm leading-6 text-gray-700">{plan.description || plan.immediate_action}</p>
              {plan.image_assessed === false && (
                <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                  The saved image was not included in this assessment. Scan the crop again for an image-based diagnosis.
                </p>
              )}
              {plan.symptoms?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-bold uppercase tracking-wide text-gray-500">Observed / likely symptoms</h4>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-gray-700">
                    {plan.symptoms.map((symptom, index) => <li key={`${index}-${symptom}`}>{symptom}</li>)}
                  </ul>
                </div>
              )}
              {plan.causes?.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-xs font-bold uppercase tracking-wide text-gray-500">Possible causes</h4>
                  <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-gray-700">
                    {plan.causes.map((cause, index) => <li key={`${index}-${cause}`}>{cause}</li>)}
                  </ul>
                </div>
              )}
            </article>
          </section>

          <div className="flex items-center justify-between text-xs text-gray-500 px-1">
            <span>Unverified general guidance from <strong className="text-emerald-700">{source}</strong></span>
            <div className="flex gap-2">
              <button 
                onClick={() => setActiveTab('all')} 
                className={`px-2.5 py-1 rounded-lg font-semibold transition ${activeTab === 'all' ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-600'}`}
              >
                All Protocols
              </button>
              <button 
                onClick={() => setActiveTab('organic')} 
                className={`px-2.5 py-1 rounded-lg font-semibold transition ${activeTab === 'organic' ? 'bg-emerald-700 text-white' : 'bg-emerald-50 text-emerald-800'}`}
              >
                Organic Focus
              </button>
              <button 
                onClick={() => setActiveTab('chemical')} 
                className={`px-2.5 py-1 rounded-lg font-semibold transition ${activeTab === 'chemical' ? 'bg-purple-700 text-white' : 'bg-purple-50 text-purple-800'}`}
              >
                Chemical Focus
              </button>
            </div>
          </div>

          <div className="grid sm:grid-cols-2 gap-4">
            {/* Immediate Action */}
            <div className="bg-white rounded-2xl p-5 border-l-4 border-l-red-500 border border-gray-100 shadow-sm sm:col-span-2">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-red-50 text-red-600 flex items-center justify-center font-bold">
                    <AlertTriangle className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="font-extrabold text-sm text-gray-900">Immediate action guidance</h4>
                    <p className="text-[11px] text-gray-400">General first steps; review before acting</p>
                  </div>
                </div>
                <span className="text-[11px] font-bold px-2 py-0.5 rounded bg-red-100 text-red-800 uppercase">Review first</span>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed pl-10 whitespace-pre-line">{plan.immediate_action}</p>
            </div>

            {/* Organic Treatment */}
            {(activeTab === 'all' || activeTab === 'organic') && (
              <div className="bg-white rounded-2xl p-5 border-l-4 border-l-emerald-600 border border-gray-100 shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-emerald-50 text-emerald-600 flex items-center justify-center">
                        <Leaf className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="font-bold text-sm text-gray-900">Organic treatment note</h4>
                        <p className="text-[11px] text-gray-400">General guidance only; no product or dose is recommended.</p>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">Not verified</span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{plan.organic_treatment}</p>
                </div>
              </div>
            )}

            {/* Chemical Treatment */}
            {(activeTab === 'all' || activeTab === 'chemical') && (
              <div className="bg-white rounded-2xl p-5 border-l-4 border-l-purple-600 border border-gray-100 shadow-sm flex flex-col justify-between">
                <div>
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <div className="w-8 h-8 rounded-lg bg-purple-50 text-purple-600 flex items-center justify-center">
                        <FlaskConical className="w-4 h-4" />
                      </div>
                      <div>
                        <h4 className="font-bold text-sm text-gray-900">Chemical safety note</h4>
                        <p className="text-[11px] text-gray-400">Consult a licensed local expert before using crop-protection products.</p>
                      </div>
                    </div>
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">Expert review</span>
                  </div>
                  <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{plan.chemical_treatment}</p>
                </div>
              </div>
            )}

            {/* Application Guidance */}
            <div className="bg-white rounded-2xl p-5 border-l-4 border-l-blue-600 border border-gray-100 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-blue-50 text-blue-600 flex items-center justify-center">
                  <Droplets className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-900">Application Technique & Timing</h4>
                  <p className="text-[11px] text-gray-400">General monitoring guidance; no application dose</p>
                </div>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">{plan.application_guidance}</p>
            </div>

            {/* Recovery Time */}
            <div className="bg-white rounded-2xl p-5 border-l-4 border-l-amber-500 border border-gray-100 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-amber-50 text-amber-600 flex items-center justify-center">
                  <Clock className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-900">Recovery estimate</h4>
                  <p className="text-[11px] text-gray-400">Not estimated from the available evidence</p>
                </div>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line font-medium text-amber-900">{plan.recovery_time}</p>
            </div>

            {/* Safety & PPE Advisory */}
            <div className="bg-amber-50/70 border border-amber-200 rounded-2xl p-5 shadow-sm">
              <div className="flex items-center gap-2 mb-2">
                <ShieldAlert className="w-5 h-5 text-amber-700 shrink-0" />
                <h4 className="font-bold text-sm text-amber-900">Safety guidance</h4>
              </div>
              <p className="text-xs text-amber-800 leading-relaxed whitespace-pre-line">{plan.safety_warning || 'No specific safety guidance available. Follow the label and local expert advice for any treatment.'}</p>
            </div>

            {/* Prevention & IPM */}
            <div className="bg-white rounded-2xl p-5 border-l-4 border-l-teal-600 border border-gray-100 shadow-sm">
              <div className="flex items-center gap-2 mb-3">
                <div className="w-8 h-8 rounded-lg bg-teal-50 text-teal-600 flex items-center justify-center">
                  <ShieldCheck className="w-4 h-4" />
                </div>
                <div>
                  <h4 className="font-bold text-sm text-gray-900">Prevention and monitoring</h4>
                  <p className="text-[11px] text-gray-400">General suggestions; confirm locally</p>
                </div>
              </div>
              <p className="text-sm text-gray-700 leading-relaxed whitespace-pre-line">
                {Array.isArray(plan.prevention) ? plan.prevention.join('\n') : plan.prevention}
              </p>
            </div>

            {/* Weather Consideration */}
            <div className="bg-sky-50 border border-sky-200 rounded-2xl p-5 shadow-sm sm:col-span-2">
              <div className="flex items-center gap-2 mb-2">
                <CloudSun className="w-5 h-5 text-sky-700 shrink-0" />
                <h4 className="font-bold text-sm text-sky-950">Weather considerations</h4>
              </div>
              <p className="text-xs text-sky-900 leading-relaxed whitespace-pre-line font-medium">
                {plan.weather_consideration}
              </p>
            </div>
          </div>
          <form onSubmit={handleDeployTreatment} className="metric-card space-y-3">
            <h3 className="text-sm font-bold text-gray-900">Record a treatment you have chosen</h3>
            <p className="text-xs text-gray-600">This adds your own plan to the Treatment Tracker. AI guidance is not a treatment prescription.</p>
            <div className="grid gap-3 sm:grid-cols-[180px_1fr]">
              <label className="text-xs font-semibold text-gray-700">Treatment category
                <select className="farm-input mt-1" value={actionType} onChange={(event) => setActionType(event.target.value)}>
                  <option value="organic">Organic</option>
                  <option value="chemical">Chemical</option>
                </select>
              </label>
              <label className="text-xs font-semibold text-gray-700">Your planned treatment *
                <textarea className="farm-input mt-1 min-h-20" minLength={10} maxLength={2000} required value={treatmentAction} onChange={(event) => setTreatmentAction(event.target.value)} placeholder="Describe the treatment you independently selected…" />
              </label>
            </div>
            <button type="submit" disabled={deploying || treatmentAction.trim().length < 10} className="btn-primary disabled:opacity-50">
              {deploying ? 'Adding…' : 'Add my treatment to Tracker'}
            </button>
          </form>
        </div>
      )}
    </div>
  )
}
