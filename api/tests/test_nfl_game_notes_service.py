from datetime import UTC, datetime, timedelta

from app.core.nfl_best_line import Quote
from app.core.nfl_qb_change import QbChange
from app.core.odds import implied_prob_from_american
from app.core.nfl_team_stats import TeamGame, team_stats
from app.services.nfl.game_notes import best_line_schema, game_notes

GAME = {
    "away_team_id": 18, "away_team": "ATL", "away_rest": 4, "home_team_id": 26, "home_team": "GB", "home_rest": 10,
    "away_score": None, "home_score": None,
}
OPENED = datetime(2026, 9, 18, 17, tzinfo=UTC)
LATEST = datetime(2026, 9, 23, 15, tzinfo=UTC)


def _injury(team_id: int, team: str, name: str, position: str, status: str | None, practice: str | None) -> dict:
    return {"team_id": team_id, "team": team, "player_name": name, "position": position,
            "injury_status": status, "practice_status": practice, "injury": "Knee", "player_id": len(name)}


def _depth(team_id: int, team: str, name: str, rank: int, previous: int | None) -> dict:
    return {"team_id": team_id, "team": team, "player_name": name, "player_id": len(name), "depth_team_id": team_id,
            "depth_position": "WR", "depth_rank": rank, "previous_depth_team_id": team_id if previous else None,
            "previous_depth_position": "WR" if previous else None, "previous_depth_rank": previous}


def _move(game_id: int, market: str, open_line: float, current: float, current_at: datetime) -> dict:
    return {"game_id": game_id, "market": market, "book": "draftkings", "open_line": open_line,
            "open_fetched_at": OPENED, "current_line": current, "current_fetched_at": current_at}


def test_notes_keep_this_games_teams_and_drop_full_practice_entries() -> None:
    injuries = [
        _injury(18, "ATL", "Michael Penix Jr.", "QB", None, "Full Participation in Practice"),
        _injury(26, "GB", "Jayden Reed", "WR", "Out", "Did Not Participate In Practice"),
        _injury(18, "ATL", "Drake London", "WR", "Questionable", "Limited Participation in Practice"),
        _injury(12, "BUF", "Other Game", "QB", "Out", None),
    ]

    notes = game_notes(33, GAME, injuries, [], [], {}, {})

    assert [item.player_name for item in notes.injuries] == ["Jayden Reed", "Drake London"]
    assert [item.player_id for item in notes.injuries] == [len("Jayden Reed"), len("Drake London")]


def test_notes_show_only_capped_depth_moves_for_this_games_teams() -> None:
    rows = [_depth(26, "GB", "Starter Up", 1, 2), _depth(26, "GB", "Deep Shuffle", 5, 4), _depth(12, "BUF", "Elsewhere", 1, 2)]

    notes = game_notes(33, GAME, [], rows, [], {}, {})

    assert [(item.player_name, item.change) for item in notes.depth_changes] == [("Starter Up", "promoted")]
    assert notes.model_dump(by_alias=True)["depthChanges"][0]["playerId"] == len("Starter Up")


def test_a_single_stored_line_has_no_move_rather_than_a_zero_move() -> None:
    moves = [_move(33, "spread", -6.5, -5.5, LATEST), _move(33, "total", 46.5, 46.5, OPENED), _move(34, "total", 50.5, 49.0, LATEST)]

    notes = game_notes(33, GAME, [], [], moves, {}, {})

    assert [(item.market, item.move) for item in notes.line_movement] == [("spread", 1.0), ("total", None)]


def test_form_carries_rest_short_week_and_results_from_each_teams_side() -> None:
    recent = {18: [{"week": 2, "opponent": "CAR", "is_home": True, "points_for": 3, "points_against": 34}]}

    notes = game_notes(33, GAME, [], [], [], recent, {})

    assert notes.away_form.short_week and notes.away_form.rest_days == 4
    assert [item.result for item in notes.away_form.recent] == ["L"]
    assert not notes.home_form.short_week and notes.home_form.recent == []


def test_a_game_with_nothing_stored_has_empty_notes() -> None:
    empty = GAME | {"away_rest": None, "home_rest": None}

    notes = game_notes(33, empty, [], [], [], {}, {})

    assert (notes.injuries, notes.depth_changes, notes.line_movement) == ([], [], [])
    assert notes.away_form.rest_days is None and not notes.away_form.short_week
    assert (notes.away_stats.games, notes.away_stats.points.value, notes.away_stats.points.rank) == (0, None, None)


def test_stats_attach_to_each_side_with_league_ranks() -> None:
    stats = team_stats([
        TeamGame(team_id=18, points_for=10, points_against=30, plays_for=60, epa_for=-6.0, successes_for=24),
        TeamGame(team_id=26, points_for=30, points_against=10),
        TeamGame(team_id=12, points_for=20, points_against=20),
    ])

    notes = game_notes(33, GAME, [], [], [], {}, stats)

    assert (notes.away_stats.team, notes.away_stats.games, notes.away_stats.efficiency_games) == ("ATL", 1, 1)
    assert (notes.away_stats.points.value, notes.away_stats.points.rank) == (10.0, 3)
    assert (notes.home_stats.points_allowed.value, notes.home_stats.points_allowed.rank) == (10.0, 1)
    assert notes.away_stats.epa_per_play.value == -0.1
    assert notes.home_stats.epa_per_play.value is None and notes.home_stats.epa_per_play.rank is None
    assert notes.model_dump(by_alias=True)["awayStats"]["epaPerPlay"] == {"value": -0.1, "rank": 1, "observedGames": 1}


def test_recent_stats_attach_to_the_correct_team_and_serialize_attempt_coverage() -> None:
    games = [TeamGame(team_id=18, points_for=10, points_against=20, pass_attempts_for=32),
             TeamGame(team_id=26, points_for=20, points_against=10, rush_attempts_against=24)]
    notes = game_notes(33, GAME, [], [], [], {}, team_stats(games), recent_stats=team_stats(games, last_n=3))
    response = notes.model_dump(by_alias=True)
    assert response["awayRecentStats"]["team"] == "ATL"
    assert response["awayRecentStats"]["passAttempts"] == {"value": 32.0, "rank": 1, "observedGames": 1}
    assert response["homeRecentStats"]["team"] == "GB"
    assert response["homeRecentStats"]["rushAttemptsAllowed"]["value"] == 24.0
    assert response["homeRecentStats"]["passAttempts"]["value"] is None


def test_injury_notes_keep_lineman_and_defender_with_stored_update_time() -> None:
    updated = datetime(2026, 10, 22, 12, tzinfo=UTC)
    rows = [_injury(18, 'ATL', 'Lineman', 'OT', 'Out', None) | {'updated_at': updated},
            _injury(26, 'GB', 'Defender', 'CB', 'Questionable', None) | {'updated_at': updated},
            _injury(12, 'BUF', 'Other game', 'LB', 'Out', None),
            _injury(18, 'ATL', 'Full practice', 'DT', None, 'Full Participation in Practice')]
    notes = game_notes(33, GAME, rows, [], [], {}, {})
    assert [(row.player_name, row.position) for row in notes.injuries] == [('Lineman', 'OT'), ('Defender', 'CB')]
    assert all(row.updated_at == updated for row in notes.injuries)
    assert notes.model_dump(mode='json', by_alias=True)['injuries'][0]['updatedAt'] == '2026-10-22T12:00:00Z'


def test_a_final_game_carries_its_score_and_a_scheduled_one_does_not() -> None:
    final = game_notes(33, GAME | {"away_score": 17, "home_score": 24}, [], [], [], {}, {})
    scheduled = game_notes(33, GAME, [], [], [], {}, {})

    assert (final.away_score, final.home_score) == (17, 24)
    assert final.model_dump(by_alias=True)["homeScore"] == 24
    assert (scheduled.away_score, scheduled.home_score) == (None, None)


def test_each_side_carries_its_own_qb_change() -> None:
    change = QbChange(usual_starter="Jordan Love", reasons=["injured", "backup_started"],
                      injury_status="Out", injury_week=4, last_game_qb="Malik Willis", last_game_week=4)

    notes = game_notes(33, GAME, [], [], [], {}, {}, {26: change, 12: change})

    assert notes.away_qb_change is None
    assert notes.model_dump(by_alias=True)["homeQbChange"] == {
        "team": "GB", "usualStarter": "Jordan Love", "reasons": ["injured", "backup_started"],
        "injuryStatus": "Out", "injuryWeek": 4, "lastGameQb": "Malik Willis", "lastGameWeek": 4, "previousQb1": None,
    }


def _quote(book: str, market: str, line: float | None, first: int, second: int, provider: str = "odds_api_io") -> Quote:
    return Quote(book, provider, market, line, first, second, implied_prob_from_american(first, second)[0], LATEST - timedelta(hours=1))


def test_best_line_rounds_for_display_and_names_the_fair_source() -> None:
    quotes = [
        _quote("pinnacle", "spread", -8.0, -103, -110, provider="the_odds_api_eu"),
        _quote("draftkings", "spread", -8.5, -116, -105),
        _quote("bet365", "spread", -9.5, -108, -114),
        _quote("bet365", "moneyline", None, -500, 370),
    ]

    block = best_line_schema(LATEST + timedelta(days=1), quotes, LATEST)

    dumped = block.model_dump(by_alias=True)
    assert dumped["maxAgeHours"] == 36
    spread = next(market for market in dumped["markets"] if market["market"] == "spread")
    assert spread["fair"]["source"] == "pinnacle" and spread["fair"]["line"] == -8.0
    assert [(side["side"], side["book"], side["pointsVsFair"], side["evPct"]) for side in spread["sides"]] == [
        ("home", "draftkings", -0.5, None), ("away", "bet365", 1.5, None),
    ]
    moneyline = next(market for market in dumped["markets"] if market["market"] == "moneyline")
    assert moneyline["fair"] is None and moneyline["sides"][1]["odds"] == 370


def test_best_line_is_null_once_kicked_off_or_without_a_fresh_book() -> None:
    quotes = [_quote("draftkings", "spread", -3.0, -110, -110)]

    assert best_line_schema(LATEST - timedelta(minutes=1), quotes, LATEST) is None
    assert best_line_schema(None, [_quote("pinnacle", "spread", -3.0, -110, -110, "the_odds_api_eu")], LATEST) is None
    assert best_line_schema(None, quotes, LATEST) is not None


def test_a_game_carries_the_best_line_it_was_given() -> None:
    block = best_line_schema(None, [_quote("draftkings", "total", 47.5, -110, -110)], LATEST)

    assert game_notes(33, GAME, [], [], [], {}, {}, None, block).best_line == block
    assert game_notes(33, GAME, [], [], [], {}, {}).best_line is None
