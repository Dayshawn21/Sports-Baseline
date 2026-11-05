import asyncio
import datetime as dt
from decimal import Decimal
from typing import cast
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import nhl_over_probability_fit as fit
from app.core.count_over_probability import NegBinParams
from app.core.nhl_over_probability_crossfit import read_family
from app.core.nhl_projection_backtest import NhlHistoryRow
from app.nhl.markets import NhlLineOnlyMarket
from app.repositories import nhl
from app.schemas.nhl_context import NhlGameContextSchema, NhlGoalieContext, NhlGoalieSide, NhlInjuryContext, NhlInjurySchema
from app.services.nhl.line_only_props import line_only_props
from app.services.nhl import projections as projection_service
from app.services.nhl.projections import NO_INPUTS, ProjectionInputs, load_projection_inputs

FETCH = dt.datetime(2026, 10, 24, 12, tzinfo=dt.UTC)
GAME = {"game_id": 1, "home_team": "CHI", "away_team": "TBL"}
SKATER, GOALIE, OTHER_GOALIE, ROOKIE = 7, 20, 21, 8


def line(player_id: int, market: str, value: str, team: str = "TB", position: str = "C") -> dict[str, object]:
    return {
        "provider": "prizepicks", "provider_prop_id": f"{player_id}-{market}", "player_id": player_id,
        "player_name": f"Player {player_id}", "position": position, "team": team, "market": market,
        "odds_type": "standard", "line": Decimal(value), "fetched_at": FETCH,
    }


def skater_rows(player_id: int, count: int) -> list[NhlHistoryRow]:
    stats = {"shots": 3, "time_on_ice_seconds": 1200}
    return [
        NhlHistoryRow(player_id, i, 2026, dt.date(2026, 10, 1) + dt.timedelta(days=i), "REG", "C", False, True, stats)
        for i in range(count)
    ]


def goalie_rows(player_id: int) -> list[NhlHistoryRow]:
    stats = {"saves": 26, "goals_against": 2, "time_on_ice_seconds": 3600}
    return [
        NhlHistoryRow(player_id, i, 2026, dt.date(2026, 10, 1) + dt.timedelta(days=i), "REG", "G", True, True, stats)
        for i in range(6)
    ]


def context(away_status: str = "confirmed", away_goalie: int | None = GOALIE, injured: int | None = None) -> NhlGameContextSchema:
    injuries = []
    if injured is not None:
        injuries = [NhlInjurySchema(
            espn_athlete_id="9", player_id=injured, player_name="X", team="TBL", status="Out", detail=None,
            source_updated_at=None, return_date=None, link_reason="matched", team_mismatch=False,
        )]
    return NhlGameContextSchema(
        injuries=NhlInjuryContext(fetched_at=FETCH, freshness="fresh", away=injuries),
        goalies=NhlGoalieContext(
            fetched_at=FETCH, freshness="fresh",
            away=NhlGoalieSide(team="TBL", player_id=away_goalie, status=away_status),
            home=NhlGoalieSide(team="CHI", status="not_reported"),
        ),
    )


def projections(lines: list[dict[str, object]], inputs: ProjectionInputs):  # noqa: ANN201
    return {(row.player_id, row.market.value): row.projection for row in line_only_props(GAME, lines, inputs).lines}


def test_skater_line_gets_the_twenty_game_mean_and_gap() -> None:
    result = projections([line(SKATER, "shots_on_goal", "2.5")], ProjectionInputs({SKATER: skater_rows(SKATER, 12)}, context()))
    served = result[(SKATER, "shots_on_goal")]
    assert (served.value, served.gap, served.flags, served.games_in_sample) == (3.0, 0.5, [], 12)
    assert served.model_version == "nhl-reference-v1"


def test_confirmed_goalie_gets_a_number_and_an_unconfirmed_one_gets_only_the_reason() -> None:
    history = {GOALIE: goalie_rows(GOALIE), OTHER_GOALIE: goalie_rows(OTHER_GOALIE)}
    result = projections(
        [line(GOALIE, "goalie_saves", "24.5", position="G"), line(OTHER_GOALIE, "goalie_saves", "24.5", position="G")],
        ProjectionInputs(history, context()),
    )
    assert result[(GOALIE, "goalie_saves")].value == 26.0
    unconfirmed = result[(OTHER_GOALIE, "goalie_saves")]
    assert (unconfirmed.value, unconfirmed.gap, unconfirmed.flags) == (None, None, ["other_starter_expected"])


def test_goalie_with_no_context_at_all_has_no_number() -> None:
    result = projections([line(GOALIE, "goalie_saves", "24.5", position="G")], ProjectionInputs({GOALIE: goalie_rows(GOALIE)}, None))
    assert result[(GOALIE, "goalie_saves")].flags == ["no_goalie_report"]


def test_player_with_too_few_games_is_not_served() -> None:
    result = projections([line(ROOKIE, "shots_on_goal", "2.5")], ProjectionInputs({ROOKIE: skater_rows(ROOKIE, 4)}, context()))
    served = result[(ROOKIE, "shots_on_goal")]
    assert (served.value, served.flags, served.games_in_sample) == (None, ["few_prior_games"], 4)


def test_out_skater_loses_the_number_and_a_player_with_no_history_is_not_served() -> None:
    result = projections(
        [line(SKATER, "shots_on_goal", "2.5"), line(99, "shots_on_goal", "2.5")],
        ProjectionInputs({SKATER: skater_rows(SKATER, 12)}, context(injured=SKATER)),
    )
    assert result[(SKATER, "shots_on_goal")].flags == ["injured_out"]
    assert result[(99, "shots_on_goal")].flags == ["few_prior_games"]


def test_a_line_whose_team_is_not_in_the_game_reads_its_goalie_as_unreported() -> None:
    result = projections(
        [line(GOALIE, "goalie_saves", "24.5", team="BOS", position="G")],
        ProjectionInputs({GOALIE: goalie_rows(GOALIE)}, context()),
    )
    assert result[(GOALIE, "goalie_saves")].flags == ["no_goalie_report"]


def test_no_inputs_never_serves_a_number() -> None:
    result = projections([line(SKATER, "shots_on_goal", "2.5")], NO_INPUTS)
    assert result[(SKATER, "shots_on_goal")].value is None


GAME_ROW = {"game_id": 1, "game_date": dt.date(2026, 10, 24), "season": 2026, "week": 3, "game_type": "REG",
            "start_utc": FETCH, "status": "scheduled", "away_team": "TBL", "home_team": "CHI",
            "away_team_name": "Tampa Bay Lightning", "home_team_name": "Chicago Blackhawks",
            "away_score": None, "home_score": None, "end_period": None}


def test_inputs_are_read_for_one_game_date_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nhl, "get_prior_history", AsyncMock(return_value={}))
    other_day = {**GAME_ROW, "game_id": 2, "game_date": dt.date(2026, 10, 25)}
    with pytest.raises(ValueError, match="one game date"):
        asyncio.run(load_projection_inputs(cast(AsyncSession, object()), [GAME_ROW, other_day], {}, FETCH))
    nhl.get_prior_history.assert_not_awaited()


def test_a_failed_context_read_still_returns_the_history(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(nhl, "get_prior_history", AsyncMock(return_value={7: skater_rows(7, 3)}))
    monkeypatch.setattr(projection_service, "load_contexts", AsyncMock(side_effect=HTTPException(503)))
    db = cast(AsyncSession, object())
    history, contexts = asyncio.run(load_projection_inputs(db, [GAME_ROW], {1: [line(7, "hits", "1.5")]}, FETCH))
    nhl.get_prior_history.assert_awaited_once_with(db, [7], dt.date(2026, 10, 24))
    assert contexts == {} and list(history) == [7]


def test_a_shown_market_line_carries_the_fit_probability_and_the_rounded_complement() -> None:
    result = projections([line(SKATER, "shots_on_goal", "2.5")], ProjectionInputs({SKATER: skater_rows(SKATER, 12)}, context()))
    served = result[(SKATER, "shots_on_goal")]
    expected = round(read_family(NegBinParams(fit.NEGBIN_R["shots_on_goal"]), 3.0, 2.5), 4)
    assert served.p_over == expected and served.flags == []
    assert set(served.model_dump(by_alias=True)) == {"modelVersion", "value", "gamesInSample", "gap", "pOver", "flags"}


def test_a_whole_number_line_and_a_hidden_market_carry_null_probabilities() -> None:
    inputs = ProjectionInputs({SKATER: skater_rows(SKATER, 12)}, context())
    whole = projections([line(SKATER, "shots_on_goal", "3.0")], inputs)[(SKATER, "shots_on_goal")]
    assert (whole.p_over, whole.flags) == (None, ["integer_line"])
    hidden = projections([line(SKATER, "hits", "1.5")], ProjectionInputs({SKATER: skater_rows_with_hits(SKATER)}, context()))
    served = hidden[(SKATER, "hits")]
    assert served.value is not None
    assert (served.p_over, served.flags) == (None, [])


def test_a_gated_goalie_line_carries_no_probability_and_the_wire_keys_are_present() -> None:
    history = {OTHER_GOALIE: goalie_rows(OTHER_GOALIE)}
    response = line_only_props(GAME, [line(OTHER_GOALIE, "goals_allowed", "2.5", position="G")], ProjectionInputs(history, context()))
    wire = response.lines[0].model_dump(mode="json", by_alias=True)["projection"]
    assert wire["value"] is None and wire["pOver"] is None and wire["flags"] == ["other_starter_expected"]


def test_the_response_names_the_fit_once_instead_of_on_every_line() -> None:
    inputs = ProjectionInputs({SKATER: skater_rows(SKATER, 12)}, context())
    assert line_only_props(GAME, [line(SKATER, "shots_on_goal", "2.5")], inputs).over_probability_version == "nhl-pover-v1"


def skater_rows_with_hits(player_id: int) -> list[NhlHistoryRow]:
    stats = {"hits": 2, "time_on_ice_seconds": 1200}
    return [
        NhlHistoryRow(player_id, i, 2026, dt.date(2026, 10, 1) + dt.timedelta(days=i), "REG", "C", False, True, stats)
        for i in range(12)
    ]


@pytest.mark.parametrize(("market", "player_id", "value", "position"), [
    ("shots_on_goal", SKATER, "2.5", "C"), ("shots_on_goal", SKATER, "3.0", "C"), ("hits", SKATER, "1.5", "C"),
    ("goalie_saves", GOALIE, "24.5", "G"), ("goals_allowed", OTHER_GOALIE, "2.5", "G"),
])
def test_the_page_value_is_the_frozen_core_value_shaped_for_the_wire(
    market: str, player_id: int, value: str, position: str,
) -> None:
    inputs = ProjectionInputs(
        {SKATER: skater_rows(SKATER, 12), GOALIE: goalie_rows(GOALIE), OTHER_GOALIE: goalie_rows(OTHER_GOALIE)},
        context(),
    )
    market_enum = NhlLineOnlyMarket(market)
    core = projection_service.core_projection(market_enum, player_id, float(value), position, "TBL", inputs)
    wire = projection_service.line_projection(market_enum, player_id, float(value), position, "TBL", inputs)

    assert (wire.model_version, wire.value, wire.games_in_sample, wire.gap, wire.flags) == (
        core.model_version, core.projection, core.games_in_sample, core.gap, list(core.flags),
    )
    assert wire.p_over == projection_service.rounded_probability(core.p_over)
