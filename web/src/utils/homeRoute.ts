/** The app routes by hash, so the home page is an empty hash or `#/`, with or without a query. */
export function isHomeRoute(hash: string): boolean {
  return /^#?\/?(\?.*)?$/.test(hash)
}
