/** Enough rows to fill a tall desktop viewport; F-77 measured about 110 ms of first-render work at this size. */
export const FIRST_ROW_BATCH = 25
/** Each later batch is about 20-25 ms of render and layout on a fast desktop. */
export const NEXT_ROW_BATCH = 25

/** How many of `total` rows to render once `batches` follow-up batches have landed. */
export function rowBatchLimit(total: number, batches: number, first = FIRST_ROW_BATCH, step = NEXT_ROW_BATCH): number {
  return Math.max(0, Math.min(total, first + Math.max(0, batches) * step))
}

/** The batch count after the next step. A hidden page runs no frames, so it takes every remaining row at once: nobody sees that task. */
export function nextBatchCount(count: number, hidden: boolean): number {
  return hidden ? Number.POSITIVE_INFINITY : count + 1
}

/** Splits one limit across two tables shown in order, the first table filling before the second starts. */
export function splitRowLimit(limit: number, firstCount: number): [number, number] {
  const first = Math.min(limit, firstCount)
  return [first, Math.max(0, limit - first)]
}
