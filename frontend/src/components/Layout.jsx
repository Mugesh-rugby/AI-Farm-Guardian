import React, { useState } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useFarm } from '../context/FarmContext'
import FarmGuardianMark from './FarmGuardianMark'
import {
  LayoutDashboard, Tractor, ScanLine, Sparkles, CloudSun,
  MessageCircle, ClipboardCheck, User, LogOut, Menu, X, ChevronLeft, ListOrdered
} from 'lucide-react'

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
  { to: '/priority', label: 'Intervention Prioritizer', icon: ListOrdered },
  { to: '/farms', label: 'My Farms', icon: Tractor },
  { to: '/scanner', label: 'Crop Scanner', icon: ScanLine },
  { to: '/rescue', label: 'AI Rescue Planner', icon: Sparkles },
  { to: '/weather', label: 'Weather', icon: CloudSun },
  { to: '/assistant', label: 'AI Farm Assistant', icon: MessageCircle },
  { to: '/treatments', label: 'Treatment Tracker', icon: ClipboardCheck },
  { to: '/profile', label: 'Profile', icon: User },
]

const MOBILE_ITEMS = [
  { to: '/dashboard', label: 'Home', icon: LayoutDashboard },
  { to: '/priority', label: 'Priority', icon: ListOrdered },
  { to: '/scanner', label: 'Scan', icon: ScanLine },
  { to: '/rescue', label: 'Rescue', icon: Sparkles },
  { to: '/assistant', label: 'Assistant', icon: MessageCircle },
  { to: '/profile', label: 'Profile', icon: User },
]

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const { activeFarm } = useFarm()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const activePage = NAV_ITEMS.find(({ to }) => location.pathname === to || location.pathname.startsWith(`${to}/`))

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  return (
    <div className="flex min-h-screen bg-gray-50">
      {/* Desktop sidebar */}
      <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-gray-200 bg-white transition-[width] duration-200 lg:flex ${sidebarCollapsed ? 'w-20' : 'w-64'}`}>
        <div className={`flex items-center gap-2 border-b border-gray-200 px-4 py-5 ${sidebarCollapsed ? 'justify-center' : ''}`}>
          <FarmGuardianMark className="h-9 w-9 rounded-xl" />
          {!sidebarCollapsed && <div>
            <p className="font-extrabold leading-tight text-emerald-900">AI Farm Guardian</p>
            <p className="text-[11px] leading-tight text-gray-500">Farm management</p>
          </div>}
        </div>
        <nav aria-label="Main navigation" className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              title={sidebarCollapsed ? label : undefined}
              aria-label={sidebarCollapsed ? label : undefined}
              className={({ isActive }) =>
                `group relative flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-colors ${sidebarCollapsed ? 'justify-center' : ''} ${
                  isActive
                    ? 'bg-emerald-700 text-white shadow-sm'
                    : 'text-gray-700 hover:bg-emerald-50 hover:text-emerald-800'
                }`
              }
            >
              <Icon className="w-[18px] h-[18px] shrink-0" />
              {!sidebarCollapsed && <span>{label}</span>}
              {sidebarCollapsed && (
                <span
                  role="tooltip"
                  className="pointer-events-none absolute left-full top-1/2 z-50 ml-3 -translate-y-1/2 whitespace-nowrap rounded-lg bg-gray-900 px-3 py-2 text-xs font-semibold text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
                >
                  {label}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-200 p-3">
          {!sidebarCollapsed && <div className="mb-3 rounded-xl bg-emerald-50 px-3 py-2">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-emerald-700">Selected farm</p>
            <p className="mt-0.5 truncate text-sm font-semibold text-gray-800">{activeFarm?.name || 'No farm selected'}</p>
          </div>}
          <div className={`flex items-center gap-3 px-3 py-2 ${sidebarCollapsed ? 'justify-center' : ''}`}>
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-emerald-100 font-bold text-emerald-800">
              {(user?.name || 'U')[0]?.toUpperCase()}
            </div>
            {!sidebarCollapsed && <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold truncate">{user?.name || 'User'}</p>
              <p className="truncate text-xs text-gray-500">{user?.email || ''}</p>
            </div>}
          </div>
          <button onClick={handleLogout} title={sidebarCollapsed ? 'Log out' : undefined} className={`mt-1 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm text-gray-600 transition-colors hover:bg-red-50 hover:text-red-600 ${sidebarCollapsed ? 'justify-center' : ''}`}>
            <LogOut className="w-[18px] h-[18px]" /> {!sidebarCollapsed && 'Log out'}
          </button>
          <button
            type="button"
            onClick={() => setSidebarCollapsed((value) => !value)}
            aria-label={sidebarCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="mt-1 flex w-full items-center justify-center rounded-lg py-2 text-gray-500 hover:bg-gray-100 hover:text-gray-900"
          >
            <ChevronLeft size={16} className={sidebarCollapsed ? 'rotate-180 transition-transform' : 'transition-transform'} />
          </button>
        </div>
      </aside>

      {/* Mobile top bar */}
      <div className="fixed left-0 right-0 top-0 z-30 flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3 lg:hidden">
        <div className="flex items-center gap-2">
          <FarmGuardianMark className="h-8 w-8 rounded-lg" iconClassName="h-4 w-4" />
          <span className="text-sm font-bold text-emerald-900">AI Farm Guardian</span>
        </div>
        <button onClick={() => setMobileOpen(true)} aria-label="Open navigation menu" aria-expanded={mobileOpen} className="p-2 text-emerald-800">
          <Menu className="w-6 h-6" />
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <button type="button" aria-label="Close navigation menu" className="absolute inset-0 bg-black/40" onClick={() => setMobileOpen(false)} />
          <div role="dialog" aria-modal="true" aria-label="Navigation menu" className="absolute right-0 top-0 bottom-0 w-72 max-w-[85vw] overflow-y-auto bg-white p-4 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <span className="font-bold text-emerald-900">Menu</span>
              <button type="button" aria-label="Close navigation menu" onClick={() => setMobileOpen(false)}><X className="w-5 h-5" /></button>
            </div>
            <nav className="space-y-1">
              {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
                <NavLink
                  key={to}
                  to={to}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium ${
                      isActive ? 'bg-emerald-700 text-white' : 'text-gray-700 hover:bg-emerald-50 hover:text-emerald-800'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  {label}
                </NavLink>
              ))}
              <button onClick={handleLogout} className="flex items-center gap-3 px-3 py-2.5 w-full text-sm text-red-600">
                <LogOut className="w-4 h-4" /> Log out
              </button>
            </nav>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="flex-1 min-w-0 pt-16 lg:pt-0 pb-20 lg:pb-0">
        <div className="sticky top-0 z-20 hidden h-16 items-center justify-between border-b border-gray-200 bg-white/95 px-6 backdrop-blur lg:flex">
          <div>
            <p className="text-xs font-medium text-gray-500">Workspace / {activePage?.label || 'Farm Guardian'}</p>
            <p className="text-sm font-semibold text-gray-900">{activeFarm?.name || 'Select or add a farm to get started'}</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="max-w-48 truncate text-sm text-gray-600">{user?.name}</span>
            <NavLink to="/profile" className="flex h-9 w-9 items-center justify-center rounded-full bg-emerald-100 font-bold text-emerald-800" aria-label="Open profile">
              {(user?.name || 'U')[0]?.toUpperCase()}
            </NavLink>
          </div>
        </div>
        <div className="max-w-7xl mx-auto p-4 sm:p-6 lg:p-8">{children}</div>
      </main>

      {/* Mobile bottom nav */}
      <nav aria-label="Mobile navigation" className="fixed bottom-0 left-0 right-0 z-30 flex items-center justify-around border-t border-gray-200 bg-white py-2 lg:hidden">
        {MOBILE_ITEMS.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-2 py-1 text-[11px] font-medium ${
                isActive ? 'text-emerald-800' : 'text-gray-500'
              }`
            }
          >
            <Icon className="w-5 h-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  )
}
