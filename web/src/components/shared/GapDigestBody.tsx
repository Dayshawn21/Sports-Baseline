interface Props {
  playerName: string
  market: string
  matchup: string
  when: string
  line: string
  model: string
  gap: string
  /** What produced the second number: "model" by default, "reference" for an unvalidated reference. */
  modelLabel?: string
}

/** A gray gap box's body, laid out like tennis's priced pick box but never colored: a gap is not a pick. */
export function GapDigestBody({ playerName, market, matchup, when, line, model, gap, modelLabel = 'model' }: Props) {
  return <>
    <strong>{playerName}</strong>
    <span className="slate-digest__what">{market} · {matchup}</span>
    <span className="slate-digest__what">{when}</span>
    <span className="slate-digest__num">
      <span>{line}<span className="slate-digest__arrow" aria-hidden="true">→</span>{model}</span>
      <span className="slate-digest__gap">{gap} gap</span>
    </span>
    <span className="slate-digest__foot">
      <span className="slate-digest__tag">Line → {modelLabel}</span>
    </span>
  </>
}
