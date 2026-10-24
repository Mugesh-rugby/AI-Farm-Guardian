import { useState, useEffect } from 'react'
import api from '../api/client'
import toast from 'react-hot-toast'
import { Link } from 'react-router-dom'
import { ClipboardList, Plus, CheckCircle, Clock, AlertTriangle, ChevronRight } from 'lucide-react'

const STATUS_CONFIG = {
  pending: { color: '#3b82f6', bg: '#eff6ff', label: 'Scheduled', icon: '📅' },
  in_progress: { color: '#f59e0b', bg: '#fffbeb', label: 'In Progress', icon: '⚙️' },
  completed: { color: '#22c55e', bg: '#f0fdf4', label: 'Completed', icon: '✅' },
}

const TYPE_CONFIG = {
  organic: { color: '#22c55e', bg: '#f0fdf4', label: 'Organic' },
  chemical: { color: '#8b5cf6', bg: '#f5f3ff', label: 'Chemical' },
  cultural: { color: '#f59e0b', bg: '#fffbeb', label: 'Cultural' },
}

export default function TreatmentTracker() {
  const [treatments, setTreatments] = useState([])
  const [issues, setIssues] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    scan_id: '', action: '', treatment_type: 'organic',
    cost: '', follow_up_at: '', notes: ''
  })

  const fetchData = async () => {
    setLoading(true)
    try {
      const [treatRes, issueRes] = await Promise.all([api.get('/treatments/'), api.get('/scans?limit=100')])
      setTreatments(treatRes.data)
      setIssues(issueRes.data.filter((scan) => scan.status !== 'resolved'))
    } catch { toast.error('Failed to load treatment data') }
    finally { setLoading(false) }
  }

  useEffect(() => { fetchData() }, [])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.scan_id) { toast.error('Select an assessed issue'); return }
    setSubmitting(true)
    try {
      await api.post('/treatments/', {
        scan_id: Number(form.scan_id),
        action: form.action,
        treatment_type: form.treatment_type,
        cost: form.cost === '' ? null : Number(form.cost),
        follow_up_at: form.follow_up_at ? new Date(form.follow_up_at).toISOString() : null,
        notes: form.notes || null,
      })
      toast.success('Treatment logged!')
      setShowForm(false)
      fetchData()
    } catch (err) { toast.error(err.response?.data?.detail || 'Failed to log treatment') }
    finally { setSubmitting(false) }
  }

  const handleStatusUpdate = async (id, status) => {
    try {
      await api.put(`/treatments/${id}`, { status })
      toast.success(`Marked as ${status}`)
      fetchData()
    } catch { toast.error('Failed to update') }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this treatment record?')) return
    try {
      await api.delete(`/treatments/${id}`)
      toast.success('Treatment deleted')
      fetchData()
    } catch { toast.error('Failed to delete treatment') }
  }

  const stats = {
    total: treatments.length,
    completed: treatments.filter(t => t.status === 'completed').length,
    in_progress: treatments.filter(t => t.status === 'in_progress').length,
    scheduled: treatments.filter(t => t.status === 'pending').length,
  }
  const progressPct = stats.total > 0 ? Math.round((stats.completed / stats.total) * 100) : 0

  return (
    <div className="p-5 animate-fade-up">
      <div className="flex items-start justify-between mb-5">
        <div>
          <h1 className="section-title">📋 Treatment Tracker</h1>
          <p className="section-subtitle">Log, track, and manage all crop treatment applications</p>
        </div>
        <button onClick={() => setShowForm(!showForm)} className="btn-primary">
          <Plus size={15} /> Log Treatment
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3 mb-5">
        {Object.entries({ 'Total': [stats.total, '#6b7280'], 'Scheduled': [stats.scheduled, '#3b82f6'], 'In Progress': [stats.in_progress, '#f59e0b'], 'Completed': [stats.completed, '#22c55e'] }).map(([label, [val, color]]) => (
          <div key={label} className="metric-card text-center">
            <div className="text-2xl font-bold" style={{ color }}>{val}</div>
            <div className="text-xs text-gray-400 mt-0.5">{label}</div>
          </div>
        ))}
      </div>

      {/* Progress */}
      {stats.total > 0 && (
        <div className="metric-card mb-5">
          <div className="flex items-center justify-between mb-2">
            <span className="text-sm font-semibold text-gray-700">Overall Treatment Progress</span>
            <span className="text-sm font-bold text-green-600">{progressPct}%</span>
          </div>
          <div className="progress-bar">
            <div className="progress-bar-fill bg-gradient-to-r from-green-400 to-green-600" style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      )}

      {/* Add Form */}
      {showForm && (
        <div className="metric-card mb-5 animate-fade-up">
          <div className="text-sm font-bold text-gray-800 mb-4">Log New Treatment</div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid md:grid-cols-2 gap-4">
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1 block">Related Issue *</label>
                <select value={form.scan_id} onChange={e => setForm({...form, scan_id: e.target.value})} className="farm-input" required>
                  <option value="">-- Select Issue --</option>
                  {issues.map(i => <option key={i.id} value={i.id}>{i.disease_name || 'Unclassified crop scan'} ({i.severity || 'unassessed'}) · Field {i.field_id}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1 block">Action / treatment record *</label>
                <input value={form.action} onChange={e => setForm({...form, action: e.target.value})} placeholder="Describe the treatment actually selected" className="farm-input" required />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1 block">Treatment Type</label>
                <select value={form.treatment_type} onChange={e => setForm({...form, treatment_type: e.target.value})} className="farm-input">
                  {['organic', 'chemical', 'cultural'].map(t => <option key={t}>{t}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1 block">Follow-up date</label>
                <input type="date" value={form.follow_up_at} onChange={e => setForm({...form, follow_up_at: e.target.value})} className="farm-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1 block">Actual cost (optional)</label>
                <input type="number" min="0" step="0.01" value={form.cost} onChange={e => setForm({...form, cost: e.target.value})} className="farm-input" />
              </div>
              <div>
                <label className="text-xs font-semibold text-gray-600 mb-1 block">Notes</label>
                <input value={form.notes} onChange={e => setForm({...form, notes: e.target.value})} placeholder="Additional observations" className="farm-input" />
              </div>
            </div>
            <div className="flex gap-3">
              <button type="submit" disabled={submitting} className="btn-primary">
                {submitting ? <span className="spinner" /> : <ClipboardList size={14} />} Log Treatment
              </button>
              <button type="button" onClick={() => setShowForm(false)} className="btn-secondary">Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* Treatment List */}
      {loading ? (
        <div className="flex justify-center py-12"><div className="spinner w-10 h-10" style={{ borderWidth: 3 }} /></div>
      ) : treatments.length === 0 ? (
        <div className="empty-state metric-card">
          <div className="empty-state-icon"><ClipboardList size={32} className="text-green-400" /></div>
          <h2 className="text-base font-bold text-green-900 mb-2">No Treatments Logged</h2>
          <p className="text-gray-400 text-sm mb-4">Generate an AI Rescue Plan and log treatments to track crop recovery progress.</p>
          <Link to="/scanner" className="btn-primary">Record a crop scan</Link>
        </div>
      ) : (
        <div className="space-y-3">
          {treatments.map(t => {
            const sCfg = STATUS_CONFIG[t.status] || STATUS_CONFIG.pending
            const tCfg = TYPE_CONFIG[t.treatment_type] || TYPE_CONFIG.organic
            return (
              <div key={t.id} className="metric-card">
                <div className="flex items-start gap-3">
                  <div className="text-xl flex-shrink-0">{sCfg.icon}</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-sm font-bold text-gray-900">{t.action}</div>
                      <span className="text-[10px] px-2 py-0.5 rounded-full font-bold flex-shrink-0" style={{ background: sCfg.bg, color: sCfg.color }}>
                        {sCfg.label}
                      </span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2 mt-1">
                      <span className="text-[10px] text-gray-500">{t.issue_name}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded font-medium" style={{ background: tCfg.bg, color: tCfg.color }}>{t.treatment_type}</span>
                      {t.follow_up_at && <span className="text-[10px] text-gray-400">Follow-up: {new Date(t.follow_up_at).toLocaleDateString()}</span>}
                      {t.cost != null && <span className="text-[10px] text-gray-400">Cost: ₹{Number(t.cost).toLocaleString('en-IN')}</span>}
                    </div>
                    {t.notes && <div className="text-[11px] text-gray-400 mt-1">{t.notes}</div>}
                  </div>
                  <div className="flex flex-col gap-1.5 flex-shrink-0">
                    {t.status === 'pending' && (
                      <button onClick={() => handleStatusUpdate(t.id, 'in_progress')} className="text-[10px] px-2 py-1 bg-amber-50 text-amber-600 border border-amber-200 rounded-lg hover:bg-amber-100 transition-colors">
                        Start
                      </button>
                    )}
                    {t.status === 'in_progress' && (
                      <button onClick={() => handleStatusUpdate(t.id, 'completed')} className="text-[10px] px-2 py-1 bg-green-50 text-green-600 border border-green-200 rounded-lg hover:bg-green-100 transition-colors">
                        ✓ Done
                      </button>
                    )}
                    <button onClick={() => handleDelete(t.id)} className="text-[10px] px-2 py-1 text-red-600 hover:bg-red-50 rounded-lg">
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
