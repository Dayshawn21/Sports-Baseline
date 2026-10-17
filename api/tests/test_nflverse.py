from datetime import date, datetime, timezone
from pathlib import Path

import httpx
import pytest

from app.ingest.nflverse import (
    RELEASE_RETRY_ATTEMPTS,
    NflverseClient,
    SeasonNotPublished,
    current_nfl_season,
    franchise_code,
    get_release_asset,
    is_retryable_status,
    parse_player_stats,
    parse_schedules,
    player_stats_url,
    schedule_url,
)


def _client(stats_status: int) -> NflverseClient:
    """An NflverseClient whose stats asset answers with the given status."""
    schedule_csv = (
        "game_id,season,week,game_type,gameday,gametime,home_team,away_team,home_score,away_score\n"
        "2030_01_DET_CHI,2030,1,REG,2030-09-13,13:00,CHI,DET,,\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "stats_player_week" in request.url.path:
            return httpx.Response(stats_status, text="" if stats_status == 404 else "player_id\n")
        return httpx.Response(200, text=schedule_csv)

    return NflverseClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


@pytest.mark.anyio
async def test_an_unpublished_season_names_the_season_instead_of_raising_http_status() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        await _client(404).fetch_season(2030)

    assert caught.value.season == 2030
    assert "2030" in str(caught.value)


@pytest.mark.anyio
async def test_a_non_404_stats_failure_still_surfaces_as_an_http_error() -> None:
    # A 500 is a transient upstream fault, not a season that does not exist yet.
    with pytest.raises(httpx.HTTPStatusError):
        await _client(500).fetch_season(2030)


def _scripted_client(*replies: int | Exception) -> tuple[httpx.AsyncClient, list[str]]:
    """A client that answers each request with the next reply; the last one repeats."""
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        reply = replies[min(len(requested), len(replies) - 1)]
        requested.append(request.url.path)
        if isinstance(reply, Exception):
            raise reply
        return httpx.Response(reply, text="ok" if reply == 200 else "")

    return httpx.AsyncClient(transport=httpx.MockTransport(handler)), requested


@pytest.mark.anyio
@pytest.mark.parametrize(
    "first",
    [404, 503, httpx.ConnectTimeout("upload window")],
    ids=["re-upload 404", "server error", "timeout"],
)
async def test_a_transient_failure_is_retried_until_the_asset_answers(first: int | Exception) -> None:
    client, requested = _scripted_client(first, 200)

    response = await get_release_asset(client, schedule_url(2026), timeout=60)

    assert response.status_code == 200
    assert len(requested) == 2


@pytest.mark.anyio
async def test_a_persistent_stats_404_retries_the_budget_then_names_the_unpublished_season() -> None:
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if "stats_player_week" in request.url.path:
            requested.append(request.url.path)
            return httpx.Response(404)
        return httpx.Response(200, text="game_id\n")

    client = NflverseClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    with pytest.raises(SeasonNotPublished):
        await client.fetch_season(2030)

    assert len(requested) == RELEASE_RETRY_ATTEMPTS == 4


@pytest.mark.anyio
async def test_a_forbidden_response_fails_on_the_first_request() -> None:
    client, requested = _scripted_client(403)

    response = await get_release_asset(client, schedule_url(2026), timeout=60)

    assert len(requested) == 1
    with pytest.raises(httpx.HTTPStatusError):
        response.raise_for_status()


@pytest.mark.parametrize(("status", "retried"), [(200, False), (403, False), (429, False), (404, True), (500, True), (503, True)])
def test_only_a_404_or_a_server_error_is_retryable(status: int, retried: bool) -> None:
    assert is_retryable_status(status) is retried


@pytest.mark.parametrize("season", [2022, 2024, 2025, 2026])
def test_player_stats_url_is_season_specific(season: int) -> None:
    assert player_stats_url(season).endswith(f"/stats_player/stats_player_week_{season}.csv")


@pytest.mark.parametrize(
    "today, season",
    [
        (date(2026, 9, 15), 2026),
        (date(2026, 12, 28), 2026),
        # Playoffs and the Super Bowl belong to the season that started last fall.
        (date(2027, 1, 10), 2026),
        (date(2027, 2, 28), 2026),
        # Off-season months name the upcoming season, so a stray run fails loudly
        # on SeasonNotPublished instead of reloading last season.
        (date(2027, 3, 1), 2027),
        (date(2027, 8, 31), 2027),
    ],
)
def test_current_nfl_season(today: date, season: int) -> None:
    assert current_nfl_season(today) == season


def test_player_stats_url_differs_per_season() -> None:
    # The previous aggregate URL was identical for every season, so a wrong season
    # argument was unobservable rather than a 404.
    assert player_stats_url(2025) != player_stats_url(2026)


def test_parse_schedules_keeps_only_regular_season_rows() -> None:
    csv_text = """game_id,season,game_type,week,gameday,weekday,gametime,away_team,away_score,home_team,home_score,location,result,total,overtime,old_game_id,gsis,nfl_detail_id,pfr,pff,espn,ftn,away_rest,home_rest,away_moneyline,home_moneyline,spread_line,away_spread_odds,home_spread_odds,total_line,under_odds,over_odds,div_game,roof,surface,temp,wind
2026_01_DET_CHI,2026,REG,1,2026-09-13,Sunday,13:00,DET,17,CHI,24,Home,7,41,0,,,,,,,,7,7,125,-145,2.5,-110,-110,41.5,-110,-110,0,outdoors,grass,70,8
2026_PRE_DET_CHI,2026,PRE,1,2026-08-13,Thursday,13:00,DET,,CHI,,Home,,,,,,,,,,,,,,,,,,,,,,,,
"""

    games = parse_schedules(csv_text, 2026)

    assert len(games) == 1
    assert games[0].game_id == "2026_01_DET_CHI"
    assert games[0].home_score == 24
    # NFLverse publishes the gametime column as an Eastern wall-clock time.
    # Persisting it as UTC would show a 1 PM kickoff as 8 AM in Central Time.
    assert games[0].start_utc == datetime(2026, 9, 13, 17, 0, tzinfo=timezone.utc)
    # NFLverse's sign: a home moneyline favorite has a positive spread_line.
    assert games[0].spread_line == 2.5
    assert games[0].total_line == 41.5
    assert games[0].home_moneyline == -145
    assert games[0].away_moneyline == 125
    assert games[0].roof == "outdoors"
    assert (games[0].home_rest, games[0].away_rest) == (7, 7)
    assert (games[0].temp, games[0].wind) == (70, 8)


@pytest.mark.parametrize("old, current", [("OAK", "LV"), ("SD", "LAC"), ("STL", "LA"), ("KC", "KC")])
def test_franchise_code_maps_relocated_teams_to_their_current_code(old: str, current: str) -> None:
    assert franchise_code(old) == current


def test_parse_schedules_stores_a_relocated_team_under_its_current_code() -> None:
    csv_text = """game_id,season,game_type,week,gameday,away_team,home_team,away_score,home_score
2015_01_STL_OAK,2015,REG,1,2015-09-13,STL,OAK,20,13
2015_01_SD_KC,2015,REG,1,2015-09-13,SD,KC,17,27
"""

    raiders_game, chiefs_game = parse_schedules(csv_text, 2015)

    assert (raiders_game.home_team, raiders_game.away_team) == ("LV", "LA")
    assert (chiefs_game.home_team, chiefs_game.away_team) == ("KC", "LAC")
    # The NFLverse game id is the join key and stays verbatim.
    assert raiders_game.game_id == "2015_01_STL_OAK"


def test_parse_player_stats_stores_relocated_team_and_opponent_under_current_codes() -> None:
    csv_text = f"""{_STATS_HEADER}
00-0030000,Quarterback,QB,OAK,SD,2019_01_SD_OAK,2019,1,REG,275,34,24,18,4,0,0,0,0,0,0,2,1,0,25.8
"""

    [stat] = parse_player_stats(csv_text, 2019)

    assert (stat.team, stat.opponent) == ("LV", "LAC")


@pytest.mark.anyio
async def test_fetch_schedules_reads_the_whole_history_file_once_and_never_the_stats_asset() -> None:
    schedule_csv = (
        "game_id,season,week,game_type,gameday,home_team,away_team,home_score,away_score\n"
        "2012_01_DAL_NYG,2012,1,REG,2012-09-05,NYG,DAL,17,24\n"
        "2013_01_NYG_DAL,2013,1,REG,2013-09-08,DAL,NYG,36,31\n"
        "2013_01_ARI_STL,2013,1,REG,2013-09-08,STL,ARI,27,24\n"
    )
    requested: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requested.append(request.url.path)
        return httpx.Response(200, text=schedule_csv)

    client = NflverseClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))

    games = await client.fetch_schedules(range(2012, 2014))

    assert len(requested) == 1
    assert "stats_player" not in requested[0]
    assert {season: len(season_games) for season, season_games in games.items()} == {2012: 1, 2013: 2}


def test_parse_schedules_reads_recorded_temperature_and_wind() -> None:
    # Real NFLverse rows: an outdoor game with recorded weather, a dome, and a closed roof.
    csv_text = """game_id,season,game_type,week,gameday,away_team,home_team,roof,temp,wind
2025_01_DAL_PHI,2025,REG,1,2025-09-04,DAL,PHI,outdoors,75,11
2025_01_KC_LAC,2025,REG,1,2025-09-05,KC,LAC,dome,,
2025_01_TB_ATL,2025,REG,1,2025-09-07,TB,ATL,closed,NA,NA
"""

    outdoor, dome, closed = parse_schedules(csv_text, 2025)

    assert (outdoor.roof, outdoor.temp, outdoor.wind) == ("outdoors", 75, 11)
    # Indoor games have no weather: unknown, never zero degrees and calm.
    assert (dome.temp, dome.wind) == (None, None)
    assert (closed.temp, closed.wind) == (None, None)


def test_parse_schedules_keeps_missing_historical_lines_unknown() -> None:
    csv_text = """game_id,season,game_type,week,gameday,away_team,home_team,spread_line,total_line,home_moneyline,away_moneyline,roof,home_rest,away_rest
2026_02_DET_CHI,2026,REG,2,2026-09-20,DET,CHI,,,,,,,
"""

    [game] = parse_schedules(csv_text, 2026)

    assert (
        game.spread_line, game.total_line, game.home_moneyline, game.away_moneyline,
        game.roof, game.home_rest, game.away_rest,
    ) == (None, None, None, None, None, None, None)


# The real NFLverse header spelling. An earlier fixture invented
# "passing_attempts" and "fantasy_tds", which do not exist in the published CSV,
# so it asserted the parser's own mistake back at it and both columns silently
# loaded as zero for a whole season.
_STATS_HEADER = (
    "player_id,player_name,position,recent_team,opponent_team,game_id,season,week,"
    "season_type,passing_yards,attempts,completions,rushing_yards,carries,"
    "receiving_yards,receptions,targets,target_share,air_yards_share,wopr,"
    "passing_tds,rushing_tds,receiving_tds,fantasy_points_ppr"
)


def test_parse_player_stats_maps_supported_prop_inputs() -> None:
    csv_text = f"""{_STATS_HEADER}
00-0030000,Quarterback,QB,CHI,DET,2026_01_DET_CHI,2026,1,REG,275,34,24,18,4,0,0,0,0,0,0,2,1,0,25.8
"""

    stats = parse_player_stats(csv_text, 2026)

    assert len(stats) == 1
    assert stats[0].passing_yards == 275
    assert stats[0].passing_completions == 24
    assert stats[0].rushing_attempts == 4
    assert stats[0].fantasy_points == 25.8


def test_kicking_counts_are_read_and_a_blank_cell_stays_unknown() -> None:
    header = f"{_STATS_HEADER},fg_made,pat_made"
    csv_text = f"""{header}
00-0035000,Kicker,K,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,0,0,0,0,0,0,0,0,0,0,0,9.0,3,2
00-0040000,Receiver,WR,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,12,2,88,7,10,0.30,0.35,0.65,0,0,3,22.1,0,0
00-0045000,Punter,P,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0.0,,
"""

    kicker, receiver, punter = parse_player_stats(csv_text, 2026)

    assert (kicker.fg_made, kicker.pat_made) == (3, 2)
    assert (receiver.fg_made, receiver.pat_made) == (0, 0)
    assert (punter.fg_made, punter.pat_made) == (None, None)


def test_a_file_without_kicking_columns_loads_them_as_unknown() -> None:
    csv_text = f"""{_STATS_HEADER}
00-0030000,Quarterback,QB,CHI,DET,2026_01_DET_CHI,2026,1,REG,275,34,24,18,4,0,0,0,0,0,0,2,1,0,25.8
"""

    [stat] = parse_player_stats(csv_text, 2026)

    assert (stat.fg_made, stat.pat_made) == (None, None)


def test_passing_attempts_is_read_from_the_column_nflverse_actually_publishes() -> None:
    csv_text = f"""{_STATS_HEADER}
00-0030000,Quarterback,QB,CHI,DET,2026_01_DET_CHI,2026,1,REG,275,34,24,18,4,0,0,0,0,0,0,2,1,0,25.8
"""

    assert parse_player_stats(csv_text, 2026)[0].passing_attempts == 34


def test_touchdowns_count_only_player_scoring_for_anytime_td_baselines() -> None:
    # Passing touchdowns belong to the scorer, not the quarterback's anytime-TD rate.
    csv_text = f"""{_STATS_HEADER}
00-0030000,Quarterback,QB,CHI,DET,2026_01_DET_CHI,2026,1,REG,275,34,24,18,4,0,0,0,0,0,0,2,1,0,25.8
00-0040000,Receiver,WR,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,12,2,88,7,10,0.30,0.35,0.65,0,0,3,22.1
"""

    quarterback, receiver = parse_player_stats(csv_text, 2026)

    assert quarterback.touchdowns == 1  # 1 rushing, not 2 passing
    assert receiver.touchdowns == 3  # 3 receiving


# Real header and real rows from stats_player_week_2025.csv (150 columns against
# the legacy file's 53). Hand-written fixtures are what let "passing_attempts" and
# "fantasy_tds" load as zero for a whole season, so this one is not hand-written.
_REAL_SAMPLE = (Path(__file__).parent / "fixtures" / "nflverse_stats_player_week.csv").read_text(
    encoding="utf-8"
)


def _by_name(stats: list, name: str):
    return next(stat for stat in stats if stat.player_name == name)


def test_the_published_header_resolves_team_from_the_renamed_column() -> None:
    # The per-season asset renamed "recent_team" to "team". Reading the old name
    # only would drop every row on the guard rather than fail visibly.
    stats = parse_player_stats(_REAL_SAMPLE, 2025)

    assert len(stats) == 3
    assert {stat.team for stat in stats} == {"KC", "LAC", "BUF"}
    assert _by_name(stats, "Patrick Mahomes").opponent == "LAC"


def test_the_published_header_stores_full_names_not_initials() -> None:
    stats = parse_player_stats(_REAL_SAMPLE, 2025)

    assert {stat.player_name for stat in stats} == {"Patrick Mahomes", "Keenan Allen", "Matt Prater"}


def test_every_stat_field_reads_non_zero_from_a_real_row() -> None:
    mahomes = _by_name(parse_player_stats(_REAL_SAMPLE, 2025), "Patrick Mahomes")

    assert mahomes.passing_yards == 258
    assert mahomes.passing_attempts == 39
    assert mahomes.passing_completions == 24
    assert mahomes.rushing_attempts == 6
    assert mahomes.rushing_yards == 57
    assert mahomes.touchdowns == 1  # 1 rushing, not 1 passing
    assert mahomes.fantasy_points == 26.02


def test_scoring_components_and_prizepicks_points_read_from_a_real_row() -> None:
    mahomes = _by_name(parse_player_stats(_REAL_SAMPLE, 2025), "Patrick Mahomes")

    assert (mahomes.passing_tds, mahomes.interceptions, mahomes.fumbles_lost) == (1, 0, 0)
    assert (mahomes.two_point_conversions, mahomes.return_tds, mahomes.fumble_recovery_tds) == (0, 0, 0)
    # No interception or lost fumble, so the two formulas agree.
    assert mahomes.prizepicks_fantasy_points == mahomes.fantasy_points == 26.02


def test_a_blank_scoring_component_stays_unknown_and_so_do_prizepicks_points() -> None:
    blank_interceptions = _REAL_SAMPLE.replace("passing_interceptions", "renamed_interceptions", 1)
    mahomes = _by_name(parse_player_stats(blank_interceptions, 2025), "Patrick Mahomes")

    assert mahomes.interceptions is None
    assert mahomes.prizepicks_fantasy_points is None
    assert mahomes.passing_tds == 1


def test_receiving_fields_read_non_zero_from_a_real_row() -> None:
    allen = _by_name(parse_player_stats(_REAL_SAMPLE, 2025), "Keenan Allen")

    assert (allen.receptions, allen.receiving_yards, allen.touchdowns) == (7, 68, 1)


def test_receiving_usage_fields_read_from_the_real_nflverse_header() -> None:
    allen = _by_name(parse_player_stats(_REAL_SAMPLE, 2025), "Keenan Allen")

    assert allen.targets == 10
    assert allen.target_share == pytest.approx(0.2941176)
    assert allen.air_yards_share == pytest.approx(0.2602339)
    assert allen.wopr == pytest.approx(0.6233402)


def test_the_published_header_includes_positions_the_legacy_asset_dropped() -> None:
    # The legacy aggregate carried only fantasy skill players, which is why
    # kickers were unmatchable in 19c.
    prater = _by_name(parse_player_stats(_REAL_SAMPLE, 2025), "Matt Prater")

    assert (prater.position, prater.team) == ("K", "BUF")


def test_a_renamed_stat_column_is_visible_as_a_zero_row_not_a_silent_average() -> None:
    # Guards the failure mode directly: drop the column the parser reads and the
    # row still parses, so only a test comparing against the real header catches it.
    without_attempts = _REAL_SAMPLE.replace("attempts", "pass_att", 1)

    assert parse_player_stats(without_attempts, 2025)[0].passing_attempts == 0


def test_missing_optional_stat_columns_do_not_crash_the_parser() -> None:
    csv_text = """player_id,player_name,position,recent_team,opponent_team,game_id,season,week,season_type
00-0030000,Quarterback,QB,CHI,DET,2026_01_DET_CHI,2026,1,REG
"""

    [stat] = parse_player_stats(csv_text, 2026)

    assert (stat.passing_attempts, stat.touchdowns) == (0, 0)
    assert (stat.targets, stat.target_share, stat.air_yards_share, stat.wopr) == (None, None, None, None)
    assert (stat.interceptions, stat.fumbles_lost, stat.prizepicks_fantasy_points) == (None, None, None)


def test_unparseable_usage_values_stay_unknown_rather_than_zero() -> None:
    csv_text = f"""{_STATS_HEADER}
00-0040000,Receiver,WR,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,0,0,88,7,NA,NA,NA,NA,0,0,1,22.1
00-0050000,Tight End,TE,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,0,0,40,4,6.0,0.2,0.1,0.35,0,0,0,8.0
00-0060000,Slot,WR,CHI,DET,2026_01_DET_CHI,2026,1,REG,0,0,0,0,0,12,2,NaN,NaN,inf,-inf,0,0,0,NaN
"""

    unknown, formatted, non_finite = parse_player_stats(csv_text, 2026)

    assert (unknown.targets, unknown.target_share, unknown.air_yards_share, unknown.wopr) == (None, None, None, None)
    assert formatted.targets == 6
    assert (non_finite.targets, non_finite.target_share, non_finite.air_yards_share, non_finite.wopr) == (None, None, None, None)
    assert non_finite.fantasy_points is None
