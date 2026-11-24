"""Shared fixtures and builders, first written for `test_nfl_prop_predictions.py`."""
from datetime import UTC, date, datetime

from app.schemas.nfl import (
    NflHistorySampleSchema, NflSlateGameSchema, NflSlateLineSchema, NflSlateResponse, NflWeatherSchema,
)


NOW = datetime(2026, 9, 27, 15, 0, tzinfo=UTC)
FETCHED = datetime(2026, 9, 27, 14, 58, tzinfo=UTC)
EMPTY = NflHistorySampleSchema(average=None, values=[])


def _line(line_id: int, **overrides: object) -> NflSlateLineSchema:
    fields: dict = {
        "line_id": line_id, "player_id": line_id, "player_name": f"Player {line_id}", "position": "WR",
        "recent_form": EMPTY, "opponent_history": EMPTY, "opponent_allowed_history": EMPTY,
        "market": "receiving_yards", "segment": "full_game", "odds_type": "standard",
        "projection": 61.2, "line": 55.5, "edge": 5.7, "games_in_sample": 9, "baseline_season": 2026,
        "baseline_reason": "current_season", "opponent_adjustment_pct": -2.5, "opponent_sample_games": 17,
        "usage_adjustment_pct": 1.0, "usage_sample_games": 9, "provider": "prizepicks", "fetched_at": FETCHED,
        "projection_model_version": "model-v4", "quality_flags": ["opponent_adjusted"],
        "p_over": 0.462, "p_under": 0.538, "over_probability_version": "nfl-pover-v1",
    } | overrides
    return NflSlateLineSchema(**fields)


def _game(game_id: int, start_utc: datetime | None, lines: list[NflSlateLineSchema]) -> NflSlateGameSchema:
    return NflSlateGameSchema(
        game_id=game_id, game_date=date(2026, 9, 27), start_utc=start_utc, away_team="BUF", home_team="MIA",
        status="scheduled", lines=lines, weather=NflWeatherSchema(venue_type="outdoor"),
    )


def _slate(*games: NflSlateGameSchema) -> NflSlateResponse:
    return NflSlateResponse(
        season=2026, week=3, game_count=len(games), line_count=sum(len(g.lines) for g in games),
        unmatched_count=0, games=list(games), unmatched=[],
    )
