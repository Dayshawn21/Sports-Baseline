import asyncio
from datetime import UTC, datetime, timedelta

from app.core.prop_predictions import FreezableGame, PropPredictionRow, freeze_rows
from app.core.prop_sports import FULL_GAME_SEGMENT, SportPropConfig
from app.services import prop_predictions

NOW = datetime(2026, 10, 21, 22, 0, tzinfo=UTC)
TOY = SportPropConfig("toy", "TOY", {}, frozenset({FULL_GAME_SEGMENT}), {}, "round")


def _row(line_id: int) -> PropPredictionRow:
    return PropPredictionRow(line_id, "toy-v1", None, 20.0, None, None, 1.5, [], {"odds_type": "standard"}, NOW)


GAMES = [
    FreezableGame(NOW + timedelta(hours=1), [_row(1), _row(2)]),
    FreezableGame(NOW, [_row(3)]),
    FreezableGame(None, [_row(4)]),
]


def test_only_games_that_have_not_started_are_frozen() -> None:
    rows, counts = freeze_rows(GAMES, NOW)

    assert [row.prop_line_id for row in rows] == [1, 2]
    assert counts == {"frozen": 2, "kicked_off": 1, "no_start_time": 1}


class _Source:
    config = TOY
    model_version = "toy-v1"
    over_probability_version = "toy-pover-v1"

    def __init__(self, current: tuple[int, int] | None) -> None:
        self.current = current
        self.asked: list[tuple] = []

    async def current_period(self, db, now):
        return self.current

    async def freezable_games(self, db, season, period, now):
        self.asked.append((season, period, now))
        return GAMES


class _Db:
    def __init__(self) -> None:
        self.commits = 0

    async def commit(self) -> None:
        self.commits += 1


def test_a_run_freezes_the_current_period_under_the_sports_code(monkeypatch) -> None:
    stored: list[tuple] = []

    async def insert(db, sport, rows):
        stored.append((sport, [row.prop_line_id for row in rows]))
        return len(rows) - 1

    monkeypatch.setattr(prop_predictions.sport_props, "insert_prop_predictions", insert)
    source, db = _Source((2026, 3)), _Db()

    run = asyncio.run(prop_predictions.freeze_current_period(db, source, NOW, dry_run=False))

    assert source.asked == [(2026, 3, NOW)]
    assert stored == [("toy", [1, 2])] and db.commits == 1
    assert run is not None and (run.season, run.period, run.inserted) == (2026, 3, 1)


def test_a_dry_run_writes_nothing_and_no_schedule_means_no_run(monkeypatch) -> None:
    async def insert(*args):
        raise AssertionError("a dry run must not write")

    monkeypatch.setattr(prop_predictions.sport_props, "insert_prop_predictions", insert)
    db = _Db()

    run = asyncio.run(prop_predictions.freeze_current_period(db, _Source((2026, 3)), NOW, dry_run=True))

    assert run is not None and run.inserted is None and len(run.rows) == 2 and db.commits == 0
    assert asyncio.run(prop_predictions.freeze_current_period(db, _Source(None), NOW, dry_run=False)) is None
