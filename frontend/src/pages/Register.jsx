import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import FarmGuardianMark from '../components/FarmGuardianMark'
import { AlertCircle, Eye, EyeOff, ArrowRight } from 'lucide-react'

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({ name: '', email: '', password: '', phone: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [showPw, setShowPw] = useState(false)

  const update = (k) => (e) => setForm({ ...form, [k]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await register(form.name, form.email, form.password, form.phone || undefined)
    if (result.success) {
      navigate('/dashboard')
    } else {
      setError(result.error || 'Registration failed.')
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

          <h2 className="login-title">Create your account</h2>
          <p className="login-subtitle">Start protecting your farm with AI</p>

          {error && (
            <div className="login-error">
              <AlertCircle style={{ width: 16, height: 16, flexShrink: 0, marginTop: 1 }} />
              <span>{error}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="login-form">
            <div className="login-field">
              <label className="login-label" htmlFor="reg-name">Full name</label>
              <input
                id="reg-name"
                required
                className="farm-input"
                value={form.name}
                onChange={update('name')}
                placeholder="Farmer name"
                autoComplete="name"
              />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="reg-email">Email address</label>
              <input
                id="reg-email"
                type="email"
                required
                className="farm-input"
                value={form.email}
                onChange={update('email')}
                placeholder="you@farm.com"
                autoComplete="email"
              />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="reg-phone">Phone (optional)</label>
              <input
                id="reg-phone"
                className="farm-input"
                value={form.phone}
                onChange={update('phone')}
                placeholder="+91 98765 43210"
                autoComplete="tel"
              />
            </div>
            <div className="login-field">
              <label className="login-label" htmlFor="reg-password">Password</label>
              <div className="login-password-wrap">
                <input
                  id="reg-password"
                  type={showPw ? 'text' : 'password'}
                  required
                  minLength={6}
                  className="farm-input"
                  value={form.password}
                  onChange={update('password')}
                  placeholder="At least 6 characters"
                  autoComplete="new-password"
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
                  Creating account…
                </>
              ) : (
                <>
                  Create account
                  <ArrowRight style={{ width: 18, height: 18 }} />
                </>
              )}
            </button>
          </form>

          <p className="login-footer-text">
            Already have an account? <Link to="/login" className="login-link">Sign in</Link>
          </p>
        </div>
      </div>
    </div>
  )
}
