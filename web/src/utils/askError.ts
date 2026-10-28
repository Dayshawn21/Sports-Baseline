/** Copy for a request that failed before or while streaming; a server `error` frame brings its own. */
export function askErrorMessage(status: number | null, detail: string | null = null): string {
  // The API's 429 and 503 details are fixed copy (daily limit, spending cap, per-minute limit).
  if ((status === 429 || status === 503) && detail) return detail
  if (status === 429) return "You're asking faster than Lineform allows. Try again in a minute."
  if (status === 404 || status === 503) return 'Ask Lineform is off right now.'
  if (status === 422) return 'Ask a question of up to 500 characters.'
  if (status === null) return "Couldn't reach Lineform. Check your connection and try again."
  return 'Something went wrong answering that. Try again.'
}

/** The per-minute limit's wait is at most a minute; the daily limit's is hours. */
const LONGEST_SHORT_WAIT_SECONDS = 60

/**
 * Whether sending the same question again could work soon. Not for Ask being
 * off, a rejected question, the daily limit or a 503 the API explained (the
 * spending cap or no key); yes for network failures, server errors and a 503
 * from a proxy with no API detail.
 */
export function askRetryable(status: number | null, detail: string | null = null, retryAfter: number | null = null): boolean {
  if (status === 404 || status === 422) return false
  if (status === 429) return retryAfter === null || retryAfter <= LONGEST_SHORT_WAIT_SECONDS
  if (status === 503) return !detail
  return true
}
