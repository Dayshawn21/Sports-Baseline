import { documentTitle } from '~/utils/sportNav'

export interface DetailTitleRegistration {
  pathname: string
  label: string | null
  owner: string
}

export type DetailTitleAction =
  | { type: 'register', registration: DetailTitleRegistration }
  | { type: 'clear', owner: string }

export function detailTitleReducer(state: DetailTitleRegistration | null, action: DetailTitleAction): DetailTitleRegistration | null {
  if (action.type === 'register') return action.registration
  return state?.owner === action.owner ? null : state
}

/** A page may name only its current route; navigation immediately uses the fallback. */
export function resolveDocumentTitle(pathname: string, registration: DetailTitleRegistration | null): string {
  const fallback = documentTitle(pathname)
  const label = registration?.pathname === pathname ? registration.label?.trim() : null
  return label ? `${label} - ${fallback}` : fallback
}
