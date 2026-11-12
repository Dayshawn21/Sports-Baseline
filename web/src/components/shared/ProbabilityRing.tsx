import type { RingModel } from '~/utils/propRowVisuals'
import './prop-table.css'

const SIZE = 20
const CENTER = SIZE / 2
const RADIUS = 7.5
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

function tickPoint(pct: number, radius: number): [number, number] {
  const angle = (pct / 100) * 2 * Math.PI - Math.PI / 2
  return [CENTER + Math.cos(angle) * radius, CENTER + Math.sin(angle) * radius]
}

/** A small ring beside the probability text it repeats, so it is hidden from screen readers. Renders nothing without a model. */
export function ProbabilityRing({ ring }: { ring: RingModel | null }) {
  if (!ring) return null
  const arc = (ring.arcPct / 100) * CIRCUMFERENCE
  const tick = ring.breakEvenPct === null ? null : [tickPoint(ring.breakEvenPct, RADIUS - 3), tickPoint(ring.breakEvenPct, RADIUS + 3)]
  return <svg className={`prob-ring${ring.tone === 'neutral' ? '' : ` is-tone-${ring.tone}`}`} width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
    <circle className="prob-ring__track" cx={CENTER} cy={CENTER} r={RADIUS} />
    <circle className="prob-ring__arc" cx={CENTER} cy={CENTER} r={RADIUS}
      strokeDasharray={`${arc} ${CIRCUMFERENCE}`} transform={`rotate(-90 ${CENTER} ${CENTER})`} />
    {tick && <line className="prob-ring__tick" x1={tick[0][0]} y1={tick[0][1]} x2={tick[1][0]} y2={tick[1][1]} />}
  </svg>
}
