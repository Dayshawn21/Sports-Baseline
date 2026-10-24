from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from app.nhl.markets import NhlLineOnlyMarket
from app.schemas.nhl import (
    NhlGameDetailResponse, NhlLineOnlyLineSchema, NhlLineOnlyPropsResponse,
    NhlMoneylineSchema, NhlSlateResponse,
)

NOW = datetime(2026, 10, 23, 12, tzinfo=UTC)


def _game(**overrides: object) -> dict[str, object]:
    return {
        "game_id": 1, "season": 2026, "week": None, "game_type": "PST",
        "game_date": date(2026, 10, 23), "start_utc": None, "status": "completed",
        "away_team": "MTL", "home_team": "CHI", "away_team_name": "Montreal",
        "home_team_name": "Chicago", "away_score": 2, "home_score": 3, "end_period": "OT",
        "prop_line_count": 0, "moneyline": None, "spread": None, "total": None,
        "context": {"injuries": {}, "goalies": {"away": {"team": "MTL"}, "home": {"team": "CHI"}}}, **overrides,
    }


def test_detail_and_slate_camel_case_and_missing_data_contract() -> None:
    game = NhlGameDetailResponse.model_validate(_game())
    slate = NhlSlateResponse(date=date(2026, 10, 23), previous_date=None, next_date=None, games=[game])
    wire = slate.model_dump(mode="json", by_alias=True)
    assert wire["date"] == "2026-10-23" and wire["previousDate"] is None
    assert wire["games"][0]["gameId"] == 1 and wire["games"][0]["endPeriod"] == "OT"
    assert wire["games"][0]["lineMovement"] == [] and wire["games"][0]["moneyline"] is None
    assert game.model_dump(by_alias=True)["lineHistory"] == []
    assert NhlLineOnlyPropsResponse(game_id=1, lines=[]).model_dump(by_alias=True) == {"gameId": 1, "lines": []}


@pytest.mark.parametrize("market", list(NhlLineOnlyMarket))
def test_all_line_only_markets_preserve_units_and_offering_identity(market: NhlLineOnlyMarket) -> None:
    line = NhlLineOnlyLineSchema(
        provider="prizepicks", provider_prop_id="offer-2", player_id=7, player_name="Player",
        position=None, team=None, market=market, odds_type="demon", line=20.5, fetched_at=NOW,
    )
    wire = line.model_dump(mode="json", by_alias=True)
    assert wire["line"] == 20.5 and wire["providerPropId"] == "offer-2"
    assert wire["market"] == market.value and wire["fetchedAt"] == "2026-10-23T12:00:00Z"
    assert set(wire) == {"provider", "providerPropId", "playerId", "playerName", "position",
                         "team", "market", "oddsType", "line", "fetchedAt"}


@pytest.mark.parametrize("overrides", [{"game_type": "PRE"}, {"game_type": "PIN"},
                                       {"end_period": "unknown"}, {"start_utc": datetime(2026, 10, 23)}])
def test_invalid_game_type_end_period_and_naive_start_fail_contract(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NhlGameDetailResponse.model_validate(_game(**overrides))


@pytest.mark.parametrize("overrides", [{"book": "pinnacle"}, {"home_win_probability": -0.1},
                                       {"home_win_probability": 1.1}, {"fetched_at": NOW.replace(tzinfo=None)}])
def test_market_probability_book_and_timestamp_contract(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        NhlMoneylineSchema.model_validate({
            "book": "draftkings", "home_odds": -110, "away_odds": 100,
            "home_win_probability": 0.52, "fetched_at": NOW, **overrides,
        })
