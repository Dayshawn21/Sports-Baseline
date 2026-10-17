import { isAxiosError } from 'axios'

export function isNotFound(error: unknown): boolean {
  return isAxiosError(error) && error.response?.status === 404
}

/** Retry transient failures as the app default does, but never a 404: it will not appear on retry. */
export function retryUnlessNotFound(failureCount: number, error: unknown): boolean {
  return !isNotFound(error) && failureCount < 2
}

export function httpStatus(error: unknown): number | undefined {
  return isAxiosError(error) ? error.response?.status : undefined
}

/** Seconds from a 429's Retry-After header, or null when it is missing or not a number. */
export function retryAfterSeconds(error: unknown): number | null {
  if (!isAxiosError(error)) return null
  const raw: unknown = error.response?.headers?.['retry-after']
  const seconds = Number(raw)
  return raw != null && raw !== '' && Number.isFinite(seconds) && seconds >= 0 ? Math.ceil(seconds) : null
}

/** A rejected key or a rate limit will not change on retry; retry anything else twice. */
export function retryUnlessAuthOrLimited(failureCount: number, error: unknown): boolean {
  const status = httpStatus(error)
  return status !== 401 && status !== 429 && failureCount < 2
}
