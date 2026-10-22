import { useSearchParams } from 'react-router-dom'
import type { MatchDetail } from '~/types/tennis'
import { useAdminView } from '~/hooks/useAdmin'
import { readMatchView, updateMatchView, type MatchView } from '~/utils/tennisMatchView'

export function useMatchView(detail: MatchDetail) {
  const [params, setParams] = useSearchParams()
  const admin = useAdminView()
  return {
    view: readMatchView(params, detail, admin),
    setView: (patch: Partial<MatchView>) => setParams(current => updateMatchView(current, patch)),
  }
}
