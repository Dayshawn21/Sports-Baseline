from datetime import date, timedelta

import pytest

from app.core.tennis_player import (
    EloSnapshot,
    PlayerMatchRow,
    ServeReturnStats,
    elo_summary,
    record_splits,
    tour_average,
)

AS_OF = date(2026, 9, 29)


def _m(days_ago: int = 10, *, won: bool = True, score: str | None = "6-4 6-3", surface: str | None = "Hard",
       best_of: int = 3, rank: int | None = 50) -> PlayerMatchRow:
    return PlayerMatchRow(AS_OF - timedelta(days=days_ago), surface, best_of, won, score, rank)


def _wl(split):
    return split.wins, split.losses


def test_wins_and_losses_by_surface():
    splits = record_splits([_m(), _m(won=False, score="4-6 3-6"), _m(surface="Clay"), _m(surface=None)], AS_OF)

    assert _wl(splits.all) == (3, 1)
    assert _wl(splits.hard) == (1, 1)
    assert _wl(splits.clay) == (1, 0)
    assert _wl(splits.grass) == (0, 0)


def test_the_window_is_the_365_days_before_as_of():
    splits = record_splits([_m(365), _m(366), _m(0)], AS_OF)

    assert splits.window_start == AS_OF - timedelta(days=365)
    assert _wl(splits.all) == (1, 0)


def test_vs_top20_skips_an_unranked_opponent():
    splits = record_splits([_m(rank=20), _m(rank=21), _m(rank=None, won=False, score="4-6 3-6")], AS_OF)

    assert _wl(splits.vs_top20) == (1, 0)


def test_deciding_sets_go_the_full_distance():
    splits = record_splits([
        _m(score="6-4 3-6 6-2"),
        _m(won=False, score="4-6 6-3 2-6"),
        _m(score="6-4 6-4"),
        _m(best_of=5, score="6-4 3-6 6-4 3-6 7-5"),
        _m(best_of=5, score="6-4 3-6 6-4 6-4"),
    ], AS_OF)

    assert _wl(splits.deciding_sets) == (2, 1)


def test_tie_break_sets_count_from_the_players_side():
    splits = record_splits([_m(score="7-6 6-7 7-6"), _m(won=False, score="6-7 6-4 6-7")], AS_OF)

    # Won 7-6 twice and lost 6-7 once in the first match; lost 6-7 twice in the second.
    assert _wl(splits.tie_breaks) == (2, 3)


def test_a_retirement_counts_in_the_record_but_not_the_set_splits():
    splits = record_splits([_m(score="7-6 3-6 2-1"), _m(score="")], AS_OF)

    assert _wl(splits.all) == (1, 0)
    assert _wl(splits.tie_breaks) == (0, 0)
    assert _wl(splits.deciding_sets) == (0, 0)


def test_tour_average_skips_small_samples_and_missing_values():
    rows = [
        (20, ServeReturnStats(hold_pct=0.80, aces_per_game=0.10)),
        (10, ServeReturnStats(hold_pct=0.70, aces_per_game=None)),
        (9, ServeReturnStats(hold_pct=0.10, aces_per_game=0.50)),
    ]

    average = tour_average(rows, min_matches=10)

    assert average.players == 2
    assert average.stats.hold_pct == pytest.approx(0.75)
    assert average.stats.aces_per_game == pytest.approx(0.10)
    assert average.stats.df_per_game is None


def test_elo_summary_with_history():
    history = [
        EloSnapshot(date(2026, 3, 2), 1900.0, 1910.0, None, None),
        EloSnapshot(date(2026, 1, 5), 1878.0, None, None, None),
        EloSnapshot(date(2026, 8, 24), 1942.0, 1968.0, 1881.0, 1903.0),
    ]

    summary = elo_summary(history)

    assert summary.latest.as_of == date(2026, 8, 24)
    assert summary.change == pytest.approx(64.0)


def test_elo_summary_with_one_snapshot_and_with_none():
    one = elo_summary([EloSnapshot(date(2026, 1, 5), 1878.0, None, None, None)])

    assert one.latest.overall == 1878.0
    assert one.change is None
    empty = elo_summary([])
    assert empty.latest is None
    assert empty.change is None
