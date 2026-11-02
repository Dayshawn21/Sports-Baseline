import type { NflSlateLine } from '~/types/nfl'

export type FormWindow = '5' | '10' | 'opp'

export const FORM_PARAM = 'form'
export const LONG_WINDOW_GAMES = 10

type FormRow = Pick<NflSlateLine, 'recentForm' | 'recentFormLong' | 'opponentHistory' | 'opponentTeam'>

export interface FormOption {
  window: FormWindow
  label: string
  /** Why the option cannot be chosen; null when it can. */
  disabledReason: string | null
}

/** Last 5 is the default and is never written to the URL. */
export function parseFormWindow(params: URLSearchParams): FormWindow {
  const value = params.get(FORM_PARAM)
  return value === '10' || value === 'opp' ? value : '5'
}

export function formOptions(row: FormRow): FormOption[] {
  return [
    { window: '5', label: 'Last 5', disabledReason: null },
    { window: '10', label: 'Last 10', disabledReason: row.recentFormLong ? null : 'Not in this slate snapshot yet' },
    { window: 'opp', label: row.opponentTeam ? `vs ${row.opponentTeam}` : 'vs Opponent', disabledReason: row.opponentTeam ? null : 'No opponent this week' },
  ]
}

/** The asked-for window, or Last 5 when the row cannot supply it. */
export function resolveFormWindow(row: FormRow, window: FormWindow): FormWindow {
  return formOptions(row).find(option => option.window === window)?.disabledReason === null ? window : '5'
}

export function formSample(row: FormRow, window: FormWindow): NflSlateLine['recentForm'] {
  const resolved = resolveFormWindow(row, window)
  if (resolved === '10') return row.recentFormLong ?? row.recentForm
  return resolved === 'opp' ? row.opponentHistory : row.recentForm
}

export function formTitle(row: FormRow, window: FormWindow): string {
  const resolved = resolveFormWindow(row, window)
  if (resolved === '10') return 'Last 10'
  return resolved === 'opp' ? `Vs ${row.opponentTeam}` : 'Recent form'
}

/** Only Last 10 can come up short of its name; the other windows already say their game count. */
export function formShortNote(row: FormRow, window: FormWindow): string | null {
  if (resolveFormWindow(row, window) !== '10') return null
  const games = formSample(row, '10').values.length
  return games > 0 && games < LONG_WINDOW_GAMES ? `${games} of ${LONG_WINDOW_GAMES} games` : null
}

export function formEmptyText(row: FormRow, window: FormWindow): string {
  return resolveFormWindow(row, window) === 'opp' ? `No earlier games against ${row.opponentTeam} since 2024.` : 'No completed history'
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

export interface FormDate {
  month: string
  day: number
  /** Two-digit calendar year, only when the game is from an earlier NFL season than the current one (a January game belongs to the season that began the year before). */
  year: string | null
}

/** A game date as shown under a bar; null for a missing or malformed date. The string is read as written, so no timezone shifts it. */
export function formHistoryDate(date: string | null | undefined, now: Date): FormDate | null {
  const match = date ? /^(\d{4})-(\d{2})-(\d{2})$/.exec(date) : null
  if (!match) return null
  const month = MONTHS[Number(match[2]) - 1]
  if (!month) return null
  const season = (year: number, monthIndex: number) => (monthIndex < 2 ? year - 1 : year)
  const sameSeason = season(Number(match[1]), Number(match[2]) - 1) === season(now.getFullYear(), now.getMonth())
  return { month, day: Number(match[3]), year: sameSeason ? null : `'${match[1].slice(2)}` }
}

export function formDateText(date: FormDate | null): string | null {
  return date ? `${date.month} ${date.day}${date.year ? ` ${date.year}` : ''}` : null
}
