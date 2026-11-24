import type { SlateCommandRow, SlateCommandScope, SlateCommandTarget } from '~/types/slateCommand'
import { type Sport, sportForPath, sportViewForPath } from '~/utils/sportNav'

const EVENT_NOUN: Record<Sport, string> = { tennis: 'match', nfl: 'game', nba: 'game', nhl: 'game' }

/** The search field's hint, in the page's own noun: a tennis "match", a team sport's "game". NHL search has no players. */
export function slateCommandPlaceholder(pathname: string, ready: boolean): string {
  if (!ready) return 'Slate search loading...'
  const sport = sportForPath(pathname)
  if (sport === 'nhl') return 'Search teams or games...'
  const noun = sport === null ? 'game' : EVENT_NOUN[sport]
  return sportViewForPath(pathname) === 'slate' ? `Jump to a ${noun} or player...` : `Jump to another ${noun} or player...`
}

export interface SlateCommandState {
  routeKey: string
  query: string
  scope: SlateCommandScope | null
}

export type SlateCommandAction =
  | { type: 'route'; routeKey: string }
  | { type: 'register'; routeKey: string; scope: SlateCommandScope | null }
  | { type: 'query'; query: string }
  | { type: 'clear' }

export function normalizeSlateCommand(value: string): string {
  return value.trim().replace(/\s+/g, ' ').toLowerCase()
}

function tokens(query: string): string[] {
  const normalized = normalizeSlateCommand(query)
  return normalized ? normalized.split(' ') : []
}

function includesEveryToken(value: string, queryTokens: readonly string[]): boolean {
  return queryTokens.every(token => value.includes(token))
}

const EXACT_LABEL = 0
const WHOLE_WORDS = 1
const WORD_PREFIXES = 2
const SUBSTRINGS = 3

function words(value: string): string[] {
  return value.split(/[^\p{L}\p{N}]+/u).filter(Boolean)
}

/** How directly a target answers the query: "KC" is the Chiefs' exact code, but only a word in "KC Concepcion". */
function targetScore(target: SlateCommandTarget, query: string, queryTokens: readonly string[]): number {
  if (normalizeSlateCommand(target.label) === query) return EXACT_LABEL
  const targetWords = words(target.searchText)
  if (queryTokens.every(token => targetWords.includes(token))) return WHOLE_WORDS
  if (queryTokens.every(token => targetWords.some(word => word.startsWith(token)))) return WORD_PREFIXES
  return SUBSTRINGS
}

// A player is the most specific answer to a name, then a team; a game is what both belong to.
const KIND_ORDER: Record<SlateCommandTarget['kind'], number> = { player: 0, team: 1, game: 2, match: 2 }

interface RankedTarget {
  target: SlateCommandTarget
  score: number
  row: number
  index: number
}

/**
 * Every target that matches the query by its own name, best first: by how directly it matches, then player, team,
 * game, then slate order. A game or match that matched only through a player or across targets follows once, after
 * them, so "allen" lists the Allens before their games.
 */
function rankedSlateCommandTargets(rows: readonly SlateCommandRow[], query: string): SlateCommandTarget[] {
  const queryTokens = tokens(query)
  if (queryTokens.length === 0) return []
  const normalized = normalizeSlateCommand(query)
  const direct: RankedTarget[] = []
  const parents: SlateCommandTarget[] = []
  matchingSlateCommandRows(rows, query).forEach((row, rowIndex) => {
    const hits = row.targets.filter(target => includesEveryToken(target.searchText, queryTokens))
    hits.forEach((target, index) => direct.push({ target, score: targetScore(target, normalized, queryTokens), row: rowIndex, index }))
    const parent = row.targets[0]
    if (parent && !hits.includes(parent)) parents.push(parent)
  })
  direct.sort((left, right) => left.score - right.score
    || KIND_ORDER[left.target.kind] - KIND_ORDER[right.target.kind]
    || left.row - right.row || left.index - right.index)
  return [...direct.map(ranked => ranked.target), ...parents]
}

/** Filter without sorting, so the slate's existing row order remains authoritative. */
export function matchingSlateCommandRows(rows: readonly SlateCommandRow[], query: string): SlateCommandRow[] {
  const queryTokens = tokens(query)
  if (queryTokens.length === 0) return [...rows]
  return rows.filter(row => includesEveryToken(row.searchText, queryTokens))
}

/** Matching jump targets, direct name hits first; see `rankedSlateCommandTargets`. */
export function matchingSlateCommandTargets(rows: readonly SlateCommandRow[], query: string): SlateCommandTarget[] {
  return rankedSlateCommandTargets(rows, query)
}

/** Enter opens the top result, the same one the list shows first. */
export function firstSlateCommandPath(rows: readonly SlateCommandRow[], query: string): string | null {
  return rankedSlateCommandTargets(rows, query)[0]?.path ?? null
}

export function initialSlateCommandState(routeKey: string): SlateCommandState {
  return { routeKey, query: '', scope: null }
}

function sameScope(left: SlateCommandScope | null, right: SlateCommandScope | null): boolean {
  if (left === right) return true
  if (!left || !right || left.periodKey !== right.periodKey || left.rows.length !== right.rows.length) return false
  return left.rows.every((row, rowIndex) => {
    const other = right.rows[rowIndex]
    return row.key === other.key
      && row.path === other.path
      && row.searchText === other.searchText
      && row.targets.length === other.targets.length
      && row.targets.every((target, targetIndex) => {
        const otherTarget = other.targets[targetIndex]
        return target.key === otherTarget.key
          && target.kind === otherTarget.kind
          && target.label === otherTarget.label
          && target.context === otherTarget.context
          && target.path === otherTarget.path
          && target.parentPath === otherTarget.parentPath
          && target.searchText === otherTarget.searchText
      })
  })
}

/** Route and period changes invalidate both the query and its page-owned target set. */
export function slateCommandReducer(state: SlateCommandState, action: SlateCommandAction): SlateCommandState {
  if (action.type === 'route') {
    return action.routeKey === state.routeKey ? state : initialSlateCommandState(action.routeKey)
  }
  if (action.type === 'register') {
    if (action.routeKey === state.routeKey && sameScope(action.scope, state.scope)) return state
    const samePeriod = action.routeKey === state.routeKey
      && action.scope !== null
      && action.scope.periodKey === state.scope?.periodKey
    return {
      routeKey: action.routeKey,
      query: samePeriod ? state.query : '',
      scope: action.scope,
    }
  }
  if (action.type === 'query') return { ...state, query: action.query }
  return state.query ? { ...state, query: '' } : state
}
