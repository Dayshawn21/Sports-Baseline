from datetime import UTC, date, datetime, timedelta

from app.schemas.nfl import (
    NflHistorySampleSchema, NflSlateGameSchema, NflSlateLineSchema, NflSlateResponse, NflWeatherSchema,
)
from app.services.nfl.prop_predictions import freeze_rows

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


def test_a_line_before_kickoff_is_frozen_as_served() -> None:
    rows, counts = freeze_rows(_slate(_game(1, NOW + timedelta(hours=2), [_line(10)])), NOW)

    assert counts == {"frozen": 1}
    row = rows[0]
    assert (row.prop_line_id, row.model_version, row.over_probability_version) == (10, "model-v4", "nfl-pover-v1")
    assert (row.projection, row.p_over, row.p_under, row.edge) == (61.2, 0.462, 0.538, 5.7)
    assert row.quality_flags == ["opponent_adjusted"]
    assert row.generated_at == NOW
    assert row.feature_snapshot == {
        "games_in_sample": 9, "baseline_season": 2026, "baseline_reason": "current_season",
        "opponent_adjustment_pct": -2.5, "usage_adjustment_pct": 1.0, "line": 55.5, "odds_type": "standard",
        "market": "receiving_yards", "segment": "full_game", "line_fetched_at": "2026-09-27T14:58:00+00:00",
    }


def test_games_at_or_past_kickoff_and_without_a_start_time_are_counted_not_frozen() -> None:
    slate = _slate(
        _game(1, NOW, [_line(10), _line(11)]),
        _game(2, NOW - timedelta(days=3), [_line(12)]),
        _game(3, None, [_line(13)]),
        _game(4, NOW + timedelta(minutes=1), [_line(14)]),
    )

    rows, counts = freeze_rows(slate, NOW)

    assert [row.prop_line_id for row in rows] == [14]
    assert counts == {"kicked_off": 3, "no_start_time": 1, "frozen": 1}


def test_a_hidden_market_and_a_line_without_a_baseline_are_still_frozen_with_nulls() -> None:
    hidden = _line(20, market="receptions", p_over=None, p_under=None, over_probability_version=None)
    no_baseline = _line(21, projection=None, edge=None, games_in_sample=0, p_over=None, p_under=None,
                        over_probability_version=None)

    rows, _ = freeze_rows(_slate(_game(1, NOW + timedelta(hours=1), [hidden, no_baseline])), NOW)

    assert [(r.prop_line_id, r.p_over, r.over_probability_version) for r in rows] == [(20, None, None), (21, None, None)]
    assert rows[1].projection is None and rows[1].edge is None
