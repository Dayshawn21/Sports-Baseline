import { createContext, useContext, useId, useLayoutEffect, useReducer, type Dispatch, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import { detailTitleReducer, resolveDocumentTitle, type DetailTitleAction } from '~/utils/documentTitle'

const TitleRegistrationContext = createContext<Dispatch<DetailTitleAction> | null>(null)

/** The shell is the only owner of the browser tab title. */
export function DocumentTitleProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const [registration, dispatch] = useReducer(detailTitleReducer, null)
  const title = resolveDocumentTitle(pathname, registration)

  useLayoutEffect(() => { document.title = title }, [title])

  return <TitleRegistrationContext.Provider value={dispatch}>{children}</TitleRegistrationContext.Provider>
}

export function useRegisterDetailTitle(label: string | null): void {
  const dispatch = useContext(TitleRegistrationContext)
  const { pathname } = useLocation()
  const owner = useId()
  if (dispatch === null) throw new Error('useRegisterDetailTitle must be used within DocumentTitleProvider')

  useLayoutEffect(() => {
    dispatch({ type: 'register', registration: { pathname, label, owner } })
    return () => dispatch({ type: 'clear', owner })
  }, [dispatch, label, owner, pathname])
}
