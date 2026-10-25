import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  AlertTriangle, Check, ChevronRight, ClipboardCheck,
  CloudSun, Leaf, ListOrdered, LoaderCircle, RefreshCw, ScanLine,
  Search, ShieldAlert, Sparkles,
} from 'lucide-react'
import toast from 'react-hot-toast'
import api from '../api/client'

const EMPTY_SUMMARY = {
  critical: 0, high: 0, medium: 0, low: 0, pending: 0, completed: 0, total: 0,
}

const PRIORITY_STYLE = {
  CRITICAL: 'border-red-200 bg-red-50 text-red-800',
  HIGH: 'border-orange-200 bg-orange-50 text-orange-800',
  MEDIUM: 'border-amber-200 bg-amber-50 text-amber-800',
  LOW: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  UNASSESSED: 'border-gray-200 bg-gray-50 text-gray-700',
}

const SUMMARY_CARDS = [
  ['critical', 'Critical', 'border-t-red-600'],
  ['high', 'High priority', 'border-t-orange-500'],
  ['medium', 'Medium priority', 'border-t-amber-500'],
  ['low', 'Low priority', 'border-t-emerald-600'],
  ['pending', 'Pending', 'border-t-sky-600'],
  ['completed', 'Completed', 'border-t-gray-500'],
]

function formatDate(value, withTime = false) {
  if (!value) return 'Not recorded'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Not recorded'
  return date.toLocaleString(undefined, withTime
    ? { dateStyle: 'medium', timeStyle: 'short' }
    : { dateStyle: 'medium' })
}

function dateInputValue(value) {
  if (!value) return ''
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return ''
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset())
  return date.toISOString().slice(0, 10)
}

function titleCase(value) {
  return (value || '').replaceAll('_', ' ').replace(/\b\w/g, (character) => character.toUpperCase())
}

function buildParams(filters) {
  return Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ''))
}

export default function InterventionPrioritizer() {
  const [searchParams] = useSearchParams()
  const scanFromUrl = searchParams.get('scanId') || ''
  const [farms, setFarms] = useState([])
  const [filters, setFilters] = useState({
    farm_id: '', field_id: '', crop_type: '', issue_type: '', problem: '', tier: '',
    status: '', date_from: '', date_to: '',
  })
  const [items, setItems] = useState([])
  const [summary, setSummary] = useState(EMPTY_SUMMARY)
  const [candidates, setCandidates] = useState([])
  const [selected, setSelected] = useState(null)
  const [selectedCandidate, setSelectedCandidate] = useState('')
  const [severity, setSeverity] = useState('')
  const [affectedArea, setAffectedArea] = useState('')
  const [followUpDate, setFollowUpDate] = useState('')
  const [chosenAction, setChosenAction] = useState('')
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')

  const fields = useMemo(
    () => farms.flatMap((farm) => (farm.fields || []).map((field) => ({ ...field, farm_name: farm.name }))),
    [farms],
  )
  const crops = useMemo(() => [...new Set(fields.map((field) => field.crop).filter(Boolean))].sort(), [fields])

  const loadData = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true)
    else setLoading(true)
    try {
      const params = buildParams(filters)
      const [farmResponse, priorityResponse, summaryResponse, candidateResponse] = await Promise.all([
        api.get('/farms/'),
        api.get('/priority/', { params }),
        api.get('/priority/summary', { params }),
        api.get('/priority/candidates', {
          params: filters.farm_id ? { farm_id: filters.farm_id } : {},
        }),
      ])
      setFarms(farmResponse.data)
      setItems(priorityResponse.data)
      setSummary(summaryResponse.data)
      setCandidates(candidateResponse.data)
      setError('')
      if (scanFromUrl && candidateResponse.data.some((item) => String(item.scan_id) === scanFromUrl)) {
        setSelectedCandidate(scanFromUrl)
      }
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'Intervention data could not be loaded.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [filters, scanFromUrl])

  useEffect(() => { loadData() }, [loadData])

  useEffect(() => {
    if (!selected) return
    const fresh = items.find((item) => item.id === selected.id)
    if (fresh) setSelected(fresh)
  }, [items, selected?.id])

  const openDetails = async (item) => {
    try {
      const response = await api.get(`/priority/cases/${item.id}`)
      setSelected(response.data)
      setChosenAction(response.data.chosen_action || '')
      setFollowUpDate(dateInputValue(response.data.follow_up_at))
    } catch (requestError) {
      toast.error(requestError.response?.data?.detail || 'Could not load intervention details.')
    }
  }

  const handleCreate = async (event) => {
    event.preventDefault()
    if (!selectedCandidate) {
      toast.error('Choose a saved crop scan first.')
      return
    }
    setSubmitting(true)
    try {
      await api.post(`/priority/from-scan/${selectedCandidate}`, {
        severity,
        affected_area_pct: affectedArea === '' ? null : Number(affectedArea),
        follow_up_at: followUpDate ? new Date(`${followUpDate}T12:00:00`).toISOString() : null,
        chosen_action: chosenAction.trim() || null,
      })
      toast.success('Intervention added to the queue.')
      setSelectedCandidate('')
      setSeverity('')
      setAffectedArea('')
      setFollowUpDate('')
      setChosenAction('')
      await loadData(true)
    } catch (requestError) {
      const detail = requestError.response?.data?.detail
      toast.error(typeof detail === 'string' ? detail : detail?.message || 'Could not create intervention.')
    } finally {
      setSubmitting(false)
    }
  }

  const updateCase = async (item, updates) => {
    try {
      await api.patch(`/priority/cases/${item.id}`, updates)
      toast.success(updates.status === 'completed' ? 'Intervention completed.' : 'Intervention updated.')
      await loadData(true)
      if (selected?.id === item.id) await openDetails(item)
    } catch (requestError) {
      toast.error(requestError.response?.data?.detail || 'Intervention could not be updated.')
    }
  }

  const reassess = async (item) => {
    try {
      await api.post(`/priority/cases/${item.id}/reassess`)
      toast.success('Priority reassessed using currently available evidence.')
      await loadData(true)
      if (selected?.id === item.id) await openDetails(item)
    } catch (requestError) {
      toast.error(requestError.response?.data?.detail || 'Priority could not be reassessed.')
    }
  }

  const visibleFields = filters.farm_id
    ? fields.filter((field) => String(field.farm_id) === String(filters.farm_id))
    : fields

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-8">
      <header className="flex flex-col justify-between gap-4 border-b border-emerald-200 pb-5 sm:flex-row sm:items-end">
        <div>
          <p className="eyebrow">Decision support | {summary.total} recorded cases</p>
          <h1 className="section-title flex items-center gap-2"><ListOrdered size={25} /> Intervention Prioritizer</h1>
          <p className="section-subtitle max-w-3xl">Review recorded crop problems, understand the evidence, and track the next field action.</p>
        </div>
        <button type="button" onClick={() => loadData(true)} disabled={refreshing} className="btn-secondary inline-flex items-center justify-center gap-2 px-3 py-2 text-sm">
          <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} /> Refresh
        </button>
      </header>

      <div className="flex flex-wrap gap-2" aria-label="Related farm tools">
        <Link to="/scanner" className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"><ScanLine size={15} /> Crop Scanner</Link>
        <Link to="/rescue" className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"><Sparkles size={15} /> AI Rescue Planner</Link>
        <Link to="/weather" className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"><CloudSun size={15} /> Weather</Link>
        <Link to="/treatments" className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"><ClipboardCheck size={15} /> Treatment Tracker</Link>
      </div>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" aria-label="Intervention counts">
        {SUMMARY_CARDS.map(([key, label, accent]) => (
          <article key={key} className={`rounded-lg border border-gray-200 border-t-4 ${accent} bg-white p-4`}>
            <p className="text-xs font-medium text-gray-500">{label}</p>
            <p className="mt-1 text-2xl font-bold text-gray-900" aria-live="polite">{summary[key] ?? 0}</p>
          </article>
        ))}
      </section>

      <section className="rounded-lg border border-gray-200 bg-white p-4 sm:p-5" aria-label="Intervention filters">
        <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-gray-800"><Search size={16} /> Filter cases</div>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs font-medium text-gray-600">Farm
            <select className="farm-input mt-1 w-full" value={filters.farm_id} onChange={(event) => { setSelectedCandidate(''); setFilters((value) => ({ ...value, farm_id: event.target.value, field_id: '' })) }}>
              <option value="">All farms</option>
              {farms.map((farm) => <option key={farm.id} value={farm.id}>{farm.name}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">Field
            <select className="farm-input mt-1 w-full" value={filters.field_id} onChange={(event) => setFilters((value) => ({ ...value, field_id: event.target.value }))}>
              <option value="">All fields</option>
              {visibleFields.map((field) => <option key={field.id} value={field.id}>{field.name}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">Crop type
            <select className="farm-input mt-1 w-full" value={filters.crop_type} onChange={(event) => setFilters((value) => ({ ...value, crop_type: event.target.value }))}>
              <option value="">All crops</option>
              {crops.map((crop) => <option key={crop} value={crop}>{crop}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">Problem type
            <select className="farm-input mt-1 w-full" value={filters.issue_type} onChange={(event) => setFilters((value) => ({ ...value, issue_type: event.target.value }))}>
              <option value="">All problem types</option>
              {['disease', 'pest', 'water_stress', 'nutrient'].map((type) => <option key={type} value={type}>{titleCase(type)}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">Problem
            <input className="farm-input mt-1 w-full" value={filters.problem} onChange={(event) => setFilters((value) => ({ ...value, problem: event.target.value }))} placeholder="Search problem name" />
          </label>
          <label className="text-xs font-medium text-gray-600">Priority
            <select className="farm-input mt-1 w-full" value={filters.tier} onChange={(event) => setFilters((value) => ({ ...value, tier: event.target.value }))}>
              <option value="">All levels</option>
              {['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'UNASSESSED'].map((tier) => <option key={tier} value={tier}>{titleCase(tier)}</option>)}
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">Workflow status
            <select className="farm-input mt-1 w-full" value={filters.status} onChange={(event) => setFilters((value) => ({ ...value, status: event.target.value }))}>
              <option value="">All statuses</option>
              <option value="pending">Pending</option>
              <option value="in_progress">In progress</option>
              <option value="completed">Completed</option>
            </select>
          </label>
          <label className="text-xs font-medium text-gray-600">Detected from
            <input type="date" className="farm-input mt-1 w-full" value={filters.date_from} onChange={(event) => setFilters((value) => ({ ...value, date_from: event.target.value }))} />
          </label>
          <label className="text-xs font-medium text-gray-600">Detected through
            <input type="date" className="farm-input mt-1 w-full" value={filters.date_to} onChange={(event) => setFilters((value) => ({ ...value, date_to: event.target.value }))} />
          </label>
        </div>
      </section>

      <div className="grid items-start gap-5 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.8fr)]">
        <section aria-labelledby="queue-title">
          <div className="mb-3 flex items-end justify-between gap-3">
            <div>
              <h2 id="queue-title" className="text-lg font-bold text-gray-900">Ranked intervention queue</h2>
              <p className="text-xs text-gray-500">Ordered by the current rule-based score; unassessed cases remain visible.</p>
            </div>
            <span className="text-xs text-gray-500">{items.length} cases</span>
          </div>
          {loading ? (
            <div className="flex min-h-48 items-center justify-center text-sm text-gray-500" role="status"><LoaderCircle className="mr-2 animate-spin" size={18} /> Loading interventions</div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 p-5 text-sm text-red-800" role="alert">{error}</div>
          ) : items.length === 0 ? (
            <div className="rounded-lg border border-dashed border-gray-300 bg-white px-5 py-10 text-center">
              <Leaf className="mx-auto text-emerald-700" size={28} />
              <h3 className="mt-3 font-semibold text-gray-900">No matching interventions</h3>
              <p className="mt-1 text-sm text-gray-500">Saved cases will appear here. Create one from a crop scan below.</p>
            </div>
          ) : (
            <ul className="space-y-3">
              {items.map((item, index) => (
                <li key={item.id}>
                  <article className={`rounded-lg border bg-white p-4 ${selected?.id === item.id ? 'border-emerald-500 ring-1 ring-emerald-500' : 'border-gray-200'}`}>
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="flex min-w-0 gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-gray-100 text-sm font-bold text-gray-700">{index + 1}</span>
                        <div className="min-w-0">
                          <h3 className="truncate font-semibold text-gray-900">{item.issue_name}</h3>
                          <p className="mt-1 flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
                            <span>{item.farm_name}</span><span aria-hidden="true">|</span><span>{item.field_name}</span><span aria-hidden="true">|</span><span>{item.crop}</span>
                          </p>
                        </div>
                      </div>
                      <span className={`rounded-md border px-2.5 py-1 text-xs font-bold ${PRIORITY_STYLE[item.tier] || PRIORITY_STYLE.UNASSESSED}`}>{titleCase(item.tier)}</span>
                    </div>
                    <div className="mt-3 grid gap-2 text-xs text-gray-600 sm:grid-cols-2">
                      <p>Detected {formatDate(item.created_at)}</p>
                      <p>Updated {formatDate(item.updated_at, true)}</p>
                      <p>Severity: {titleCase(item.severity || 'unassessed')}</p>
                      <p>Scan confidence: {item.confidence == null ? 'Not available' : `${Number(item.confidence).toFixed(1)}% estimate`}</p>
                      <p>Workflow: {titleCase(item.status)}</p>
                    </div>
                    <p className="mt-3 text-sm font-semibold text-gray-800">
                      {item.score == null ? 'Priority score unavailable' : `Priority score ${Number(item.score).toFixed(1)} / 100`}
                      <span className="ml-2 text-xs font-normal text-gray-500">{item.scoring_method}</span>
                    </p>
                    <p className="mt-1 text-sm text-gray-600">{item.recommended_next_action}</p>
                    {item.reasons?.length > 0 && <p className="mt-2 line-clamp-2 text-xs text-gray-500">Factors: {item.reasons.slice(0, 2).join(' ')}</p>}
                    <div className="mt-3 flex flex-wrap items-center gap-2">
                      <button type="button" onClick={() => openDetails(item)} className="btn-secondary inline-flex items-center gap-1 px-3 py-1.5 text-xs">Details <ChevronRight size={14} /></button>
                      <Link to={`/rescue/${item.scan_id}`} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-emerald-800 hover:bg-emerald-50"><Sparkles size={14} /> Rescue plan</Link>
                      <Link to={`/treatments?scanId=${item.scan_id}`} className="inline-flex items-center gap-1 rounded-md px-2 py-1.5 text-xs font-semibold text-gray-700 hover:bg-gray-100"><ClipboardCheck size={14} /> Log treatment</Link>
                      {item.status !== 'completed' && <button type="button" onClick={() => updateCase(item, { status: item.status === 'pending' ? 'in_progress' : 'completed' })} className="ml-auto inline-flex items-center gap-1 rounded-md bg-emerald-700 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-800">{item.status === 'pending' ? 'Start' : 'Complete'} <Check size={14} /></button>}
                    </div>
                  </article>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="space-y-4">
          {selected && (
            <section className="rounded-lg border border-gray-200 bg-white p-4 sm:p-5" aria-labelledby="detail-title">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="eyebrow">{selected.scoring_method} | updated {formatDate(selected.updated_at, true)}</p>
                  <h2 id="detail-title" className="mt-1 text-lg font-bold text-gray-900">Why this needs attention</h2>
                </div>
                <span className={`rounded-md border px-2 py-1 text-xs font-bold ${PRIORITY_STYLE[selected.tier] || PRIORITY_STYLE.UNASSESSED}`}>{titleCase(selected.tier)}</span>
              </div>
              <p className="mt-3 text-sm font-semibold text-gray-800">{selected.recommended_next_action}</p>
              <ul className="mt-3 space-y-2 text-sm text-gray-700">
                {(selected.reasons || []).map((reason, index) => <li key={`${reason}-${index}`} className="flex gap-2"><span className="text-emerald-700">&bull;</span><span>{reason}</span></li>)}
              </ul>
              {selected.missing_information?.length > 0 && (
                <div className="mt-4 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-950">
                  <p className="font-semibold">Information not recorded</p>
                  <p className="mt-1">{selected.missing_information.join(' | ')}</p>
                </div>
              )}
              {selected.weather_context && (
                <div className="mt-3 rounded-md bg-sky-50 p-3 text-xs text-sky-950">
                  <p className="font-semibold">Weather context | {selected.weather_context.source || 'weather service'}</p>
                  <p className="mt-1">{selected.weather_context.temperature != null ? `${selected.weather_context.temperature} C | ` : ''}{selected.weather_context.humidity != null ? `${selected.weather_context.humidity}% humidity | ` : ''}{selected.weather_context.rain_probability != null ? `${selected.weather_context.rain_probability}% rain chance` : 'No rainfall probability recorded'}</p>
                  <p className="mt-1">Updated {formatDate(selected.weather_context.updated_at, true)}</p>
                </div>
              )}
              {selected.treatments?.length > 0 && (
                <div className="mt-4 border-t border-gray-100 pt-3">
                  <h3 className="text-sm font-semibold text-gray-800">Linked treatment records</h3>
                  <ul className="mt-2 space-y-2 text-xs text-gray-600">
                    {selected.treatments.map((treatment) => <li key={treatment.id} className="flex justify-between gap-2"><span>{treatment.action}</span><span className="shrink-0">{titleCase(treatment.status)}</span></li>)}
                  </ul>
                  <p className="mt-2 text-xs text-gray-500">Treatment completion is not evidence that the crop problem has improved.</p>
                </div>
              )}
              <label className="mt-4 block text-xs font-medium text-gray-600">Record chosen action
                <textarea className="farm-input mt-1 w-full" rows="2" maxLength="2000" value={chosenAction} onChange={(event) => setChosenAction(event.target.value)} placeholder="Farmer-recorded action" />
              </label>
              <label className="mt-3 block text-xs font-medium text-gray-600">Schedule follow-up
                <input type="date" className="farm-input mt-1 w-full" value={followUpDate} onChange={(event) => setFollowUpDate(event.target.value)} />
              </label>
              <div className="mt-3 flex flex-wrap gap-2">
                <button type="button" onClick={() => updateCase(selected, { chosen_action: chosenAction || null, follow_up_at: followUpDate ? new Date(`${followUpDate}T12:00:00`).toISOString() : null })} className="btn-primary px-3 py-2 text-xs text-white">Save follow-up/action</button>
                <button type="button" onClick={() => reassess(selected)} className="btn-secondary inline-flex items-center gap-1 px-3 py-2 text-xs"><RefreshCw size={13} /> Reassess</button>
              </div>
              <div className="mt-4 flex flex-wrap gap-3 border-t border-gray-100 pt-3 text-xs font-semibold">
                <Link to={`/scanner`} className="text-emerald-800 hover:underline">New scan</Link>
                <Link to={`/rescue/${selected.scan_id}`} className="text-emerald-800 hover:underline">AI rescue plan</Link>
                <Link to="/weather" className="text-emerald-800 hover:underline">Weather</Link>
                <Link to={`/treatments?scanId=${selected.scan_id}`} className="text-emerald-800 hover:underline">Treatment tracker</Link>
              </div>
            </section>
          )}

          <section className="rounded-lg border border-emerald-200 bg-white p-4 sm:p-5" aria-labelledby="create-title">
            <div className="flex items-start gap-3">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-emerald-100 text-emerald-800"><AlertTriangle size={18} /></span>
              <div>
                <h2 id="create-title" className="font-bold text-gray-900">Create from a crop scan</h2>
                <p className="mt-1 text-xs leading-5 text-gray-600">Model confidence is not severity. Record what you observe before adding urgency.</p>
              </div>
            </div>
            {candidates.length === 0 ? (
              <div className="mt-4 rounded-md bg-gray-50 p-3 text-sm text-gray-600">No unlinked crop scans are available. Scan a field to start a case.</div>
            ) : (
              <form className="mt-4 space-y-3" onSubmit={handleCreate}>
                <label className="block text-xs font-medium text-gray-600">Saved scan
                  <select className="farm-input mt-1 w-full" value={selectedCandidate} onChange={(event) => setSelectedCandidate(event.target.value)} required>
                    <option value="">Choose scan</option>
                    {candidates.map((candidate) => <option key={candidate.scan_id} value={candidate.scan_id}>{candidate.issue_name} | {candidate.farm_name} / {candidate.field_name} | {formatDate(candidate.created_at)}</option>)}
                  </select>
                </label>
                <label className="block text-xs font-medium text-gray-600">Observed severity
                  <select className="farm-input mt-1 w-full" value={severity} onChange={(event) => setSeverity(event.target.value)} required>
                    <option value="">Choose observed severity</option>
                    {['low', 'medium', 'high', 'critical'].map((value) => <option key={value} value={value}>{titleCase(value)}</option>)}
                  </select>
                </label>
                <label className="block text-xs font-medium text-gray-600">Affected area (%) | optional
                  <input className="farm-input mt-1 w-full" type="number" min="0" max="100" step="0.1" value={affectedArea} onChange={(event) => setAffectedArea(event.target.value)} placeholder="Only enter an observed estimate" />
                </label>
                <label className="block text-xs font-medium text-gray-600">Follow-up date | optional
                  <input className="farm-input mt-1 w-full" type="date" value={followUpDate} onChange={(event) => setFollowUpDate(event.target.value)} />
                </label>
                <label className="block text-xs font-medium text-gray-600">Chosen action | optional
                  <input className="farm-input mt-1 w-full" value={chosenAction} onChange={(event) => setChosenAction(event.target.value)} maxLength="2000" placeholder="Record an action selected by the farmer" />
                </label>
                <button type="submit" disabled={submitting || !selectedCandidate} className="btn-primary inline-flex w-full items-center justify-center gap-2 px-3 py-2.5 text-sm text-white disabled:opacity-50">
                  {submitting ? <LoaderCircle size={16} className="animate-spin" /> : <ChevronRight size={16} />} Add to intervention queue
                </button>
              </form>
            )}
            <div className="mt-4 flex items-start gap-2 border-t border-gray-100 pt-3 text-xs leading-5 text-gray-500">
              <ShieldAlert size={15} className="mt-0.5 shrink-0" />
              <p>Rule-based decision support, not an XGBoost model or an agronomic diagnosis. Initial weights and thresholds require agricultural expert review.</p>
            </div>
          </section>
        </aside>
      </div>
    </div>
  )
}