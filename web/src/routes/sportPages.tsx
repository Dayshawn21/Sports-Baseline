import { lazy, type ComponentType, type ReactElement } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { SPORTS, sportViews, type Sport, type SportViewPaths } from '~/utils/sportNav'

const TennisIntelligencePage = lazy(() => import('~/pages/TennisIntelligencePage'))
const TennisPropBoardPage = lazy(() => import('~/pages/TennisPropBoardPage'))
const TennisMatchPage = lazy(() => import('~/pages/TennisMatchPage'))
const TennisModelPage = lazy(() => import('~/pages/TennisModelPage'))
const TennisPlayerPage = lazy(() => import('~/pages/TennisPlayerPage'))
const NflIntelligencePage = lazy(() => import('~/pages/NflIntelligencePage'))
const NflPropBoardPage = lazy(() => import('~/pages/NflPropBoardPage'))
const NflGamePage = lazy(() => import('~/pages/NflGamePage'))
const NflModelPage = lazy(() => import('~/pages/NflModelPage'))
const NflPlayerPage = lazy(() => import('~/pages/NflPlayerPage'))
const NbaSlatePage = lazy(() => import('~/pages/NbaSlatePage'))
const NbaGamePage = lazy(() => import('~/pages/NbaGamePage'))
const NbaPlayerPage = lazy(() => import('~/pages/NbaPlayerPage'))
const NbaModelPage = lazy(() => import('~/pages/NbaModelPage'))
const NbaPropBoardPage = lazy(() => import('~/pages/NbaPropBoardPage'))
const NhlSlatePage = lazy(() => import('~/pages/NhlSlatePage'))
const NhlGamePage = lazy(() => import('~/pages/NhlGamePage'))
const NhlPlayerPage = lazy(() => import('~/pages/NhlPlayerPage'))
const NhlPropBoardPage = lazy(() => import('~/pages/NhlPropBoardPage'))
const NhlModelPage = lazy(() => import('~/pages/NhlModelPage'))

/** A detail page path sits under its sport's prefix, so the nav highlights the sport. */
interface SportRoute {
  path: string
  element: ReactElement
}

type SportViewsOf<S extends Sport> = Extract<typeof SPORTS[number], { code: S }>['views']

type OptionalView = 'props' | 'model'

/** A page for each optional view exactly when the views promise one. */
type OptionalPages<V extends SportViewPaths> = {
  [K in OptionalView as V extends Record<K, string> ? K : never]: ComponentType
} & {
  [K in OptionalView as V extends Record<K, string> ? never : K]?: never
}

/** The pages for a set of views: always a slate, plus a Props or Model page exactly when promised. */
export type ViewPages<V extends SportViewPaths> = { slate: ComponentType, details: SportRoute[] } & OptionalPages<V>

type SportPages<S extends Sport> = ViewPages<SportViewsOf<S>>

export const SPORT_PAGES: { [S in Sport]: SportPages<S> } = {
  tennis: {
    slate: TennisIntelligencePage,
    props: TennisPropBoardPage,
    model: TennisModelPage,
    details: [
      { path: '/tennis/match/:matchId', element: <TennisMatchPage /> },
      { path: '/tennis/player/:playerId', element: <TennisPlayerPage /> },
    ],
  },
  nfl: {
    slate: NflIntelligencePage,
    props: NflPropBoardPage,
    model: NflModelPage,
    details: [
      { path: '/nfl/game/:gameId', element: <NflGamePage /> },
      { path: '/nfl/player/:playerId', element: <NflPlayerPage /> },
    ],
  },
  nba: {
    slate: NbaSlatePage,
    props: NbaPropBoardPage,
    model: NbaModelPage,
    details: [
      { path: '/nba/game/:gameId', element: <NbaGamePage /> },
      { path: '/nba/player/:playerId', element: <NbaPlayerPage /> },
    ],
  },
  nhl: {
    slate: NhlSlatePage,
    props: NhlPropBoardPage,
    model: NhlModelPage,
    details: [
      { path: '/nhl/game/:gameId', element: <NhlGamePage /> },
      { path: '/nhl/player/:playerId', element: <NhlPlayerPage /> },
    ],
  },
}

type AnySportPages = { slate: ComponentType, props?: ComponentType, model?: ComponentType, details: SportRoute[] }

/** Props boards lived at `/<sport>/board`; old links and bookmarks land on the board, filters intact. */
function LegacyBoardRedirect({ to }: { to: string }) {
  const { search } = useLocation()
  return <Navigate to={`${to}${search}`} replace />
}

/** Every sport's view and detail routes, in registry order. */
export function sportRoutes(): SportRoute[] {
  return SPORTS.flatMap(sport => {
    const pages: AnySportPages = SPORT_PAGES[sport.code]
    const views = sportViews(sport.code).map(({ view, path }) => {
      // ViewPages pairs each promised view with its page, so the page exists.
      const Page = pages[view]!
      return { path, element: <Page /> }
    })
    const legacy = sport.views.props
      ? [{ path: `/${sport.code}/board`, element: <LegacyBoardRedirect to={sport.views.props} /> }]
      : []
    return [...views, ...legacy, ...pages.details]
  })
}
