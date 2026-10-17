export type SportView = 'slate' | 'props' | 'model'

export const SPORT_VIEWS: SportView[] = ['slate', 'props', 'model']

/** Every sport has a slate; Props comes with a prop board and Model with a graded track record page. */
export type SportViewPaths = { slate: string, props?: string, model?: string }

interface SportDefinition {
  code: string
  label: string
  /** Detail pages (a match, a game, a player) sit under this prefix, so the nav highlights their sport. */
  prefix: string
  views: SportViewPaths
}

/** The sport registry: one entry per sport drives the nav, the view switch and (with `SPORT_PAGES`) the routes. */
export const SPORTS = [
  { code: 'tennis', label: 'Tennis', prefix: '/tennis/', views: { slate: '/', props: '/tennis/board', model: '/tennis/model' } },
  { code: 'nfl', label: 'NFL', prefix: '/nfl/', views: { slate: '/nfl', props: '/nfl/board', model: '/nfl/model' } },
  { code: 'nba', label: 'NBA', prefix: '/nba/', views: { slate: '/nba', model: '/nba/model' } },
] as const satisfies readonly SportDefinition[]

export type Sport = typeof SPORTS[number]['code']

function sportDefinition(sport: Sport): SportDefinition {
  return SPORTS.find(entry => entry.code === sport)!
}

export function sportViews(sport: Sport): { view: SportView, path: string }[] {
  const views: SportViewPaths = sportDefinition(sport).views
  return SPORT_VIEWS.flatMap(view => {
    const path = views[view]
    return path ? [{ view, path }] : []
  })
}

const ADMIN_PATH = '/admin'

export const NAV_ITEMS = [
  ...SPORTS.map(sport => ({ key: sport.views.slate, label: sport.label })),
  { key: '/how-it-works', label: 'How it works' },
  { key: ADMIN_PATH, label: 'Admin' },
]

/** Visitors never see the Admin entry; the owner sees it once signed in, and always in dev. */
export function visibleNavItems<T extends { key: string }>(items: T[], adminVisible: boolean): T[] {
  return adminVisible ? items : items.filter(item => item.key !== ADMIN_PATH)
}

function sportViewEntry(pathname: string): { sport: SportDefinition, view: SportView } | null {
  for (const sport of SPORTS) {
    const match = sportViews(sport.code).find(entry => entry.path === pathname)
    if (match) return { sport, view: match.view }
  }
  return null
}

/** The nav entry to highlight; a sport's slate path covers all of its views and detail pages. */
export function navKeyForPath(pathname: string): string {
  const entry = sportViewEntry(pathname)
  if (entry) return entry.sport.views.slate
  const sport = SPORTS.find(definition => pathname.startsWith(definition.prefix))
  if (sport) return sport.views.slate
  return NAV_ITEMS.some(item => item.key === pathname) ? pathname : '/'
}

export function sportViewForPath(pathname: string): SportView | null {
  return sportViewEntry(pathname)?.view ?? null
}
