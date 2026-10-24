import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../api/client'
import {
  AlertTriangle, ArrowRight, CheckCircle2, ClipboardList, Clock3, Leaf,
  Plus, RefreshCw, ScanLine, Tractor
} from 'lucide-react'
import {
  ArcElement, CategoryScale, Chart as ChartJS, Filler, Legend, LinearScale,
  LineElement, PointElement, Tooltip
} from 'chart.js'
import { Doughnut, Line } from 'react-chartjs-2'

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, ArcElement, Tooltip, Legend, Filler)

const PRIORITY_COLORS = {
  CRITICAL: '#dc2626',
  HIGH: '#ea580c',
  MEDIUM: '#d97706',
  LOW: '#16a34a',
}

function formatDate(value) {
  if (!value) return 'Date unavailable'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? 'Date unavailable'
    : date.toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' })
}

function severityClass(severity) {
  switch ((severity || '').toLowerCase()) {
    case 'critical': return 'bg-red-50 text-red-700'
    case 'high': return 'bg-orange-50 text-orange-700'
    case 'medium': return 'bg-amber-50 text-amber-700'
    case 'low': return 'bg-emerald-50 text-emerald-700'
    default: return 'bg-gray-100 text-gray-600'
  }
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState('')
  const [reloadKey, setReloadKey] = useState(0)

  const loadDashboard = useCallback(async (silent = false) => {
    if (silent) setRefreshing(true)
    else setLoading(true)
    try {
      const response = await api.get('/dashboard/')
      setData(response.data)
      setError('')
    } catch (err) {
      setError(err.response?.data?.detail || 'Dashboard data could not be loaded. Check the connection and try again.')
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }, [])

  useEffect(() => {
    loadDashboard()
    const timer = window.setInterval(() => loadDashboard(true), 60_000)
    return () => window.clearInterval(timer)
  }, [loadDashboard, reloadKey])

  const scanActivity = data?.scan_activity || []
  const priorityDistribution = data?.priority_distribution || {}
  const priorityTotal = Object.values(priorityDistribution).reduce((sum, count) => sum + (Number(count) || 0), 0)
  const recentScans = data?.recent_scans || []
  const highestIssue = data?.highest_priority || data?.top_priority
  const treatments = data?.treatment_stats || {}

  const activityChart = {
    labels: scanActivity.map(({ date }) => {
      const parsed = new Date(`${date}T00:00:00`)
      return parsed.toLocaleDateString(undefined, { day: 'numeric', month: 'short' })
    }),
    datasets: [{
      label: 'Scans',
      data: scanActivity.map(({ scans }) => scans),
      borderColor: '#18734b',
      backgroundColor: 'rgba(24, 115, 75, 0.1)',
      fill: true,
      tension: 0.3,
      pointRadius: 2,
      pointHoverRadius: 5,
    }],
  }

  const priorityChart = {
    labels: ['Critical', 'High', 'Medium', 'Low'],
    datasets: [{
      data: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((tier) => Number(priorityDistribution[tier]) || 0),
      backgroundColor: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((tier) => PRIORITY_COLORS[tier]),
      borderWidth: 3,
      borderColor: '#fff',
      hoverOffset: 4,
    }],
  }

  if (loading) {
    return (
      <div className="flex min-h-64 items-center justify-center" role="status">
        <div className="h-9 w-9 animate-spin rounded-full border-4 border-emerald-700 border-t-transparent" />
        <span className="sr-only">Loading dashboard</span>
      </div>
    )
  }

  if (error && !data) {
    return (
      <section className="mx-auto max-w-2xl rounded-2xl border border-amber-200 bg-white p-8 text-center shadow-sm" role="alert">
        <AlertTriangle className="mx-auto mb-3 text-amber-600" size={30} />
        <h1 className="text-xl font-bold text-gray-900">Dashboard is unavailable</h1>
        <p className="mt-2 text-sm text-gray-600">{error}</p>
        <button type="button" onClick={() => setReloadKey((key) => key + 1)} className="btn-primary mt-5 inline-flex items-center gap-2 px-4 py-2 text-white">
          <RefreshCw size={15} /> Try again
        </button>
      </section>
    )
  }

  const metrics = [
    { label: 'Farms', value: data?.farms_count ?? data?.farm_count ?? 0, icon: Tractor, color: 'text-emerald-700 bg-emerald-50', detail: 'Your registered farms' },
    { label: 'Fields', value: data?.fields_count ?? data?.field_count ?? 0, icon: Leaf, color: 'text-lime-700 bg-lime-50', detail: 'Across your farms' },
    { label: 'Crop scans', value: data?.scan_count ?? 0, icon: ScanLine, color: 'text-sky-700 bg-sky-50', detail: 'Saved assessments' },
    { label: 'Active risks', value: data?.active_issues_count ?? 0, icon: AlertTriangle, color: 'text-amber-700 bg-amber-50', detail: 'Recorded active scans' },
  ]

  return (
    <div className="mx-auto max-w-7xl space-y-6 pb-8">
      <header className="flex flex-col justify-between gap-4 rounded-2xl border border-emerald-100 bg-gradient-to-br from-white via-white to-emerald-50 p-5 shadow-sm sm:flex-row sm:items-center sm:p-7">
        <div>
          <p className="eyebrow">Farm overview</p>
          <h1 className="section-title">Your farm dashboard</h1>
          <p className="section-subtitle max-w-2xl">
            A live summary of the farms, scans, risks, and treatments saved to your account.
          </p>
          {error && <p className="mt-2 text-sm text-amber-700" role="status">Refresh failed: {error}</p>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button
            type="button"
            onClick={() => loadDashboard(true)}
            disabled={refreshing}
            className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm"
            aria-label="Refresh dashboard data"
          >
            <RefreshCw size={15} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
          <Link to="/farms" className="btn-secondary inline-flex items-center gap-2 px-3 py-2 text-sm">
            <Plus size={16} /> Add farm
          </Link>
          <Link to="/scanner" className="btn-primary inline-flex items-center gap-2 px-4 py-2 text-sm text-white">
            <ScanLine size={16} /> Scan a crop
          </Link>
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-label="Account totals">
        {metrics.map(({ label, value, icon: Icon, color, detail }) => (
          <article key={label} className="metric-card rounded-2xl border bg-white p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-medium text-gray-500">{label}</p>
                <p className="mt-2 text-3xl font-bold tracking-tight text-gray-900">{value}</p>
              </div>
              <span className={`inline-flex h-11 w-11 items-center justify-center rounded-xl ${color}`}>
                <Icon size={20} aria-hidden="true" />
              </span>
            </div>
            <p className="mt-3 text-xs text-gray-500">{detail}</p>
          </article>
        ))}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <article className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-5 flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-gray-900">Highest priority active scan</h2>
              <p className="mt-1 text-sm text-gray-500">Based on priority records saved for your farms.</p>
            </div>
            <Link to="/rescue" className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold text-emerald-700 hover:text-emerald-900">
              Open rescue planner <ArrowRight size={15} />
            </Link>
          </div>
          {highestIssue ? (
            <div className="flex flex-col gap-4 rounded-xl border border-amber-100 bg-amber-50/60 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-lg font-bold text-gray-900">{highestIssue.issue_name || highestIssue.disease_name || 'Recorded crop risk'}</p>
                <p className="mt-1 text-sm text-gray-600">
                  {[highestIssue.farm_name, highestIssue.field_name, highestIssue.crop].filter(Boolean).join(' · ') || 'Farm details unavailable'}
                </p>
                <p className="mt-2 text-xs text-gray-600">
                  {highestIssue.timeframe ? `Suggested timeframe: ${highestIssue.timeframe}` : 'Review the scan details and recommended next steps.'}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-2">
                <span className="rounded-full bg-white px-3 py-1.5 text-xs font-bold text-amber-800">
                  {highestIssue.priority_category || highestIssue.tier || 'Priority'} · {Number(highestIssue.priority_score ?? highestIssue.score ?? 0).toFixed(0)}
                </span>
                <Link to={highestIssue.scan_id ? `/rescue/${highestIssue.scan_id}` : '/rescue'} className="inline-flex items-center gap-1.5 rounded-lg bg-emerald-700 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-800">
                  Review plan <ArrowRight size={14} />
                </Link>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center">
              <CheckCircle2 className="mx-auto mb-2 text-emerald-600" size={25} />
              <p className="font-semibold text-gray-800">No active priority risks</p>
              <p className="mt-1 text-sm text-gray-500">New assessed risks will appear here after a scan is saved.</p>
            </div>
          )}
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-xl bg-gray-50 p-3">
              <p className="text-xs font-medium text-gray-500">Treatments completed</p>
              <p className="mt-1 text-lg font-bold text-gray-900">{treatments.completed ?? data?.treatments_completed ?? 0}</p>
            </div>
            <div className="rounded-xl bg-gray-50 p-3">
              <p className="text-xs font-medium text-gray-500">Treatments tracked</p>
              <p className="mt-1 text-lg font-bold text-gray-900">{treatments.total ?? data?.treatments_total ?? 0}</p>
            </div>
          </div>
        </article>

        <article className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4">
            <h2 className="text-base font-bold text-gray-900">Scan activity</h2>
            <p className="mt-1 text-sm text-gray-500">Saved scans per day over the last 30 calendar days.</p>
          </div>
          <div className="h-56">
            {scanActivity.length > 0 ? (
              <Line
                data={activityChart}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  interaction: { intersect: false, mode: 'index' },
                  scales: {
                    y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: '#eef2ef' } },
                    x: { grid: { display: false }, ticks: { maxTicksLimit: 7, maxRotation: 0 } },
                  },
                  plugins: { legend: { display: false } },
                }}
              />
            ) : (
              <div className="flex h-full items-center justify-center text-sm text-gray-500">No scan activity recorded yet.</div>
            )}
          </div>
        </article>
      </section>

      <section className="grid gap-6 xl:grid-cols-[1fr_1.4fr]">
        <article className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4">
            <h2 className="text-base font-bold text-gray-900">Active priority distribution</h2>
            <p className="mt-1 text-sm text-gray-500">Saved priority assessments by tier.</p>
          </div>
          {priorityTotal > 0 ? (
            <div className="flex h-56 items-center justify-center">
              <Doughnut
                data={priorityChart}
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  cutout: '68%',
                  plugins: { legend: { position: 'right', labels: { usePointStyle: true, boxWidth: 8, padding: 16 } } },
                }}
              />
            </div>
          ) : (
            <div className="flex h-56 flex-col items-center justify-center text-center">
              <ClipboardList className="mb-2 text-gray-300" size={28} />
              <p className="text-sm font-medium text-gray-700">No priority assessments yet</p>
              <p className="mt-1 text-xs text-gray-500">Saved assessments will be grouped here.</p>
            </div>
          )}
        </article>

        <article className="rounded-2xl border border-gray-100 bg-white p-5 shadow-sm sm:p-6">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <h2 className="text-base font-bold text-gray-900">Recent crop scans</h2>
              <p className="mt-1 text-sm text-gray-500">Latest assessments saved to your account.</p>
            </div>
            <Link to="/scanner" className="inline-flex shrink-0 items-center gap-1 text-sm font-semibold text-emerald-700 hover:text-emerald-900">
              New scan <ArrowRight size={15} />
            </Link>
          </div>
          {recentScans.length ? (
            <ul className="divide-y divide-gray-100">
              {recentScans.slice(0, 5).map((scan) => (
                <li key={scan.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="flex min-w-0 items-center gap-3">
                    <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-700">
                      <Leaf size={17} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-gray-900">{scan.disease_name || 'Crop scan'}</p>
                      <p className="mt-0.5 inline-flex items-center gap-1 text-xs text-gray-500">
                        <Clock3 size={12} /> {formatDate(scan.created_at)}
                      </p>
                    </div>
                  </div>
                  <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs font-semibold capitalize ${severityClass(scan.severity)}`}>
                    {scan.severity || 'Unassessed'}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <div className="rounded-xl border border-dashed border-gray-200 px-4 py-8 text-center">
              <ScanLine className="mx-auto mb-2 text-gray-300" size={27} />
              <p className="text-sm font-medium text-gray-700">No scans recorded</p>
              <p className="mt-1 text-xs text-gray-500">Your saved scan results will appear here.</p>
              <Link to="/scanner" className="mt-3 inline-flex items-center gap-1 text-sm font-semibold text-emerald-700 hover:text-emerald-900">
                Scan a crop <ArrowRight size={14} />
              </Link>
            </div>
          )}
        </article>
      </section>
    </div>
  )
}
