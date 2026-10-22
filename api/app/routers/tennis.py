import asyncio
from dataclasses import asdict
from datetime import date, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_odds_events import event_start, match_event
from app.db.pool import get_db
from app.repositories import matches as match_repo
from app.repositories.players import get_latest_elo, get_rolling_stats, get_rolling_stats_batch_all_surfaces, normalize_name
from app.repositories.props import get_today_props, get_today_match_odds_as_props
from app.schemas.tennis import (
    BankrollBuilderResponse,
    BankrollPickSchema,
    BestPickSchema,
    BestPicksResponse,
    MatchBestPicksSchema,
    MatchDetailResponse,
    MatchResearchSchema,
    MatchH2H,
    MatchMeetingSchema,
    MatchOddsHistoryResponse,
    MatchOddsRow,
    MatchPlayerDetail,
    MatchRecentFormResponse,
    MatchPrediction,
    ModelPredictionsResponse,
    ModelPrizePicksLinesResponse,
    ModelPropTiersResponse,
    ParlayLegSchema,
    PlayerDetailResponse,
    PlayerEloPointSchema,
    PlayerEloSchema,
    PlayerMatchLogSchema,
    PastPropSchema,
    PastPropSummarySchema,
    PlayerMatchesResponse,
    PlayerPropsResponse,
    PlayerRecordSchema,
    PlayerNextMatchSchema,
    PlayerServeReturnResponse,
    PlayerSurfaceComparisonSchema,
    PlayerSurfaceStatsSchema,
    TourAverageStatsSchema,
    PlayerStatsResponse,
    PlayerRecentForm,
    PlayerFormStats,
    PredictionsResponse,
    RecentMatchResult as RecentMatchResultSchema,
    SuggestedParlaySchema,
)
from app.services.tennis.best_picks import BestPick, build_best_picks
from app.services.tennis.match_detail import (
    MatchDetail,
    MatchDetailPlayer,
    build_match_detail,
    match_odds_history,
    winner_side,
)
from app.services.tennis.live_odds_cache import TimedSingleFlight
from app.services.tennis.prediction_cache import cached_best_picks, cached_predictions
from app.services.tennis.predictor import PredictionOutput
from app.services.tennis import track_record
from app.services.tennis.player_detail import (
    MatchLogEntry,
    PlayerDetail,
    PlayerServeReturn,
    build_player_matches,
    build_player_props,
    build_player_detail,
    build_serve_return,
)

router = APIRouter()
_PLAYER_STATS_MIN_SURFACE_SAMPLE = 10


@router.get("/matches/{match_id}/recent-form", response_model=MatchRecentFormResponse)
async def get_match_recent_form(
    match_id: int, db: AsyncSession = Depends(get_db)
) -> MatchRecentFormResponse:
    match_players = await match_repo.get_match_players(db, match_id)
    if match_players is None:
        raise HTTPException(status_code=404, detail="Match not found")

    match_date, players = match_players
    player_ids = [player.id for player in players]
    results = await match_repo.get_recent_completed_matches(
        db, player_ids, match_date
    )
    stats_by_player = await get_rolling_stats_batch_all_surfaces(db, player_ids)
    return MatchRecentFormResponse(
        match_id=match_id,
        players=[
            PlayerRecentForm(
                player_id=player.id,
                player_name=player.name,
                matches=[
                    RecentMatchResultSchema(
                        match_date=result.match_date,
                        opponent_name=result.opponent_name,
                        score=result.score,
                        result=result.result,
                        aces=result.aces,
                        double_faults=result.double_faults,
                        break_chances_created=result.break_chances_created,
                        break_points_converted=result.break_points_converted,
                    )
                    for result in results[player.id]
                ],
                last_52_w=PlayerFormStats(
                    svc_pts_won=stats.svc_pts_won,
                    ret_pts_won=stats.ret_pts_won,
                    aces_per_game=stats.aces_per_game,
                    df_per_game=stats.df_per_game,
                    hold_pct=stats.hold_pct,
                    break_pct=stats.break_pct,
                    win_rate=stats.win_rate,
                ) if (stats := stats_by_player.get((player.id, None))) else None,
            )
            for player in players
        ],
    )


# ── Live-odds helpers ─────────────────────────────────────────────────────────

# Odds move, but not so fast that a moneyline a few minutes old misleads a pick,
# and a longer window is what keeps page loads inside the hourly API quota.
_LIVE_ODDS_TTL_SECONDS = 15 * 60
_LIVE_ODDS: TimedSingleFlight[dict] = TimedSingleFlight(_LIVE_ODDS_TTL_SECONDS)


def _dec_to_american(dec) -> Optional[int]:
    try:
        d = float(dec)
        if d <= 1.0:
            return None
        if d >= 2.0:
            return round((d - 1) * 100)
        return round(-100 / (d - 1))
    except (TypeError, ValueError, ZeroDivisionError):
        return None


async def _overlay_live_moneyline(predictions: list[PredictionOutput]) -> None:
    """Fetch live moneyline odds and fill in any predictions missing DB odds.

    DB odds (from odds_api.py ingest) are used when available — live API is
    only called when one or more predictions have no odds in the DB, and its
    result is shared across requests for _LIVE_ODDS_TTL_SECONDS.
    """
    needs = [p for p in predictions if p.p1_odds_american is None or p.p2_odds_american is None]
    if not needs:
        return

    # Lazy import to avoid circular dependency at module load time
    from app.routers.props import _fetch_live_tennis_odds

    live_data = await _LIVE_ODDS.get(
        ("DraftKings,Bet365", 24),
        lambda: _fetch_live_tennis_odds(bookmakers="DraftKings,Bet365", hours_ahead=24),
    )
    if not live_data:
        return

    events = live_data.get("events") or []
    if not events:
        return

    _ML_NAMES = {"ml", "h2h", "moneyline", "winner", "match winner", "match ml", "match result"}

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
                        h_odds = _dec_to_american(sel.get("home"))
                        a_odds = _dec_to_american(sel.get("away"))
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


def _to_schema(o: PredictionOutput) -> MatchPrediction:
    return MatchPrediction(
        match_id=o.match_id,
        start_utc=o.start_utc,
        p1_name=o.p1_name,
        p2_name=o.p2_name,
        tour=o.tour,
        tour_label=o.tour_label or o.tour,
        surface=o.surface,
        tournament=o.tournament,
        round=o.round,
        p1_win_prob=o.p1_win_prob,
        p2_win_prob=o.p2_win_prob,
        p1_elo_prob=o.p1_elo_prob,
        p1_ml_prob=o.p1_ml_prob,
        p1_market_prob=o.p1_market_prob,
        ensemble_weights=o.ensemble_weights,
        quality_flags=o.quality_flags,
        p1_odds_american=o.p1_odds_american,
        p2_odds_american=o.p2_odds_american,
        h2h_p1_wins=o.h2h_p1_wins,
        h2h_p2_wins=o.h2h_p2_wins,
        p1_id=o.p1_id,
        p2_id=o.p2_id,
    )


def _pick_schema(p: BestPick) -> BestPickSchema:
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


def _player_detail_schema(p: MatchDetailPlayer) -> MatchPlayerDetail:
    return MatchPlayerDetail(
        player_id=p.player_id, name=p.name, rank=p.rank, hand=p.hand,
        country=p.country, elo=p.elo, elo_surface=p.elo_surface,
    )


def _match_detail_schema(d: MatchDetail) -> MatchDetailResponse:
    m = d.match
    return MatchDetailResponse(
        match_id=m.id,
        status=m.status,
        start_utc=m.start_utc,
        tour=m.tour,
        tour_label=d.tour_label,
        surface=m.surface,
        indoor=d.meta.indoor,
        tournament=m.tournament,
        round=m.round,
        best_of=d.best_of,
        score=d.meta.score,
        winner_side=winner_side(m),
        p1=_player_detail_schema(d.p1),
        p2=_player_detail_schema(d.p2),
        h2h=MatchH2H(
            p1_wins=d.h2h["p1_wins"],
            p2_wins=d.h2h["p2_wins"],
            surface_p1_wins=d.h2h_surface["p1_wins"] if d.h2h_surface else None,
            surface_p2_wins=d.h2h_surface["p2_wins"] if d.h2h_surface else None,
        ),
        meetings=[
            MatchMeetingSchema(
                match_date=mt.match_date, tournament=mt.tournament, round=mt.round,
                surface=mt.surface, score=mt.score, winner_side=mt.winner_side,
            )
            for mt in d.meetings
        ],
        prediction=_to_schema(d.prediction) if d.prediction else None,
        prediction_source=d.prediction_source,
        prediction_generated_at=d.prediction_generated_at,
        model_version=d.model_version,
        ml_pick=_pick_schema(d.ml_pick) if d.ml_pick else None,
        research=MatchResearchSchema(**asdict(d.research)) if d.research else None,
    )


@router.get("/matches/{match_id}", response_model=MatchDetailResponse)
async def get_match_detail(
    match_id: int, request: Request, db: AsyncSession = Depends(get_db)
) -> MatchDetailResponse:
    detail = await build_match_detail(db, request.app.state.registry, match_id, date.today())
    if detail is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return _match_detail_schema(detail)


@router.get("/matches/{match_id}/odds-history", response_model=MatchOddsHistoryResponse)
async def get_match_odds_history(
    match_id: int,
    market: Literal["moneyline", "total_games"] = "moneyline",
    db: AsyncSession = Depends(get_db),
) -> MatchOddsHistoryResponse:
    rows = await match_odds_history(db, match_id, market)
    if rows is None:
        raise HTTPException(status_code=404, detail="Match not found")
    return MatchOddsHistoryResponse(
        match_id=match_id,
        market=market,
        rows=[
            MatchOddsRow(book=r.book, p1_odds=r.p1_odds, p2_odds=r.p2_odds, line=r.line, fetched_at=r.fetched_at)
            for r in rows
        ],
    )


def _player_page_schema(detail: PlayerDetail) -> PlayerDetailResponse:
    latest = detail.elo.summary.latest
    return PlayerDetailResponse(
        player_id=detail.header.id,
        name=detail.header.name,
        tour=detail.header.tour,
        hand=detail.header.hand,
        country=detail.header.country,
        birth_date=detail.header.birth_date,
        rank=detail.rank,
        elo=PlayerEloSchema(
            overall=latest.overall if latest else None,
            hard=latest.hard if latest else None,
            clay=latest.clay if latest else None,
            grass=latest.grass if latest else None,
            as_of=latest.as_of if latest else None,
            change=detail.elo.summary.change,
            tour_rank=detail.elo.tour_rank,
            tour_rank_of=detail.elo.tour_rank_of,
            history=[
                PlayerEloPointSchema(as_of=s.as_of, overall=s.overall, hard=s.hard, clay=s.clay, grass=s.grass)
                for s in detail.elo.history
            ],
        ),
        next_match=PlayerNextMatchSchema(**vars(detail.next_match)) if detail.next_match else None,
        aliases=detail.aliases,
        stats_computed_at=detail.stats_computed_at,
    )


@router.get("/players/{player_id:int}", response_model=PlayerDetailResponse)
async def get_player_detail(player_id: int, db: AsyncSession = Depends(get_db)) -> PlayerDetailResponse:
    detail = await build_player_detail(db, player_id, date.today())
    if detail is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return _player_page_schema(detail)


def _serve_return_schema(result: PlayerServeReturn) -> PlayerServeReturnResponse:
    return PlayerServeReturnResponse(
        tour=result.tour,
        surfaces=[
            PlayerSurfaceComparisonSchema(
                surface=s.surface,
                player=PlayerSurfaceStatsSchema(matches=s.player_matches, **vars(s.player)) if s.player else None,
                tour_average=TourAverageStatsSchema(players=s.tour_average.players, **vars(s.tour_average.stats)),
            )
            for s in result.surfaces
        ],
    )


@router.get("/players/{player_id:int}/serve-return", response_model=PlayerServeReturnResponse)
async def get_player_serve_return(player_id: int, db: AsyncSession = Depends(get_db)) -> PlayerServeReturnResponse:
    result = await build_serve_return(db, player_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return _serve_return_schema(result)


def _match_log_schema(entry: MatchLogEntry) -> PlayerMatchLogSchema:
    m, box = entry.match, entry.box
    return PlayerMatchLogSchema(
        match_id=m.match_id, match_date=m.match_date, tournament=m.tournament, round=m.round,
        surface=m.surface, best_of=m.best_of, opponent_id=m.opponent_id, opponent_name=m.opponent_name,
        opponent_rank=m.opponent_rank, result="W" if m.won else "L", score=m.score,
        aces=box.aces if box else None,
        double_faults=box.double_faults if box else None,
        bp_saved=box.break_points_saved if box else None,
        bp_faced=box.break_points_faced if box else None,
        bp_won=box.break_points_converted if box else None,
        bp_created=box.break_chances_created if box else None,
    )


@router.get("/players/{player_id:int}/matches", response_model=PlayerMatchesResponse)
async def get_player_matches(
    player_id: int,
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> PlayerMatchesResponse:
    matches = await build_player_matches(db, player_id, limit, date.today())
    if matches is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerMatchesResponse(
        log=[_match_log_schema(entry) for entry in matches.log],
        record=PlayerRecordSchema.model_validate(matches.record),
    )


@router.get("/players/{player_id:int}/props", response_model=PlayerPropsResponse)
async def get_player_props(player_id: int, db: AsyncSession = Depends(get_db)) -> PlayerPropsResponse:
    props = await build_player_props(db, player_id)
    if props is None:
        raise HTTPException(status_code=404, detail="Player not found")
    return PlayerPropsResponse(
        projection_version=props.projection_version,
        rows=[PastPropSchema.model_validate(row) for row in props.rows],
        summary=PastPropSummarySchema(hits=props.hits, misses=props.misses),
    )


@router.get("/model/predictions", response_model=ModelPredictionsResponse)
async def get_model_predictions(
    model_version: str = Query(track_record.DEFAULT_MODEL_VERSION, max_length=64),
    db: AsyncSession = Depends(get_db),
) -> ModelPredictionsResponse:
    grading = await track_record.get_prediction_grading(db, model_version)
    if grading is None:
        raise HTTPException(status_code=503, detail="Prediction grading is unavailable; try again shortly")
    if model_version not in {v.model_version for v in grading.versions}:
        raise HTTPException(status_code=404, detail=f"No settled predictions for model version {model_version}")
    return ModelPredictionsResponse.model_validate(grading)


@router.get("/model/prizepicks-lines", response_model=ModelPrizePicksLinesResponse)
async def get_model_prizepicks_lines(db: AsyncSession = Depends(get_db)) -> ModelPrizePicksLinesResponse:
    settlement = await track_record.get_line_settlement(db)
    if settlement is None:
        raise HTTPException(status_code=503, detail="PrizePicks line grading is unavailable; try again shortly")
    return ModelPrizePicksLinesResponse.model_validate(settlement)


@router.get("/model/prop-tiers", response_model=ModelPropTiersResponse)
async def get_model_prop_tiers(db: AsyncSession = Depends(get_db)) -> ModelPropTiersResponse:
    grading = await track_record.get_tier_grading(db)
    if grading is None:
        raise HTTPException(status_code=503, detail="Tier grading is unavailable; try again shortly")
    return ModelPropTiersResponse.model_validate(grading)


PREDICTIONS_UNAVAILABLE = "Tennis predictions are temporarily unavailable."


def _target_dates(match_date: Optional[date], today: date) -> list[date]:
    return [match_date] if match_date else [today, today + timedelta(days=1)]


async def _slate_predictions(
    db: AsyncSession, request: Request, match_date: Optional[date], today: date
) -> list[PredictionOutput]:
    results = await cached_predictions(db, request.app.state.registry, _target_dates(match_date, today), today)
    if results is None:
        raise HTTPException(status_code=503, detail=PREDICTIONS_UNAVAILABLE)
    return results


@router.get("/predictions/today", response_model=PredictionsResponse)
async def get_predictions_today(
    match_date: date = None,
    tour: str = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    today = date.today()
    results = await _slate_predictions(db, request, match_date, today)

    if tour:
        results = [r for r in results if r.tour.upper() == tour.upper()]

    return PredictionsResponse(
        date=match_date or today,
        count=len(results),
        matches=[_to_schema(r) for r in results],
    )


@router.get("/predictions/best-picks", response_model=BestPicksResponse)
async def get_best_picks(
    match_date: date = None,
    tour: str = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Return top 3 best picks per matchup, combining ML value, prop edges, and derived picks."""
    today = date.today()
    response = await cached_best_picks(
        _target_dates(match_date, today),
        today,
        lambda: _build_best_picks(db, request, match_date, today),
    )
    if response is None:
        raise HTTPException(status_code=503, detail=PREDICTIONS_UNAVAILABLE)
    if tour:
        matches = [m for m in response.matches if m.tour.upper() == tour.upper()]
        response = BestPicksResponse(date=response.date, count=len(matches), matches=matches)
    return response


async def _build_best_picks(
    db: AsyncSession, request: Request, match_date: Optional[date], today: date
) -> BestPicksResponse:
    target_date = _target_dates(match_date, today)

    # 1. Get predictions
    predictions = await _slate_predictions(db, request, match_date, today)

    if not predictions:
        return BestPicksResponse(date=match_date or today, count=0, matches=[])

    # 1b. Overlay live moneyline odds for any predictions missing DB odds
    try:
        await _overlay_live_moneyline(predictions)
    except Exception:
        pass

    # 2. Get all props (all sources)
    player_props = await get_today_props(db)
    odds_props = await get_today_match_odds_as_props(db, books=["draftkings", "bet365", "betonline.ag"])
    all_props = [*player_props, *odds_props]
    matches = await match_repo.get_upcoming(db, target_date)
    match_player_ids_map = {m.id: (m.p1_id, m.p2_id) for m in matches}

    # 3. Get rolling stats for all players in props + their opponents
    from app.routers.props import (
        _fetch_market_total_games,
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
    market_total_games = await _fetch_market_total_games(db, all_props)

    # 5. Build best picks per match, in a worker thread: pure CPU that would
    # otherwise hold every other request on the hosted instance (37e).
    def assemble() -> list[MatchBestPicksSchema]:
        # Cards read the board's rows for player props, never their own copy (F-04, F-05).
        prop_lines = enrich_with(
            player_props, opponent_ids_map, rolling_stats, prediction_win_probs, market_win_probs, market_total_games
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
                    _pick_schema(p) for p in m.picks
                ],
            )
            for m in match_picks
        ]

    schemas = await asyncio.to_thread(assemble)
    return BestPicksResponse(date=match_date or today, count=len(schemas), matches=schemas)


@router.get("/players/stats", response_model=PlayerStatsResponse | None)
async def get_player_stats(
    name: str,
    tour: str | None = None,
    surface: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    from sqlalchemy import text

    norm = normalize_name(name)
    if tour:
        row = await db.execute(
            text("SELECT id FROM players WHERE name_norm = :n AND tour = :t"),
            {"n": norm, "t": tour.upper()},
        )
        r = row.fetchone()
        player_id = r[0] if r else None
        if player_id is None:
            fallback_sql = """
                SELECT id FROM players
                WHERE name_norm = :n
                ORDER BY
                    CASE
                        WHEN :t = 'CHALLENGER' AND tour = 'ATP' THEN 0
                        WHEN :t = 'CHALLENGER' AND tour = 'WTA' THEN 1
                        ELSE 2
                    END,
                    id
                LIMIT 1
            """
            row = await db.execute(text(fallback_sql), {"n": norm, "t": tour.upper()})
            r = row.fetchone()
            player_id = r[0] if r else None
    else:
        row = await db.execute(
            text("SELECT id FROM players WHERE name_norm = :n LIMIT 1"),
            {"n": norm},
        )
        r = row.fetchone()
        player_id = r[0] if r else None

    if player_id is None:
        # try aliases
        row = await db.execute(
            text("""
                SELECT p.id FROM player_aliases a
                JOIN players p ON p.id = a.canonical_player_id
                WHERE a.alias_name_norm = :n LIMIT 1
            """),
            {"n": norm},
        )
        r = row.fetchone()
        player_id = r[0] if r else None

    if player_id is None:
        return None

    # Prefer last_52w (complete stats including ret_pts_won).
    # Use surface-specific rows only when the sample is large enough; otherwise
    # mirror the projection path and show the all-surface baseline.
    stats = await get_rolling_stats(db, player_id, surface=surface, stat_period="last_52w")
    if surface is not None and (
        stats is None or (stats.matches_count or 0) < _PLAYER_STATS_MIN_SURFACE_SAMPLE
    ):
        fallback_stats = await get_rolling_stats(db, player_id, surface=None, stat_period="last_52w")
        if fallback_stats is not None:
            stats = fallback_stats
    if stats is None:
        return None

    elo_data = await get_latest_elo(db, player_id)
    return PlayerStatsResponse(
        player_id=stats.player_id,
        surface=stats.surface,
        stat_period=stats.stat_period,
        win_rate=stats.win_rate,
        svc_pts_won=stats.svc_pts_won,
        ret_pts_won=stats.ret_pts_won,
        aces_per_game=stats.aces_per_game,
        df_per_game=stats.df_per_game,
        hold_pct=stats.hold_pct,
        break_pct=stats.break_pct,
        matches_count=stats.matches_count,
        first_in_pct=stats.first_in_pct,
        first_won_pct=stats.first_won_pct,
        second_won_pct=stats.second_won_pct,
        dominance_ratio=stats.dominance_ratio,
        break_points_created_per_return_game=stats.break_points_created_per_return_game,
        allowed_break_points_per_service_game=stats.allowed_break_points_per_service_game,
        elo=elo_data.elo if elo_data else None,
        elo_hard=elo_data.elo_hard if elo_data else None,
        elo_clay=elo_data.elo_clay if elo_data else None,
        elo_grass=elo_data.elo_grass if elo_data else None,
    )


@router.get("/players/compare")
async def compare_players(p1: str, p2: str, db: AsyncSession = Depends(get_db)):
    # TODO: implement
    return {}


@router.get("/bankroll/today", response_model=BankrollBuilderResponse)
async def get_bankroll_builder(
    match_date: date = None,
    tour: str = None,
    max_singles: int = 15,
    max_parlays: int = 10,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Bankroll Builder: ranked singles + 2-leg parlays across all bet types."""
    from app.services.tennis.bankroll_builder import build_bankroll_picks

    today = date.today()
    target_date = match_date or [today, today + timedelta(days=1)]
    result = await build_bankroll_picks(
        db, request, target_date,
        tour_filter=tour,
        max_singles=max_singles,
        max_parlays=max_parlays,
    )

    return BankrollBuilderResponse(
        date=result.date,
        total_matches_scanned=result.total_matches_scanned,
        singles_count=len(result.singles),
        parlays_count=len(result.parlays),
        singles=[
            BankrollPickSchema(
                match_id=s.match_id,
                p1_name=s.p1_name, p2_name=s.p2_name,
                tour=s.tour, surface=s.surface,
                tournament=s.tournament, round=s.round,
                start_utc=s.start_utc,
                bet_type=s.bet_type,
                pick_label=s.pick_label,
                pick_side=s.pick_side,
                our_prob=s.our_prob,
                market_prob=s.market_prob,
                odds_american=s.odds_american,
                edge_pct=s.edge_pct,
                ev=s.ev,
                kelly_fraction=s.kelly_frac,
                confidence=s.confidence,
                reasoning=s.reasoning,
            )
            for s in result.singles
        ],
        parlays=[
            SuggestedParlaySchema(
                legs=[
                    ParlayLegSchema(
                        match_id=leg.match_id,
                        p1_name=leg.p1_name, p2_name=leg.p2_name,
                        tour=leg.tour,
                        bet_type=leg.bet_type,
                        pick_label=leg.pick_label,
                        our_prob=leg.our_prob,
                        odds_american=leg.odds_american,
                        confidence=leg.confidence,
                    )
                    for leg in p.legs
                ],
                combined_prob=p.combined_prob,
                combined_odds_american=p.combined_odds_american,
                combined_ev=p.combined_ev,
                combined_kelly=p.combined_kelly,
                combined_edge_pct=p.combined_edge_pct,
                confidence=p.confidence,
            )
            for p in result.parlays
        ],
    )


@router.get("/parlays/suggested")
async def get_suggested_parlays(
    match_date: date = None,
    tour: str = None,
    request: Request = None,
    db: AsyncSession = Depends(get_db),
):
    """Legacy endpoint — redirects to bankroll builder."""
    return await get_bankroll_builder(match_date, tour, 15, 10, request, db)
