import { useEffect, useState } from 'react'
import { sportViewForPath, type SportView } from '~/utils/sportNav'

/** The last sport view visited this session, so sport tabs on Home or a game page keep it. */
export function useLastSportView(pathname: string): SportView | null {
  const [lastView, setLastView] = useState<SportView | null>(() => sportViewForPath(pathname))
  useEffect(() => {
    const view = sportViewForPath(pathname)
    if (view) setLastView(view)
  }, [pathname])
  return lastView
}
