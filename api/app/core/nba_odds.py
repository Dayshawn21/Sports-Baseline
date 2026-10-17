"""Match The Odds API NBA events to stored NBA games (item 20d).

Market parsing reuses `app.core.nfl_odds.parse_game_markets`, which is
sport-agnostic. Pure: no DB, no I/O.
"""
from __future__ import annotations

import datetime as dt
from collections.abc import Mapping, Sequence

# Names as listed by GET /v4/sports/basketball_nba/events on 2026-10-06; codes are
# ESPN's `sport_teams.team_code`.
_TEAM_CODES = {
    "atlanta hawks": "ATL", "boston celtics": "BOS", "brooklyn nets": "BKN", "charlotte hornets": "CHA",
    "chicago bulls": "CHI", "cleveland cavaliers": "CLE", "dallas mavericks": "DAL", "denver nuggets": "DEN",
    "detroit pistons": "DET", "golden state warriors": "GS", "houston rockets": "HOU", "indiana pacers": "IND",
    "los angeles clippers": "LAC", "los angeles lakers": "LAL", "memphis grizzlies": "MEM", "miami heat": "MIA",
    "milwaukee bucks": "MIL", "minnesota timberwolves": "MIN", "new orleans pelicans": "NO",
    "new york knicks": "NY", "oklahoma city thunder": "OKC", "orlando magic": "ORL",
    "philadelphia 76ers": "PHI", "phoenix suns": "PHX", "portland trail blazers": "POR",
    "sacramento kings": "SAC", "san antonio spurs": "SA", "toronto raptors": "TOR", "utah jazz": "UTAH",
    "washington wizards": "WSH",
}

# Providers disagree on tip-off by minutes (PrizePicks 15:10 ET vs 19:00Z for one game),
# while the same two teams never meet twice within a day.
MATCH_WINDOW = dt.timedelta(hours=6)


def odds_api_team_code(name: object) -> str | None:
    """A The Odds API team name in ESPN code form; unknown names give None."""
    return _TEAM_CODES.get(" ".join(str(name).casefold().split()))


def _commence_time(event: Mapping[str, object]) -> dt.datetime | None:
    try:
        parsed = dt.datetime.fromisoformat(str(event.get("commence_time") or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def match_nba_game(event: Mapping[str, object], games: Sequence[Mapping[str, object]]) -> tuple[int, bool] | None:
    """The stored game id and whether the provider's home team is the stored home team.

    None unless exactly one game has both teams and a tip-off inside the window.
    """
    home, away = odds_api_team_code(event.get("home_team")), odds_api_team_code(event.get("away_team"))
    commence = _commence_time(event)
    if home is None or away is None or commence is None:
        return None
    candidates: list[tuple[int, bool]] = []
    for game in games:
        start = game.get("start_utc")
        if not isinstance(start, dt.datetime) or abs(start - commence) > MATCH_WINDOW:
            continue
        if game.get("home_team") == home and game.get("away_team") == away:
            candidates.append((int(str(game["game_id"])), True))
        elif game.get("home_team") == away and game.get("away_team") == home:
            candidates.append((int(str(game["game_id"])), False))
    return candidates[0] if len(candidates) == 1 else None
