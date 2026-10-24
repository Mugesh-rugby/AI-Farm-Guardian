import React from 'react'

export default function EmptyState({ icon: Icon, title, message, action }) {
  return (
    <div className="empty-state bg-white rounded-2xl border border-dashed border-farm-200">
      {Icon && (
        <div className="w-14 h-14 rounded-full bg-farm-100 flex items-center justify-center mb-3">
          <Icon className="w-6 h-6 text-farm-600" />
        </div>
      )}
      <p className="font-semibold text-earth-800">{title}</p>
      {message && <p className="text-sm mt-1 max-w-sm">{message}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}
