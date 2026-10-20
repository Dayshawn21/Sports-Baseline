"""The tennis model track record page's data (build-plan 32b).

Each section aggregates what an existing grading report computes (26a, 26b, 26f)
into page-shaped rows, and is shared across requests for CACHE_TTL_SECONDS:
grading reads every settled match, and the answer only changes once a day.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.backtest.tennis_prizepicks_lines import ODDS_TYPES, SettledLine, settle_rows
from app.backtest.tennis_prop_snapshots import GradedPick, grade
from app.backtest.tennis_predictions import (
    CLV_MIN_GAP,
    DEFAULT_MODEL_VERSION,
    ENSEMBLE_MARKET_COMPONENTS,
    GROUPS,
    MARKET_COMPONENTS,
    Component,
)
from app.core.tennis_grading import (
    CalibrationBin,
    calibration_bins,
    clv_summary,
    paired_loss_difference,
    score_component,
)
from app.core.box_score_join import JoinResult
from app.core.prop_ev import break_even_probability, leg_decimal_odds
from app.core.track_record import (
    TIER_BREAK_EVEN,
    TIER_RULE_TIERS,
    TIER_RULE_VERSION,
    TIER_VERDICT_SAMPLE,
    Signal,
    binomial_standard_error,
    loss_signal,
    rate_signal,
    tier_verdict,
)
from app.repositories import player_match_stats as box_score_repo
from app.repositories import predictions as prediction_repo
from app.repositories import prop_snapshots as prop_snapshot_repo
from app.repositories import props as props_repo
from app.repositories.predictions import GradedPrediction
from app.repositories.prop_snapshots import GradedPropSnapshot
from app.repositories.props import PrizePicksLineRow
from app.services.tennis.live_odds_cache import TimedSingleFlight

CACHE_TTL_SECONDS = 15 * 60

# The market is the baseline row, so it leads, then the ensemble it is judged by.
_GETTERS = dict(MARKET_COMPONENTS)
_TABLE_COMPONENTS: tuple[Component, ...] = tuple(
    (name, _GETTERS[name]) for name in ("market", "ensemble", "elo", "ml")
)
_CALIBRATION_SOURCES = ("ensemble", "market", "ml")
_POOLED_GROUP = "ATP+WTA"


@dataclass(frozen=True)
class LossComparison:
    mean: float
    standard_error: Optional[float]
    signal: Signal


@dataclass(frozen=True)
class ComponentRow:
    name: str
    log_loss: float
    brier: float
    vs_market: Optional[LossComparison]


@dataclass(frozen=True)
class GroupScores:
    group: str
    n: int
    components: list[ComponentRow]


@dataclass(frozen=True)
class CalibrationSeries:
    source: str
    bins: list[CalibrationBin]


@dataclass(frozen=True)
class ClvLine:
    group: str
    min_gap: float
    eligible: int
    moved: int
    toward: int
    away: int
    mean_move_toward: float


@dataclass(frozen=True)
class GradingCounts:
    settled: int
    other_versions: int
    incomplete: int
    graded: int
    with_market: int
    with_close: int


@dataclass(frozen=True)
class VersionCount:
    model_version: str
    settled: int
    served: bool


@dataclass(frozen=True)
class PredictionGrading:
    graded_at: datetime
    model_version: str
    counts: GradingCounts
    groups: list[GroupScores]
    ensemble_market_groups: list[GroupScores]
    calibration: list[CalibrationSeries]
    clv: list[ClvLine]
    versions: list[VersionCount]


def version_counts(rows: list[GradedPrediction], served: str) -> list[VersionCount]:
    """The served version first, even with nothing settled, then the newest predicted first."""
    settled = Counter(r.model_version for r in rows)
    latest: dict[str, datetime] = {}
    for r in rows:
        if r.model_version not in latest or r.generated_at > latest[r.model_version]:
            latest[r.model_version] = r.generated_at
    others = sorted((v for v in settled if v != served), key=lambda v: latest[v], reverse=True)
    return [VersionCount(v, settled[v], v == served) for v in (served, *others)]


def _common(rows: list[GradedPrediction], components: tuple[Component, ...]) -> list[GradedPrediction]:
    return [r for r in rows if all(get(r) is not None for _, get in components)]


def _group_scores(
    group: str, rows: list[GradedPrediction], table_components: tuple[Component, ...] = _TABLE_COMPONENTS,
) -> GroupScores:
    subset = _common(rows, table_components)
    if not subset:
        return GroupScores(group, 0, [])
    outcomes = [r.p1_won for r in subset]
    market = [r.market_prob for r in subset]
    components = []
    for name, get in table_components:
        probabilities = [get(r) for r in subset]
        score = score_component(probabilities, outcomes)
        vs_market = None
        if name != "market":
            diff = paired_loss_difference(probabilities, market, outcomes)
            vs_market = LossComparison(diff.mean, diff.standard_error, loss_signal(diff.mean, diff.standard_error))
        components.append(ComponentRow(name, score.log_loss, score.brier, vs_market))
    return GroupScores(group, len(subset), components)


def _calibration(rows: list[GradedPrediction]) -> list[CalibrationSeries]:
    subset = _common(rows, MARKET_COMPONENTS)
    outcomes = [r.p1_won for r in subset]
    return [
        CalibrationSeries(source, calibration_bins([_GETTERS[source](r) for r in subset], outcomes) if subset else [])
        for source in _CALIBRATION_SOURCES
    ]


def _clv_line(group: str, rows: list[GradedPrediction], min_gap: float) -> ClvLine:
    summary = clv_summary([(r.ensemble_prob, r.market_prob, r.closing_market_prob) for r in rows], min_gap)
    return ClvLine(group, min_gap, summary.eligible, summary.moved, summary.toward,
                   summary.moved - summary.toward, summary.mean_move_toward)


def build_prediction_grading(
    rows: list[GradedPrediction], model_version: str, graded_at: datetime,
) -> PredictionGrading:
    versioned = [r for r in rows if r.model_version == model_version]
    graded = [r for r in versioned if r.completed_score]
    counts = GradingCounts(
        settled=len(rows),
        other_versions=len(rows) - len(versioned),
        incomplete=len(versioned) - len(graded),
        graded=len(graded),
        with_market=sum(r.market_prob is not None for r in graded),
        with_close=sum(r.closing_market_prob is not None for r in graded),
    )
    by_group = {group: [r for r in graded if r.tour in tours] for group, tours in GROUPS}
    clv = []
    for group, subset in (("all", graded), *by_group.items()):
        clv.append(_clv_line(group, subset, 0.0))
        clv.append(_clv_line(group, subset, CLV_MIN_GAP))
    return PredictionGrading(
        graded_at=graded_at,
        model_version=model_version,
        counts=counts,
        groups=[_group_scores(group, subset) for group, subset in by_group.items()],
        ensemble_market_groups=[
            _group_scores(group, subset, ENSEMBLE_MARKET_COMPONENTS) for group, subset in by_group.items()
        ],
        calibration=_calibration(by_group[_POOLED_GROUP]),
        clv=clv,
        versions=version_counts(rows, DEFAULT_MODEL_VERSION),
    )


@dataclass(frozen=True)
class LineExclusions:
    live: int
    promo: int
    incomplete_score: int
    unjoined: int
    not_settleable: int


@dataclass(frozen=True)
class LineSettlementRow:
    stat: str
    odds_type: str
    settled: int
    over_share: float
    under_share: float
    push_share: float
    over_rate: Optional[float]
    """Overs among decided lines, pushes excluded."""
    standard_error: Optional[float]
    break_even: Optional[float]
    signal: Signal


@dataclass(frozen=True)
class LineSettlement:
    graded_at: datetime
    excluded: LineExclusions
    rows: list[LineSettlementRow]


def _settlement_row(stat: str, odds_type: str, lines: list[SettledLine]) -> LineSettlementRow:
    n = len(lines)
    counts = Counter(line.outcome for line in lines)
    decided = counts["over"] + counts["under"]
    over_rate = counts["over"] / decided if decided else None
    # Goblin and demon lines stack several per player-stat and move together, so
    # they get no error bar and therefore never a signal color (the 26b rule).
    # A 0% or 100% rate has a zero binomial error, which would color a stat with
    # a handful of lines as if it were certain.
    se = (binomial_standard_error(over_rate, decided)
          if over_rate is not None and 0 < over_rate < 1 and odds_type == "standard" else None)
    decimal = leg_decimal_odds(odds_type, source="prizepicks")
    break_even = break_even_probability(decimal) if decimal else None
    signal = (rate_signal(over_rate, se, break_even)
              if over_rate is not None and break_even is not None else "neutral")
    return LineSettlementRow(stat, odds_type, n, counts["over"] / n, counts["under"] / n, counts["push"] / n,
                             over_rate, se, break_even, signal)


def build_line_settlement(
    rows: list[PrizePicksLineRow], joins: dict[tuple[int, int], JoinResult], graded_at: datetime,
) -> LineSettlement:
    settled, excluded = settle_rows(rows, joins)
    table = []
    for odds_type in ODDS_TYPES:
        of_type = [line for line in settled if line.odds_type == odds_type]
        for stat in sorted({line.stat for line in of_type}):
            table.append(_settlement_row(stat, odds_type, [line for line in of_type if line.stat == stat]))
    return LineSettlement(
        graded_at=graded_at,
        excluded=LineExclusions(excluded.live, excluded.promo, excluded.incomplete_score,
                                sum(excluded.unjoined.values()), sum(excluded.not_settleable.values())),
        rows=table,
    )


@dataclass(frozen=True)
class TierExclusions:
    non_standard: int
    """Graded goblin and demon picks, which the tier rule does not grade."""
    awaiting: int
    """Standard picks with no settlement yet: retirements, unjoined or unsettleable box-score stats."""


@dataclass(frozen=True)
class TierRow:
    tier: str
    decided: int
    hits: int
    pushes: int
    hit_rate: Optional[float]
    standard_error: Optional[float]
    verdict: str
    verdict_sample_size: int
    """Decided picks in the verdict sample, or on the mature days so far while accruing."""
    verdict_hit_rate: Optional[float]
    signal: Signal


@dataclass(frozen=True)
class TierGrading:
    graded_at: datetime
    projection_version: str
    verdict_sample: int
    break_even: float
    excluded: TierExclusions
    tiers: list[TierRow]
    pass_snapshotted: int


def _tier_row(tier: str, picks: list[GradedPick], as_of: date) -> TierRow:
    decided = [p for p in picks if p.hit is not None]
    hits = sum(bool(p.hit) for p in decided)
    hit_rate = hits / len(decided) if decided else None
    se = binomial_standard_error(hit_rate, len(decided)) if hit_rate is not None else None
    verdict = tier_verdict(
        [(p.row.snapshot_at.astimezone(UTC).date(), bool(p.hit)) for p in decided if p.row.snapshot_at], as_of,
    )
    return TierRow(tier, len(decided), hits, len(picks) - len(decided), hit_rate, se,
                   verdict.verdict, verdict.sample_size, verdict.hit_rate, verdict.signal)


def build_tier_grading(
    rows: list[GradedPropSnapshot], joins: dict[tuple[int, int], JoinResult], as_of: date, graded_at: datetime,
) -> TierGrading:
    picks, awaiting = grade(rows, joins)
    standard = [p for p in picks if p.odds_type == "standard"]
    standard_rows = [r for r in rows if (r.odds_type or "standard").lower() == "standard"]
    graded_ids = {p.row.snapshot_id for p in picks}
    ungraded_standard = sum(r.snapshot_id not in graded_ids and r.recommendation is not None for r in standard_rows)
    return TierGrading(
        graded_at=graded_at,
        projection_version=TIER_RULE_VERSION,
        verdict_sample=TIER_VERDICT_SAMPLE,
        break_even=TIER_BREAK_EVEN,
        excluded=TierExclusions(non_standard=len(picks) - len(standard), awaiting=ungraded_standard),
        tiers=[_tier_row(tier, [p for p in standard if p.row.confidence == tier], as_of) for tier in TIER_RULE_TIERS],
        pass_snapshotted=sum(r.confidence == "PASS" for r in standard_rows),
    )


# The rows are cached, not each version's grading: one load serves every version,
# and an arbitrary requested version cannot grow the cache.
_PREDICTIONS: TimedSingleFlight[tuple[list[GradedPrediction], datetime]] = TimedSingleFlight(CACHE_TTL_SECONDS)
_LINES: TimedSingleFlight[LineSettlement] = TimedSingleFlight(CACHE_TTL_SECONDS)
_TIERS: TimedSingleFlight[TierGrading] = TimedSingleFlight(CACHE_TTL_SECONDS)


async def get_prediction_grading(
    db: AsyncSession, model_version: str = DEFAULT_MODEL_VERSION,
) -> Optional[PredictionGrading]:
    """None when grading failed; the failure is shared for the cache window too."""
    async def fetch() -> tuple[list[GradedPrediction], datetime]:
        return await prediction_repo.get_graded_predictions(db), datetime.now(UTC)

    loaded = await _PREDICTIONS.get("predictions", fetch)
    if loaded is None:
        return None
    rows, graded_at = loaded
    return build_prediction_grading(rows, model_version, graded_at)


async def get_line_settlement(db: AsyncSession) -> Optional[LineSettlement]:
    async def fetch() -> LineSettlement:
        rows = await props_repo.get_settleable_prizepicks_lines(db)
        contexts = await box_score_repo.get_box_score_candidates(
            db, sorted({(row.player_id, row.match_id) for row in rows}),
        )
        joins = {pair: context.join() for pair, context in contexts.items()}
        return build_line_settlement(rows, joins, datetime.now(UTC))

    return await _LINES.get("prizepicks-lines", fetch)


async def get_tier_grading(db: AsyncSession) -> Optional[TierGrading]:
    async def fetch() -> TierGrading:
        rows = await prop_snapshot_repo.get_graded_prop_snapshots(db, TIER_RULE_VERSION)
        contexts = await box_score_repo.get_box_score_candidates(
            db, sorted({(row.player_id, row.match_id) for row in rows}),
        )
        joins = {pair: context.join() for pair, context in contexts.items()}
        now = datetime.now(UTC)
        return build_tier_grading(rows, joins, now.date(), now)

    return await _TIERS.get("prop-tiers", fetch)
