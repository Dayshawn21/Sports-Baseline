from dataclasses import replace

import pytest

from app.backtest import nfl_game_context
from app.backtest.nfl_game_efficiency import (
    build_features, describe_efficiency_fit, efficiency_report, fit_efficiency, fit_rates, metric_maps,
    missing_efficiency, require_coverage,
)
from app.core.nfl_elo import NflEloGame
from app.core.nfl_game_lines import NflGameLineGame
from app.ingest.nflverse_team_efficiency import NflverseTeamEfficiency

PAIRS = [(("AAA", "BBB"), ("CCC", "DDD")), (("AAA", "CCC"), ("BBB", "DDD")), (("AAA", "DDD"), ("BBB", "CCC"))]


def _games(seasons: range = range(2013, 2023)) -> list[NflGameLineGame]:
    return [
        NflGameLineGame(NflEloGame(f"{season}_{week:02d}_{away}_{home}", season, week, home, away, 24, 20), 3.0, 44.5, None, None)
        for season in seasons for week in range(1, 7)
        for home, away in PAIRS[week % 3]
    ]


def _rows(games: list[NflGameLineGame]) -> dict[tuple[str, bool], NflverseTeamEfficiency]:
    # Team strength is fixed, so ratings have something real to learn.
    strength = {"AAA": 6.0, "BBB": 2.0, "CCC": -2.0, "DDD": -6.0}
    rows: dict[tuple[str, bool], NflverseTeamEfficiency] = {}
    for index, line_game in enumerate(games):
        game = line_game.game
        for is_home, team in ((True, game.home_team), (False, game.away_team)):
            noise = (index * 7 + is_home) % 5 - 2
            rows[(game.game_key, is_home)] = NflverseTeamEfficiency(
                game.game_key, is_home, 60 + int(strength[team]) + noise, strength[team] + noise, 26 + int(strength[team]),
            )
    return rows


def test_metric_maps_turn_sums_into_per_play_rates() -> None:
    maps = metric_maps({("g", True): NflverseTeamEfficiency("g", True, 50, 5.0, 20)})

    assert maps["epa_per_play"][("g", True)] == pytest.approx(0.1)
    assert maps["success_rate"][("g", True)] == pytest.approx(0.4)
    assert maps["plays"][("g", True)] == 50.0


def test_the_coverage_guard_names_final_games_missing_either_side() -> None:
    games = _games(range(2025, 2027))
    rows = _rows(games)
    missing_key = games[0].game.game_key
    del rows[(missing_key, False)]
    # A 2026 game without rows is fine: it is never scored.
    del rows[(games[-1].game.game_key, True)]

    assert missing_efficiency(games, rows) == [missing_key]
    with pytest.raises(ValueError, match=missing_key):
        require_coverage(games, rows)


def test_the_coverage_guard_skips_unplayed_games() -> None:
    games = _games(range(2025, 2026))
    unplayed = replace(games[0], game=replace(games[0].game, home_score=None, away_score=None))
    rows = _rows(games[1:])

    assert missing_efficiency([unplayed, *games[1:]], rows) == []


def test_chosen_rates_ignore_every_holdout_efficiency_row() -> None:
    games = _games()
    rows = _rows(games)
    altered = {
        key: replace(row, epa=-row.epa * 9, plays=row.plays * 2, successes=0) if key[0].startswith("2022") else row
        for key, row in rows.items()
    }

    assert fit_rates(games, metric_maps(altered)) == fit_rates(games, metric_maps(rows))


def _scored(games: list[NflGameLineGame]) -> list[NflGameLineGame]:
    """Vary lines and scores so the residual fit has something to fit."""
    return [
        replace(
            line_game, spread_line=float(index % 7 - 3), total_line=40.0 + index % 9,
            game=replace(line_game.game, home_score=17 + index % 13, away_score=14 + index * 3 % 11),
        )
        for index, line_game in enumerate(games)
    ]


def test_the_fit_ignores_every_holdout_outcome_and_efficiency_row() -> None:
    games = _scored(_games())
    rows = _rows(games)
    flipped_games = [
        replace(g, game=replace(g.game, home_score=g.game.away_score, away_score=(g.game.home_score or 0) + 30))
        if g.game.season == 2022 else g
        for g in games
    ]
    altered_rows = {
        key: replace(row, epa=-row.epa * 9, plays=row.plays * 2, successes=0) if key[0].startswith("2022") else row
        for key, row in rows.items()
    }

    assert fit_efficiency(flipped_games, altered_rows) == fit_efficiency(games, rows)


def test_the_fit_refuses_to_run_with_missing_rows() -> None:
    games = _scored(_games())
    rows = _rows(games)
    del rows[(games[40].game.game_key, True)]

    with pytest.raises(ValueError, match=games[40].game.game_key):
        fit_efficiency(games, rows)


def test_the_verdict_comes_from_the_shared_24e_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    games = _scored(_games())
    rows = _rows(games)
    result = fit_efficiency(games, rows)

    monkeypatch.setattr(nfl_game_context, "context_adopted", lambda score: True)
    report = efficiency_report(games, rows, result)

    assert "TOTAL EFFICIENCY" in report and "SPREAD EFFICIENCY" in report
    assert report.count("Verdict: ADOPTED (provisional)") == 2
    assert describe_efficiency_fit(result).startswith("Learning rates (fit-season next-game MAE): epa_per_play")


def test_features_exist_for_every_game_and_favor_the_stronger_home_offense() -> None:
    games = _games()
    maps = metric_maps(_rows(games))

    features = build_features(games, maps, {"epa_per_play": 0.1, "success_rate": 0.1, "plays": 0.1})

    assert set(features) == {line_game.game.game_key for line_game in games}
    late = [line_game.game.game_key for line_game in games if line_game.game.season == 2022]
    strong_home = next(key for key in late if key.endswith("_AAA"))
    assert features[strong_home].epa_edge > 0
