import asyncio
import gzip

import httpx
import pytest

from app.ingest.nflverse import SeasonNotPublished
from app.ingest.nflverse_team_efficiency import (
    NflverseTeamEfficiency,
    fetch_team_efficiency,
    parse_team_efficiency,
)

# Published column names, in a subset: the real file has ~370 columns and DictReader
# ignores the rest.
HEADER = "play_id,game_id,season,season_type,home_team,away_team,posteam,play_type,two_point_attempt,epa"
GAME = "2024_01_ARI_BUF"


def _play(play_type: str, epa: str, *, posteam: str = "BUF", two_point: str = "0",
          season_type: str = "REG", season: str = "2024", game: str = GAME) -> str:
    return f"1,{game},{season},{season_type},BUF,ARI,{posteam},{play_type},{two_point},{epa}"


def _parse(*plays: str) -> dict[tuple[str, bool], NflverseTeamEfficiency]:
    return {(row.game_id, row.is_home): row for row in parse_team_efficiency([HEADER, *plays], 2024)}


def test_runs_and_passes_sum_into_one_home_offense_row() -> None:
    row = _parse(_play("run", "0.5"), _play("pass", "-0.25"))[(GAME, True)]
    assert (row.plays, row.successes) == (2, 1)
    assert row.epa == pytest.approx(0.25)


def test_sacks_and_scrambles_count_because_they_arrive_as_passes() -> None:
    # NFLverse files both a sack and a scramble under play_type `pass`.
    row = _parse(_play("pass", "-1.8"), _play("pass", "0.9"))[(GAME, True)]
    assert row.plays == 2


@pytest.mark.parametrize("play_type", ["no_play", "qb_kneel", "qb_spike", "punt", "field_goal", ""])
def test_non_offensive_play_types_are_excluded(play_type: str) -> None:
    assert _parse(_play(play_type, "0.4")) == {}


def test_two_point_attempts_are_excluded() -> None:
    assert _parse(_play("pass", "0.7", two_point="1")) == {}


@pytest.mark.parametrize("epa", ["", "NA"])
def test_plays_without_epa_are_excluded(epa: str) -> None:
    assert _parse(_play("run", epa)) == {}


def test_zero_epa_is_a_play_but_not_a_success() -> None:
    row = _parse(_play("run", "0"))[(GAME, True)]
    assert (row.plays, row.successes) == (1, 0)


def test_postseason_and_other_season_rows_are_ignored() -> None:
    assert _parse(_play("run", "0.5", season_type="POST"), _play("run", "0.5", season="2023")) == {}


def test_each_offense_in_a_game_gets_its_own_row() -> None:
    rows = _parse(_play("run", "0.5"), _play("pass", "0.2", posteam="ARI"), _play("run", "-0.1", posteam="ARI"))
    assert rows[(GAME, True)].plays == 1
    away = rows[(GAME, False)]
    assert (away.plays, away.successes) == (2, 1)
    assert away.epa == pytest.approx(0.1)


@pytest.mark.parametrize("posteam", ["", "KC"])
def test_offense_outside_the_game_is_skipped(posteam: str) -> None:
    assert _parse(_play("run", "0.5", posteam=posteam)) == {}


def _fetch(status: int, body: bytes = b"") -> list[NflverseTeamEfficiency]:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/pbp/play_by_play_2024.csv.gz")
        return httpx.Response(status, content=body)

    async def go() -> list[NflverseTeamEfficiency]:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_team_efficiency(client, 2024)

    return asyncio.run(go())


def test_fetch_decompresses_and_parses_the_season_archive() -> None:
    body = gzip.compress("\n".join([HEADER, _play("run", "0.5")]).encode())

    assert [(row.game_id, row.is_home, row.plays) for row in _fetch(200, body)] == [(GAME, True, 1)]


def test_an_unpublished_season_names_the_season_and_asset() -> None:
    with pytest.raises(SeasonNotPublished) as caught:
        _fetch(404)

    assert "play-by-play" in str(caught.value)
