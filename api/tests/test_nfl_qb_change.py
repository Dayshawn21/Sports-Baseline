from app.core.nfl_qb_change import Qb, QbGame, QbInjury, attempts_leader, last_game_leader, qb_change

MAYFIELD = Qb(player_id=1, name="Baker Mayfield")
DANIELS = Qb(player_id=2, name="Jalon Daniels")
PENIX = Qb(player_id=3, name="Michael Penix Jr.")
RUSH = Qb(player_id=4, name="Cooper Rush")


def _game(recency: int, qb: Qb, attempts: int = 34, season: int = 2026) -> QbGame:
    return QbGame(season=season, week=5 - recency, recency=recency, qb=qb, attempts=attempts)


def _starts(qb: Qb, recencies: range, season: int = 2026) -> list[QbGame]:
    return [_game(recency, qb, season=season) for recency in recencies]


def test_a_healthy_qb1_who_played_the_last_game_has_no_change() -> None:
    assert qb_change(_starts(MAYFIELD, range(1, 5)), {MAYFIELD.player_id: QbInjury(4, "Questionable")}, MAYFIELD, MAYFIELD) is None


def test_an_injured_qb1_and_his_backup_both_name_their_week() -> None:
    games = [_game(1, DANIELS, 27), _game(2, MAYFIELD), _game(2, DANIELS, 3), *_starts(MAYFIELD, range(3, 5))]

    change = qb_change(games, {MAYFIELD.player_id: QbInjury(4, "Out")}, MAYFIELD, MAYFIELD)

    assert change is not None
    assert change.reasons == ["injured", "backup_started"]
    assert (change.usual_starter, change.injury_status, change.injury_week) == ("Baker Mayfield", "Out", 4)
    assert (change.last_game_qb, change.last_game_week, change.previous_qb1) == ("Jalon Daniels", 4, None)


def test_the_chart_starter_beats_fill_ins_who_threw_more() -> None:
    games = [_game(1, PENIX, 25), _game(2, RUSH, 22), _game(3, RUSH, 30)]

    assert qb_change(games, {}, PENIX, PENIX) is None


def test_a_qb1_change_names_the_previous_qb1() -> None:
    change = qb_change(_starts(PENIX, range(1, 3)), {}, PENIX, RUSH)

    assert change is not None
    assert (change.reasons, change.previous_qb1) == (["depth_chart"], "Cooper Rush")


def test_a_practice_only_report_is_not_an_injury() -> None:
    assert qb_change(_starts(MAYFIELD, range(1, 3)), {MAYFIELD.player_id: QbInjury(5, None)}, MAYFIELD, None) is None


def test_without_a_chart_the_attempts_leader_is_the_usual_starter() -> None:
    games = [_game(1, DANIELS, 27), *_starts(MAYFIELD, range(2, 5))]

    change = qb_change(games, {}, None, None)

    assert change is not None
    assert (change.usual_starter, change.reasons) == ("Baker Mayfield", ["backup_started"])


def test_last_seasons_starter_never_outvotes_this_seasons() -> None:
    games = [*[_game(recency, DANIELS, 25) for recency in range(1, 5)], *_starts(MAYFIELD, range(5, 9), season=2025)]

    assert attempts_leader(games) == DANIELS


def test_tied_attempts_go_to_the_more_recent_qb() -> None:
    assert attempts_leader([_game(1, DANIELS, 60), _game(2, MAYFIELD, 30), _game(3, MAYFIELD, 30)]) == DANIELS


def test_a_last_game_tie_keeps_the_usual_starter() -> None:
    leader = last_game_leader([_game(1, DANIELS, 20), _game(1, MAYFIELD, 20)], MAYFIELD)

    assert leader is not None and leader.qb == MAYFIELD


def test_a_team_with_no_chart_and_no_games_has_no_change() -> None:
    assert qb_change([], {}, None, None) is None
