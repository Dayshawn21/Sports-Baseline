/** Copy for a request that failed before or while streaming; a server `error` frame brings its own. */
export function askErrorMessage(status: number | null): string {
  if (status === 429) return "You're asking faster than Lineform allows. Try again in a minute."
  if (status === 404 || status === 503) return 'Ask Lineform is off right now.'
  if (status === 422) return 'Ask a question of up to 500 characters.'
  if (status === null) return "Couldn't reach Lineform. Check your connection and try again."
  return 'Something went wrong answering that. Try again.'
}
