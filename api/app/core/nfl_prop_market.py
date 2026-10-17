"""Settling stored sportsbook prop prices against what happened.

The forward holdout for build-plan item 25: The Odds API sells current markets
only, so the sample can only accrue week by week from prices already stored.
Every priced player-game becomes one case, and a case the book would void is
never scored as a miss.

Pure: no DB, no I/O.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from app.core.nfl_prop_odds import devigged_book_probabilities
from app.core.nfl_td_backtest import NflTdScore, brier, log_loss


class PropOutcome(str, Enum):
    SCORED = "scored"
    NOT_SCORED = "not_scored"
    DID_NOT_PLAY = "did_not_play"


def settle(touchdowns: int | None, offense_snaps: int | None) -> PropOutcome:
    """Anytime-TD result for one priced player-game.

    NFLverse weekly stats hold only players who recorded something, so a missing
    stat row does not mean the player sat: a blocking tight end with snaps and no
    touches played and did not score. Snaps are the fallback evidence. With
    neither, the player is treated as inactive, which the book voids, rather than
    as a loss that would drag every arm's mean predicted above the actual rate.
    """
    if touchdowns is not None:
        return PropOutcome.SCORED if touchdowns > 0 else PropOutcome.NOT_SCORED
    if offense_snaps is not None and offense_snaps > 0:
        return PropOutcome.NOT_SCORED
    return PropOutcome.DID_NOT_PLAY


@dataclass(frozen=True)
class SettledPropRow:
    """One priced player-game in a completed game, before the arms are computed.

    `player_id` is None for a provider name that never resolved: those rows are
    carried so the report can count them, never guessed into a player.
    """
    game_id: int
    season: int
    week: int
    player_id: int | None
    provider_player_name: str
    book_probability: float
    book_count: int
    includes_margin: bool
    total_line: float | None
    # "book" (a stored market total) or "nflverse" (the closing line on the game).
    total_source: str | None
    touchdowns: int | None
    offense_snaps: int | None


@dataclass(frozen=True)
class PropCase:
    """One settled priced player-game, with each arm's probability where it exists.

    The shape item 25c reads when it rates against the market. `book_raw` is the
    stored consensus with the book's margin still in it; `book_devig` is 25a's
    normalization, absent when the game carries no market total; `model` is the
    production anytime-TD probability, absent when the player has too little
    history for a case.
    """
    player_id: int
    game_id: int
    season: int
    week: int
    outcome: PropOutcome
    book_raw: float
    book_devig: float | None
    model: float | None

    @property
    def scored(self) -> bool:
        return self.outcome is PropOutcome.SCORED

    @property
    def is_settled(self) -> bool:
        return self.outcome is not PropOutcome.DID_NOT_PLAY

    @property
    def in_common_subset(self) -> bool:
        """Every arm has a probability, so the arms can be compared on the same rows."""
        return self.is_settled and self.book_devig is not None and self.model is not None


ARMS: tuple[str, ...] = ("book_raw", "book_devig", "model")


def _arm_probability(case: PropCase, arm: str) -> float | None:
    return {"book_raw": case.book_raw, "book_devig": case.book_devig, "model": case.model}[arm]


def build_prop_cases(
    rows: Sequence[SettledPropRow], model_probabilities: Mapping[tuple[int, int, int], float],
) -> list[PropCase]:
    """Settled cases with all three arms, de-vigging one game at a time.

    Unresolved rows carry no player and no result, so they leave the sample here
    and survive only as a coverage count. De-vigging is per game because the
    margin is measured against the game's expected scorers, and a price that
    already has both sides is left alone, matching the slate.
    """
    by_game: dict[int, list[SettledPropRow]] = {}
    for row in rows:
        if row.player_id is not None:
            by_game.setdefault(row.game_id, []).append(row)

    cases: list[PropCase] = []
    for game_rows in by_game.values():
        marginal = {row.player_id: row.book_probability for row in game_rows if row.includes_margin}
        devigged = devigged_book_probabilities(marginal, game_rows[0].total_line)
        for row in game_rows:
            cases.append(PropCase(
                player_id=row.player_id, game_id=row.game_id, season=row.season, week=row.week,
                outcome=settle(row.touchdowns, row.offense_snaps),
                book_raw=row.book_probability,
                book_devig=devigged.get(row.player_id),
                model=model_probabilities.get((row.player_id, row.season, row.week)),
            ))
    return cases


def score_arm(cases: Sequence[PropCase], arm: str) -> NflTdScore | None:
    """One arm over the common subset. None when nothing has settled yet."""
    subset = [case for case in cases if case.in_common_subset]
    if not subset:
        return None
    probabilities = [_arm_probability(case, arm) for case in subset]
    outcomes = [case.scored for case in subset]
    return NflTdScore(
        games=len(subset), log_loss=log_loss(probabilities, outcomes), brier=brier(probabilities, outcomes),
        mean_predicted=sum(probabilities) / len(subset),
        actual_rate=sum(outcomes) / len(subset),
    )


def by_week(cases: Sequence[PropCase]) -> list[tuple[tuple[int, int], list[PropCase]]]:
    weeks: dict[tuple[int, int], list[PropCase]] = {}
    for case in cases:
        weeks.setdefault((case.season, case.week), []).append(case)
    return sorted(weeks.items())


@dataclass(frozen=True)
class PropCoverage:
    """What the sample holds and what it lost, so a shrinking arm is visible."""
    priced_player_games: int
    unresolved: int
    settled: int
    did_not_play: int
    missing_total: int
    missing_model: int
    common_subset: int


def coverage(rows: Sequence[SettledPropRow], cases: Sequence[PropCase]) -> PropCoverage:
    settled = [case for case in cases if case.is_settled]
    return PropCoverage(
        priced_player_games=len(rows),
        unresolved=sum(1 for row in rows if row.player_id is None),
        settled=len(settled),
        did_not_play=sum(1 for case in cases if not case.is_settled),
        missing_total=sum(1 for case in settled if case.book_devig is None),
        missing_model=sum(1 for case in settled if case.model is None),
        common_subset=sum(1 for case in cases if case.in_common_subset),
    )
