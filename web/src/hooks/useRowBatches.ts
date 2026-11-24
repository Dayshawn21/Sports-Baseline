import { useEffect, useState } from 'react'
import { nextBatchCount, rowBatchLimit } from '~/utils/rowBatches'

/**
 * How many of `total` rows to render now. The first batch commits with the page, then one more
 * batch lands after each paint, so one long task becomes several short ones (F-77).
 */
export function useRowBatches(total: number): number {
  const [batches, setBatches] = useState(0)
  const limit = rowBatchLimit(total, batches)
  useEffect(() => {
    if (limit >= total) return
    let timer: number | undefined
    // The frame callback runs before paint; the timeout queues the next batch after it.
    const next = () => { timer = window.setTimeout(() => setBatches(count => nextBatchCount(count, document.hidden)), 0) }
    const frame = document.hidden ? undefined : requestAnimationFrame(next)
    if (frame === undefined) next()
    return () => {
      if (frame !== undefined) cancelAnimationFrame(frame)
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [limit, total])
  return limit
}
