"""The NFL model track record (33d): the graded record the 27a, 27j and 28 reports print.

The loaders here are the ones those CLIs call, so the page and the reports read
the same rows through the same grading code and cannot disagree.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.nfl_game_line_clv import EARLY_WEEKS, game_models
from app.backtest.nfl_prizepicks_lines import BUCKET_LABELS, BUCKETS, MoneylineTiming, one_call_per_player_game
from app.core.nfl_elo import NFL_ELO_MODEL_VERSION
from app.core.nfl_game_line_clv import (
    PICK_THRESHOLD, VERDICT_PICKS, ClvMarketGrade, ClvSummary, Market, Verdict, grade_market, summarize, verdict,
)
from app.core.nfl_line_grading import (
    SETTLED_OUTCOMES, EdgeBucket, HitSummary, LineResult, OverProbabilityRead, model_hits, over_probability_reads,
    reference_lines, settle_line,
)
from app.core.nfl_over_probability_calibration import MAX_BIN_GAP, MAX_ECE, MIN_BIN_PAIRS, MIN_CASES
from app.core.nfl_over_probability_fit_report import (
    FIT_MARKETS, FIT_PROJECTION_MODEL_VERSION, FIT_SEASON, FitMarketRow,
)
from app.core.nfl_projection import NFL_PROJECTION_MODEL_VERSION
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.core.prop_ranking_rule import BREAK_EVEN_BY_ODDS_TYPE
from app.core.track_record import Signal, rate_signal, verdict_signal
from app.repositories import nfl as nfl_repo
from app.services import prop_ranking
from app.services.nfl.slate import build_slate
from app.services.nfl.targets_ranking import NflTargetsRankingSource
from app.services.prop_ranking import RankingCalls, RankingRecord, RankingSource, display_standard_error
from app.services.sport_registry import prop_source
from app.services.tennis.live_odds_cache import TimedSingleFlight

CACHE_TTL_SECONDS = 15 * 60
# The CLV report names the total model by its parameter set; it carries no version string.
CLV_MODEL_VERSIONS: dict[Market, str] = {"spread": NFL_ELO_MODEL_VERSION, "total": "NFL_SCORING_V1"}


@dataclass(frozen=True)
class LineGradingInputs:
    results: list[LineResult]
    edges: dict[int, float]
    p_overs: dict[int, float]
    timing: MoneylineTiming


async def load_line_grading(db: AsyncSession, season: int) -> LineGradingInputs:
    """Every pre-kickoff line settled, with the edge and P(over) today's `build_slate` gives it."""
    lines = await nfl_repo.get_gradeable_prop_lines(db, season)
    edges: dict[int, float] = {}
    p_overs: dict[int, float] = {}
    games_graded = 0
    after_kickoff = 0
    graded_games = {line.game_id for line in lines}
    for week in sorted({line.week for line in lines}):
        games = await nfl_repo.get_slate_games(db, season, week)
        kickoffs = {game["game_id"]: game["start_utc"] for game in games}
        last_kickoff = max(kickoff for kickoff in kickoffs.values() if kickoff is not None)
        slate = await build_slate(db, season, week, last_kickoff)
        edges.update(
            {line.line_id: line.edge for game in slate.games for line in game.lines if line.edge is not None}
        )
        p_overs.update(
            {line.line_id: line.p_over for game in slate.games for line in game.lines if line.p_over is not None}
        )
        moneylines = await nfl_repo.get_slate_market_probabilities(db, season, week)
        for game_id, (_, fetched_at) in moneylines.items():
            if game_id not in graded_games:
                continue
            games_graded += 1
            kickoff = kickoffs.get(game_id)
            if fetched_at is not None and kickoff is not None and fetched_at > kickoff:
                after_kickoff += 1
    results = [settle_line(line) for line in lines]
    return LineGradingInputs(results, edges, p_overs, MoneylineTiming(games_graded, after_kickoff))


def ranking_source(model_version: str = NFL_PROJECTION_MODEL_VERSION) -> RankingSource:
    if model_version == NFL_PROJECTION_MODEL_VERSION:
        return prop_source("nfl")
    if model_version == NFL_TARGETS_MODEL_VERSION:
        return NflTargetsRankingSource()
    raise ValueError(f"Unknown NFL ranking model: {model_version}")


async def load_ranking_calls(
    db: AsyncSession, season: int, model_version: str = NFL_PROJECTION_MODEL_VERSION,
) -> RankingCalls:
    """Each provider prop's latest frozen pre-kickoff row as a settled call, or the reason it is not one."""
    return await prop_ranking.load_ranking_calls(db, ranking_source(model_version), season)


async def load_clv_grades(db: AsyncSession, season: int) -> list[ClvMarketGrade]:
    """The pinned game model graded against entry-to-close movement, spread then total."""
    models = game_models(await nfl_repo.get_elo_games(db))
    games = await nfl_repo.get_game_line_clv_games(db, season)
    return [grade_market(games, models, "spread"), grade_market(games, models, "total")]


def build_ranking_record(
    inputs: RankingCalls, season: int, graded_at: datetime, model_version: str = NFL_PROJECTION_MODEL_VERSION,
) -> RankingRecord:
    source = ranking_source(model_version)
    return prop_ranking.build_ranking_record(
        inputs, season, graded_at, source.model_version, source.over_probability_version,
    )


@dataclass(frozen=True)
class ClvRule:
    pick_threshold: float
    verdict_picks: int


@dataclass(frozen=True)
class ClvRow:
    n: int
    mean_clv: float | None
    standard_error: float | None
    toward: int
    away: int
    flat: int
    wins: int
    losses: int
    pushes: int


@dataclass(frozen=True)
class ClvMarketRow:
    market: Market
    model_version: str
    graded: int
    excluded: dict[str, int]
    median_lead_hours: float | None
    min_lead_hours: float | None
    verdict: Verdict
    verdict_weeks: list[int]
    # Every pick while accruing; the fixed verdict sample once decided.
    headline: ClvRow
    all: ClvRow
    early: ClvRow
    late: ClvRow
    signal: Signal


@dataclass(frozen=True)
class ClvRecord:
    graded_at: datetime
    season: int
    rule: ClvRule
    markets: list[ClvMarketRow]


def _clv_row(summary: ClvSummary) -> ClvRow:
    record = summary.record
    return ClvRow(
        n=summary.n, mean_clv=summary.mean_clv, standard_error=summary.standard_error,
        toward=summary.toward, away=summary.away, flat=summary.flat,
        wins=record.hits, losses=record.misses, pushes=record.pushes,
    )


def _clv_market(grade: ClvMarketGrade) -> ClvMarketRow:
    result = verdict(grade.picks)
    headline = result.summary
    return ClvMarketRow(
        market=grade.market, model_version=CLV_MODEL_VERSIONS[grade.market], graded=grade.graded,
        excluded=dict(sorted(grade.excluded.items())),
        median_lead_hours=grade.median_lead_hours,
        min_lead_hours=min(grade.lead_hours) if grade.lead_hours else None,
        verdict=result.verdict, verdict_weeks=list(result.weeks),
        headline=_clv_row(headline),
        all=_clv_row(summarize(grade.picks)),
        early=_clv_row(summarize([pick for pick in grade.picks if pick.week <= EARLY_WEEKS])),
        late=_clv_row(summarize([pick for pick in grade.picks if pick.week > EARLY_WEEKS])),
        signal=verdict_signal(result.verdict != "accruing", headline.mean_clv, headline.standard_error, 0.0),
    )


def build_clv_record(grades: Sequence[ClvMarketGrade], season: int, graded_at: datetime) -> ClvRecord:
    return ClvRecord(
        graded_at=graded_at, season=season, rule=ClvRule(PICK_THRESHOLD, VERDICT_PICKS),
        markets=[_clv_market(grade) for grade in grades],
    )


@dataclass(frozen=True)
class LineCoverage:
    loaded: int
    settled: int
    void_dnp: int
    unsettleable_segment: int
    week_not_loaded: int


@dataclass(frozen=True)
class HitRow:
    calls: int
    hits: int
    pushes: int
    hit_rate: float | None
    standard_error: float | None
    signal: Signal


@dataclass(frozen=True)
class EdgeHitRow(HitRow):
    bucket: EdgeBucket
    label: str


@dataclass(frozen=True)
class MarketHitRow(HitRow):
    market: str


@dataclass(frozen=True)
class WeekHitRow(HitRow):
    week: int


@dataclass(frozen=True)
class OverProbabilityRow:
    """Served P(over) against settled lines; display only, so it never carries a signal."""

    odds_type: str
    scored: int
    unscored: int
    mean_predicted: float | None
    over_rate: float | None
    brier: float | None


@dataclass(frozen=True)
class ReliabilityBin:
    n: int
    mean_predicted: float
    observed: float


@dataclass(frozen=True)
class LineRecord:
    graded_at: datetime
    season: int
    model_version: str
    break_even: float
    coverage: LineCoverage
    calls: HitRow
    by_edge: list[EdgeHitRow]
    by_market: list[MarketHitRow]
    by_week: list[WeekHitRow]
    over_probability: list[OverProbabilityRow]
    reliability: list[ReliabilityBin]


STANDARD_BREAK_EVEN = BREAK_EVEN_BY_ODDS_TYPE["standard"]
OVER_PROBABILITY_KEYS = ("standard", "goblin", "demon", "all")


def _hit_fields(summary: HitSummary | None) -> dict[str, int | float | None | str]:
    summary = summary or HitSummary(0, 0, 0)
    rate = summary.hit_rate
    standard_error = display_standard_error(summary.calls, rate, summary.standard_error)
    return {
        "calls": summary.calls, "hits": summary.hits, "pushes": summary.pushes, "hit_rate": rate,
        "standard_error": standard_error,
        "signal": rate_signal(rate, standard_error, STANDARD_BREAK_EVEN) if rate is not None else "neutral",
    }


def _over_probability_row(odds_type: str, read: OverProbabilityRead) -> OverProbabilityRow:
    return OverProbabilityRow(
        odds_type=odds_type, scored=read.scored, unscored=read.unscored, mean_predicted=read.mean_predicted,
        over_rate=read.over_rate, brier=read.report.brier if read.report else None,
    )


def build_line_record(inputs: LineGradingInputs, season: int, graded_at: datetime) -> LineRecord:
    """27a's model calls and 27g's forward read, grouped exactly as the 27a report groups them."""
    results = inputs.results
    references = reference_lines(result.line for result in results)
    calls = one_call_per_player_game(results)

    def hits(subset: Sequence[LineResult]) -> dict[EdgeBucket | Literal["all"], HitSummary]:
        return model_hits(subset, inputs.edges, references)

    overall = hits(calls)
    markets = {market: hits([c for c in calls if c.line.market == market]).get("all")
               for market in sorted({c.line.market for c in calls})}
    weeks = {week: hits([c for c in calls if c.line.week == week]).get("all")
             for week in sorted({c.line.week for c in calls})}
    outcomes = Counter(result.outcome for result in results)
    reads = over_probability_reads(results, inputs.p_overs)
    overall_read = reads.get("all")
    return LineRecord(
        graded_at=graded_at, season=season, model_version=NFL_PROJECTION_MODEL_VERSION,
        break_even=STANDARD_BREAK_EVEN,
        coverage=LineCoverage(
            loaded=len(results), settled=sum(outcomes[o] for o in SETTLED_OUTCOMES), void_dnp=outcomes["void_dnp"],
            unsettleable_segment=outcomes["unsettleable_segment"], week_not_loaded=outcomes["week_not_loaded"],
        ),
        calls=HitRow(**_hit_fields(overall.get("all"))),
        by_edge=[
            EdgeHitRow(**_hit_fields(overall.get(bucket)), bucket=bucket, label=BUCKET_LABELS[bucket])
            for bucket in BUCKETS
        ],
        by_market=[
            MarketHitRow(**_hit_fields(summary), market=market)
            for market, summary in markets.items() if summary is not None and summary.calls
        ],
        by_week=[
            WeekHitRow(**_hit_fields(summary), week=week)
            for week, summary in weeks.items() if summary is not None and summary.calls
        ],
        over_probability=[_over_probability_row(key, reads[key]) for key in OVER_PROBABILITY_KEYS if key in reads],
        reliability=[
            ReliabilityBin(b.n, b.mean_predicted, b.observed)
            for b in (overall_read.report.bins if overall_read and overall_read.report else ())
        ],
    )


@dataclass(frozen=True)
class FitRule:
    min_cases: int
    max_ece: float
    max_bin_gap: float
    min_bin_pairs: int


@dataclass(frozen=True)
class FitRecord:
    fit_season: int
    projection_version: str
    # False once the projection moves on: the slate then hides P(over) until the fit is regenerated.
    served: bool
    rule: FitRule
    markets: tuple[FitMarketRow, ...]


def build_fit_record(live_projection_version: str) -> FitRecord:
    """The recorded 27g fit; static, so it needs no database and no cache."""
    return FitRecord(
        fit_season=FIT_SEASON, projection_version=FIT_PROJECTION_MODEL_VERSION,
        served=FIT_PROJECTION_MODEL_VERSION == live_projection_version,
        rule=FitRule(MIN_CASES, MAX_ECE, MAX_BIN_GAP, MIN_BIN_PAIRS), markets=FIT_MARKETS,
    )


def get_fit_record() -> FitRecord:
    return build_fit_record(NFL_PROJECTION_MODEL_VERSION)


_RANKING: TimedSingleFlight[RankingRecord] = TimedSingleFlight(CACHE_TTL_SECONDS)
_CLV: TimedSingleFlight[ClvRecord] = TimedSingleFlight(CACHE_TTL_SECONDS)
_LINES: TimedSingleFlight[LineRecord] = TimedSingleFlight(CACHE_TTL_SECONDS)


async def get_ranking_record(
    db: AsyncSession, season: int, model_version: str = NFL_PROJECTION_MODEL_VERSION,
) -> RankingRecord | None:
    """None when grading failed; the failure is shared for the cache window too."""
    source = ranking_source(model_version)

    async def fetch() -> RankingRecord:
        inputs = await load_ranking_calls(db, season, model_version)
        return build_ranking_record(inputs, season, datetime.now(UTC), model_version)

    return await _RANKING.get((season, source.model_version, source.over_probability_version), fetch)


async def get_clv_record(db: AsyncSession, season: int) -> ClvRecord | None:
    async def fetch() -> ClvRecord:
        return build_clv_record(await load_clv_grades(db, season), season, datetime.now(UTC))

    return await _CLV.get(season, fetch)


async def get_line_record(db: AsyncSession, season: int) -> LineRecord | None:
    """The slowest section: it replays `build_slate` for every graded week."""
    async def fetch() -> LineRecord:
        return build_line_record(await load_line_grading(db, season), season, datetime.now(UTC))

    return await _LINES.get(season, fetch)
