"""Assemble the NFL slate: games, prop lines, projections, edges, and evidence.

Lives outside the router so a backtest can replay the exact projection the
`/nfl/slate` endpoint serves.
"""
from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence, Set as AbstractSet
from dataclasses import asdict, replace
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nfl_over_probability import OverProbability, over_probability
from app.core.nfl_over_probability_fit import FIT_PROJECTION_MODEL_VERSION, QUANTILES_BY_GROUP, SHOWN_MARKETS
from app.core.nfl_projection import (
    NflHistoricalAverages, NflSeasonTouchdowns, baseline_projection, edge, edge_is_comparable, line_quality_flags,
    model_projection, model_quality_flags, moneyline_is_stale, MONEYLINE_UNSCALED_MARKETS, NflProjectionInput,
    NFL_PROJECTION_MODEL_VERSION,
    NflUsageInput, opponent_adjustment_pct, slate_line_rank, USAGE_ADJUSTED_MARKETS,
    td_seasons_used, usage_adjustment_pct,
)
from app.core.nfl_availability import NflAvailability, availability_flags
from app.core.nfl_elo import NFL_ELO_MODEL_VERSION
from app.core.nfl_game_lines import game_model_line
from app.core.nfl_scoring_ratings import NFL_SCORING_V1, replay as replay_scoring
from app.core.nfl_season_blend import apply_season_blend
from app.core.nfl_team_game_dvp import apply_team_game_dvp, league_averages, team_game_inputs
from app.core.nfl_snap_share import (
    SNAP_SHARE_COEFFICIENTS, NflSnapEvidence, NflSnapSeason, production_anytime_td_probability, snap_evidence,
)
from app.core.nfl_baseline import BLENDED_SEASONS, MIN_BASELINE_GAMES
from app.core.nfl_prop_odds import NflSlateBookOdds, consensus, devigged_book_probabilities, slate_book_odds
from app.nfl.markets import NflPropMarket
from app.nfl.weather import stadium_for_home_team
from app.repositories import nfl as nfl_repo
from app.repositories import nfl_targets as targets_repo
from app.services.nfl.targets import targets_slate_line
from app.schemas.nfl import (
    NflGameModelSchema, NflHistoryResultSchema, NflHistorySampleSchema, NflSlateGameSchema, NflSlateLineSchema,
    NflSlateResponse, NflUnmatchedLineSchema, NflWeatherSchema,
)

TEAM_NOT_IN_GAME_FLAG = "team_not_in_game"
SNAP_SHARE_UNAVAILABLE_FLAG = "snap_share_unavailable"
OVER_PROBABILITY_VERSION = "nfl-pover-v1"


def slate_over_probability(
    market: str, position: str | None, segment: str, games: int, projection: float | None, line: float | None,
    *, fit_version: str = FIT_PROJECTION_MODEL_VERSION,
    tables: Mapping[tuple[str, str], Sequence[float]] = QUANTILES_BY_GROUP,
    shown: AbstractSet[str] = SHOWN_MARKETS,
) -> OverProbability | None:
    """P(over) for a line in a market the 27g fit showed, or None.

    Odds type is deliberately not a condition: goblin and demon lines are what
    27h will rank. A fit on another projection version is never read, because
    its residuals describe a different model.
    """
    quantiles = tables.get((market, position or ""))
    if (
        segment != "full_game" or market not in shown or quantiles is None or games < MIN_BASELINE_GAMES
        or fit_version != NFL_PROJECTION_MODEL_VERSION or projection is None or line is None
    ):
        return None
    return over_probability(quantiles, projection, line)


def _usage_input(row: dict) -> NflUsageInput | None:
    player, position = row.get("usage"), row.get("position_usage")
    if player is None or position is None:
        return None
    return NflUsageInput(
        player["games"], player["targets"], player["target_share"],
        position["targets"], position["target_share"],
    )


def _history_value(market: NflPropMarket, row: dict) -> float:
    # One past game either had a TD or not; its average is then the share of games scored in.
    if market is NflPropMarket.ANYTIME_TOUCHDOWN:
        return 1.0 if row["touchdowns"] > 0 else 0.0
    return baseline_projection(market, NflHistoricalAverages(
        1, row["passing_yards"], row["passing_attempts"], row["passing_completions"],
        row["rushing_yards"], row["rushing_attempts"], row["receiving_yards"],
        row["receptions"], row["touchdowns"], row["fantasy_points"],
    ))


def _history_sample(market: NflPropMarket, rows: list[dict], limit: int | None = None) -> NflHistorySampleSchema:
    values = [
        NflHistoryResultSchema(
            value=_history_value(market, item), opponent_team=item.get("opponent_team"),
        )
        for item in rows[:limit]
    ]
    return NflHistorySampleSchema(
        average=round(sum(item.value for item in values) / len(values), 2) if values else None,
        values=values,
    )


def _weather_schema(game: dict, stored: dict) -> NflWeatherSchema:
    stadium = stadium_for_home_team(game["home_team"])
    return NflWeatherSchema(**(stored | {"venue_type": stored.get("venue_type") or (stadium.venue_type if stadium else "unknown")}))


def _td_seasons(row: dict) -> list[NflSeasonTouchdowns]:
    return [NflSeasonTouchdowns(item["season"], item["games"], item["touchdowns"]) for item in row.get("td_seasons", [])]


def _snap_seasons(row: dict) -> list[NflSnapSeason]:
    return [NflSnapSeason(item["season"], item["games"], item["share"]) for item in row.get("snap_seasons", [])]


def anytime_td(row: dict, line_season: int, position_td_rate: float) -> tuple[float, float]:
    """Shared by /projections and /slate so both return the same anytime-TD probability."""
    return production_anytime_td_probability(
        row.get("position"), _td_seasons(row), _snap_seasons(row), line_season,
        position_td_rate, row.get("position_snap_share", 0.0),
    )


def _snap_evidence(market: NflPropMarket, row: dict, line_season: int) -> NflSnapEvidence | None:
    """Evidence for RB and TE anytime-TD lines, the only lines snap share feeds."""
    if market is not NflPropMarket.ANYTIME_TOUCHDOWN or row.get("position") not in SNAP_SHARE_COEFFICIENTS:
        return None
    return snap_evidence(_snap_seasons(row), line_season, row.get("position_snap_share", 0.0))


def _baseline(
    market: NflPropMarket, row: dict, line_season: int,
    averages: NflHistoricalAverages, position_averages: NflHistoricalAverages,
) -> tuple[float, int]:
    """Baseline and the game count model_projection regresses by.

    Anytime TD passes its already-shrunk weighted games, so the model does not
    pull the same rate toward the position a second time.
    """
    if market is not NflPropMarket.ANYTIME_TOUCHDOWN:
        return baseline_projection(market, averages), averages.games
    probability, weighted_games = anytime_td(row, line_season, position_averages.touchdowns)
    return probability, round(weighted_games)


def _baseline_label(
    market: NflPropMarket, row: dict, line_season: int, averages: NflHistoricalAverages,
) -> tuple[int | None, str, int]:
    """(season, reason, games) that describe the evidence behind the baseline."""
    used = _td_seasons(row) if market is NflPropMarket.ANYTIME_TOUCHDOWN else []
    used = td_seasons_used(used, line_season)
    if not used:
        return row["baseline_season"], row["baseline_reason"], averages.games
    return max(entry.season for entry in used), BLENDED_SEASONS, sum(entry.games for entry in used)


def _availability(row: dict) -> NflAvailability:
    return NflAvailability(
        injury_status=row.get("injury_status"),
        depth_team_id=row.get("depth_team_id"), depth_position=row.get("depth_position"),
        depth_rank=row.get("depth_rank"),
        previous_depth_team_id=row.get("previous_depth_team_id"),
        previous_depth_position=row.get("previous_depth_position"),
        previous_depth_rank=row.get("previous_depth_rank"),
    )


def _game_model(
    elo: tuple[str, float, float] | None, totals: dict[str, float], odds: dict | None,
) -> NflGameModelSchema | None:
    """The display-only model line for one slate game, or None without both pre-game ratings."""
    if elo is None:
        return None
    game_key, home_elo, away_elo = elo
    line = game_model_line(
        home_elo, away_elo, totals[game_key],
        odds.get("home_moneyline") if odds else None, odds.get("away_moneyline") if odds else None,
    )
    return NflGameModelSchema(model_version=NFL_ELO_MODEL_VERSION, **asdict(line))


def _team_flags(row: dict) -> list[str]:
    # The slate query leaves the opponent NULL exactly when the player's as-of team
    # is neither side (moved, cut, or retired), so home/away and DVP are unknown too.
    return [TEAM_NOT_IN_GAME_FLAG] if row.get("opponent_team") is None else []


def _slate_line(
    row: dict, line_season: int, home_market_prob: float | None, history: list[dict] | None = None,
    book_odds: NflSlateBookOdds | None = None, devigged: float | None = None, opponent_allowed: list[dict] | None = None,
    market_is_stale: bool = False,
) -> NflSlateLineSchema:
    market = NflPropMarket(row["market"])
    averages = NflHistoricalAverages(**row["averages"])
    position_averages = NflHistoricalAverages(**row["position_averages"])
    opponent_averages = (
        NflHistoricalAverages(**row["opponent_averages"])
        if row["opponent_averages"] is not None else None
    )
    league_position_averages = (
        NflHistoricalAverages(**row["league_position_averages"])
        if row["league_position_averages"] is not None else None
    )
    label_season, label_reason, label_games = _baseline_label(market, row, line_season, averages)
    label_averages = replace(averages, games=label_games)
    has_baseline = label_games > 0
    baseline, model_games = _baseline(market, row, line_season, averages, position_averages)
    if not has_baseline:
        baseline = None
    usage_applicable = market in USAGE_ADJUSTED_MARKETS
    usage = _usage_input(row) if usage_applicable else None
    model_input = NflProjectionInput(
        baseline or 0.0,
        baseline_projection(market, position_averages),
        model_games,
        home_market_prob,
        row["player_team_id"] == row["home_team_id"],
        market_is_stale,
        baseline_projection(market, opponent_averages) if opponent_averages is not None else None,
        baseline_projection(market, league_position_averages) if league_position_averages is not None else None,
        opponent_averages.games if opponent_averages is not None else 0,
        usage_applicable,
        usage,
        uses_game_environment=row.get("uses_game_environment", False),
        environment_adjustment_pct=row.get("environment_adjustment_pct"),
        wind_adjustment_pct=row.get("wind_adjustment_pct"),
        moneyline_scaled=market not in MONEYLINE_UNSCALED_MARKETS,
    )
    projection = model_projection(model_input) if has_baseline else None
    comparable = edge_is_comparable(market, label_games, row["segment"], row["odds_type"])
    player_history = history or []
    opponent_history = [
        item for item in player_history if item["opponent_team_id"] == row.get("opponent_team_id")
    ]
    snap = _snap_evidence(market, row, line_season)
    snap_flags = [SNAP_SHARE_UNAVAILABLE_FLAG] if snap is not None and snap.share is None else []
    over = slate_over_probability(market.value, row["position"], row["segment"], label_games, projection, row["line"])
    return NflSlateLineSchema(
        line_id=row["id"], player_id=row["player_id"], player_name=row["player_name"],
        position=row["position"], opponent_team=row.get("opponent_team"),
        opponent_position_average=(
            baseline_projection(market, opponent_averages) if opponent_averages is not None else None
        ),
        recent_form=_history_sample(market, player_history, limit=5),
        opponent_history=_history_sample(market, opponent_history),
        opponent_allowed_history=_history_sample(market, opponent_allowed or [], limit=5),
        market=market.value, segment=row["segment"],
        odds_type=row["odds_type"], projection=projection, line=row["line"],
        edge=edge(projection, row["line"]) if comparable else None,
        games_in_sample=label_games, baseline_season=label_season,
        baseline_reason=label_reason,
        opponent_adjustment_pct=opponent_adjustment_pct(model_input),
        opponent_sample_games=opponent_averages.games if opponent_averages is not None else None,
        usage_adjustment_pct=usage_adjustment_pct(model_input),
        usage_sample_games=usage.games if usage is not None else None,
        provider=row["provider"], fetched_at=row["fetched_at"],
        projection_model_version=NFL_PROJECTION_MODEL_VERSION,
        quality_flags=line_quality_flags(
            label_averages, label_season, line_season, row["segment"], row["odds_type"],
            row.get("current_season_games"),
        ) + model_quality_flags(model_input) + _team_flags(row) + availability_flags(_availability(row)) + snap_flags,
        book_probability=book_odds.probability if book_odds else None,
        book_count=book_odds.book_count if book_odds else None,
        book_includes_margin=book_odds.includes_margin if book_odds else None,
        book_fetched_at=book_odds.fetched_at if book_odds else None,
        # Only a margin-carrying price needs correcting, and `book_odds` is
        # already None for anything but a full-game anytime-TD line.
        book_probability_devigged=devigged if book_odds and book_odds.includes_margin else None,
        injury_status=row.get("injury_status"), practice_status=row.get("practice_status"),
        injury=row.get("injury"), depth_position=row.get("depth_position"), depth_rank=row.get("depth_rank"),
        previous_depth_position=row.get("previous_depth_position"),
        previous_depth_rank=row.get("previous_depth_rank"),
        snap_share=round(snap.share, 3) if snap is not None and snap.share is not None else None,
        snap_share_games=snap.games if snap is not None else None,
        p_over=round(over.p_over, 3) if over is not None else None,
        p_under=round(1 - round(over.p_over, 3), 3) if over is not None else None,
        over_probability_version=OVER_PROBABILITY_VERSION if over is not None else None,
    )


async def build_slate(db: AsyncSession, season: int, week: int, now: datetime) -> NflSlateResponse:
    """One week's games with our baseline, the market's line, and the edge between.

    `now` is passed in so a backtest can replay a past week at its own game time.
    """
    games = await nfl_repo.get_slate_games(db, season, week)
    line_rows = await nfl_repo.get_slate_lines(db, season, week)
    history_by_player = await nfl_repo.get_slate_player_history(
        db, season, week, sorted({row["player_id"] for row in line_rows}),
    )
    opponent_allowed_history = await nfl_repo.get_slate_opponent_position_history(db, season, week)
    team_game_totals = await nfl_repo.get_team_game_position_totals(db, season, week)
    team_game_league = league_averages(team_game_totals)
    market_probabilities = await nfl_repo.get_slate_market_probabilities(db, season, week)
    kickoffs = {game["game_id"]: game["start_utc"] for game in games}
    matchup_context = await nfl_repo.get_slate_matchup_context(db, season, week)
    weather_by_game = await nfl_repo.get_slate_weather(db, season, week)
    unmatched_rows = await nfl_repo.get_unmatched_slate_lines(db, season, week)
    prop_odds = await nfl_repo.get_slate_prop_odds(db, season, week)
    elo_by_game = await nfl_repo.get_slate_team_elo(db, season, week)
    elo_games = await nfl_repo.get_elo_games(db)
    targets_rows = await targets_repo.get_targets_serving_lines(db, season, week)
    unmatched_targets = await targets_repo.get_unmatched_targets_lines(db, season, week)

    # Everything below is CPU only. Run in a worker thread so the event loop keeps
    # answering /health and other visitors: inline, a cold week stalled the loop for
    # 3.6 s locally, about 10 s on the hosted demo, past Render's 5 s health check (37d).
    def assemble() -> NflSlateResponse:
        totals = {row.game_key: row.expected_total for row in replay_scoring(elo_games, NFL_SCORING_V1)}

        # Normalizing needs every player in a game at once, so it is computed per
        # game up front rather than inside the per-line loop below.
        devigged_by_game: dict[int, dict[int, float]] = {}
        for (game_id, player_id), prices in prop_odds.items():
            player_consensus = consensus([(probability, margin) for probability, margin, _ in prices])
            if player_consensus is not None and player_consensus.includes_margin:
                devigged_by_game.setdefault(game_id, {})[player_id] = player_consensus.probability
        devigged_by_game = {
            game_id: devigged_book_probabilities(
                players, (matchup_context.get(game_id, {}).get("odds") or {}).get("total"),
            )
            for game_id, players in devigged_by_game.items()
        }

        lines_by_game: dict[int, list[NflSlateLineSchema]] = {}
        for row in line_rows:
            row = apply_season_blend(apply_team_game_dvp(
                row | team_game_inputs(team_game_totals, team_game_league, row.get("opponent_team_id"), row["position"]),
            ), season)
            home_market_prob, market_fetched_at = market_probabilities.get(row["game_id"], (None, None))
            book_odds = slate_book_odds(row["market"], row["segment"], prop_odds.get((row["game_id"], row["player_id"]), []))
            lines_by_game.setdefault(row["game_id"], []).append(
                _slate_line(
                    row, season, home_market_prob,
                    history_by_player.get(row["player_id"], []), book_odds,
                    devigged_by_game.get(row["game_id"], {}).get(row["player_id"]),
                    opponent_allowed_history.get((row.get("opponent_team_id"), row["position"]), []),
                    market_is_stale=moneyline_is_stale(market_fetched_at, kickoffs.get(row["game_id"]), now),
                )
            )
        for row in targets_rows:
            lines_by_game.setdefault(row.game_id, []).append(targets_slate_line(row))
        for game_lines in lines_by_game.values():
            # Current-season edges first, then stale-baseline edges, then unpriced rows.
            game_lines.sort(key=lambda item: slate_line_rank(item.edge, item.quality_flags))

        return NflSlateResponse(
            season=season, week=week, game_count=len(games), line_count=len(line_rows) + len(targets_rows),
            unmatched_count=len(unmatched_rows) + len(unmatched_targets),
            games=[
                NflSlateGameSchema(
                    **game, **matchup_context.get(game["game_id"], {}), lines=lines_by_game.get(game["game_id"], []),
                    weather=_weather_schema(game, weather_by_game.get(game["game_id"], {})),
                    model=_game_model(
                        elo_by_game.get(game["game_id"]), totals,
                        matchup_context.get(game["game_id"], {}).get("odds"),
                    ),
                )
                for game in games
            ],
            unmatched=[
                NflUnmatchedLineSchema(
                    line_id=row["id"], player_name=row["player_name"],
                    provider_team=row["provider_team"], provider_position=row["provider_position"],
                    market=row["market"], segment=row["segment"], odds_type=row["odds_type"],
                    line=row["line"], provider=row["provider"], fetched_at=row["fetched_at"],
                )
                for row in unmatched_rows
            ] + [NflUnmatchedLineSchema.model_validate(row, from_attributes=True) for row in unmatched_targets],
        )

    return await asyncio.to_thread(assemble)
