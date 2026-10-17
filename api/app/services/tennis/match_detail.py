"""Everything the match page shows about one match (build-plan 32a)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_format import display_tour, infer_best_of
from app.ml.registry import ModelRegistry
from app.repositories import matches as match_repo
from app.repositories import players as player_repo
from app.repositories import predictions as prediction_repo
from app.repositories.matches import Match, MatchMeeting, MatchMeta, OddsHistoryRow
from app.repositories.players import PlayerElo, PlayerProfile
from app.repositories.predictions import StoredPrediction
from app.services.tennis import predictor
from app.services.tennis.best_picks import MONEYLINE_PICKS_ENABLED, BestPick, generate_ml_pick
from app.services.tennis.predictor import PredictionOutput

LIVE_STATUSES = frozenset({"scheduled", "live"})


@dataclass(frozen=True)
class MatchDetailPlayer:
    player_id: int
    name: str
    rank: Optional[int]
    hand: Optional[str]
    country: Optional[str]
    elo: Optional[float]
    elo_surface: Optional[float]


@dataclass(frozen=True)
class MatchDetail:
    match: Match
    meta: MatchMeta
    tour_label: str
    best_of: int
    p1: MatchDetailPlayer
    p2: MatchDetailPlayer
    h2h: dict[str, int]
    h2h_surface: Optional[dict[str, int]]
    meetings: list[MatchMeeting]
    prediction: Optional[PredictionOutput]
    prediction_source: Optional[str]
    prediction_generated_at: Optional[datetime]
    model_version: Optional[str]
    ml_pick: Optional[BestPick]


def surface_elo(elo: Optional[PlayerElo], surface: Optional[str]) -> Optional[float]:
    if elo is None or surface is None:
        return None
    return {"hard": elo.elo_hard, "clay": elo.elo_clay, "grass": elo.elo_grass}.get(surface.lower())


def winner_side(match: Match) -> Optional[str]:
    if match.winner_id is None:
        return None
    if match.winner_id == match.p1_id:
        return "p1"
    return "p2" if match.winner_id == match.p2_id else None


def prediction_ref_date(match_date: date, today: date) -> date:
    # The slate predicts today and tomorrow against history up to today, so a
    # match tomorrow must use today too or it would see results the slate cannot.
    return min(match_date, today)


def stored_prediction_output(
    stored: StoredPrediction,
    match: Match,
    p1_name: str,
    p2_name: str,
    tour_label: str,
    best_of: int,
    h2h: dict[str, int],
) -> PredictionOutput:
    ensemble = stored.p1_ensemble_prob
    return PredictionOutput(
        match_id=match.id,
        start_utc=match.start_utc,
        p1_name=p1_name,
        p2_name=p2_name,
        tour=match.tour,
        surface=match.surface,
        tournament=match.tournament,
        round=match.round,
        p1_win_prob=ensemble,
        p2_win_prob=1 - ensemble if ensemble is not None else None,
        p1_elo_prob=stored.p1_elo_prob,
        p1_ml_prob=stored.p1_ml_prob,
        p1_market_prob=stored.p1_market_prob,
        ensemble_weights=stored.ensemble_weights,
        quality_flags=stored.quality_flags,
        p1_odds_american=stored.p1_odds,
        p2_odds_american=stored.p2_odds,
        h2h_p1_wins=h2h["p1_wins"],
        h2h_p2_wins=h2h["p2_wins"],
        tour_label=tour_label,
        best_of=best_of,
        p1_id=match.p1_id,
        p2_id=match.p2_id,
    )


def _player(
    player_id: int,
    rank: Optional[int],
    profiles: dict[int, PlayerProfile],
    elos: dict[int, PlayerElo],
    surface: Optional[str],
) -> MatchDetailPlayer:
    profile = profiles.get(player_id)
    elo = elos.get(player_id)
    return MatchDetailPlayer(
        player_id=player_id,
        name=profile.name if profile else "",
        rank=rank,
        hand=profile.hand if profile else None,
        country=profile.country if profile else None,
        elo=elo.elo if elo else None,
        elo_surface=surface_elo(elo, surface),
    )


async def build_match_detail(
    db: AsyncSession,
    registry: ModelRegistry,
    match_id: int,
    today: date,
) -> Optional[MatchDetail]:
    found = await match_repo.get_match(db, match_id)
    if found is None:
        return None
    match, meta = found

    player_ids = [match.p1_id, match.p2_id]
    profiles = await player_repo.get_player_profiles(db, player_ids)
    elos = await player_repo.get_latest_elo_batch(db, player_ids)
    h2h = await match_repo.get_h2h(db, match.p1_id, match.p2_id, None)
    h2h_surface = (
        await match_repo.get_h2h(db, match.p1_id, match.p2_id, match.surface)
        if match.surface else None
    )
    meetings = await match_repo.get_meetings(db, match.p1_id, match.p2_id, match.match_date)

    p1_profile, p2_profile = profiles.get(match.p1_id), profiles.get(match.p2_id)
    tour_label = display_tour(
        match.tour,
        p1_profile.tour if p1_profile else None,
        p2_profile.tour if p2_profile else None,
    )
    best_of = infer_best_of(match.tour, match.tournament, match.round, match.best_of)
    p1 = _player(match.p1_id, match.p1_rank, profiles, elos, match.surface)
    p2 = _player(match.p2_id, match.p2_rank, profiles, elos, match.surface)

    prediction: Optional[PredictionOutput] = None
    source: Optional[str] = None
    stored: Optional[StoredPrediction] = None
    if match.status in LIVE_STATUSES:
        predicted = await predictor.predict_matches(
            db, registry, [match], prediction_ref_date(match.match_date, today)
        )
        if predicted:
            prediction, source = predicted[0], "live"
    elif match.start_utc is not None:
        # A finished match is never re-predicted: today's inputs include its result.
        stored = await prediction_repo.get_prestart_prediction(db, match.id, match.start_utc)
        if stored is not None:
            prediction = stored_prediction_output(stored, match, p1.name, p2.name, tour_label, best_of, h2h)
            source = "stored"

    return MatchDetail(
        match=match,
        meta=meta,
        tour_label=tour_label,
        best_of=best_of,
        p1=p1,
        p2=p2,
        h2h=h2h,
        h2h_surface=h2h_surface,
        meetings=meetings,
        prediction=prediction,
        prediction_source=source,
        prediction_generated_at=stored.generated_at if stored else None,
        model_version=stored.model_version if stored else None,
        ml_pick=generate_ml_pick(prediction) if prediction and MONEYLINE_PICKS_ENABLED else None,
    )


async def match_odds_history(
    db: AsyncSession, match_id: int, market: str
) -> Optional[list[OddsHistoryRow]]:
    """None when the match does not exist; prices after the start are in-play, so dropped."""
    found = await match_repo.get_match(db, match_id)
    if found is None:
        return None
    match, _meta = found
    return await match_repo.get_odds_history(db, match_id, market, match.start_utc)
