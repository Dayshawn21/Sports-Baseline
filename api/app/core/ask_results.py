"""Turn service responses into the small rows Ask Lineform tools return (47a).

A full slate or prop board is far too large to hand the model: the NBA board is
about 5 MB a day. Each trimmer keeps the fields an answer needs, caps the row
count, and stamps every row with the page it came from (`url`) and how the app
labels its numbers (`signal`). Inputs are plain mappings in the shape each
service serializes to, so this module never touches the database.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import JsonValue

from app.core.ask_links import AskSport, game_path

Signal = Literal["pick", "reference_only", "none"]
Row = dict[str, JsonValue]
Source = Mapping[str, object]

CENTRAL = ZoneInfo("America/Chicago")
MAX_GAMES = 20
MAX_PROPS = 10
# The tennis slate colors a pick as a best bet only past this EV, with the
# stricter LOCK and STRONG bars below (isPricedBestBet in web/src/utils/unifiedTennis.ts).
MIN_BEST_BET_EV_PCT = 5.0


def signal_for(sport: AskSport, kind: Literal["fact", "model", "pick"], priced_best_bet: bool = False) -> Signal:
    """How the app labels a row. Only a tennis priced best bet is a pick; NFL and
    NBA projections, gaps and probabilities are reference only, as is every
    tennis moneyline (moneyline picks are off) and every unpriced tennis angle."""
    if kind == "fact":
        return "none"
    if kind == "pick" and sport == "tennis" and priced_best_bet:
        return "pick"
    return "reference_only"


def is_priced_best_bet(pick: Source) -> bool:
    ev, kelly, odds = pick.get("ev_pct"), pick.get("kelly_fraction"), pick.get("odds_american")
    if pick.get("pick_type") == "moneyline":
        return False
    if not isinstance(ev, (int, float)) or ev < MIN_BEST_BET_EV_PCT:
        return False
    if not isinstance(kelly, (int, float)) or kelly < 0 or odds is None:
        return False
    tier = pick.get("confidence")
    if tier == "LOCK":
        return ev >= 15 and kelly >= 0.03
    if tier == "STRONG":
        return ev >= 10 and kelly >= 0.02
    return tier == "LEAN"


def _as_datetime(start: object) -> dt.datetime | None:
    if isinstance(start, str):
        start = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    return start if isinstance(start, dt.datetime) else None


def ct_label(start: object) -> str | None:
    """'Tue Oct 27, 7:30 PM CT' from an aware datetime or ISO string."""
    start = _as_datetime(start)
    if start is None:
        return None
    local = start.astimezone(CENTRAL)
    return f"{local:%a %b} {local.day}, {local:%I:%M %p}".replace(" 0", " ") + " CT"


def _iso(start: object) -> str | None:
    return start.isoformat() if isinstance(start, dt.datetime) else start if isinstance(start, str) else None


def _num(value: object, places: int) -> float | None:
    return round(float(value), places) if isinstance(value, (int, float)) else None


def _map(value: object) -> Source:
    return value if isinstance(value, Mapping) else {}


def _record(value: object) -> str | None:
    record = _map(value)
    return f"{record['wins']}-{record['losses']}" if "wins" in record and "losses" in record else None


def _capped(rows: list[Row], cap: int) -> tuple[list[Row], bool]:
    return rows[:cap], len(rows) > cap


def trim_nba_slate(games: Sequence[Source]) -> tuple[list[Row], bool]:
    """Rows from NbaSlateResponse.games, dumped with field names (snake_case)."""
    rows: list[Row] = []
    for game in games:
        moneyline, spread, total = _map(game.get("moneyline")), _map(game.get("spread")), _map(game.get("total"))
        rows.append({
            "game_id": game["game_id"], "matchup": f"{game['away_team']} @ {game['home_team']}",
            "start": ct_label(game.get("start_utc")), "start_utc": _iso(game.get("start_utc")),
            "status": game.get("status"), "away_score": game.get("away_score"), "home_score": game.get("home_score"),
            "away_record": _record(game.get("away_record")), "home_record": _record(game.get("home_record")),
            "book": moneyline.get("book") or spread.get("book") or total.get("book"),
            "home_moneyline": moneyline.get("home_odds"), "away_moneyline": moneyline.get("away_odds"),
            "market_home_win_probability": _num(moneyline.get("home_win_probability"), 3),
            "home_spread": spread.get("home_line"), "total": total.get("line"),
            "prop_lines": game.get("prop_line_count"),
            "url": game_path("nba", int(str(game["game_id"]))), "signal": signal_for("nba", "fact"),
        })
    return _capped(rows, MAX_GAMES)


def trim_nfl_slate(games: Sequence[Source]) -> tuple[list[Row], bool]:
    """Rows from the stored NFL slate JSON (camelCase, as the endpoint serves it)."""
    rows: list[Row] = []
    for game in games:
        odds, model = _map(game.get("odds")), _map(game.get("model"))
        lines = game.get("lines")
        rows.append({
            "game_id": game["gameId"], "matchup": f"{game['awayTeam']} @ {game['homeTeam']}",
            "start": ct_label(game.get("startUtc")), "start_utc": _iso(game.get("startUtc")),
            "status": game.get("status"), "away_record": _record(game.get("awayContext")),
            "home_record": _record(game.get("homeContext")), "book": odds.get("book"),
            "home_moneyline": odds.get("homeMoneyline"), "away_moneyline": odds.get("awayMoneyline"),
            "home_spread": odds.get("homeSpread"), "total": odds.get("total"),
            "model_not_a_pick": {
                "home_spread": _num(model.get("homeSpread"), 1), "total": _num(model.get("total"), 1),
                "home_win_probability": _num(model.get("homeWinProbability"), 3),
            } if model else None,
            "prop_lines": len(lines) if isinstance(lines, list) else 0,
            "url": game_path("nfl", int(str(game["gameId"]))),
            "signal": signal_for("nfl", "model" if model else "fact"),
        })
    return _capped(rows, MAX_GAMES)


def _started(start: object, now: dt.datetime) -> bool:
    when = _as_datetime(start)
    return when is not None and when <= now


def trim_tennis_slate(predictions: Sequence[Source], now: dt.datetime) -> tuple[list[Row], bool]:
    """Rows from tennis PredictionOutput dataclasses (asdict). Predictions carry
    no status, so matches already started go last; otherwise the cap would
    fill with the morning's finished matches."""
    ordered = sorted(
        predictions,
        key=lambda p: (_started(p.get("start_utc"), now), _iso(p.get("start_utc")) or "~"),
    )
    rows: list[Row] = [
        {
            "game_id": p["match_id"], "matchup": f"{p['p1_name']} vs {p['p2_name']}",
            "tour": p.get("tour_label") or p.get("tour"), "tournament": p.get("tournament"),
            "round": p.get("round"), "surface": p.get("surface"),
            "start": ct_label(p.get("start_utc")), "start_utc": _iso(p.get("start_utc")),
            "started": _started(p.get("start_utc"), now),
            "p1_moneyline": p.get("p1_odds_american"), "p2_moneyline": p.get("p2_odds_american"),
            "model_p1_win_probability": _num(p.get("p1_win_prob"), 3),
            "model_p2_win_probability": _num(p.get("p2_win_prob"), 3),
            "url": game_path("tennis", int(str(p["match_id"]))), "signal": signal_for("tennis", "model"),
        }
        for p in ordered
    ]
    return _capped(rows, MAX_GAMES)


def trim_nba_gaps(items: Sequence[Source], limit: int) -> tuple[list[Row], bool]:
    """Rows from NbaSlateGapsResponse.items, keeping the digest's ranking. The
    market filter runs in the service, before ranking."""
    kept = list(items)
    rows: list[Row] = [
        {
            "rank": rank, "player_id": item["player_id"], "player": item["player_name"],
            "game_id": item["game_id"], "matchup": f"{item['away_team']} @ {item['home_team']}",
            "start": ct_label(item.get("start_utc")), "market": item["market"], "line": item["line"],
            "projection": _num(item.get("projection"), 2), "gap": _num(item.get("gap"), 2),
            "gap_share_pct": _num(100 * float(str(item["gap_share"])), 1),
            "label": "reference projection gap, not a pick",
            "url": game_path("nba", int(str(item["game_id"]))), "signal": signal_for("nba", "model"),
        }
        for rank, item in enumerate(kept, start=1)
    ]
    return _capped(rows, min(limit, MAX_PROPS))


def _tennis_pick_order(matches: Sequence[Source]) -> list[tuple[Source, Source]]:
    """The slate digest's order first (each match's first priced best bet, in
    match order), then the other priced best bets, then the unpriced angles."""
    pairs = [(match, pick) for match in matches for pick in match.get("picks") or [] if isinstance(pick, Mapping)]
    firsts: list[tuple[Source, Source]] = []
    seen: set[object] = set()
    for match, pick in pairs:
        if is_priced_best_bet(pick) and match.get("match_id") not in seen:
            seen.add(match.get("match_id"))
            firsts.append((match, pick))
    others = [pair for pair in pairs if is_priced_best_bet(pair[1]) and pair not in firsts]
    angles = [pair for pair in pairs if not is_priced_best_bet(pair[1])]
    return firsts + others + angles


def trim_tennis_picks(
    matches: Sequence[Source], market: str | None, limit: int, now: dt.datetime
) -> tuple[list[Row], bool]:
    """Rows from BestPicksResponse.matches, dumped with field names. PASS picks
    never show on the slate, and a started match is no longer a play."""
    needle = market.lower() if market else None
    upcoming = [m for m in matches if not _started(m.get("start_utc"), now)]
    rows: list[Row] = []
    for match, pick in _tennis_pick_order(upcoming):
        if pick.get("confidence") == "PASS":
            continue
        if needle and needle not in str(pick.get("label", "")).lower():
            continue
        priced = is_priced_best_bet(pick)
        rows.append({
            "rank": len(rows) + 1, "game_id": match["match_id"],
            "matchup": f"{match['p1_name']} vs {match['p2_name']}", "tour": match.get("tour_label") or match.get("tour"),
            "tournament": match.get("tournament"), "start": ct_label(match.get("start_utc")),
            "pick": pick.get("pick"), "label": pick.get("label"), "player": pick.get("player_name"),
            "tier": pick.get("confidence"), "odds": pick.get("odds_american"),
            "ev_pct": _num(pick.get("ev_pct"), 1), "model_probability": _num(pick.get("model_prob"), 3),
            "reasoning": pick.get("reasoning"),
            "kind": "priced best bet" if priced else "angle, not a best bet",
            "url": game_path("tennis", int(str(match["match_id"]))),
            "signal": signal_for("tennis", "pick", priced_best_bet=priced),
        })
    return _capped(rows, min(limit, MAX_PROPS))
