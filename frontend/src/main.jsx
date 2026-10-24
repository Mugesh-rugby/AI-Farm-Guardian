import React from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { Toaster } from 'react-hot-toast'
import { AuthProvider } from './context/AuthContext.jsx'
import { FarmProvider } from './context/FarmContext.jsx'
import App from './App.jsx'
import './index.css'

const root = createRoot(document.getElementById('app'))
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <FarmProvider>
          <App />
          <Toaster position="top-right" toastOptions={{ duration: 3000 }} />
        </FarmProvider>
      </AuthProvider>
    </BrowserRouter>
  </React.StrictMode>
)
