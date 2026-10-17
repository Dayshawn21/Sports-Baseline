"""The rule that decides whether the closing line moves toward the NFL game model (item 28).

Pre-registered 2026-09-26, before any line movement was read. The entry line is
the earliest stored book line a bettor could have taken once the previous week's
results were known; CLV is how far the close then moved toward the model.
Changing any constant here starts a new rule; it is never a re-read of the old one.

Every line is in book sign: a home spread is negative when the home team is favored.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import sqrt
from statistics import median, stdev
from typing import Literal

from app.core.nfl_game_lines import PickRecord, pick_record

Market = Literal["spread", "total"]
Verdict = Literal["pass", "reject", "accruing"]

PICK_THRESHOLD = 1.5
VERDICT_PICKS = 150
STANDARD_ERRORS_REQUIRED = 2.0
# A week's results must be in before its ratings are current; the late game ends about 3.5 hours after kickoff.
WINDOW_AFTER_PREVIOUS_KICKOFF = timedelta(hours=6)
FIRST_WEEK_WINDOW = timedelta(days=7)
# Movement over the last day is too small to act on, so an entry line that late does not count.
MIN_LEAD = timedelta(hours=24)
PREFERRED_BOOK = "draftkings"


@dataclass(frozen=True)
class OddsCandidate:
    """One stored pre-kickoff `sport_game_odds` row for a game and market."""

    id: int
    book: str
    line: float
    fetched_at: datetime


@dataclass(frozen=True)
class ClvGame:
    """A regular-season game with its NFLverse closing lines and every pre-kickoff odds row."""

    game_key: str
    week: int
    kickoff: datetime | None
    completed: bool
    home_score: int | None
    away_score: int | None
    # NFLverse sign: positive when the home team is favored, the opposite of a book.
    spread_line: float | None
    total_line: float | None
    # None in the season's first week.
    previous_week_last_kickoff: datetime | None
    candidates: dict[Market, list[OddsCandidate]]


@dataclass(frozen=True)
class ClvPick:
    game_key: str
    week: int
    market: Market
    model: float
    entry: float
    close: float
    # The actual home margin for a spread, total points for a total.
    outcome: int

    @property
    def direction(self) -> int:
        return 1 if self.model > self.entry else -1

    @property
    def clv(self) -> float:
        """Points the close moved toward the model; negative when it moved away."""
        return (self.close - self.entry) * self.direction


def window_open(kickoff: datetime, previous_week_last_kickoff: datetime | None) -> datetime:
    if previous_week_last_kickoff is None:
        return kickoff - FIRST_WEEK_WINDOW
    return previous_week_last_kickoff + WINDOW_AFTER_PREVIOUS_KICKOFF


def entry_line(candidates: Iterable[OddsCandidate], opens: datetime, kickoff: datetime) -> OddsCandidate | None:
    """The earliest in-window DraftKings row, else the earliest in-window row from another book."""
    # The current ingest stores The Odds API's lowercase book keys; capitalized names
    # came from an earlier code path (the 2026-09-17 run) and are not trusted.
    eligible = [
        c for c in candidates
        if c.book == c.book.lower() and opens <= c.fetched_at <= kickoff - MIN_LEAD
    ]
    pool = [c for c in eligible if c.book == PREFERRED_BOOK] or eligible
    return min(pool, key=lambda c: (c.fetched_at, c.book, c.id), default=None)


def clv_pick(
    game_key: str, week: int, market: Market, model: float, entry: float, close: float, outcome: int,
) -> ClvPick | None:
    """A pick when the model differs from the entry line by at least the threshold."""
    # Rounded so a float hair under 1.5 still counts, as in `nfl_game_lines.pick_record`.
    if round(abs(model - entry), 9) < PICK_THRESHOLD:
        return None
    return ClvPick(game_key, week, market, model, entry, close, outcome)


@dataclass(frozen=True)
class GameModel:
    """The pinned model's pre-game home spread (book sign) and total for one game."""

    home_spread: float
    total: float


@dataclass(frozen=True)
class ClvMarketGrade:
    market: Market
    # Games with a model, an entry line and a final close, whether or not they became a pick.
    graded: int
    picks: list[ClvPick]
    excluded: Counter[str]
    # Hours from each graded game's entry line to its kickoff.
    lead_hours: list[float]

    @property
    def median_lead_hours(self) -> float | None:
        return median(self.lead_hours) if self.lead_hours else None


def grade_market(games: Sequence[ClvGame], models: Mapping[str, GameModel], market: Market) -> ClvMarketGrade:
    """Turn one market's games into picks, counting every game left out by its reason."""
    # A week counts only once every game in it is final, so a half-played week can never
    # close the verdict sample and then change it.
    unfinished_weeks = {game.week for game in games if not game.completed}
    picks: list[ClvPick] = []
    excluded: Counter[str] = Counter()
    lead_hours: list[float] = []
    for game in games:
        close = _close(game, market)
        model = models.get(game.game_key)
        if not game.completed:
            excluded["not played yet"] += 1
        elif game.week in unfinished_weeks:
            excluded["week not finished"] += 1
        elif close is None or game.kickoff is None or game.home_score is None or game.away_score is None:
            excluded["no closing line or score"] += 1
        elif model is None:
            excluded["no model rating"] += 1
        elif (entry := entry_line(
            game.candidates[market], window_open(game.kickoff, game.previous_week_last_kickoff), game.kickoff,
        )) is None:
            excluded["no entry line"] += 1
        else:
            lead_hours.append((game.kickoff - entry.fetched_at).total_seconds() / 3600)
            outcome = game.home_score - game.away_score if market == "spread" else game.home_score + game.away_score
            modelled = model.home_spread if market == "spread" else model.total
            pick = clv_pick(game.game_key, game.week, market, modelled, entry.line, close, outcome)
            if pick is not None:
                picks.append(pick)
    return ClvMarketGrade(market, len(lead_hours), picks, excluded, lead_hours)


def _close(game: ClvGame, market: Market) -> float | None:
    """The NFLverse close in book sign."""
    if market == "total":
        return game.total_line
    return None if game.spread_line is None else -game.spread_line


@dataclass(frozen=True)
class ClvSummary:
    n: int
    mean_clv: float | None
    # None below two picks, where a spread of outcomes does not exist yet.
    standard_error: float | None
    toward: int
    away: int
    flat: int
    # The model side graded against the entry line: context only, never a verdict input.
    record: PickRecord


@dataclass(frozen=True)
class ClvVerdict:
    verdict: Verdict
    # The fixed verdict sample once it exists, otherwise every pick so far.
    summary: ClvSummary
    weeks: tuple[int, ...]


def summarize(picks: Sequence[ClvPick]) -> ClvSummary:
    clvs = [pick.clv for pick in picks]
    n = len(clvs)
    # `pick_record` reads NFLverse sign (positive = home favored), so book-sign spreads flip.
    signs = [-1 if pick.market == "spread" else 1 for pick in picks]
    return ClvSummary(
        n=n,
        mean_clv=sum(clvs) / n if n else None,
        standard_error=stdev(clvs) / sqrt(n) if n >= 2 else None,
        toward=sum(clv > 0 for clv in clvs),
        away=sum(clv < 0 for clv in clvs),
        flat=sum(clv == 0 for clv in clvs),
        record=pick_record(
            [sign * pick.model for sign, pick in zip(signs, picks)],
            [sign * pick.entry for sign, pick in zip(signs, picks)],
            [pick.outcome for pick in picks],
            PICK_THRESHOLD,
        ),
    )


def verdict_sample(picks: Iterable[ClvPick]) -> list[ClvPick] | None:
    """The first whole weeks whose picks reach `VERDICT_PICKS`, or None while they have not."""
    ordered = sorted(picks, key=lambda pick: pick.week)
    for i, pick in enumerate(ordered):
        last_of_week = i + 1 == len(ordered) or ordered[i + 1].week != pick.week
        if last_of_week and i + 1 >= VERDICT_PICKS:
            return ordered[: i + 1]
    return None


def verdict(picks: Sequence[ClvPick]) -> ClvVerdict:
    sample = verdict_sample(picks)
    if sample is None:
        return ClvVerdict("accruing", summarize(picks), tuple(sorted({pick.week for pick in picks})))
    summary = summarize(sample)
    assert summary.mean_clv is not None and summary.standard_error is not None
    passed = summary.mean_clv - STANDARD_ERRORS_REQUIRED * summary.standard_error > 0
    return ClvVerdict("pass" if passed else "reject", summary, tuple(sorted({pick.week for pick in sample})))
