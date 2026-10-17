import { useState, type CSSProperties } from 'react'
import ErrorState from '~/components/shared/ErrorState'
import { usePlayerServeReturn } from '~/hooks/useTennisPlayer'
import type { PlayerSurface } from '~/types/tennis'
import { SERVE_RETURN_METRICS, defaultSurface, metricBar, metricText } from '~/utils/tennisPlayer'

const SURFACES: { key: PlayerSurface, label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'Hard', label: 'Hard' },
  { key: 'Clay', label: 'Clay' },
  { key: 'Grass', label: 'Grass' },
]
const SMALL_SAMPLE = 10

export default function PlayerServeReturn({ playerId, nextSurface }: { playerId: number, nextSurface: string | null | undefined }) {
  const query = usePlayerServeReturn(playerId)
  const [surface, setSurface] = useState<PlayerSurface>(() => defaultSurface(nextSurface))
  const label = SURFACES.find((s) => s.key === surface)?.label ?? surface

  const heading = (
    <div className="tennis-player-section-head">
      <h2 className="tennis-match-section">Serve and return · 52 weeks</h2>
      <div className="segment-toggle" role="group" aria-label="Surface">
        {SURFACES.map((s) => (
          <button key={s.key} type="button" className={s.key === surface ? 'is-selected' : ''}
            aria-pressed={s.key === surface} onClick={() => setSurface(s.key)}>{s.label}</button>
        ))}
      </div>
    </div>
  )

  if (query.isLoading) return <>{heading}<div className="tennis-match-empty">Loading serve and return...</div></>
  if (query.isError || !query.data) return <>{heading}<ErrorState error={query.error} onRetry={() => void query.refetch()} /></>

  const comparison = query.data.surfaces.find((s) => s.surface === surface)
  const player = comparison?.player
  const average = comparison?.tourAverage
  const where = surface === 'all' ? 'all surfaces' : label.toLowerCase()

  return (
    <>
      {heading}
      {!player ? (
        <div className="tennis-match-empty">No matches on {where} in 52 weeks.</div>
      ) : (
        <div className="tennis-match-card tennis-player-splits">
          {SERVE_RETURN_METRICS.map(({ metric, label: metricLabel }) => {
            const fill = metricBar(player[metric], metric)
            const mark = average ? metricBar(average[metric], metric) : null
            return (
              <div key={metric} className="tennis-player-split">
                <span>{metricLabel}</span>
                <div className="tennis-player-split__track">
                  {fill != null && <div className="tennis-player-split__fill" style={{ '--p': `${fill}%` } as CSSProperties} />}
                  {mark != null && <div className="tennis-player-split__avg" style={{ '--a': `${mark}%` } as CSSProperties}
                    title={`${query.data.tour} average ${metricText(average![metric], metric)}`} />}
                </div>
                <span className="tennis-player-split__value">{metricText(player[metric], metric)}</span>
              </div>
            )
          })}
          <p className="tennis-player-note">
            Dashed mark: {query.data.tour} average on {where}, over {average?.players ?? 0} players with {SMALL_SAMPLE}+
            matches. {player.matches} match{player.matches === 1 ? '' : 'es'} in the window
            {player.matches < SMALL_SAMPLE && <strong className="tennis-player-small"> · small sample</strong>}.
            Ace and DF rates are per serve point; BP converted is break points won over chances.
          </p>
        </div>
      )}
    </>
  )
}
