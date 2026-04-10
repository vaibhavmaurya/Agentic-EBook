import axios from 'axios'
import { useAuthStore } from '../store/authStore'

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? ''

export const apiClient = axios.create({ baseURL: BASE_URL })

// Attach JWT to every request
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// On 401, attempt token refresh once then redirect to login
apiClient.interceptors.response.use(
  (res) => res,
  async (err) => {
    if (err.response?.status === 401) {
      const newToken = await useAuthStore.getState().refreshToken()
      if (newToken) {
        err.config.headers.Authorization = `Bearer ${newToken}`
        return apiClient.request(err.config)
      }
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)
