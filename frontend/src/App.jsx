import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import AppErrorBoundary from './components/AppErrorBoundary'

const Login = lazy(() => import('./pages/Login'))
const Register = lazy(() => import('./pages/Register'))
const Dashboard = lazy(() => import('./pages/Dashboard'))
const MyFarms = lazy(() => import('./pages/MyFarms'))
const CropScanner = lazy(() => import('./pages/CropScanner'))
const RescuePlanner = lazy(() => import('./pages/RescuePlanner'))
const Weather = lazy(() => import('./pages/Weather'))
const AiAssistant = lazy(() => import('./pages/AiAssistant'))
const TreatmentTracker = lazy(() => import('./pages/TreatmentTracker'))
const Profile = lazy(() => import('./pages/Profile'))

function Protected({ children }) {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50" role="status">
        <div className="text-center">
          <div className="mx-auto mb-3 h-9 w-9 animate-spin rounded-full border-4 border-emerald-700 border-t-transparent" />
          <p className="text-sm font-medium text-gray-600">Checking your session...</p>
        </div>
      </div>
    )
  }
  if (!user) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

function HomeRedirect() {
  const { user, loading } = useAuth()
  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50" role="status">
        <p className="text-sm font-medium text-gray-600">Checking your session...</p>
      </div>
    )
  }
  return <Navigate to={user ? '/dashboard' : '/login'} replace />
}

export default function App() {
  return (
    <AppErrorBoundary>
      <Suspense fallback={
        <div className="flex min-h-screen items-center justify-center text-sm text-gray-500" role="status">
          Loading page...
        </div>
      }>
        <Routes>
          <Route path="/" element={<HomeRedirect />} />
          <Route path="/login" element={<Login />} />
          <Route path="/register" element={<Register />} />
          <Route path="/dashboard" element={<Protected><Dashboard /></Protected>} />
          <Route path="/farms" element={<Protected><MyFarms /></Protected>} />
          <Route path="/scanner" element={<Protected><CropScanner /></Protected>} />
          <Route path="/rescue" element={<Protected><RescuePlanner /></Protected>} />
          <Route path="/rescue/:scanId" element={<Protected><RescuePlanner /></Protected>} />
          <Route path="/weather" element={<Protected><Weather /></Protected>} />
          <Route path="/assistant" element={<Protected><AiAssistant /></Protected>} />
          <Route path="/treatments" element={<Protected><TreatmentTracker /></Protected>} />
          <Route path="/profile" element={<Protected><Profile /></Protected>} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </Routes>
      </Suspense>
    </AppErrorBoundary>
  )
}
