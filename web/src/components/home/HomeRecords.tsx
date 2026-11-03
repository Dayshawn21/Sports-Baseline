import { Link } from 'react-router-dom'
import type { HomeRecord } from '~/utils/homeRecords'
import { SPORTS, sportViews } from '~/utils/sportNav'
import './home.css'

/** One row per sport that has a model page; NHL has none, so it has no row. */
export function HomeRecords({ records }: { records: HomeRecord[] }) {
  return <div className="home-records">
    {records.map(record => {
      const model = sportViews(record.sport).find(entry => entry.view === 'model')
      const label = SPORTS.find(entry => entry.code === record.sport)!.label
      return model && <Link key={record.sport} to={model.path} className="home-records__row">
        <b>{label}</b>
        <span className="home-records__detail">{record.detail}</span>
        <span className={`home-records__label${record.status === 'ready' ? '' : ' is-quiet'}`}>{record.label}</span>
      </Link>
    })}
  </div>
}
