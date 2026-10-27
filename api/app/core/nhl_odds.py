"""Match NHL events and parse full-game Odds-API.io markets without I/O."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from math import isfinite
from typing import Literal, get_args

from app.core.nhl_names import fold_name
from app.core.odds import decimal_to_american, devig_two_way, near_even_rungs

_TEAM_CODES = {
    "anaheim ducks": "ANA", "boston bruins": "BOS", "buffalo sabres": "BUF",
    "calgary flames": "CGY", "carolina hurricanes": "CAR", "chicago blackhawks": "CHI",
    "colorado avalanche": "COL", "columbus blue jackets": "CBJ", "dallas stars": "DAL",
    "detroit red wings": "DET", "edmonton oilers": "EDM", "florida panthers": "FLA",
    "los angeles kings": "LAK", "minnesota wild": "MIN", "montreal canadiens": "MTL",
    "nashville predators": "NSH", "new jersey devils": "NJD", "new york islanders": "NYI",
    "new york rangers": "NYR", "ottawa senators": "OTT", "philadelphia flyers": "PHI",
    "pittsburgh penguins": "PIT", "san jose sharks": "SJS", "seattle kraken": "SEA",
    "st. louis blues": "STL", "tampa bay lightning": "TBL", "toronto maple leafs": "TOR",
    "utah mammoth": "UTA", "vancouver canucks": "VAN", "vegas golden knights": "VGK",
    "washington capitals": "WSH", "winnipeg jets": "WPG",
}
_MARKETS = {"ML": "moneyline", "Spread": "spread", "Totals": "total"}
MATCH_WINDOW = timedelta(hours=6)
# Bet365 rows stay readable after it went paid-only on Odds-API.io (2026-10-26).
NhlBook = Literal["draftkings", "fanduel", "bet365"]
NHL_ODDS_BOOKS: tuple[str, ...] = get_args(NhlBook)


@dataclass(frozen=True)
class NhlGameMarket:
    market: str
    line: float | None
    first_side: str
    second_side: str
    first_odds: int
    second_odds: int
    first_market_prob: float
    second_market_prob: float
    raw_market: dict[str, object]


def provider_team_code(name: object) -> str | None:
    if not isinstance(name, str):
        return None
    return _TEAM_CODES.get(" ".join(fold_name(name).casefold().split()))


def event_start(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def match_nhl_game(
    event: Mapping[str, object], games: Sequence[Mapping[str, object]],
) -> tuple[int, bool] | None:
    """Return a unique stored game id and whether the provider's home agrees."""
    league = event.get("league")
    if not isinstance(league, Mapping) or league.get("slug") != "usa-nhl":
        return None
    home, away = provider_team_code(event.get("home")), provider_team_code(event.get("away"))
    start = event_start(event.get("date"))
    if home is None or away is None or home == away or start is None:
        return None
    candidates: list[tuple[int, bool]] = []
    for game in games:
        stored_start, game_id = game.get("start_utc"), game.get("game_id")
        if not isinstance(stored_start, datetime) or stored_start.utcoffset() is None:
            continue
        if not isinstance(game_id, int) or isinstance(game_id, bool):
            continue
        if abs(stored_start - start) > MATCH_WINDOW:
            continue
        if (game.get("home_team"), game.get("away_team")) == (home, away):
            candidates.append((game_id, True))
        elif (game.get("home_team"), game.get("away_team")) == (away, home):
            candidates.append((game_id, False))
    return candidates[0] if len(candidates) == 1 else None


def _number(value: object) -> float | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (ValueError, OverflowError):
        return None
    return number if isfinite(number) else None


def _full_game(raw: Mapping[str, object]) -> bool:
    # Exact market names are the provider's full-game contract; explicit metadata must agree.
    for key in ("period", "segment", "scope"):
        if key in raw and raw[key] not in (None, "full-game", "full_game", "Full Game", "match"):
            return False
    return not any(key in raw for key in ("draw", "tie"))


def _priced_rungs(raw: Mapping[str, object], name: str) -> list[tuple[float, float, float | None]]:
    odds = raw.get("odds")
    if not isinstance(odds, list):
        return []
    if any(isinstance(rung, Mapping) and not _full_game(rung) for rung in odds):
        return []
    first, second = ("over", "under") if name == "Totals" else ("home", "away")
    priced: list[tuple[float, float, float | None]] = []
    for rung in odds:
        if not isinstance(rung, Mapping):
            continue
        p1, p2 = _number(rung.get(first)), _number(rung.get(second))
        line = _number(rung.get("hdp"))
        if p1 is None or p2 is None or p1 <= 1 or p2 <= 1:
            continue
        if not all(isfinite((price - 1) * 100) for price in (p1, p2)):
            continue
        if not all(-2147483648 <= decimal_to_american(price) <= 2147483647 for price in (p1, p2)):
            continue
        if name == "Spread" and (line is None or abs(line) != 1.5):
            continue
        if name == "Totals" and (line is None or not 0 < line <= 99999.99):
            continue
        priced.append((p1, p2, None if name == "ML" else line))
    return priced


def _parse_market(raw: Mapping[str, object], name: str, homes_agree: bool) -> NhlGameMarket | None:
    priced = _priced_rungs(raw, name)
    if not _full_game(raw) or not priced:
        return None
    first, second, line = min(
        near_even_rungs(priced, lambda rung: (rung[0], rung[1])),
        key=lambda rung: (1 / rung[0] + 1 / rung[1], abs(rung[0] - rung[1])),
    )
    sides = ("over", "under") if name == "Totals" else ("home", "away")
    selected: dict[str, object] = {sides[0]: first, sides[1]: second}
    if line is not None:
        selected["hdp"] = line
    raw_market: dict[str, object] = {
        "name": name, "odds": [selected], "period": "full-game",
        "updatedAt": raw.get("updatedAt") if isinstance(raw.get("updatedAt"), str) else None,
    }
    if name != "Totals" and not homes_agree:
        first, second = second, first
        line = None if line is None else -line
    p1, p2 = devig_two_way(1 / first, 1 / second)
    return NhlGameMarket(
        _MARKETS[name], line, *sides, decimal_to_american(first), decimal_to_american(second),
        p1, p2, raw_market,
    )


def parse_nhl_game_markets(markets: Sequence[object], homes_agree: bool) -> list[NhlGameMarket]:
    """Parse one book; discard conflicting duplicate markets and preserve raw orientation."""
    rows: dict[str, NhlGameMarket] = {}
    conflicts: set[str] = set()
    for raw in markets:
        if not isinstance(raw, Mapping):
            continue
        name = raw.get("name")
        if not isinstance(name, str) or name not in _MARKETS:
            continue
        row = _parse_market(raw, name, homes_agree)
        if row is None:
            conflicts.add(name)
        elif name in rows and rows[name] != row:
            conflicts.add(name)
        else:
            rows[name] = row
    return [row for name, row in rows.items() if name not in conflicts]
