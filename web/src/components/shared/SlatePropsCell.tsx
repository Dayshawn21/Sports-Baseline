import { slatePropsText } from '~/utils/slateProps'

/** The props column of a slate row, in the secondary tier so prices stay the brightest numbers. */
export function SlatePropsCell({ count }: { count: number }) {
  const empty = count === 0
  return <td className={`nfl-slate-table__props is-num${empty ? ' is-empty' : ''}`} aria-label={empty ? 'No props' : undefined}>
    {slatePropsText(count)}<span className="nfl-slate-table__unit"> props</span>
  </td>
}
