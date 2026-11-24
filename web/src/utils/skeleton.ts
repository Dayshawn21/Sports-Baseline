export const SKELETON_MIN_WIDTH = 40
export const SKELETON_MAX_WIDTH = 90

/** Bar widths (percent of the cell) per row and column: varied so the rows read as text, fixed so renders match. */
export function skeletonWidths(rows: number, columns: number): number[][] {
  if (rows <= 0 || columns <= 0) return []
  const span = SKELETON_MAX_WIDTH - SKELETON_MIN_WIDTH + 1
  return Array.from({ length: rows }, (_, row) =>
    Array.from({ length: columns }, (_, column) => SKELETON_MIN_WIDTH + ((row * 37 + column * 23 + row * column * 11) % span)),
  )
}
