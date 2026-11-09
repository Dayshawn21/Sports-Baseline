interface Props {
  playerName: string
  market: string
  matchup: string
  when: string
  line: string
  model: string
  gap: string
  /** A muted line under the gap that sizes it ("107% of a typical line"). */
  gapDetail?: string | null
  /** What produced the second number: "model" by default, "reference" for an unvalidated reference. */
  modelLabel?: string
  /** How the gap is scaled, finishing "Gap is model minus line, ..."; left out when `gapDetail` says it. */
  gapScale?: string
}

/** A gray gap box's body, laid out like tennis's priced pick box but never colored: a gap is not a pick. */
export function GapDigestBody({ playerName, market, matchup, when, line, model, gap, gapDetail, modelLabel = 'model', gapScale }: Props) {
  return <>
    <strong>{playerName}</strong>
    <span className="slate-digest__what">{market} · {matchup}</span>
    <span className="slate-digest__what">{when}</span>
    <span className="slate-digest__num">
      <span>{line}<span className="slate-digest__arrow" aria-hidden="true">→</span>{model}</span>
      <span className="slate-digest__gap">{gap}</span>
    </span>
    {gapDetail && <span className="slate-digest__gap-detail">{gapDetail}</span>}
    <span className="slate-digest__basis">
      Line <span aria-hidden="true">→</span><span className="slate-digest__sr"> then</span> {modelLabel}. Gap is {modelLabel} minus line{gapScale ? `, ${gapScale}` : ''}.
    </span>
  </>
}
