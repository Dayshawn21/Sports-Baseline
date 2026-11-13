import { Select } from 'antd'
import { useSearchParams } from 'react-router-dom'
import { YesNoList } from '~/components/nba/NbaPlayerFormSection'
import { GameLogBars } from '~/components/nfl/NflPropDetailSections'
import type { NbaPlayerMarket, NbaSplitTeammate, NbaTeammateSplit } from '~/types/nba'
import { NBA_SEASON_START_MONTH, nbaChartLine } from '~/utils/nbaPlayer'
import {
  SMALL_SPLIT_SAMPLE, SPLIT_BAR_LIMIT, activeTeammate, marketSplit, parseOutParam, splitSideText, teammateLabel,
  type SplitSideSummary,
} from '~/utils/nbaTeammateSplit'
import { playerSearch } from '~/utils/nflPlayer'

const DOUBLE_DOUBLE = 'double_double'

function WithoutGames({ side, market, line }: { side: SplitSideSummary, market: string, line: number | null }) {
  const sample = {
    average: side.average,
    values: side.games.slice(0, SPLIT_BAR_LIMIT).map(game => ({ value: game.value, opponentTeam: game.opponent, gameDate: game.gameDate })),
  }
  return market === DOUBLE_DOUBLE
    ? <YesNoList sample={sample} />
    : <GameLogBars row={{ market, line, segment: 'full_game' }} sample={sample} seasonStartMonth={NBA_SEASON_START_MONTH} />
}

function Split({ split, teammate, market }: { split: NbaTeammateSplit, teammate: NbaSplitTeammate, market: NbaPlayerMarket }) {
  if (teammate.firstTeamGameDate === null) {
    return <p className="nba-split-note">No {split.team} games on record for {teammate.playerName}.</p>
  }
  const line = nbaChartLine(market)
  const result = marketSplit(split, teammate, market.market, line)
  const small = Math.min(result.with.games.length, result.without.games.length) < SMALL_SPLIT_SAMPLE
  const notLoaded = result.with.notLoaded + result.without.notLoaded
  const notes = [
    small ? `Small sample: under ${SMALL_SPLIT_SAMPLE} games on a side.` : null,
    result.before > 0 ? `${result.before} earlier ${result.before === 1 ? 'game' : 'games'} left out: he had not played for ${split.team} yet.` : null,
    notLoaded > 0 ? `${notLoaded} not loaded.` : null,
  ].filter(Boolean).join(' ')
  const shown = Math.min(result.without.games.length, SPLIT_BAR_LIMIT)
  return <>
    <dl className="nba-split-sides">
      <div><dt>With him</dt><dd>{splitSideText(result.with, market.market, line)}</dd></div>
      <div><dt>Without him</dt><dd>{splitSideText(result.without, market.market, line)}</dd></div>
    </dl>
    {notes && <p className="nba-split-note">{notes}</p>}
    {shown === 0
      ? <p className="nba-split-note">No games without him this season.</p>
      : <>
        <p className="nba-split-note">
          Without him{shown < result.without.games.length ? `, last ${shown}` : ''}{line === null ? '' : `, line ${line}`}
        </p>
        <WithoutGames side={result.without} market={market.market} line={line} />
      </>}
  </>
}

/** This season's games split by a teammate listed out tonight. Reference only: it never moves a projection, P(over) or rank. */
export function NbaTeammateSplitSection({ split, market }: { split: NbaTeammateSplit | null, market: NbaPlayerMarket }) {
  const [params, setParams] = useSearchParams()
  if (split === null) return null
  const teammate = activeTeammate(parseOutParam(params), split)
  const choose = (playerId: number | undefined) =>
    setParams(playerSearch(params, { out: playerId === undefined ? null : String(playerId) }), { replace: true })
  return <section className="nfl-prop-detail__section nba-split" aria-label="Teammate out split">
    <div className="nfl-prop-detail__section-head"><h3>Teammate out</h3><span>{split.season}-{String(split.season + 1).slice(-2)}, reference only</span></div>
    <Select className="nba-split-picker" aria-label="Teammate out" allowClear showSearch optionFilterProp="label"
      placeholder="Choose a teammate listed out" value={teammate?.playerId} onChange={choose}
      options={split.teammates.map(option => ({ value: option.playerId, label: teammateLabel(option) }))} />
    {teammate === null
      ? <p className="nba-split-note">Pick a teammate listed out to split this season's games.</p>
      : <Split split={split} teammate={teammate} market={market} />}
  </section>
}
