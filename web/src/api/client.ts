import axios from 'axios'
import { adminKeyHeaders, isAdminRejection, sessionAdminKey } from '~/utils/adminAuth'
import { resolveApiBaseUrl } from '~/utils/apiBase'

const client = axios.create({
  baseURL: resolveApiBaseUrl(import.meta.env.VITE_API_BASE_URL),
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
})

client.interceptors.request.use(config => {
  config.headers.set(adminKeyHeaders(config.url, sessionAdminKey.read()))
  return config
})

client.interceptors.response.use(undefined, (error: unknown) => {
  if (axios.isAxiosError(error) && isAdminRejection(error.config?.url, error.response?.status)) {
    sessionAdminKey.clear()
  }
  return Promise.reject(error)
})

export default client
