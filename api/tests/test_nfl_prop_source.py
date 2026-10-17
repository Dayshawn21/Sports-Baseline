import asyncio
from datetime import UTC, date, datetime, timedelta
from typing import cast

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.prop_ranking_check import FrozenLine
from app.services.nfl import prop_source
from app.services.nfl.prop_source import NflPropSource
from app.services.sport_props import ProviderLine, SportPropSource
from tests.test_nfl_prop_predictions import _game, _line, _slate

NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
DB = cast(AsyncSession, object())
SOURCE: SportPropSource = NflPropSource()


def _recorder(calls: list[tuple], name: str, result: object):
    async def fake(*args: object) -> object:
        calls.append((name, *args[1:]))
        return result
    return fake


def test_the_nfl_period_is_the_week_and_every_read_goes_to_the_nfl_repository(monkeypatch) -> None:
    calls: list[tuple] = []
    frozen = [FrozenLine(1, 3, 7, 9, "receptions", "standard", "over", 0.6, 0.4, "v4", None)]
    monkeypatch.setattr(prop_source.nfl_repo, "get_current_week", _recorder(calls, "current", (2026, 4)))
    monkeypatch.setattr(prop_source.nfl_repo, "get_finished_weeks", _recorder(calls, "finished", {1, 2, 3}))
    monkeypatch.setattr(prop_source.nfl_repo, "get_frozen_coverage", _recorder(calls, "coverage", {3: (10, 8)}))
    monkeypatch.setattr(prop_source.nfl_repo, "get_frozen_gradeable_lines", _recorder(calls, "frozen", frozen))

    assert asyncio.run(SOURCE.current_period(DB, NOW)) == (2026, 4)
    assert asyncio.run(SOURCE.finished_periods(DB, 2026)) == {1, 2, 3}
    assert asyncio.run(SOURCE.frozen_coverage(DB, 2026)) == {3: (10, 8)}
    assert asyncio.run(SOURCE.frozen_lines(DB, 2026)) == frozen
    assert calls == [("current", NOW), ("finished", 2026), ("coverage", 2026), ("frozen", 2026)]
    assert (SOURCE.config.code, SOURCE.config.period_label) == ("nfl", "week")


def test_freezable_games_are_the_weeks_slate_with_every_line_as_a_row(monkeypatch) -> None:
    calls: list[tuple] = []
    slate = _slate(_game(1, NOW + timedelta(hours=2), [_line(10), _line(11)]), _game(2, None, [_line(12)]))
    monkeypatch.setattr(prop_source, "build_slate", _recorder(calls, "slate", slate))

    games = asyncio.run(SOURCE.freezable_games(DB, 2026, 4, NOW))

    assert calls == [("slate", 2026, 4, NOW)]
    assert [(game.start_utc, [row.prop_line_id for row in game.rows]) for game in games] == [
        (NOW + timedelta(hours=2), [10, 11]), (None, [12]),
    ]
    assert games[0].rows[0].generated_at == NOW


def test_the_resolver_links_players_and_games_from_one_load(monkeypatch) -> None:
    calls: list[tuple] = []
    monkeypatch.setattr(prop_source.nfl_repo, "get_player_candidates",
                        _recorder(calls, "candidates", [(7, "Jahan Dotson", "ATL", "WR")]))
    monkeypatch.setattr(prop_source.sport_props, "get_game_index",
                        _recorder(calls, "games", {("ATL", date(2026, 10, 5)): 40}))
    monkeypatch.setattr(prop_source.sport_props, "get_player_aliases", _recorder(calls, "aliases", {}))

    resolve = asyncio.run(SOURCE.load_resolver(DB))
    kickoff = datetime(2026, 10, 5, 17, 0, tzinfo=UTC)
    linked = resolve(ProviderLine("Jahan Dotson", "ATL", "WR", kickoff))
    unknown = resolve(ProviderLine("Nobody Here", "ATL", "WR", kickoff))

    assert calls == [("candidates",), ("games", "nfl"), ("aliases", "nfl")]
    assert (linked.player_id, linked.game_id, linked.matched) == (7, 40, True)
    assert (unknown.player_id, unknown.game_id, unknown.matched) == (None, 40, False)
    assert linked.reason == "unique_name"
