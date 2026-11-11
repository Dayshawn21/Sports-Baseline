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
  /** The kinds of detail page under the prefix (`/nfl/game/:id`); any other path there is not a page. */
  details: readonly string[]
}

/** The sport registry: one entry per sport drives the top bar, the phone drawer and (with `SPORT_PAGES`) the routes. */
export const SPORTS = [
  { code: 'tennis', label: 'Tennis', prefix: '/tennis/', views: { slate: '/tennis', props: '/tennis/props', model: '/tennis/model' }, details: ['match', 'player'] },
  { code: 'nfl', label: 'NFL', prefix: '/nfl/', views: { slate: '/nfl', props: '/nfl/props', model: '/nfl/model' }, details: ['game', 'player'] },
  { code: 'nba', label: 'NBA', prefix: '/nba/', views: { slate: '/nba', props: '/nba/props', model: '/nba/model' }, details: ['game', 'player'] },
  { code: 'nhl', label: 'NHL', prefix: '/nhl/', views: { slate: '/nhl', props: '/nhl/props', model: '/nhl/model' }, details: ['game', 'player'] },
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

export const HOME_PATH = '/'
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

/** The sport code a path belongs to, as `activeSport` reads it; null outside every sport. */
export function sportForPath(pathname: string): Sport | null {
  const code = activeSport(pathname)?.code
  return SPORTS.find(sport => sport.code === code)?.code ?? null
}

export interface ShellSportTab { code: Sport, label: string, path: string, active: boolean }
export interface ShellViewTab { view: SportView, label: string, path: string, active: boolean }
export interface ShellLink { key: string, label: string, active: boolean }
export interface ShellHomeTab { label: string, path: string, active: boolean }
export interface ShellNav { home: ShellHomeTab, sports: ShellSportTab[], views: ShellViewTab[], links: ShellLink[] }

/**
 * Where a sport tab goes: the view being read (or the last one, off a view page) carries over, so
 * NFL Props to NBA is one click. The active sport follows the same rule, so its own tab never
 * throws the view away; the Slate tab (or `S`) is the way back to the slate.
 */
function sportTabPath(sport: SportDefinition, view: SportView | null): string {
  return (view && sport.views[view]) ?? sport.views.slate
}

/** Everything the top bar shows for a path: sport tabs, the active sport's views, and the other links. */
export function shellNav(pathname: string, adminVisible: boolean, lastView: SportView | null = null): ShellNav {
  const sport = activeSport(pathname)
  const view = sportViewForPath(pathname)
  const carriedView = view ?? lastView
  return {
    home: { label: 'Home', path: HOME_PATH, active: pathname === HOME_PATH },
    sports: SPORTS.map(entry => {
      const active = entry.code === sport?.code
      return { code: entry.code, label: entry.label, path: sportTabPath(entry, carriedView), active }
    }),
    views: sport
      ? viewsOf(sport).map(entry => ({ ...entry, label: VIEW_LABELS[entry.view], active: entry.view === view }))
      : [],
    links: visibleNavItems(EXTRA_LINKS, adminVisible).map(link => ({ ...link, active: link.key === pathname })),
  }
}

/** The phone menu holds only what the sport picker and views row do not: Home and the closing links. */
export function phoneMenuItems(adminVisible: boolean): { key: string, label: string }[] {
  return [{ key: HOME_PATH, label: 'Home' }, ...visibleNavItems(EXTRA_LINKS, adminVisible)]
}

/** The browser tab title: the sport and view or detail kind (`NFL game`), then the app name. */
export function documentTitle(pathname: string): string {
  const sport = activeSport(pathname)
  const view = sportViewForPath(pathname)
  const extra = EXTRA_LINKS.find(link => link.key === pathname)
  const detail = sport && !view ? pathname.slice(sport.prefix.length).split('/')[0] : ''
  const page = extra?.label
    ?? (sport && view ? `${sport.label} ${view}` : null)
    ?? (sport && sport.details.includes(detail) ? `${sport.label} ${detail}` : null)
  return page ? `${page} · ${APP_NAME}` : APP_NAME
}
