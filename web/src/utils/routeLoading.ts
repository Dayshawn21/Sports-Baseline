import { sportViewForPath } from '~/utils/sportNav'

export type RouteLoadingShape = 'slate' | 'board' | 'spinner'

/** What to show while a page's code downloads: the table skeleton for slates and boards, the spinner elsewhere. */
export function routeLoadingShape(pathname: string): RouteLoadingShape {
  const view = sportViewForPath(pathname)
  if (view === 'slate') return 'slate'
  if (view === 'props') return 'board'
  return 'spinner'
}
