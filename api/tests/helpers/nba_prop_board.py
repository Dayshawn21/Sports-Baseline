"""Shared fixtures and builders, first written for `test_nba_prop_board.py`."""
import datetime as dt


from app.core.nba_line_only import LINE_ONLY_COLUMNS
from app.core.nba_projection_backtest import NbaHistoryRow


DATE = dt.date(2026, 10, 20)
PREVIOUS = DATE - dt.timedelta(days=1)
NEXT = DATE + dt.timedelta(days=2)
FETCHED = dt.datetime(2026, 10, 20, 15, tzinfo=dt.UTC)


def _game(game_id: int, status: str = "scheduled", start: dt.datetime | None = FETCHED) -> dict[str, object]:
    return {"game_id": game_id, "away_team": "NY", "home_team": "BOS", "start_utc": start,
            "status": status, "season": 2026, "game_date": DATE}


def _line(player_id: int, name: str, market: str, line: float, odds_type: str = "standard") -> dict[str, object]:
    return {"player_id": player_id, "player_name": name, "position": "G", "team": "NYK",
            "market": market, "odds_type": odds_type, "line": line, "fetched_at": FETCHED}


def _prior() -> list[NbaHistoryRow]:
    return [
        NbaHistoryRow(player_id=1, game_id=day, season=2025, game_date=dt.date(2026, 4, day), game_type="REG",
                      did_not_play=False, minutes=32.0, stats={"points": 20, "rebounds": 6, "assists": 5})
        for day in range(1, 21)
    ]


def _box(player_id: int, points: int | None) -> dict[str, object]:
    return {**{column: 0 for column in LINE_ONLY_COLUMNS}, "player_id": player_id, "points": points,
            "rebounds": 10, "assists": 5, "game_date": dt.date(2026, 4, 20), "opponent": "BOS",
            "did_not_play": False}
