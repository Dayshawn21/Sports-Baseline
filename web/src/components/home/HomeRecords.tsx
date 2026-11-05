import { Link } from 'react-router-dom'
import type { HomeRecord, RecordSport } from '~/utils/homeRecords'
import { sportViews } from '~/utils/sportNav'
import './home.css'

const TITLE: Record<RecordSport, string> = { tennis: 'Tennis', nfl: 'NFL props', nba: 'NBA props', nhl: 'NHL props' }

/** One card per sport with a model page. */
export function HomeRecords({ records }: { records: HomeRecord[] }) {
  return <div className="home-records">
    {records.map(record => {
      const model = sportViews(record.sport).find(entry => entry.view === 'model')
      return model && <Link key={record.sport} to={model.path} className="home-rec">
        <div className="home-rec__label">{TITLE[record.sport]}</div>
        <div className={`home-rec__val${record.status === 'ready' ? '' : ' is-quiet'}`}>{record.label}</div>
        <div className="home-rec__sub">{record.detail}.</div>
      </Link>
    })}
  </div>
}
