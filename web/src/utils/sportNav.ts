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

/** The sport registry: one entry per sport drives the top bar, the phone drawer and (with `SPORT_PAGES`) the routes. */
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
  return viewsOf(sportDefinition(sport))
}

function viewsOf(definition: SportDefinition): { view: SportView, path: string }[] {
  const views: SportViewPaths = definition.views
  return SPORT_VIEWS.flatMap(view => {
    const path = views[view]
    return path ? [{ view, path }] : []
  })
}

const ADMIN_PATH = '/admin'
const APP_NAME = 'Lineform'

const EXTRA_LINKS = [
  { key: '/how-it-works', label: 'How it works' },
  { key: ADMIN_PATH, label: 'Admin' },
]

export const VIEW_LABELS: Record<SportView, string> = { slate: 'Slate', props: 'Props', model: 'Model' }

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

export function sportViewForPath(pathname: string): SportView | null {
  return sportViewEntry(pathname)?.view ?? null
}

/** The sport a path belongs to: one of its views or a detail page under its prefix; null elsewhere. */
function activeSport(pathname: string): SportDefinition | null {
  return sportViewEntry(pathname)?.sport ?? SPORTS.find(sport => pathname.startsWith(sport.prefix)) ?? null
}

export interface ShellSportTab { code: Sport, label: string, path: string, active: boolean }
export interface ShellViewTab { view: SportView, label: string, path: string, active: boolean }
export interface ShellLink { key: string, label: string, active: boolean }
export interface ShellNav { sports: ShellSportTab[], views: ShellViewTab[], links: ShellLink[] }

/** Everything the top bar shows for a path: sport tabs, the active sport's views, and the other links. */
export function shellNav(pathname: string, adminVisible: boolean): ShellNav {
  const sport = activeSport(pathname)
  const view = sportViewForPath(pathname)
  return {
    sports: SPORTS.map(entry => ({ code: entry.code, label: entry.label, path: entry.views.slate, active: entry.code === sport?.code })),
    views: sport
      ? viewsOf(sport).map(entry => ({ ...entry, label: VIEW_LABELS[entry.view], active: entry.view === view }))
      : [],
    links: visibleNavItems(EXTRA_LINKS, adminVisible).map(link => ({ ...link, active: link.key === pathname })),
  }
}

export interface MenuSection { label: string | null, items: { key: string, label: string }[] }

/** The phone drawer: every sport with its views nested under it, then the other links in an unlabeled section. */
export function menuSections(adminVisible: boolean): MenuSection[] {
  return [
    ...SPORTS.map(sport => ({ label: sport.label, items: viewsOf(sport).map(entry => ({ key: entry.path, label: VIEW_LABELS[entry.view] })) })),
    { label: null, items: visibleNavItems(EXTRA_LINKS, adminVisible) },
  ]
}

/** The browser tab title: the sport and view or detail kind (`NFL game`), then the app name. */
export function documentTitle(pathname: string): string {
  const sport = activeSport(pathname)
  const view = sportViewForPath(pathname)
  const extra = EXTRA_LINKS.find(link => link.key === pathname)
  const detail = sport && !view ? pathname.slice(sport.prefix.length).split('/')[0] : ''
  const page = extra?.label
    ?? (sport && view ? `${sport.label} ${view}` : null)
    ?? (sport && /^[a-z]+$/.test(detail) ? `${sport.label} ${detail}` : null)
  return page ? `${page} · ${APP_NAME}` : APP_NAME
}
