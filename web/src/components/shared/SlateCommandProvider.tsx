import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, type ReactNode } from 'react'
import { useLocation } from 'react-router-dom'
import type { SlateCommandScope } from '~/types/slateCommand'
import { initialSlateCommandState, slateCommandReducer } from '~/utils/slateCommand'

interface SlateCommandContextValue {
  query: string
  scope: SlateCommandScope | null
  setQuery: (query: string) => void
  clearQuery: () => void
  registerScope: (scope: SlateCommandScope | null) => void
}

const SlateCommandContext = createContext<SlateCommandContextValue | null>(null)

export function SlateCommandProvider({ children }: { children: ReactNode }) {
  const { pathname } = useLocation()
  const [state, dispatch] = useReducer(slateCommandReducer, pathname, initialSlateCommandState)

  useEffect(() => dispatch({ type: 'route', routeKey: pathname }), [pathname])

  const setQuery = useCallback((query: string) => dispatch({ type: 'query', query }), [])
  const clearQuery = useCallback(() => dispatch({ type: 'clear' }), [])
  const registerScope = useCallback((scope: SlateCommandScope | null) => {
    dispatch({ type: 'register', routeKey: pathname, scope })
  }, [pathname])

  const active = state.routeKey === pathname
  const value = useMemo<SlateCommandContextValue>(() => ({
    query: active ? state.query : '',
    scope: active ? state.scope : null,
    setQuery,
    clearQuery,
    registerScope,
  }), [active, clearQuery, registerScope, setQuery, state.query, state.scope])

  return <SlateCommandContext.Provider value={value}>{children}</SlateCommandContext.Provider>
}

export function useSlateCommand(): SlateCommandContextValue {
  const value = useContext(SlateCommandContext)
  if (value === null) throw new Error('useSlateCommand must be used within SlateCommandProvider')
  return value
}

/** Register page-owned rows. Passing null makes the command unavailable without loading anything. */
export function useRegisterSlateCommand(scope: SlateCommandScope | null): void {
  const { registerScope } = useSlateCommand()
  useEffect(() => registerScope(scope), [registerScope, scope])
}
