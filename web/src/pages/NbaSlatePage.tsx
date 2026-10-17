import { Button } from 'antd'
import { useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { NbaSlateGameCard } from '~/components/nba/NbaSlateGameCard'
import ErrorState from '~/components/shared/ErrorState'
import LoadingState from '~/components/shared/LoadingState'
import SportViewSwitch from '~/components/shared/SportViewSwitch'
import StatChip from '~/components/shared/StatChip'
import { useNbaSlate } from '~/hooks/useNba'
import type { NbaSlateGame } from '~/types/nba'
import { nbaSlateCard, nbaSlateSummary, parseSlateDate, slateDateLabel } from '~/utils/nbaSlate'
import './nfl-slate.css'

const MISSING = '--'

function Summary({ games }: { games: NbaSlateGame[] }) {
  const summary = nbaSlateSummary(games)
  return <section className="page-head__stats nfl-slate__stats" aria-label="Day summary">
    <StatChip value={summary.games} label="Games" />
    <StatChip value={summary.propLines} label="Prop lines" />
    <StatChip value={`${summary.finals} / ${summary.games}`} label="Final" />
    <StatChip value={summary.oddsUpdated ?? MISSING} label="Odds updated" />
  </section>
}

function Legend() {
  return <p className="nfl-slate__legend">
    <span><b>Market</b> is DraftKings when stored, else the latest book; win probability is de-vigged.</span>
    <span><b>No model yet.</b> NBA lines are display only until a projection passes its backtest.</span>
    <span><b>Scores</b> load the morning after each game.</span>
  </p>
}

export default function NbaSlatePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  // A malformed link falls back to the API's choice rather than an error page.
  const requested = parseSlateDate(searchParams.get('date'))
  const slate = useNbaSlate(requested)
  const cards = useMemo(() => {
    const now = new Date()
    return (slate.data?.games ?? []).map(game => nbaSlateCard(game, now))
  }, [slate.data])

  if (slate.isLoading) return <LoadingState message="Loading NBA slate..." />
  if (slate.isError || !slate.data) return <ErrorState error={slate.error} onRetry={() => void slate.refetch()} />
  const { date, previousDate, nextDate, games } = slate.data
  const goTo = (target: string) => setSearchParams({ date: target })
  return <div className="page-shell nfl-slate nba-slate"><div className="page-container is-wide">
    <header className="nfl-slate__head">
      <div>
        <div className="unified-eyebrow">NBA · {slateDateLabel(date)}</div>
        <h1 className="unified-page-title">NBA Slate</h1>
        <p className="unified-page-subtitle">Every game on this date, with the market and stored prop lines.</p>
      </div>
      <div className="nfl-slate__controls">
        <SportViewSwitch sport="nba" />
        <Button disabled={previousDate === null} onClick={() => previousDate && goTo(previousDate)}>← Previous</Button>
        <Button disabled={nextDate === null} onClick={() => nextDate && goTo(nextDate)}>Next →</Button>
      </div>
    </header>
    {games.length === 0 ? <div className="nfl-empty">No NBA games on this date.</div> : <>
      <Summary games={games} />
      <Legend />
      <section className="nfl-slate-window" aria-label="Games">
        <div className="nfl-slate-grid">{cards.map(card => <NbaSlateGameCard key={card.gameId} card={card} />)}</div>
      </section>
    </>}
  </div></div>
}
