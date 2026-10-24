import { Component } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'

export default class AppErrorBoundary extends Component {
  state = { hasError: false }

  static getDerivedStateFromError() {
    return { hasError: true }
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="flex min-h-screen items-center justify-center bg-gray-50 px-5">
          <section className="w-full max-w-md rounded-2xl border border-amber-200 bg-white p-8 text-center shadow-sm" role="alert">
            <AlertTriangle className="mx-auto mb-4 text-amber-600" size={32} />
            <h1 className="text-xl font-bold text-gray-900">This page could not load</h1>
            <p className="mt-2 text-sm text-gray-600">
              Try the page again. If the problem continues, return to the dashboard.
            </p>
            <div className="mt-6 flex justify-center gap-3">
              <button type="button" className="btn-secondary" onClick={() => window.location.reload()}>
                Reload page
              </button>
              <Link className="btn-primary" to="/dashboard">
                Dashboard
              </Link>
            </div>
          </section>
        </main>
      )
    }

    return this.props.children
  }
}
