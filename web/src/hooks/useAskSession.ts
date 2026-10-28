import { useCallback, useEffect, useReducer, useRef } from 'react'
import { AskHttpError, streamAsk } from '~/api/ask'
import { askErrorMessage, askRetryable } from '~/utils/askError'
import { askReducer } from '~/utils/askSession'

/** The drawer's questions and answers, kept in memory only; each question is sent alone. */
export function useAskSession() {
  const [turns, dispatch] = useReducer(askReducer, [])
  const controller = useRef<AbortController | null>(null)

  const stop = useCallback(() => {
    controller.current?.abort()
    controller.current = null
    dispatch({ type: 'stop' })
  }, [])

  const send = useCallback(async (question: string) => {
    controller.current?.abort()
    const current = new AbortController()
    controller.current = current
    dispatch({ type: 'start', question })
    try {
      await streamAsk(question, { signal: current.signal, onEvent: event => dispatch({ type: 'event', event }) })
      // A stream that closed without `done` or `error` was cut off.
      if (!current.signal.aborted) dispatch({ type: 'fail', message: askErrorMessage(null) })
    } catch (error) {
      if (current.signal.aborted) return
      if (error instanceof AskHttpError) {
        dispatch({
          type: 'fail',
          message: askErrorMessage(error.status, error.detail),
          retryable: askRetryable(error.status, error.detail, error.retryAfter),
        })
      } else {
        dispatch({ type: 'fail', message: askErrorMessage(null) })
      }
    } finally {
      if (controller.current === current) controller.current = null
    }
  }, [])

  useEffect(() => () => controller.current?.abort(), [])

  const running = turns.at(-1)?.status === 'running'
  return { turns, running, send, stop }
}
