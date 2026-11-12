import { Link } from 'react-router-dom'
import { tallyText, type BoardRecord } from '~/utils/boardRecord'
import './board-record-strip.css'

const STATUS_TEXT = { loading: 'Loading record', error: 'Record unavailable' } as const

/** The board's graded record in one gray line; color stays on the Model page, so a good run never reads as a pick. */
export default function BoardRecordStrip({ record }: { record: BoardRecord }) {
  const picks = record.graded ? record.graded.wins + record.graded.losses : 0
  return <section className="board-record" aria-label="Model record">
    <div className="board-record__live">
      <b>Record</b>
      {record.status !== 'ready' ? <span>{STATUS_TEXT[record.status]}</span> : <>
        {record.version && <span className="board-record__version" title={record.version}>{record.version}</span>}
        {record.graded ? <>
          <span className="board-record__num">{tallyText(record.graded)}</span>
          <span>{picks} graded · {record.adoptedSlices} of {record.liveSlices} live slices adopted</span>
        </> : <span>{record.note}</span>}
      </>}
      <Link to={record.modelPath}>Model page →</Link>
    </div>
    {record.setAside.length > 0 && <div className="board-record__aside">
      {record.setAside.map(segment => <span key={segment.label}>
        {segment.label}{segment.tally && <span className="board-record__num"> {tallyText(segment.tally)}</span>}
      </span>)}
    </div>}
  </section>
}
