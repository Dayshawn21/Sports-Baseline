import type { PropLine } from '~/types/tennis'

const OPINION_LABELS: Record<string, string> = {
  aces: 'ace',
  double_faults: 'double fault',
  total_games: 'game',
  break_points_converted: 'break point converted',
  break_points_won: 'break point won',
  'Break Points Won': 'break point won',
  winners: 'winner',
  unforced_errors: 'unforced error',
  game_spread: 'game spread',
  set_handicap: 'set handicap',
  fantasy_score: 'fantasy point',
  'Fantasy Score': 'fantasy point',
  total_sets: 'set',
  'Total Sets': 'set',
  total_tie_breaks: 'tie break',
  'Total Tie Breaks': 'tie break',
}

export function generateOpinion(prop: PropLine): string | null {
  if (!prop.recommendation || prop.statAvg == null || prop.line == null) return null
  const line = parseFloat(String(prop.line))
  if (isNaN(line)) return null

  const oddsType = (prop.oddsType ?? '').toLowerCase()
  const isGoblin = oddsType === 'goblin'
  const isDemon  = oddsType === 'demon'

  const label = OPINION_LABELS[prop.statType] ?? prop.statType.replace(/_/g, ' ')
  const dir = prop.recommendation
  const statKey = prop.statType.trim().toLowerCase().replace(/ /g, '_')
  const avgVerb = statKey === 'fantasy_score' ? 'projects for' : 'averages'

  const lead =
    prop.confidence === 'LOCK'   ? 'Strong LOCK' :
    prop.confidence === 'STRONG' ? 'Strong lean' :
    prop.confidence === 'LEAN'   ? 'Slight lean' : 'Lean'

  // Tier note: goblins are easy lines, demons are hard lines
  const tierNote = isDemon
    ? ' (demon — hard line)'
    : isGoblin
      ? ' (goblin — soft line)'
      : ''

  const sentence1 = `${lead} ${dir}${tierNote} — player ${avgVerb} ${prop.statAvg.toFixed(1)} ${label}s vs a ${line.toFixed(1)} line.`

  const prob = dir === 'OVER' ? prop.pOver : prop.pUnder
  const parts: string[] = []
  if (prob != null) parts.push(`${(prob * 100).toFixed(0)}% probability`)
  if (prop.edgePct != null && Math.abs(prop.edgePct) >= 1)
    parts.push(`${Math.abs(prop.edgePct).toFixed(1)}% edge`)

  let sentence2 = parts.join(', ')
  if (prop.matchesCount != null) {
    sentence2 += ` with ${prop.matchesCount} matches in the sample`
    if (prop.matchesCount < 10) sentence2 += ' (small sample — treat with caution)'
  }
  sentence2 = sentence2 ? sentence2.charAt(0).toUpperCase() + sentence2.slice(1) + '.' : ''

  return [sentence1, sentence2].filter(Boolean).join(' ')
}
