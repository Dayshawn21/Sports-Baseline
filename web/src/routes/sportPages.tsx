import type { ComponentType, ReactElement } from 'react'
import TennisIntelligencePage from '~/pages/TennisIntelligencePage'
import TennisPropBoardPage from '~/pages/TennisPropBoardPage'
import TennisMatchPage from '~/pages/TennisMatchPage'
import TennisModelPage from '~/pages/TennisModelPage'
import TennisPlayerPage from '~/pages/TennisPlayerPage'
import NflIntelligencePage from '~/pages/NflIntelligencePage'
import NflPropBoardPage from '~/pages/NflPropBoardPage'
import NflGamePage from '~/pages/NflGamePage'
import NflModelPage from '~/pages/NflModelPage'
import NflPlayerPage from '~/pages/NflPlayerPage'
import NbaSlatePage from '~/pages/NbaSlatePage'
import NbaGamePage from '~/pages/NbaGamePage'
import NbaModelPage from '~/pages/NbaModelPage'
import { SPORTS, sportViews, type Sport, type SportViewPaths } from '~/utils/sportNav'

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
    model: NbaModelPage,
    details: [{ path: '/nba/game/:gameId', element: <NbaGamePage /> }],
  },
}

type AnySportPages = { slate: ComponentType, props?: ComponentType, model?: ComponentType, details: SportRoute[] }

/** Every sport's view and detail routes, in registry order. */
export function sportRoutes(): SportRoute[] {
  return SPORTS.flatMap(sport => {
    const pages: AnySportPages = SPORT_PAGES[sport.code]
    const views = sportViews(sport.code).map(({ view, path }) => {
      // ViewPages pairs each promised view with its page, so the page exists.
      const Page = pages[view]!
      return { path, element: <Page /> }
    })
    return [...views, ...pages.details]
  })
}
