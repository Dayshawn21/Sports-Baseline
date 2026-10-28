"""The tennis best-picks response: slate predictions, the live moneyline overlay
and the per-match pick assembly, shared by the router and Ask Lineform (47a)."""
from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.bookmakers import stored_book_keys
from app.core.tennis_odds_events import event_start, match_event
from app.ml.registry import ModelRegistry
from app.repositories import matches as match_repo
from app.repositories.players import get_rolling_stats_batch_all_surfaces
from app.repositories.props import get_today_match_odds_as_props, get_today_props
from app.schemas.tennis import BestPickSchema, BestPicksResponse, MatchBestPicksSchema
from app.services.tennis.best_picks import BestPick, build_best_picks
from app.services.tennis.live_odds_cache import TimedSingleFlight
from app.services.tennis.prediction_cache import cached_best_picks, cached_predictions
from app.services.tennis.predictor import PredictionOutput

PREDICTIONS_UNAVAILABLE = "Tennis predictions are temporarily unavailable."

# Odds move, but not so fast that a moneyline a few minutes old misleads a pick,
# and a longer window is what keeps page loads inside the hourly API quota.
_LIVE_ODDS_TTL_SECONDS = 15 * 60
_LIVE_ODDS: TimedSingleFlight[dict] = TimedSingleFlight(_LIVE_ODDS_TTL_SECONDS)

_ML_NAMES = {"ml", "h2h", "moneyline", "winner", "match winner", "match ml", "match result"}


class PredictionsUnavailable(Exception):
    """The prediction build failed; callers surface it as a 503 or a tool note."""


def target_dates(match_date: Optional[date], today: date) -> list[date]:
    return [match_date] if match_date else [today, today + timedelta(days=1)]


async def slate_predictions(
    db: AsyncSession, registry: ModelRegistry, match_date: Optional[date], today: date
) -> list[PredictionOutput]:
    results = await cached_predictions(db, registry, target_dates(match_date, today), today)
    if results is None:
        raise PredictionsUnavailable(PREDICTIONS_UNAVAILABLE)
    return results


def dec_to_american(dec) -> Optional[int]:
    try:
        d = float(dec)
        if d <= 1.0:
            return None
        if d >= 2.0:
            return round((d - 1) * 100)
        return round(-100 / (d - 1))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


async def overlay_live_moneyline(predictions: list[PredictionOutput]) -> None:
    """Fetch live moneyline odds and fill in any predictions missing DB odds.

    DB odds (from odds_api.py ingest) are used when available; the live API is
    only called when one or more predictions have no odds in the DB, and its
    result is shared across requests for _LIVE_ODDS_TTL_SECONDS.
    """
    needs = [p for p in predictions if p.p1_odds_american is None or p.p2_odds_american is None]
    if not needs:
        return

    # Lazy import to avoid circular dependency at module load time
    from app.routers.props import _fetch_live_tennis_odds

    bookmakers = settings.live_odds_bookmakers
    live_data = await _LIVE_ODDS.get(
        (bookmakers, 24),
        lambda: _fetch_live_tennis_odds(bookmakers=bookmakers, hours_ahead=24),
    )
    if not live_data:
        return

    events = live_data.get("events") or []
    if not events:
        return

    for pred in needs:
        for ev in events:
            home_is_p1 = match_event(
                pred.p1_name, pred.p2_name,
                ev.get("home") or "", ev.get("away") or "",
                match_start=pred.start_utc, event_start=event_start(ev),
            )
            if home_is_p1 is None:
                continue

            for bk in ev.get("bookmakers") or []:
                for mkt in bk.get("markets") or []:
                    if (mkt.get("name") or "").lower().strip() not in _ML_NAMES:
                        continue
                    for sel in mkt.get("selections") or []:
                        if not isinstance(sel, dict):
                            continue
                        h_odds = dec_to_american(sel.get("home"))
                        a_odds = dec_to_american(sel.get("away"))
                        if h_odds and a_odds:
                            if home_is_p1:
                                pred.p1_odds_american = h_odds
                                pred.p2_odds_american = a_odds
                            else:
                                pred.p1_odds_american = a_odds
                                pred.p2_odds_american = h_odds
                            break
                    if pred.p1_odds_american:
                        break
                if pred.p1_odds_american:
                    break
            break  # matched one event, move to next prediction


def pick_schema(p: BestPick) -> BestPickSchema:
    return BestPickSchema(
        pick_type=p.pick_type,
        label=p.label,
        pick=p.pick,
        player_name=p.player_name,
        edge_pct=p.edge_pct,
        confidence=p.confidence,
        reasoning=p.reasoning,
        odds_american=p.odds_american,
        ev_pct=p.ev_pct,
        model_prob=p.model_prob,
        market_prob=p.market_prob,
        kelly_fraction=p.kelly_fraction,
        data_quality_flags=list(p.data_quality_flags),
        odds_source=p.odds_source,
    )


async def build_best_picks_response(
    db: AsyncSession, registry: ModelRegistry, match_date: Optional[date], today: date
) -> BestPicksResponse:
    target_date = target_dates(match_date, today)

    # 1. Get predictions
    predictions = await slate_predictions(db, registry, match_date, today)

    if not predictions:
        return BestPicksResponse(date=match_date or today, count=0, matches=[])

    # 1b. Overlay live moneyline odds for any predictions missing DB odds
    try:
        await overlay_live_moneyline(predictions)
    except Exception:
        pass

    # 2. Get all props (all sources)
    player_props = await get_today_props(db)
    odds_props = await get_today_match_odds_as_props(db, books=stored_book_keys(settings.live_odds_bookmakers))
    all_props = [*player_props, *odds_props]
    matches = await match_repo.get_upcoming(db, target_date)
    match_player_ids_map = {m.id: (m.p1_id, m.p2_id) for m in matches}

    # 3. Get rolling stats for all players in props + their opponents
    from app.routers.props import (
        _fetch_market_totals,
        _fetch_market_win_probs,
        _fetch_opponent_ids,
        _fetch_win_probs,
        enrich_with,
    )
    opponent_ids_map = await _fetch_opponent_ids(db, all_props)
    prop_player_ids = [p.player_id for p in all_props if p.player_id is not None]
    opponent_ids = list(opponent_ids_map.values())
    match_player_ids = [pid for pair in match_player_ids_map.values() for pid in pair]
    all_player_ids = list(set(prop_player_ids + opponent_ids + match_player_ids))
    rolling_stats = await get_rolling_stats_batch_all_surfaces(db, all_player_ids) if all_player_ids else {}

    # 4. Get win probs and market totals
    prediction_win_probs = await _fetch_win_probs(db, all_props)
    market_win_probs = await _fetch_market_win_probs(db, all_props)
    market_totals = await _fetch_market_totals(db, all_props)
    market_total_games = {match_id: total.line for match_id, total in market_totals.items()}

    # 5. Build best picks per match, in a worker thread: pure CPU that would
    # otherwise hold every other request on the hosted instance (37e).
    def assemble() -> list[MatchBestPicksSchema]:
        # Cards read the board's rows for player props, never their own copy (F-04, F-05).
        prop_lines = enrich_with(
            player_props, opponent_ids_map, rolling_stats, prediction_win_probs, market_win_probs, market_totals
        )
        match_picks = []
        for pred in predictions:
            mbp = build_best_picks(
                pred,
                all_props,
                rolling_stats,
                prop_lines,
                match_player_ids_map.get(pred.match_id),
                market_total_games,
            )
            if mbp.picks:  # only include matches that have at least 1 pick
                match_picks.append(mbp)
        return [
            MatchBestPicksSchema(
                match_id=m.match_id,
                start_utc=m.start_utc,
                p1_name=m.p1_name,
                p2_name=m.p2_name,
                tour=m.tour,
                tour_label=m.tour_label or m.tour,
                surface=m.surface,
                tournament=m.tournament,
                round=m.round,
                p1_win_prob=m.p1_win_prob,
                p2_win_prob=m.p2_win_prob,
                p1_odds_american=m.p1_odds_american,
                p2_odds_american=m.p2_odds_american,
                h2h_p1_wins=m.h2h_p1_wins,
                h2h_p2_wins=m.h2h_p2_wins,
                picks=[
                    pick_schema(p) for p in m.picks
                ],
            )
            for m in match_picks
        ]

    schemas = await asyncio.to_thread(assemble)
    return BestPicksResponse(date=match_date or today, count=len(schemas), matches=schemas)


async def best_picks_for(
    db: AsyncSession,
    registry: ModelRegistry,
    match_date: Optional[date],
    today: date,
    tour: Optional[str] = None,
) -> Optional[BestPicksResponse]:
    """The cached best picks, optionally for one tour; None when the build failed."""
    response = await cached_best_picks(
        target_dates(match_date, today),
        today,
        lambda: build_best_picks_response(db, registry, match_date, today),
    )
    if response is None:
        return None
    if tour:
        matches = [m for m in response.matches if m.tour.upper() == tour.upper()]
        response = BestPicksResponse(date=response.date, count=len(matches), matches=matches)
    return response
