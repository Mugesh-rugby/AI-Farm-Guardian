import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 15000,
  withCredentials: true,
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    const isAuthRoute = ['/auth/login', '/auth/register', '/auth/me'].some((path) =>
      error.config?.url?.includes(path)
    )
    if (error.response?.status === 401 && !isAuthRoute) {
      if (!['/login', '/register'].includes(window.location.pathname)) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api
