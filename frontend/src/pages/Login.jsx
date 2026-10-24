import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import FarmGuardianMark from '../components/FarmGuardianMark'
import { AlertCircle, Eye, EyeOff, ArrowRight } from 'lucide-react'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPw, setShowPw] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await login(email, password)
    if (result.success) {
      navigate('/dashboard')
    } else {
      setError(result.error || 'Login failed. Check your credentials.')
    }
    setLoading(false)
  }

  return (
    <div className="login-page login-page-centered">
      <div className="login-form-panel">
        <div className="login-form-container">
          <div className="login-mobile-logo">
            <FarmGuardianMark className="h-10 w-10 rounded-xl" iconClassName="h-5 w-5" />
            <span className="login-mobile-brand">AI Farm Guardian</span>
          </div>

          <h2 className="login-title">Welcome back</h2>
          <p className="login-subtitle">Sign in to access your farm dashboard</p>

          {error && (
            <div className="login-error">
              <AlertCircle style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label className="login-label" htmlFor="login-email">Email address</label>
              <input
                id="login-email"
                type="email"
                required
                className="farm-input"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@farm.com"
                autoComplete="email"
              />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="login-password">Password</label>
              <div className="login-password-wrap">
                <input
                  id="login-password"
                  type={showPw ? 'text' : 'password'}
                  required
                  className="farm-input"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  className="login-pw-toggle"
                  onClick={() => setShowPw(!showPw)}
                  tabIndex={-1}
                  aria-label={showPw ? 'Hide password' : 'Show password'}
                >
                  {showPw
                    ? <EyeOff style={{ width: 18, height: 18 }} />
                    : <Eye style={{ width: 18, height: 18 }} />
                  }
                </button>
              </div>
            </div>

            <button type="submit" disabled={loading} className="btn-primary login-submit">
              {loading ? (
                <>
                  <span className="spinner" style={{ width: 18, height: 18 }} />
                  Signing in…
                </>
              ) : (
                <>
                  Sign in
                  <ArrowRight style={{ width: 18, height: 18 }} />
                </>
              )}
            </button>
          </form>

          <p className="login-footer-text">
            Don't have an account? <Link to="/register" className="login-link">Create account</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
