import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import client from '../api/client'
import EmptyState from '../components/EmptyState'
import { useFarm } from '../context/FarmContext'
import toast from 'react-hot-toast'
import { 
  Sparkles, Leaf, FlaskConical, CheckCircle2, Database,
  Layers, ThermometerSun
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

      {/* Concise diagnosis and treatment plan */}
      {!loading && plan && (
        <div className="space-y-4">
          <p className="px-1 text-xs text-gray-500">
            Guidance from <strong className="text-emerald-700">{source}</strong>; confirm important decisions with a local agricultural expert.
          </p>
          <section className="grid gap-4 lg:grid-cols-2">
            <article className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
              <h3 className="text-base font-bold text-gray-900">Diagnosis</h3>
              <p className="mt-2 text-sm leading-6 text-gray-700">{plan.description || plan.immediate_action}</p>
              {plan.image_assessed === false && (
                <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900">
                  The saved image was not included. Scan the crop again for an image-based diagnosis.
                </p>
              )}
              {plan.symptoms?.length > 0 && (
                <p className="mt-3 text-sm leading-6 text-gray-600">
                  <strong className="text-gray-800">Visible signs:</strong> {plan.symptoms.join('; ')}
                </p>
              )}
              {plan.causes?.length > 0 && (
                <p className="mt-2 text-sm leading-6 text-gray-600">
                  <strong className="text-gray-800">Possible cause:</strong> {plan.causes.join('; ')}
                </p>
              )}
            </article>

            <article className="rounded-2xl border border-emerald-100 bg-white p-5 shadow-sm">
              <div className="flex items-center gap-2">
                <Leaf size={18} className="text-emerald-700" />
                <h3 className="text-base font-bold text-gray-900">Treatment plan</h3>
              </div>
              {plan.organicTreatment?.length > 0 ? (
                <ol className="mt-3 list-inside list-decimal space-y-2 text-sm leading-6 text-gray-700">
                  {plan.organicTreatment.slice(0, 3).map((step, index) => (
                    <li key={`${index}-${step}`}>{step}</li>
                  ))}
                </ol>
              ) : (
                <p className="mt-3 text-sm text-gray-600">No treatment steps were returned. Retry diagnosis or consult a local crop expert.</p>
              )}
              <div className="mt-4 border-t border-gray-100 pt-3">
                <div className="flex items-center gap-2">
                  <FlaskConical size={16} className="text-purple-700" />
                  <h4 className="text-sm font-semibold text-gray-900">Chemical safety</h4>
                </div>
                <p className="mt-1 text-sm leading-6 text-gray-600">
                  {plan.chemicalTreatment?.[0] || 'Ask a qualified local expert before using any crop-protection product.'}
                </p>
              </div>
            </article>
          </section>
          {plan.prevention?.length > 0 && (
            <section className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm">
              <h3 className="text-sm font-bold text-gray-900">Monitor and prevent</h3>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm leading-6 text-gray-700">
                {plan.prevention.slice(0, 3).map((item, index) => <li key={`${index}-${item}`}>{item}</li>)}
              </ul>
            </section>
          )}
          <p className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">
            <CheckCircle2 size={15} className="mt-0.5 shrink-0" />
            AI guidance is not a confirmed diagnosis. Do not use chemicals without local expert advice and label directions.
          </p>
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
