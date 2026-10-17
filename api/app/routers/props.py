import logging
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.odds import american_to_prob, devig_two_way
from app.core.prop_ev import assess_prop
from app.core.prop_probs import games_won_probabilities, prop_probabilities, prop_side
from app.core.prop_projection import (
    _ACE_MATCHUP_FACTOR_MAX,
    _ACE_MATCHUP_FACTOR_MIN,
    _BASELINE_HOLD_PCT,
    _BASELINE_RET_PTS_WON,
    _BREAK_CHANCE_FACTOR_MAX,
    _BREAK_CHANCE_FACTOR_MIN,
    _BREAK_CHANCES_PER_MATCH,
    _BREAK_POINTS_PER_BREAK_GAME,
    _LEAGUE_ACE_RATE,
    _SERVICE_GAMES_PER_MATCH,
    _SERVE_POINTS_PER_MATCH,
    _SURFACE_ACE_FACTOR,
    _SURFACE_DF_FACTOR,
    ace_matchup_factor as _ace_matchup_factor,
    compute_stat_avg as _compute_stat_avg,
    expected_break_point_chances as _expected_break_point_chances,
    expected_service_points as _expected_service_points,
    expected_total_games as _expected_total_games,
    first_set_for_matchup as _first_set_for_matchup,
    normalize_stat_type as _normalize_stat_type,
    serve_hold as _serve_hold,
)
from app.core.tennis_first_set import FIRST_SET_STATS, pmf_probabilities, stat_pmf
from app.core.tennis_odds_events import odds_event_tour
from app.db.pool import get_db
from app.repositories.players import PlayerRollingStats, get_rolling_stats_batch_all_surfaces
from app.repositories.props import Prop, get_today_match_odds_as_props, get_today_props
from app.schemas.props import PropAudit, PropLine, PropsAuditResponse, PropsAuditSummary, PropsResponse
from app.services.tennis.live_odds_cache import LiveOddsRateLimited

logger = logging.getLogger(__name__)

router = APIRouter()
ODDS_API_BASE = "https://api.odds-api.io/v3"

# Default expected counts per match (used for Poisson when no player stats available)
_DEFAULT_EXPECTED: dict[str, float] = {
    "aces": 8.0,
    "double_faults": 3.0,
    "break_points": 1.2,
}

_STATS_STALE_HOURS = 48
_SMALL_SAMPLE_MATCHES = 10
_SUPPORTED_PROJECTION_STATS = {
    "aces",
    "double_faults",
    "break_points_converted",
    "break_points_won",
    "total_games_won",
    "games_won",
    "total_games",
    "total_sets",
    "total_tie_breaks",
    "fantasy_score",
    *FIRST_SET_STATS,
}
_CONF_RANK = {"PASS": 0, "LEAN": 1, "STRONG": 2, "LOCK": 3}
_CONF_BY_RANK = {v: k for k, v in _CONF_RANK.items()}


def _cap_confidence(confidence: Optional[str], cap: str) -> Optional[str]:
    if confidence is None:
        return None
    return _CONF_BY_RANK[min(_CONF_RANK.get(confidence, 0), _CONF_RANK[cap])]


def _downgrade_confidence(confidence: Optional[str]) -> Optional[str]:
    if confidence is None:
        return None
    return _CONF_BY_RANK[max(0, _CONF_RANK.get(confidence, 0) - 1)]


def _deciding_set_probability(win_prob: Optional[float], best_of: int) -> Optional[float]:
    if win_prob is None:
        return None
    p = _clamp(float(win_prob), 0.01, 0.99)
    return 2.0 * p * (1.0 - p)


def _match_link_method(prop: Prop) -> Optional[str]:
    raw = prop.raw_json or {}
    method = raw.get("match_link_method")
    return str(method) if method else None


def _match_finished(prop: Prop) -> bool:
    return (prop.match_status or "").lower() in {"completed", "cancelled"}


def _f(v) -> Optional[float]:
    """Coerce a DB value (possibly Decimal) to float, preserving None."""
    return float(v) if v is not None else None


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _projection_inputs(
    stat_type: str,
    stats: PlayerRollingStats,
    opponent_stats: Optional[PlayerRollingStats],
    win_prob: Optional[float],
    market_total_games: Optional[float],
    best_of: int = 3,
) -> dict[str, float | str]:
    st = _normalize_stat_type(stat_type)
    inputs: dict[str, float | str] = {
        "projection_source": "market_total" if market_total_games is not None and market_total_games >= 17.0 else "model_total",
        "expected_total_games": round(
            _expected_total_games(stats, opponent_stats, win_prob, market_total_games, best_of), 2
        ),
        "expected_service_points": round(
            _expected_service_points(stats, opponent_stats, win_prob, market_total_games, best_of), 2
        ),
    }

    if market_total_games is not None:
        inputs["market_total_games"] = round(market_total_games, 2)
    if st == "aces":
        ace_rate = _f(stats.aces_per_game)
        opp_allowed = _f(getattr(opponent_stats, "allowed_aces_per_sp", None)) if opponent_stats is not None else None
        if ace_rate is not None:
            inputs["player_ace_rate"] = round(ace_rate, 4)
        if opp_allowed is not None:
            inputs["opponent_allowed_ace_rate"] = round(opp_allowed, 4)
    elif st == "double_faults":
        df_rate = _f(stats.df_per_game)
        opp_allowed = _f(getattr(opponent_stats, "allowed_df_per_sp", None)) if opponent_stats is not None else None
        if df_rate is not None:
            inputs["player_df_rate"] = round(df_rate, 4)
        if opp_allowed is not None:
            inputs["opponent_allowed_df_rate"] = round(opp_allowed, 4)
    elif st in FIRST_SET_STATS:
        inputs["player_hold"] = round(_serve_hold(stats), 4)
        inputs["opponent_hold"] = round(
            _serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT, 4
        )
    elif st in ("break_points_converted", "break_points_won"):
        bp_rate = _f(stats.break_pct)
        created_rate = _f(getattr(stats, "break_points_created_per_return_game", None))
        allowed_rate = _f(getattr(opponent_stats, "allowed_break_points_per_service_game", None)) if opponent_stats is not None else None
        if bp_rate is not None:
            inputs["break_point_conversion_rate"] = round(bp_rate, 4)
        if created_rate is not None:
            inputs["player_bp_chances_created_per_return_game"] = round(created_rate, 4)
        if allowed_rate is not None:
            inputs["opponent_bp_chances_allowed_per_service_game"] = round(allowed_rate, 4)
        inputs["expected_break_point_chances"] = round(
            _expected_break_point_chances(stats, opponent_stats, win_prob, market_total_games),
            2,
        )

    return inputs


def _compute_opponent_allowed(
    stat_type: str,
    opponent_stats: PlayerRollingStats,
    surface: Optional[str] = None,
) -> Optional[float]:
    """Derive what the opponent typically 'gives up' per match for this stat.

    Same units as the line (and stat_avg), so the UI can display side-by-side with player's avg.
    Returns None for stats where 'opponent concedes' is not meaningful (DFs, moneyline, etc.).
    """
    st = _normalize_stat_type(stat_type)
    surf_key = (surface or "").title()

    if st == "aces":
        surf_factor = _SURFACE_ACE_FACTOR.get(surf_key, 1.0)
        # Prefer the opponent's actual allowed-ace rate vs the field when available
        allowed_ace = _f(getattr(opponent_stats, "allowed_aces_per_sp", None))
        if allowed_ace is not None and allowed_ace > 0:
            return allowed_ace * _SERVE_POINTS_PER_MATCH * surf_factor
        # Fallback to league-rate-scaled-by-return-strength (pre-migration-0009 data)
        opp_ret = _f(opponent_stats.ret_pts_won)
        if opp_ret is None:
            return None
        baseline_nonreturn = max(1e-6, 1.0 - _BASELINE_RET_PTS_WON)
        opp_nonreturn = max(0.05, 1.0 - opp_ret)
        matchup_factor = _clamp(
            opp_nonreturn / baseline_nonreturn,
            _ACE_MATCHUP_FACTOR_MIN,
            _ACE_MATCHUP_FACTOR_MAX,
        )
        return _LEAGUE_ACE_RATE * _SERVE_POINTS_PER_MATCH * surf_factor * matchup_factor

    if st in ("break_points_converted", "break_points_won"):
        opp_hold = _serve_hold(opponent_stats)
        if opp_hold is None:
            return None
        return (1.0 - opp_hold) * _SERVICE_GAMES_PER_MATCH

    if st in ("total_games_won", "games_won"):
        opp_hold = _serve_hold(opponent_stats)
        opp_bp = _f(opponent_stats.break_pct)
        if opp_hold is None or opp_bp is None:
            return None
        return opp_hold * _SERVICE_GAMES_PER_MATCH + opp_bp * _BREAK_CHANCES_PER_MATCH

    if st == "total_games":
        opp_hold = _serve_hold(opponent_stats)
        opp_bp = _f(opponent_stats.break_pct)
        if opp_hold is None or opp_bp is None:
            return None
        opp_games = opp_hold * _SERVICE_GAMES_PER_MATCH + opp_bp * _BREAK_CHANCES_PER_MATCH
        return opp_games * 2

    return None


def _enrich(
    prop: Prop,
    stats: Optional[PlayerRollingStats] = None,
    opponent_stats: Optional[PlayerRollingStats] = None,
    win_prob: Optional[float] = None,
    market_total_games: Optional[float] = None,
) -> PropLine:
    line_f = float(prop.line) if prop.line is not None else None
    stat_norm = _normalize_stat_type(prop.stat_type)
    is_prizepicks = prop.source == "prizepicks"
    match_finished = _match_finished(prop)
    # An unlinked prop carries no format, so 3 is the fallback rather than a
    # claim. Every projection below already defaults to 3, so this only changes
    # behavior for props that really are best-of-5.
    best_of = prop.best_of or 3
    data_quality_flags: list[str] = []
    if prop.player_id is None:
        data_quality_flags.append("missing_player")
    if prop.match_id is None:
        data_quality_flags.append("missing_match")
    if prop.surface is None:
        data_quality_flags.append("missing_surface")
    if stats is None:
        data_quality_flags.append("missing_stats")
    if opponent_stats is None and prop.match_id is not None:
        data_quality_flags.append("missing_opponent_stats")
    if win_prob is None and prop.match_id is not None:
        data_quality_flags.append("missing_prediction")
    if stat_norm not in _SUPPORTED_PROJECTION_STATS:
        data_quality_flags.append("unsupported_stat")
    # New and not yet graded forward (26f): shown, but never above LEAN.
    if stat_norm in FIRST_SET_STATS:
        data_quality_flags.append("ungraded_stat")
    if _match_link_method(prop) == "player_date_fallback":
        data_quality_flags.append("match_link_fallback")
    # Set-count stats derive from expected_sets_from_win_prob, which is hardcoded
    # best-of-3 (2 + 2p(1-p), so 2.0 to 2.5 sets). A best-of-5 match runs 3 to 5,
    # and there is no fitted best-of-5 set model yet. Flag rather than project:
    # a confidently wrong number is worse than a blank one.
    if best_of >= 5 and stat_norm in ("total_sets", "total_tie_breaks"):
        data_quality_flags.append("bo5_unsupported_stat")
    if match_finished:
        data_quality_flags.append("match_finished")
    if prop.match_link_invalid:
        data_quality_flags.append("match_link_invalid")

    # Compute player-specific stat average and recommendation
    stat_avg = edge_pct = recommendation = None
    expected_service_points = None
    projection_source = "market_total" if market_total_games is not None and market_total_games >= 17.0 else "model_total"
    projection_inputs: dict[str, float | str] = {}
    matches_count = None
    if stats is not None and line_f is not None:
        stat_avg = _compute_stat_avg(
            prop.stat_type,
            stats,
            opponent_stats=opponent_stats,
            win_prob=win_prob,
            surface=prop.surface,
            market_total_games=market_total_games,
            best_of=best_of,
        )
        expected_service_points = _expected_service_points(
            stats, opponent_stats, win_prob, market_total_games, best_of
        )
        projection_inputs = _projection_inputs(
            prop.stat_type, stats, opponent_stats, win_prob, market_total_games, best_of
        )
        matches_count = stats.matches_count
        if matches_count is not None and matches_count < _SMALL_SAMPLE_MATCHES:
            data_quality_flags.append("small_sample")
        if stat_avg is not None and line_f > 0:
            edge_pct = round((stat_avg - line_f) / line_f * 100, 1)
            recommendation = "OVER" if stat_avg >= line_f else "UNDER"
            # PrizePicks demon/goblin are OVER-only bets, so OVER is the only side
            # there is. Whether it is worth playing is the EV tier's call — this
            # used to blank the side whenever the projection sat below the line,
            # which left rows showing a confidence and no direction to act on.
            if (prop.odds_type or "").lower() in ("demon", "goblin"):
                recommendation = "OVER"
    elif stats is not None:
        matches_count = stats.matches_count

    # Poisson probabilities — stat_avg is already per-match count (same scale as line)
    expected = stat_avg if stat_avg is not None else _DEFAULT_EXPECTED.get(stat_norm)
    p_over = p_under = p_push = confidence = None
    ev_pct = break_even_pct = hit_probability = None
    if expected is not None and line_f is not None:
        if stat_norm in FIRST_SET_STATS and stats is not None:
            probs = pmf_probabilities(stat_pmf(stat_norm, _first_set_for_matchup(stats, opponent_stats)), line_f)
        elif stat_norm in ("total_games_won", "games_won") and stats is not None:
            player_hold = _serve_hold(stats)
            opp_hold = _serve_hold(opponent_stats) if opponent_stats is not None else _BASELINE_HOLD_PCT
            probs = games_won_probabilities(line_f, expected, win_prob, player_hold, opp_hold)
        else:
            probs = prop_probabilities(
                prop.stat_type,
                line_f,
                expected,
                best_of,
                p_deciding_set=_deciding_set_probability(win_prob, best_of),
            )
        p_over, p_under, p_push = probs.p_over, probs.p_under, probs.p_push

        # Demon/goblin are OVER-only, so the OVER side is the only playable one.
        # Standard picks can be taken either way, so take the better side.
        odds_type_norm = (prop.odds_type or "").lower()
        if recommendation is not None and odds_type_norm not in ("demon", "goblin"):
            recommendation = prop_side(p_over, p_under)
        if odds_type_norm in ("demon", "goblin"):
            actionable = max(1e-9, 1.0 - p_push)
            hit_probability = p_over / actionable
        else:
            hit_probability = probs.decision_probability

        # Grade on expected value, not raw probability: a goblin that hits 97%
        # of the time still loses money if its price needs 76% and the line is
        # nearly free. See app/core/prop_ev.py.
        # Pass the book's real price when the row carries one. Today only the
        # match-odds sources populate p1_odds/p2_odds and those markets exit as
        # unsupported_stat before reaching here, so this changes nothing yet — it
        # keeps a priced sportsbook player prop from being graded on the
        # PrizePicks tier table the moment one lands.
        side_odds = None
        if recommendation is not None:
            side_odds = prop.p1_odds if recommendation == "OVER" else prop.p2_odds
        assessment = assess_prop(
            hit_probability,
            prop.odds_type,
            american_odds=side_odds,
            source=prop.source,
        )
        if assessment is not None:
            confidence = assessment.confidence
            ev_pct = assessment.ev_pct
            break_even_pct = round(assessment.break_even_probability * 100.0, 1)

    # Opponent "gives up" — derived per-match figure in same units as the line
    opp_stat_avg = None
    opp_matches_count = None
    if opponent_stats is not None:
        opp_stat_avg = _compute_opponent_allowed(prop.stat_type, opponent_stats, surface=prop.surface)
        opp_matches_count = opponent_stats.matches_count

    # Stats freshness — use the older of player/opponent computed_at so we flag the whole row
    stats_computed_at = None
    stats_stale = None
    candidate_times = [s.computed_at for s in (stats, opponent_stats) if s is not None and s.computed_at is not None]
    if candidate_times:
        stats_computed_at = min(candidate_times)
        age_hours = (datetime.now(UTC) - stats_computed_at).total_seconds() / 3600.0
        stats_stale = age_hours > _STATS_STALE_HOURS
        if stats_stale:
            data_quality_flags.append("stale_stats")

    if stat_norm in _SUPPORTED_PROJECTION_STATS:
        if prop.player_id is None:
            projection_status = "missing_player"
        elif prop.match_id is None:
            projection_status = "missing_match"
        elif stats is None:
            projection_status = "missing_stats"
        elif stat_avg is None:
            projection_status = "unsupported_stat"
        else:
            projection_status = "ok"
    else:
        projection_status = "unsupported_stat"

    if is_prizepicks:
        hard_blocks = {
            "missing_player",
            "missing_match",
            "missing_stats",
            "unsupported_stat",
            "match_finished",
            "match_link_invalid",
            "bo5_unsupported_stat",
        }
        if hard_blocks.intersection(data_quality_flags):
            recommendation = None
            confidence = None
        if {"stale_stats", "small_sample", "ungraded_stat"}.intersection(data_quality_flags):
            confidence = _cap_confidence(confidence, "LEAN")
        for flag in ("missing_opponent_stats", "missing_prediction"):
            if flag in data_quality_flags:
                confidence = _downgrade_confidence(confidence)

    projection_found = stat_avg is not None
    audit = PropAudit(
        player_resolved=prop.player_id is not None,
        match_linked=prop.match_id is not None,
        stats_fresh=False if stats_stale else True if stats_computed_at is not None else None,
        sample_size=matches_count,
        opponent_stats_found=opponent_stats is not None,
        prediction_found=win_prob is not None,
        projection_found=projection_found,
        match_link_method=_match_link_method(prop),
    )

    return PropLine(
        id=prop.id,
        player_id=prop.player_id,
        player_name=prop.player_name,
        match_id=prop.match_id,
        source=prop.source,
        stat_type=prop.stat_type,
        line=prop.line,
        odds_type=prop.odds_type,
        fetched_at=prop.fetched_at,
        start_time=prop.start_time,
        match_status=prop.match_status,
        match_finished=match_finished,
        match_link_invalid=prop.match_link_invalid,
        p1_odds=prop.p1_odds,
        p2_odds=prop.p2_odds,
        p_over=round(p_over, 3) if p_over is not None else None,
        p_under=round(p_under, 3) if p_under is not None else None,
        p_push=round(p_push, 3) if p_push is not None else None,
        confidence=confidence,
        recommendation=recommendation,
        stat_avg=round(stat_avg, 2) if stat_avg is not None else None,
        edge_pct=edge_pct,
        ev_pct=ev_pct,
        hit_probability=round(hit_probability, 3) if hit_probability is not None else None,
        break_even_pct=break_even_pct,
        matches_count=matches_count,
        surface=prop.surface,
        market_total_games=round(market_total_games, 2) if market_total_games is not None else None,
        expected_service_points=round(expected_service_points, 2) if expected_service_points is not None else None,
        projection_source=projection_source if stats is not None else None,
        projection_inputs=projection_inputs,
        opponent_stat_avg=round(opp_stat_avg, 2) if opp_stat_avg is not None else None,
        opponent_matches_count=opp_matches_count,
        stats_computed_at=stats_computed_at,
        stats_stale=stats_stale,
        data_quality_flags=sorted(set(data_quality_flags)),
        projection_status=projection_status,
        audit=audit,
    )


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    txt = str(value).strip()
    if not txt:
        return None
    if txt.endswith("Z"):
        txt = txt.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(txt)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _extract_bookmakers(event: dict[str, Any]) -> list[tuple[str, list[dict[str, Any]]]]:
    out: list[tuple[str, list[dict[str, Any]]]] = []
    books = event.get("bookmakers") or {}
    if isinstance(books, dict):
        for name, markets in books.items():
            if isinstance(markets, list):
                out.append((str(name), markets))
        return out
    if isinstance(books, list):
        for b in books:
            if not isinstance(b, dict):
                continue
            name = str(b.get("name") or b.get("key") or "").strip()
            markets = b.get("markets")
            if name and isinstance(markets, list):
                out.append((name, markets))
    return out


def _normalize_market(market: dict[str, Any]) -> dict[str, Any]:
    odds = market.get("odds") if isinstance(market.get("odds"), list) else []
    return {
        "name": market.get("name"),
        "selections": odds,
    }


def _provider_status_error(error: httpx.HTTPStatusError, label: str) -> HTTPException:
    detail = f"{label}: {(error.response.text or '')[:260]}"
    if error.response.status_code == 429:
        return LiveOddsRateLimited(error.response.headers.get("x-ratelimit-reset"), detail)
    return HTTPException(status_code=error.response.status_code, detail=detail)


async def _fetch_live_tennis_odds(bookmakers: str, hours_ahead: int) -> dict[str, Any]:
    api_key = (settings.odds_api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=500, detail="ODDS_API_KEY is missing in backend config.")

    params = {"sport": "tennis", "apiKey": api_key}
    now = datetime.now(UTC)
    cutoff = now + timedelta(hours=hours_ahead)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            events_resp = await client.get(f"{ODDS_API_BASE}/events", params=params)
            events_resp.raise_for_status()
            events_data = events_resp.json()
        except httpx.HTTPStatusError as e:
            raise _provider_status_error(e, "Events fetch failed") from e
        except httpx.HTTPError as e:
            # The message can carry the request URL, and with it the apiKey parameter.
            logger.warning("Odds-API.io events fetch failed: %s", type(e).__name__)
            raise HTTPException(status_code=502, detail="Events fetch failed") from e

        events = (events_data.get("data") or events_data.get("events") or []) if isinstance(events_data, dict) else (events_data or [])
        filtered = []
        for ev in events:
            if not isinstance(ev, dict):
                continue
            league_name: str = (ev.get("league") or {}).get("name") or ""
            tour = odds_event_tour(league_name)
            if tour is None:
                continue
            start = _parse_dt(ev.get("start") or ev.get("date") or ev.get("commenceTime"))
            if start is None or start < now or start > cutoff:
                continue
            ev_id = ev.get("id")
            if ev_id is None:
                continue
            filtered.append({
                "id": int(ev_id),
                "home": ev.get("home"),
                "away": ev.get("away"),
                "start": start.isoformat(),
                "tour": tour,
                "league": league_name,
            })

        if not filtered:
            return {"bookmakers": bookmakers, "count": 0, "events": []}

        # Batch in groups of 10 (API limit), with a small delay between batches
        import asyncio as _asyncio
        odds_events_all: list[dict] = []
        for i in range(0, len(filtered), 10):
            if i > 0:
                await _asyncio.sleep(0.2)
            batch_ids = ",".join(str(e["id"]) for e in filtered[i:i + 10])
            odds_params = {"eventIds": batch_ids, "bookmakers": bookmakers, "apiKey": api_key}
            try:
                odds_resp = await client.get(f"{ODDS_API_BASE}/odds/multi", params=odds_params)
                odds_resp.raise_for_status()
                odds_data = odds_resp.json()
                batch_events = (odds_data.get("data") or odds_data.get("events") or []) if isinstance(odds_data, dict) else (odds_data or [])
                odds_events_all.extend(batch_events)
            except httpx.HTTPStatusError as e:
                raise _provider_status_error(e, "Odds fetch failed") from e
            except httpx.HTTPError as e:
                logger.warning("Odds-API.io odds fetch failed: %s", type(e).__name__)
                raise HTTPException(status_code=502, detail="Odds fetch failed") from e

    odds_events = odds_events_all
    odds_by_id: dict[int, dict[str, Any]] = {}
    for ev in odds_events:
        if isinstance(ev, dict) and ev.get("id") is not None:
            odds_by_id[int(ev["id"])] = ev

    merged = []
    for ev in filtered:
        raw = odds_by_id.get(ev["id"])
        if not raw:
            continue
        books = []
        for book_name, markets in _extract_bookmakers(raw):
            books.append({
                "bookmaker": book_name,
                "marketCount": len(markets),
                "markets": [_normalize_market(m) for m in markets if isinstance(m, dict)],
            })
        merged.append({
            "eventId": ev["id"],
            "home": ev["home"],
            "away": ev["away"],
            "start": ev["start"],
            "tour": ev.get("tour"),
            "league": ev.get("league"),
            "bookmakers": books,
        })

    return {"bookmakers": bookmakers, "count": len(merged), "events": merged}


def _pick_stats_for_player(
    player_id: Optional[int],
    surface: Optional[str],
    all_stats: dict[tuple[int, Optional[str]], PlayerRollingStats],
) -> Optional[PlayerRollingStats]:
    """Return surface-specific stats if available, else fall back to all-surface."""
    if player_id is None:
        return None
    surface_stats = all_stats.get((player_id, surface))
    if surface_stats is not None and (surface_stats.matches_count or 0) >= _SMALL_SAMPLE_MATCHES:
        return surface_stats
    return all_stats.get((player_id, None))


def _pick_stats(
    prop: "Prop",
    all_stats: dict[tuple[int, Optional[str]], PlayerRollingStats],
) -> Optional[PlayerRollingStats]:
    return _pick_stats_for_player(prop.player_id, prop.surface, all_stats)


async def _fetch_win_probs(
    db: AsyncSession,
    props: list["Prop"],
) -> dict[tuple[int, int], float]:
    """Return match-specific win probabilities keyed by (player_id, match_id).

    Joins matches with their latest prediction so we know p1_ensemble_prob, then
    maps each player to their win probability for that specific match.
    """
    match_ids = list({p.match_id for p in props if p.match_id is not None and p.player_id is not None})
    if not match_ids:
        return {}

    rows = await db.execute(
        text("""
            SELECT m.id, m.p1_id, m.p2_id, pred.p1_ensemble_prob
            FROM matches m
            LEFT JOIN LATERAL (
                SELECT p1_ensemble_prob
                FROM predictions
                WHERE match_id = m.id
                ORDER BY generated_at DESC
                LIMIT 1
            ) pred ON true
            WHERE m.id = ANY(:mids)
        """),
        {"mids": match_ids},
    )

    result: dict[tuple[int, int], float] = {}
    for match_id, p1_id, p2_id, p1_prob in rows.fetchall():
        if p1_prob is None:
            continue
        result[(p1_id, match_id)] = float(p1_prob)
        result[(p2_id, match_id)] = 1.0 - float(p1_prob)
    return result


async def _fetch_market_win_probs(
    db: AsyncSession,
    props: list["Prop"],
) -> dict[tuple[int, int], float]:
    """Return moneyline-implied win probabilities keyed by (player_id, match_id)."""
    match_ids = list({p.match_id for p in props if p.match_id is not None and p.player_id is not None})
    if not match_ids:
        return {}

    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (mo.match_id)
                mo.match_id, m.p1_id, m.p2_id, mo.p1_odds, mo.p2_odds
            FROM match_odds mo
            JOIN matches m ON m.id = mo.match_id
            WHERE mo.match_id = ANY(:mids)
              AND mo.market = 'moneyline'
              AND mo.p1_odds IS NOT NULL
              AND mo.p2_odds IS NOT NULL
            ORDER BY mo.match_id, mo.fetched_at DESC
        """),
        {"mids": match_ids},
    )

    result: dict[tuple[int, int], float] = {}
    for match_id, p1_id, p2_id, p1_odds, p2_odds in rows.fetchall():
        p1_prob, p2_prob = devig_two_way(american_to_prob(int(p1_odds)), american_to_prob(int(p2_odds)))
        result[(p1_id, match_id)] = p1_prob
        result[(p2_id, match_id)] = p2_prob
    return result


async def _fetch_market_total_games(
    db: AsyncSession,
    props: list["Prop"],
) -> dict[int, float]:
    """Return latest full-match market total-games line keyed by match_id."""
    match_ids = list({p.match_id for p in props if p.match_id is not None})
    if not match_ids:
        return {}

    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (mo.match_id)
                mo.match_id, mo.line
            FROM match_odds mo
            WHERE mo.match_id = ANY(:mids)
              AND mo.market = 'total_games'
              AND mo.line IS NOT NULL
              AND mo.line >= 17
            ORDER BY
                mo.match_id,
                -- Recency first: an old DraftKings total must not beat a fresh
                -- Bet365 one. The book only settles rows from the same run.
                mo.fetched_at DESC,
                CASE
                    WHEN LOWER(mo.book) = 'draftkings' THEN 0
                    WHEN LOWER(mo.book) IN ('bet365', 'betonline.ag', 'betonline') THEN 1
                    ELSE 2
                END
        """),
        {"mids": match_ids},
    )

    return {int(match_id): float(line) for match_id, line in rows.fetchall()}


async def _fetch_opponent_ids(
    db: AsyncSession,
    props: list["Prop"],
) -> dict[tuple[int, int], int]:
    """Return opponent player IDs keyed by (player_id, match_id)."""
    match_ids = list({p.match_id for p in props if p.match_id is not None and p.player_id is not None})
    if not match_ids:
        return {}

    rows = await db.execute(
        text("""
            SELECT id, p1_id, p2_id
            FROM matches
            WHERE id = ANY(:mids)
        """),
        {"mids": match_ids},
    )

    result: dict[tuple[int, int], int] = {}
    for match_id, p1_id, p2_id in rows.fetchall():
        result[(p1_id, match_id)] = p2_id
        result[(p2_id, match_id)] = p1_id
    return result


async def _enrich_props(db: AsyncSession, props: list["Prop"]) -> list[PropLine]:
    opponent_ids_map = await _fetch_opponent_ids(db, props)
    player_ids = {p.player_id for p in props if p.player_id is not None}
    opponent_ids = set(opponent_ids_map.values())
    rolling_stats = await get_rolling_stats_batch_all_surfaces(db, list(player_ids | opponent_ids))
    prediction_probs = await _fetch_win_probs(db, props)
    market_probs = await _fetch_market_win_probs(db, props)
    market_total_games = await _fetch_market_total_games(db, props)
    return [
        _enrich(
            p,
            _pick_stats(p, rolling_stats),
            _pick_stats_for_player(
                opponent_ids_map.get((p.player_id, p.match_id)) if p.player_id and p.match_id else None,
                p.surface,
                rolling_stats,
            ),
            (
                prediction_probs.get((p.player_id, p.match_id))
                or market_probs.get((p.player_id, p.match_id))
            ) if p.player_id and p.match_id else None,
            market_total_games.get(p.match_id) if p.match_id is not None else None,
        )
        for p in props
    ]


# Public so the daily snapshot job stores exactly what the page computes. The
# enrichment belongs in a service; moving it is deferred to item 17.
enrich_props = _enrich_props


def _audit_summary(props: list[PropLine]) -> PropsAuditSummary:
    def has(flag: str, prop: PropLine) -> bool:
        return flag in (prop.data_quality_flags or [])

    flagged = [
        f"{p.player_name or 'Unknown'} | {p.stat_type} {p.line} | {', '.join(p.data_quality_flags)}"
        for p in props
        if p.data_quality_flags
    ]
    return PropsAuditSummary(
        total_props=len(props),
        unresolved_player_count=sum(1 for p in props if has("missing_player", p)),
        unlinked_match_count=sum(1 for p in props if has("missing_match", p)),
        missing_stats_count=sum(1 for p in props if has("missing_stats", p)),
        stale_stats_count=sum(1 for p in props if has("stale_stats", p)),
        unsupported_stat_count=sum(1 for p in props if has("unsupported_stat", p)),
        missing_prediction_count=sum(1 for p in props if has("missing_prediction", p)),
        small_sample_count=sum(1 for p in props if has("small_sample", p)),
        top_flagged_examples=flagged[:10],
    )


_CONF_TIERS = {"LOCK", "STRONG", "LEAN"}
_CONF_MULT = {"LOCK": 2.0, "STRONG": 1.5, "LEAN": 1.0}
_MIN_CONF_MAP = {
    "LOCK": {"LOCK"},
    "STRONG": {"LOCK", "STRONG"},
    "LEAN": {"LOCK", "STRONG", "LEAN"},
}


def _prop_score(prop: PropLine) -> float:
    """Rank picks by expected value, discounted for a thin sample.

    This used to score `abs(edge_pct)` — a projection delta, not a betting edge —
    and then apply a per-tier fudge (demon x1.2, goblin x0.85) to compensate for
    the fact that the delta ignored payout. `ev_pct` accounts for payout directly,
    so that fudge is gone: reapplying it would double-count the same correction.
    """
    if prop.ev_pct is None or prop.confidence not in _CONF_MULT:
        return 0.0
    n = prop.matches_count
    sample_bonus = 1.2 if n and n >= 20 else 1.0 if n and n >= 10 else 0.8 if n and n >= 5 else 0.5
    return prop.ev_pct * _CONF_MULT[prop.confidence] * sample_bonus


@router.get("/top", response_model=PropsResponse)
async def get_top_props(
    limit: int = 10,
    min_confidence: str = "LEAN",
    db: AsyncSession = Depends(get_db),
):
    try:
        keep = _MIN_CONF_MAP.get(min_confidence.upper(), _MIN_CONF_MAP["LEAN"])
        cap = min(max(limit, 1), 20)
        props = await get_today_props(db, source="prizepicks")
        enriched = await _enrich_props(db, props)
        filtered = [
            p for p in enriched
            if p.confidence in keep and p.recommendation is not None
        ]
        top = sorted(filtered, key=_prop_score, reverse=True)[:cap]
        return PropsResponse(source="prizepicks", count=len(top), props=top)
    except Exception as e:
        logger.exception("Top props failed")
        raise HTTPException(status_code=500, detail="Top props are temporarily unavailable.") from e


@router.get("/prizepicks/audit", response_model=PropsAuditResponse)
async def get_prizepicks_props_audit(db: AsyncSession = Depends(get_db)):
    try:
        props = await get_today_props(db, source="prizepicks")
        enriched = await _enrich_props(db, props)
        return PropsAuditResponse(
            source="prizepicks",
            count=len(enriched),
            props=enriched,
            summary=_audit_summary(enriched),
        )
    except Exception as e:
        logger.exception("PrizePicks audit failed")
        raise HTTPException(status_code=500, detail="The PrizePicks audit is temporarily unavailable.") from e


@router.get("/prizepicks", response_model=PropsResponse)
async def get_prizepicks_props(db: AsyncSession = Depends(get_db)):
    try:
        props = await get_today_props(db, source="prizepicks")
        enriched = await _enrich_props(db, props)
        return PropsResponse(
            source="prizepicks",
            count=len(props),
            props=enriched,
        )
    except Exception as e:
        logger.exception("PrizePicks props failed")
        raise HTTPException(status_code=500, detail="PrizePicks props are temporarily unavailable.") from e


@router.get("/dk", response_model=PropsResponse)
async def get_dk_props(db: AsyncSession = Depends(get_db)):
    props = await get_today_props(db, source="draftkings")
    odds_props = await get_today_match_odds_as_props(db, books=["draftkings"])
    props = [*props, *odds_props]
    enriched = await _enrich_props(db, props)
    return PropsResponse(
        source="draftkings",
        count=len(props),
        props=enriched,
    )


@router.get("/bet", response_model=PropsResponse)
async def get_bet_props(db: AsyncSession = Depends(get_db)):
    books = ["bet365", "betonline.ag", "betonline"]
    odds_props = await get_today_match_odds_as_props(db, books=books)
    enriched = await _enrich_props(db, odds_props)
    return PropsResponse(
        source="bet",
        count=len(odds_props),
        props=enriched,
    )
