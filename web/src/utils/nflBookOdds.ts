interface NflBookOddsFields {
  projection: number | null
  bookProbability: number | null
  bookProbabilityDevigged: number | null
  bookCount: number | null
  bookIncludesMargin: boolean | null
  bookFetchedAt: string | null
}

export interface NflBookOddsEvidence {
  summary: string
  comparison: string
}

function formatAge(fetchedAt: string, now: number): string {
  const minutes = Math.max(0, Math.round((now - Date.parse(fetchedAt)) / 60_000))
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.round(minutes / 60)
  return hours < 48 ? `${hours}h ago` : `${Math.round(hours / 24)}d ago`
}

/** Sportsbook consensus beside the model, or null when no book priced the line. */
export function nflBookOddsEvidence(row: NflBookOddsFields, now: number): NflBookOddsEvidence | null {
  if (row.bookProbability === null || row.bookFetchedAt === null) return null
  const books = row.bookCount === 1 ? '1 book' : `${row.bookCount ?? 0} books`
  // Compare against the de-vigged price where there is one: the raw price
  // carries the book's margin, which makes the model look low against every
  // line rather than against the mispriced ones.
  const devigged = row.bookProbabilityDevigged
  const headline = devigged ?? row.bookProbability
  const label = devigged === null ? '' : ' de-vigged'
  const summary = `${(headline * 100).toFixed(1)}%${label} · ${books} · ${formatAge(row.bookFetchedAt, now)}`
  const note = devigged === null
    ? (row.bookIncludesMargin ? ' · includes book margin' : '')
    : ` · ${(row.bookProbability * 100).toFixed(1)}% raw`
  if (row.projection === null) return { summary, comparison: `No model baseline${note}` }
  const gap = (row.projection - headline) * 100
  return { summary, comparison: `Model ${gap > 0 ? '+' : ''}${gap.toFixed(1)} pts vs books${note}` }
}
