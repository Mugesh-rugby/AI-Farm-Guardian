import React from 'react'
import { PlugZap } from 'lucide-react'

export default function ConnectApiState({ title, reason, envVar }) {
  return (
    <div className="empty-state bg-white rounded-2xl border border-dashed border-farm-200">
      <div className="w-14 h-14 rounded-full bg-farm-100 flex items-center justify-center mb-3">
        <PlugZap className="w-6 h-6 text-farm-600" />
      </div>
      <p className="font-semibold text-earth-800">{title || 'API not connected'}</p>
      <p className="text-sm mt-1 max-w-sm">
        {reason || 'This feature needs a live API key to return real data.'}
      </p>
      {envVar && (
        <p className="text-xs mt-3 bg-farm-50 border border-farm-100 rounded-lg px-3 py-1.5 font-mono">
          Set <strong>{envVar}</strong> in backend/.env
        </p>
      )}
    </div>
  )
}
