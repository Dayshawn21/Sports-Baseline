"""Pure parsing and orientation for The Odds API NFL game-odds markets."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from math import isfinite
from typing import Mapping

from app.core.odds import implied_prob_from_american


@dataclass(frozen=True)
class NflGameMarket:
    market: str
    line: float | None
    first_side: str
    second_side: str
    first_odds: int
    second_odds: int
    first_market_prob: float
    second_market_prob: float
    raw_market: dict[str, object]


_TEAM_CODES = {
    "arizona cardinals": "ARI", "atlanta falcons": "ATL", "baltimore ravens": "BAL", "buffalo bills": "BUF", "carolina panthers": "CAR", "chicago bears": "CHI", "cincinnati bengals": "CIN", "cleveland browns": "CLE", "dallas cowboys": "DAL", "denver broncos": "DEN", "detroit lions": "DET", "green bay packers": "GB", "houston texans": "HOU", "indianapolis colts": "IND", "jacksonville jaguars": "JAX", "kansas city chiefs": "KC", "las vegas raiders": "LV", "los angeles chargers": "LAC", "los angeles rams": "LA", "miami dolphins": "MIA", "minnesota vikings": "MIN", "new england patriots": "NE", "new orleans saints": "NO", "new york giants": "NYG", "new york jets": "NYJ", "philadelphia eagles": "PHI", "pittsburgh steelers": "PIT", "san francisco 49ers": "SF", "seattle seahawks": "SEA", "tampa bay buccaneers": "TB", "tennessee titans": "TEN", "washington commanders": "WAS",
}


def provider_team_code(name: object) -> str | None:
    label = " ".join(str(name).casefold().split())
    return _TEAM_CODES.get(label) or (str(name).upper() if len(str(name)) in (2, 3) else None)


def match_scheduled_game(event: Mapping[str, object], games: list[dict[str, object]]) -> tuple[int, bool] | None:
    home, away = provider_team_code(event.get("home_team")), provider_team_code(event.get("away_team"))
    try:
        event_date = date.fromisoformat(str(event.get("commence_time") or "")[:10])
    except ValueError:
        return None
    if home is None or away is None:
        return None
    candidates: list[tuple[int, bool]] = []
    for game in games:
        game_date = game.get("game_date")
        if not isinstance(game_date, date) or abs((game_date - event_date).days) > 1:
            continue
        if game.get("home_team") == home and game.get("away_team") == away:
            candidates.append((int(game["game_id"]), True))
        elif game.get("home_team") == away and game.get("away_team") == home:
            candidates.append((int(game["game_id"]), False))
    return candidates[0] if len(candidates) == 1 else None


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _market(market: str, line: float | None, first_side: str, second_side: str, first_price: object, second_price: object, raw_market: Mapping[str, object]) -> NflGameMarket | None:
    first_number, second_number = _number(first_price), _number(second_price)
    if first_number is None or second_number is None or first_number == 0 or second_number == 0 or abs(first_number) < 100 or abs(second_number) < 100:
        return None
    first_odds, second_odds = round(first_number), round(second_number)
    first_probability, second_probability = implied_prob_from_american(first_odds, second_odds)
    return NflGameMarket(market, line, first_side, second_side, first_odds, second_odds, first_probability, second_probability, dict(raw_market))


def _outcomes(raw_market: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    outcomes = raw_market.get("outcomes")
    if not isinstance(outcomes, list):
        return {}
    return {" ".join(str(item.get("name")).casefold().split()): item for item in outcomes if isinstance(item, Mapping) and isinstance(item.get("name"), str)}


def parse_game_markets(markets: list[Mapping[str, object]], provider_home_is_nfl_home: bool, provider_home_team: str, provider_away_team: str) -> list[NflGameMarket]:
    """Parse The Odds API primary markets into stable NFL game-odds snapshots."""
    home_name = " ".join((provider_home_team if provider_home_is_nfl_home else provider_away_team).casefold().split())
    away_name = " ".join((provider_away_team if provider_home_is_nfl_home else provider_home_team).casefold().split())
    parsed: list[NflGameMarket] = []
    for raw_market in markets:
        outcomes = _outcomes(raw_market)
        key = str(raw_market.get("key") or "").casefold()
        home, away = outcomes.get(home_name), outcomes.get(away_name)
        if key == "h2h" and home and away:
            result = _market("moneyline", None, "home", "away", home.get("price"), away.get("price"), raw_market)
        elif key == "spreads" and home and away:
            result = _market("spread", _number(home.get("point")), "home", "away", home.get("price"), away.get("price"), raw_market)
        elif key == "totals":
            over, under = outcomes.get("over"), outcomes.get("under")
            result = _market("total", _number(over.get("point")) if over else None, "over", "under", over.get("price") if over else None, under.get("price") if under else None, raw_market)
        else:
            result = None
        if result is not None and (result.market == "moneyline" or result.line is not None):
            parsed.append(result)
    return parsed
