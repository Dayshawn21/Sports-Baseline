import { Tooltip } from 'antd'
import type { CSSProperties } from 'react'
import type { MatchDetail } from '~/types/tennis'
import { getDisplayFlagLabel, getDisplayFlags } from '~/components/tennis/qualityFlags'
import { fmtPct } from '~/utils/odds'
import { componentRows, heroSide, sideView, weightColumnLabel } from '~/utils/tennisMatch'

function lastName(name: string): string {
  return name.split(/\s+/).filter(Boolean).pop() ?? name
}

export default function MatchComponents({ detail }: { detail: MatchDetail }) {
  const prediction = detail.prediction
  if (!prediction) return null
  const side = heroSide(detail)
  const rows = componentRows(detail, side)
  const flags = getDisplayFlags(prediction.qualityFlags)

  return (
    <section aria-labelledby="tennis-match-components">
      <h2 id="tennis-match-components" className="tennis-match-section">Where the number comes from</h2>
      <div className="tennis-match-card tennis-match-components">
        <div className="tennis-match-comp is-head">
          <span>Component</span>
          <span>{lastName(sideView(detail, side).name)} win probability</span>
          <span>Prob</span>
          <span>{weightColumnLabel(detail)}</span>
        </div>
        {rows.map((row) => (
          <div key={row.key} className={`tennis-match-comp${row.key === 'ensemble' ? ' is-ensemble' : ''}`}>
            <span>{row.label}</span>
            <div className="tennis-match-comp__track" aria-hidden="true">
              {row.prob != null && <div className="tennis-match-comp__fill" style={{ '--p': `${row.prob * 100}%` } as CSSProperties} />}
              <div className="tennis-match-comp__mid" />
            </div>
            <span className="tennis-match-comp__num">{row.prob != null ? fmtPct(row.prob) : <em>{row.missingNote}</em>}</span>
            <span className="tennis-match-comp__num is-dim">{row.weight != null ? row.weight.toFixed(2) : ''}</span>
          </div>
        ))}
        {flags.length > 0 && (
          <div className="tennis-match-flags">
            {flags.map((flag) => (
              <Tooltip key={flag} title={getDisplayFlagLabel(prediction, flag)}>
                <span className="tennis-match-flag">{flag.replaceAll('_', ' ')}</span>
              </Tooltip>
            ))}
          </div>
        )}
      </div>
    </section>
  )
}
