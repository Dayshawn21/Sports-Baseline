from datetime import date, datetime, timedelta, timezone

from app.core.nba_resolution import index_nba_candidates, resolve_nba_line
from app.core.nfl_resolution import PlayerCandidate, Resolution, resolve_player

EASTERN = timezone(timedelta(hours=-4))
CANDIDATES = index_nba_candidates([
    PlayerCandidate(1, "Egor Demin", "BKN", "G"),
    PlayerCandidate(2, "Stephen Curry", "GS", "G"),
    PlayerCandidate(3, "Seth Curry", "CHA", "G"),
    PlayerCandidate(4, "Julius Randle", "MIN", "F"),
    PlayerCandidate(5, "Jalen Brunson", "NY", "G"),
    PlayerCandidate(6, "Nikola Jokić", "DEN", "C"),
])
OPENING = date(2026, 10, 20)
GAMES = {("NY", OPENING): 100, ("CLE", OPENING): 100, ("BKN", OPENING): 200, ("MIN", OPENING): 300}


def _resolve(name: str, team: str | None, hour: int = 19, minute: int = 0):
    start = datetime(2026, 10, 20, hour, minute, tzinfo=EASTERN)
    return resolve_nba_line(name, team, start, CANDIDATES, GAMES)


def test_accented_provider_name_links_to_the_ascii_player() -> None:
    result, game_id = _resolve("Egor Dëmin", "BKN")
    assert (result.player_id, game_id) == (1, 200)


def test_accented_stored_name_is_folded_too() -> None:
    result, _ = _resolve("Nikola Jokic", "DEN")
    assert result.player_id == 6


def test_shared_initial_and_surname_resolve_by_full_name() -> None:
    stephen, _ = _resolve("Stephen Curry", "GSW")
    seth, _ = _resolve("Seth Curry", "CHA")
    assert (stephen.player_id, stephen.reason) == (2, Resolution.FULL_NAME)
    assert (seth.player_id, seth.reason) == (3, Resolution.FULL_NAME)


def test_prizepicks_team_code_finds_the_espn_game() -> None:
    result, game_id = _resolve("Jalen Brunson", "NYK")
    assert (result.player_id, game_id) == (5, 100)


def test_late_tip_on_the_next_utc_day_finds_the_eastern_date_game() -> None:
    _, game_id = _resolve("Jalen Brunson", "NYK", hour=22, minute=30)
    assert game_id == 100


def test_unstored_rookie_has_no_player_but_still_gets_the_game() -> None:
    result, game_id = _resolve("Unknown Rookie", "NYK")
    assert (result.player_id, result.reason, game_id) == (None, Resolution.NO_CANDIDATE, 100)


def test_hyphenated_position_never_contradicts() -> None:
    # "J. Randle" matches no full name, so resolution reaches the position step. NFL's
    # resolver, given PrizePicks' "F-C", rejects both stored forwards as contradicted.
    index = index_nba_candidates([
        PlayerCandidate(4, "Julius Randle", "MIN", "F"),
        PlayerCandidate(7, "Jalen Randle", "LAL", "F"),
    ])
    assert resolve_player("J. Randle", "MIN", "F-C", index).reason is Resolution.CONTRADICTED
    start = datetime(2026, 10, 20, 19, tzinfo=EASTERN)
    result, _ = resolve_nba_line("J. Randle", "MIN", start, index, GAMES)
    assert (result.player_id, result.reason) == (4, Resolution.TEAM_TIEBREAK)
