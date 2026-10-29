import StatChip from '~/components/shared/StatChip'

interface Props {
  matches: number
  props: number
  locks: number
  strongOrBetter: number
}

/** The slate's four counts in the shared chip strip every slate uses. Locks and Strong+ count priced best bets only (48f), in the neutral chip color since no tennis tier has passed the 32b rule. */
export default function TennisSlateSummary({ matches, props, locks, strongOrBetter }: Props) {
  return (
    <section className="page-head__stats" aria-label="Slate summary">
      <StatChip value={matches} label="Matches" />
      <StatChip value={locks} label="Locks" />
      <StatChip value={strongOrBetter} label="Strong+" />
      <StatChip value={props} label="Player props" />
    </section>
  )
}
