import { useAuth } from '../context/AuthContext'
import { User, Mail, LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function Profile() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const handleLogout = async () => { await logout(); navigate('/login') }

  return (
    <div className="p-5 animate-fade-up max-w-2xl">
      <h1 className="section-title mb-1">👤 Farmer Profile</h1>
      <p className="section-subtitle mb-5">Manage your account</p>

      {/* Profile Info */}
      <div className="metric-card mb-5">
        <div className="flex items-center gap-4 mb-5">
          <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-green-400 to-green-700 flex items-center justify-center text-2xl font-bold text-white">
            {user?.name?.[0]?.toUpperCase()}
          </div>
          <div>
            <div className="text-lg font-bold text-gray-900">{user?.name}</div>
            <div className="text-sm text-gray-500">{user?.email}</div>
            <div className="text-xs text-green-500 font-medium mt-0.5">🌾 AI Farm Guardian Member</div>
          </div>
        </div>
        <div className="grid gap-3">
          {[
            { icon: User, label: 'Full Name', value: user?.name },
            { icon: Mail, label: 'Email', value: user?.email },
          ].map(f => (
            <div key={f.label} className="flex items-center gap-3 p-3 bg-gray-50 rounded-xl">
              <f.icon size={15} className="text-green-500" />
              <div>
                <div className="text-[10px] text-gray-400">{f.label}</div>
                <div className="text-sm font-medium text-gray-800">{f.value}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="metric-card mb-5">
        <div className="text-sm font-bold text-gray-800 mb-1">Service configuration</div>
        <p className="text-xs text-gray-500">
          Integration keys are configured only on the backend in its private environment file. They are never stored in or returned to your profile.
        </p>
      </div>

      {/* Logout */}
      <div className="metric-card">
        <div className="text-sm font-bold text-gray-800 mb-2">Account Actions</div>
        <button onClick={handleLogout} className="flex items-center gap-2 px-4 py-2.5 bg-red-50 text-red-600 border border-red-200 rounded-xl hover:bg-red-100 transition-colors text-sm font-medium w-full">
          <LogOut size={15} /> Sign Out from AI Farm Guardian
        </button>
      </div>
    </div>
  )
}
