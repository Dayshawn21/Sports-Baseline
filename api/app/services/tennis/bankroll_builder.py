"""
Bankroll Builder: cross-match pick ranking + 2-leg parlay generator.

Scans all today's matches across 4 bet types (ML, straight sets, underdog set, total games),
ranks every pick by composite value, and suggests optimal 2-leg parlays.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from itertools import combinations
from typing import Optional

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.bettable_criteria import MIN_EV, assess_bettable_pick
from app.core.kelly import expected_value, kelly_fraction
from app.core.odds import (
    american_to_decimal,
    american_to_prob,
    decimal_to_american,
    devig_two_way,
    prob_to_american,
)
from app.core.poisson import confidence_tier
from app.core.prop_probs import total_games_probs
from app.core.tennis_sets import set_outcomes
from app.repositories import matches as match_repo
from app.repositories import players as player_repo
from app.services.tennis.best_picks import _compute_stat_avg, _CONF_MULT
from app.services.tennis.predictor import PredictionOutput, predict_today

# ── Constants ────────────────────────────────────────────────────────────────
_SERVICE_GAMES_PER_MATCH = 11.0
_MIN_PROB_SWEEP = 0.40      # minimum prob for 2-0 sweep
_MIN_PROB_DOG_SET = 0.55    # minimum prob for underdog wins a set
_MIN_DOG_WIN_PROB = 0.20    # underdog must have ≥ 20 % win prob
_MIN_PROB_TOTAL = 0.55      # minimum Poisson prob for totals
_PARLAY_MIN_PROB = 0.30     # minimum combined prob for a 2-leg parlay
_PARLAY_MIN_LEG_PROB = 0.60  # each leg must be a clear model favorite


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class BankrollPick:
    match_id: int
    p1_name: str
    p2_name: str
    tour: str
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    start_utc: Optional[datetime]

    bet_type: str       # "ml" | "2-0" | "3-0" | "underdog_set" | "total_games"
    pick_label: str     # e.g. "Sinner ML (-150)"
    pick_side: str      # "p1" | "p2" | "over" | "under"

    our_prob: float
    market_prob: Optional[float]
    odds_american: Optional[int]

    edge_pct: float
    ev: float
    kelly_frac: float
    confidence: str
    reasoning: str

    rank_score: float = 0.0


@dataclass
class ParlayLeg:
    match_id: int
    p1_name: str
    p2_name: str
    tour: str
    bet_type: str
    pick_label: str
    our_prob: float
    odds_american: Optional[int]
    confidence: str


@dataclass
class SuggestedParlay:
    legs: list[ParlayLeg]
    combined_prob: float
    combined_odds_american: int
    combined_ev: float
    combined_kelly: float
    combined_edge_pct: float
    confidence: str


@dataclass
class BankrollBuilderResult:
    date: date
    total_matches_scanned: int
    singles: list[BankrollPick]
    parlays: list[SuggestedParlay]


# ── Helpers ──────────────────────────────────────────────────────────────────

def _odds_str(odds: Optional[int]) -> str:
    if odds is None:
        return "N/A"
    return f"+{odds}" if odds > 0 else str(odds)


def _devig_pair(p1_odds: Optional[int], p2_odds: Optional[int]) -> tuple[Optional[float], Optional[float]]:
    """Return (p1_no_vig, p2_no_vig) from American odds, or (None, None)."""
    if p1_odds is None or p2_odds is None:
        return None, None
    raw1 = american_to_prob(p1_odds)
    raw2 = american_to_prob(p2_odds)
    return devig_two_way(raw1, raw2)


def _pick_score(ev: float, kelly: float, conf: str, has_market_odds: bool) -> float:
    """Composite ranking score: higher = better bankroll value."""
    conf_mult = _CONF_MULT.get(conf, 0.5)
    market_mult = 1.2 if has_market_odds else 0.8
    return ev * kelly * conf_mult * market_mult * 1000  # scale up for readability


# ── ML picks ─────────────────────────────────────────────────────────────────

def _generate_ml_picks(pred: PredictionOutput) -> list[BankrollPick]:
    """Generate moneyline picks for both sides if positive EV."""
    picks: list[BankrollPick] = []
    if pred.p1_win_prob is None or pred.p1_odds_american is None or pred.p2_odds_american is None:
        return picks

    market_p1, market_p2 = _devig_pair(pred.p1_odds_american, pred.p2_odds_american)

    for side, our_p, mkt_p, odds, name in [
        ("p1", pred.p1_win_prob, market_p1, pred.p1_odds_american, pred.p1_name),
        ("p2", pred.p2_win_prob, market_p2, pred.p2_odds_american, pred.p2_name),
    ]:
        ev = expected_value(our_p, odds)
        kf = kelly_fraction(our_p, odds)
        assessment = assess_bettable_pick(
            our_p,
            ev,
            kf,
            data_quality_flags=getattr(pred, "quality_flags", []) or [],
            odds_source="posted",
        )
        if assessment is None:
            continue

        edge = round((our_p - (mkt_p or our_p)) / max(mkt_p or our_p, 0.01) * 100, 1)
        conf = assessment.confidence

        last_name = name.split()[-1]
        picks.append(BankrollPick(
            match_id=pred.match_id,
            p1_name=pred.p1_name, p2_name=pred.p2_name,
            tour=pred.tour, surface=pred.surface,
            tournament=pred.tournament, round=pred.round,
            start_utc=pred.start_utc,
            bet_type="ml",
            pick_label=f"{last_name} ML ({_odds_str(odds)})",
            pick_side=side,
            our_prob=round(our_p, 4),
            market_prob=round(mkt_p, 4) if mkt_p else None,
            odds_american=odds,
            edge_pct=edge,
            ev=round(ev, 4),
            kelly_frac=round(kf, 4),
            confidence=conf,
            reasoning=(
                f"Model gives {last_name} {our_p:.0%} win prob vs "
                f"{mkt_p:.0%} implied — {ev*100:.1f}% EV at {_odds_str(odds)}"
                if mkt_p else
                f"Model gives {last_name} {our_p:.0%} win prob — {ev*100:.1f}% EV at {_odds_str(odds)}"
            ),
            rank_score=_pick_score(ev, kf, conf, True),
        ))

    return picks


# ── Set-based derived picks ──────────────────────────────────────────────────

def _straight_sets_probability(fav_p: float, best_of: int) -> float:
    """Favorite wins without dropping a set. Best-of-5 has no fitted model, so it
    keeps treating sets as independent."""
    if best_of >= 5:
        return fav_p ** 3
    return set_outcomes(fav_p).favorite_straight


def _generate_set_picks(
    pred: PredictionOutput,
    market_odds: dict[str, dict],
) -> list[BankrollPick]:
    """Generate straight-sets and underdog set-cover picks.

    When real set_handicap odds are missing, derive market-implied set probs
    from moneyline odds. Best-of-3 straight sets is 2-0, best-of-5 is 3-0.
    Then convert to fair odds and compute a real edge.
    """
    picks: list[BankrollPick] = []
    if pred.p1_win_prob is None:
        return picks

    p = pred.p1_win_prob
    fav_is_p1 = p >= 0.5
    fav_p = max(p, 1 - p)
    dog_p = 1 - fav_p
    fav_name = pred.p1_name if fav_is_p1 else pred.p2_name
    dog_name = pred.p2_name if fav_is_p1 else pred.p1_name
    fav_last = fav_name.split()[-1]
    dog_last = dog_name.split()[-1]
    straight_sets_needed = 3 if pred.best_of >= 5 else 2
    set_cover_line = 2.5 if pred.best_of >= 5 else 1.5
    straight_bet_type = f"{straight_sets_needed}-0"

    # Source 1: real set-handicap market odds.
    sh = market_odds.get("set_handicap")
    sh_fav_odds: Optional[int] = None    # -1.5 (fav sweeps)
    sh_dog_odds: Optional[int] = None    # +1.5 (dog wins a set)
    sh_mkt_fav: Optional[float] = None   # devigged market prob for fav sweep
    sh_mkt_dog: Optional[float] = None   # devigged market prob for dog set

    sh_line = abs(float(sh["line"])) if sh and sh.get("line") is not None else None
    sh_line_matches = sh_line is None or sh_line == set_cover_line
    if sh_line_matches and sh and sh.get("p1_odds") and sh.get("p2_odds"):
        if fav_is_p1:
            sh_fav_odds = sh["p1_odds"]
            sh_dog_odds = sh["p2_odds"]
        else:
            sh_fav_odds = sh["p2_odds"]
            sh_dog_odds = sh["p1_odds"]
        sh_mkt_fav, sh_mkt_dog = _devig_pair(sh_fav_odds, sh_dog_odds)

    # Source 2: derive from moneyline when matching set-handicap odds are unavailable.
    has_real_sh = sh_fav_odds is not None
    if not has_real_sh and pred.p1_odds_american is not None and pred.p2_odds_american is not None:
        ml_p1_nv, ml_p2_nv = _devig_pair(pred.p1_odds_american, pred.p2_odds_american)
        if ml_p1_nv is not None:
            mkt_fav_p = ml_p1_nv if fav_is_p1 else ml_p2_nv
            sh_mkt_fav = _straight_sets_probability(mkt_fav_p, pred.best_of)
            sh_mkt_dog = 1 - sh_mkt_fav
            sh_fav_odds = prob_to_american(sh_mkt_fav)
            sh_dog_odds = prob_to_american(sh_mkt_dog)

    # Straight-sets favorite.
    p_sweep = _straight_sets_probability(fav_p, pred.best_of)
    if p_sweep >= _MIN_PROB_SWEEP and sh_fav_odds is not None:
        odds = sh_fav_odds
        mkt_p = sh_mkt_fav

        ev = expected_value(p_sweep, odds)
        kf = kelly_fraction(p_sweep, odds) if ev > 0 else 0.0
        assessment = assess_bettable_pick(
            p_sweep,
            ev,
            kf,
            odds_source="posted" if has_real_sh else "imputed",
        )
        if assessment is not None:
            edge = round((p_sweep - (mkt_p or 0.40)) / max(mkt_p or 0.40, 0.01) * 100, 1)
            conf = assessment.confidence
            src = "" if has_real_sh else " (odds from ML)"
            picks.append(BankrollPick(
                match_id=pred.match_id,
                p1_name=pred.p1_name, p2_name=pred.p2_name,
                tour=pred.tour, surface=pred.surface,
                tournament=pred.tournament, round=pred.round,
                start_utc=pred.start_utc,
                bet_type=straight_bet_type,
                pick_label=f"{fav_last} {straight_bet_type} ({_odds_str(odds)})",
                pick_side="p1" if fav_is_p1 else "p2",
                our_prob=round(p_sweep, 4),
                market_prob=round(mkt_p, 4) if mkt_p else None,
                odds_american=odds,
                edge_pct=edge,
                ev=round(ev, 4),
                kelly_frac=round(kf, 4),
                confidence=conf,
                reasoning=(
                    f"{fav_last} at {fav_p:.0%} win prob → {p_sweep:.0%} sweep "
                    f"vs {mkt_p:.0%} implied{src}"
                ),
                rank_score=_pick_score(ev, kf, conf, has_real_sh),
            ))

    # Underdog set cover.
    p_dog_set = 1 - p_sweep
    if p_dog_set >= _MIN_PROB_DOG_SET and dog_p >= _MIN_DOG_WIN_PROB and sh_dog_odds is not None:
        odds = sh_dog_odds
        mkt_p = sh_mkt_dog

        ev = expected_value(p_dog_set, odds)
        kf = kelly_fraction(p_dog_set, odds) if ev > 0 else 0.0
        assessment = assess_bettable_pick(
            p_dog_set,
            ev,
            kf,
            odds_source="posted" if has_real_sh else "imputed",
        )
        if assessment is not None:
            edge = round((p_dog_set - (mkt_p or 0.50)) / max(mkt_p or 0.50, 0.01) * 100, 1)
            conf = assessment.confidence
            src = "" if has_real_sh else " (odds from ML)"
            picks.append(BankrollPick(
                match_id=pred.match_id,
                p1_name=pred.p1_name, p2_name=pred.p2_name,
                tour=pred.tour, surface=pred.surface,
                tournament=pred.tournament, round=pred.round,
                start_utc=pred.start_utc,
                bet_type="underdog_set",
                pick_label=f"{dog_last} +{set_cover_line:.1f} Sets ({_odds_str(odds)})",
                pick_side="p2" if fav_is_p1 else "p1",
                our_prob=round(p_dog_set, 4),
                market_prob=round(mkt_p, 4) if mkt_p else None,
                odds_american=odds,
                edge_pct=edge,
                ev=round(ev, 4),
                kelly_frac=round(kf, 4),
                confidence=conf,
                reasoning=(
                    f"{dog_last} has {p_dog_set:.0%} chance of winning a set "
                    f"vs {mkt_p:.0%} implied{src}"
                ),
                rank_score=_pick_score(ev, kf, conf, has_real_sh),
            ))

    return picks


# ── Total Games picks ────────────────────────────────────────────────────────

def _generate_total_picks(
    pred: PredictionOutput,
    market_odds: dict[str, dict],
    p1_stats,
    p2_stats,
) -> list[BankrollPick]:
    """Generate total games over/under picks from the set-count mixture model."""
    picks: list[BankrollPick] = []

    tg = market_odds.get("total_games")
    if not tg or tg.get("line") is None:
        return picks

    line = float(tg["line"])
    if line <= 0:
        return picks
    # Lines < 17 are per-set totals (e.g. 10.5 = tiebreak bet); skip — our model
    # computes full-match expected games (~25-35), applying that to a per-set line
    # produces fraudulently high probabilities.
    if line < 17.0:
        return picks

    # Compute expected total from both players' stats
    # win_prob must be keyword: the third positional parameter is opponent_stats, and
    # passing a float there makes serve_hold raise AttributeError on a real slate.
    p1_expected = _compute_stat_avg("total_games", p1_stats, win_prob=pred.p1_win_prob,
                                    best_of=pred.best_of) if p1_stats else None
    p2_expected = _compute_stat_avg("total_games", p2_stats, win_prob=pred.p2_win_prob,
                                    best_of=pred.best_of) if p2_stats else None

    if p1_expected is not None and p2_expected is not None:
        # Average the two player projections (each already doubled for match total)
        expected_total = (p1_expected + p2_expected) / 2.0
    elif p1_expected is not None:
        expected_total = p1_expected
    elif p2_expected is not None:
        expected_total = p2_expected
    else:
        return picks

    # Total games is a mixture over how many sets get played, so it needs the chance the
    # match goes the distance. 2*p*(1-p) is kept here for the reason in best_picks.
    wp = pred.p1_win_prob
    p_deciding = (2 * wp * (1 - wp)) if wp is not None else None
    probs = total_games_probs(line, expected_total, p_deciding, pred.best_of)
    p_over, p_under = probs.p_over, probs.p_under

    over_odds = tg.get("p1_odds")    # p1_odds = over side by convention
    under_odds = tg.get("p2_odds")   # p2_odds = under side

    mkt_over, mkt_under = _devig_pair(over_odds, under_odds)

    # Try OVER
    if p_over >= _MIN_PROB_TOTAL and over_odds:
        ev = expected_value(p_over, over_odds)
        kf = kelly_fraction(p_over, over_odds) if ev > 0 else 0.0
        assessment = assess_bettable_pick(p_over, ev, kf, odds_source="posted")
        if assessment is None:
            pass
        else:
            edge = round((p_over - (mkt_over or 0.50)) / max(mkt_over or 0.50, 0.01) * 100, 1)
            conf = assessment.confidence
            picks.append(BankrollPick(
                match_id=pred.match_id,
                p1_name=pred.p1_name, p2_name=pred.p2_name,
                tour=pred.tour, surface=pred.surface,
                tournament=pred.tournament, round=pred.round,
                start_utc=pred.start_utc,
                bet_type="total_games",
                pick_label=f"Over {line} Games ({_odds_str(over_odds)})",
                pick_side="over",
                our_prob=round(p_over, 4),
                market_prob=round(mkt_over, 4) if mkt_over else None,
                odds_american=over_odds,
                edge_pct=edge,
                ev=round(ev, 4),
                kelly_frac=round(kf, 4),
                confidence=conf,
                reasoning=f"Expected {expected_total:.1f} total games vs {line} line — {p_over:.0%} over",
                rank_score=_pick_score(ev, kf, conf, True),
            ))

    # Try UNDER
    if p_under >= _MIN_PROB_TOTAL and under_odds:
        ev = expected_value(p_under, under_odds)
        kf = kelly_fraction(p_under, under_odds) if ev > 0 else 0.0
        assessment = assess_bettable_pick(p_under, ev, kf, odds_source="posted")
        if assessment is None:
            pass
        else:
            edge = round((p_under - (mkt_under or 0.50)) / max(mkt_under or 0.50, 0.01) * 100, 1)
            conf = assessment.confidence
            picks.append(BankrollPick(
                match_id=pred.match_id,
                p1_name=pred.p1_name, p2_name=pred.p2_name,
                tour=pred.tour, surface=pred.surface,
                tournament=pred.tournament, round=pred.round,
                start_utc=pred.start_utc,
                bet_type="total_games",
                pick_label=f"Under {line} Games ({_odds_str(under_odds)})",
                pick_side="under",
                our_prob=round(p_under, 4),
                market_prob=round(mkt_under, 4) if mkt_under else None,
                odds_american=under_odds,
                edge_pct=edge,
                ev=round(ev, 4),
                kelly_frac=round(kf, 4),
                confidence=conf,
                reasoning=f"Expected {expected_total:.1f} total games vs {line} line — {p_under:.0%} under",
                rank_score=_pick_score(ev, kf, conf, True),
            ))

    return picks


# ── Parlay generator ─────────────────────────────────────────────────────────

_MAIN_TOURS = {"ATP", "WTA"}


def _is_main_tour(tour: str) -> bool:
    return tour.upper() in _MAIN_TOURS


def _generate_parlays(
    singles: list[BankrollPick],
    max_parlays: int = 10,
) -> list[SuggestedParlay]:
    """Build best 2-leg parlays from independent matches.

    ATP/WTA legs only combine with other ATP/WTA legs.
    Challenger legs only combine with other Challenger legs.
    """
    eligible = [s for s in singles if s.odds_american is not None and s.ev > 0]
    if len(eligible) < 2:
        return []

    # Use top 50 picks so high-prob favorites that rank lower individually still qualify
    top = eligible[:50]
    candidates: list[SuggestedParlay] = []

    for a, b in combinations(top, 2):
        if a.match_id == b.match_id:
            continue

        # ATP/WTA only pair with ATP/WTA; Challengers only pair with Challengers
        if _is_main_tour(a.tour) != _is_main_tour(b.tour):
            continue

        # Both legs must be clear model favorites
        if a.our_prob < _PARLAY_MIN_LEG_PROB or b.our_prob < _PARLAY_MIN_LEG_PROB:
            continue

        comb_prob = a.our_prob * b.our_prob
        if comb_prob < _PARLAY_MIN_PROB:
            continue

        comb_dec = american_to_decimal(a.odds_american) * american_to_decimal(b.odds_american)
        comb_american = decimal_to_american(comb_dec)
        comb_ev = expected_value(comb_prob, comb_american)
        comb_kelly = kelly_fraction(comb_prob, comb_american) if comb_ev > 0 else 0.0

        if comb_ev <= 0:
            continue

        # Combined probability edge vs market
        comb_mkt = (a.market_prob or a.our_prob) * (b.market_prob or b.our_prob)
        combined_edge_pct = round((comb_prob - comb_mkt) / max(comb_mkt, 0.01) * 100, 1)

        conf = confidence_tier(comb_prob)

        candidates.append(SuggestedParlay(
            legs=[
                ParlayLeg(
                    match_id=a.match_id, p1_name=a.p1_name, p2_name=a.p2_name,
                    tour=a.tour, bet_type=a.bet_type, pick_label=a.pick_label,
                    our_prob=a.our_prob, odds_american=a.odds_american,
                    confidence=a.confidence,
                ),
                ParlayLeg(
                    match_id=b.match_id, p1_name=b.p1_name, p2_name=b.p2_name,
                    tour=b.tour, bet_type=b.bet_type, pick_label=b.pick_label,
                    our_prob=b.our_prob, odds_american=b.odds_american,
                    confidence=b.confidence,
                ),
            ],
            combined_prob=round(comb_prob, 4),
            combined_odds_american=comb_american,
            combined_ev=round(comb_ev, 4),
            combined_kelly=round(comb_kelly, 4),
            combined_edge_pct=combined_edge_pct,
            confidence=conf,
        ))

    # Sort by combined probability edge (highest edge first)
    candidates.sort(key=lambda p: p.combined_edge_pct, reverse=True)

    # Deduplicate: each match can appear as a leg in at most 2 parlays
    # so one dominant pick can't flood every slot
    match_usage: dict[int, int] = {}
    deduped: list[SuggestedParlay] = []
    for p in candidates:
        ids = [leg.match_id for leg in p.legs]
        if all(match_usage.get(mid, 0) < 2 for mid in ids):
            for mid in ids:
                match_usage[mid] = match_usage.get(mid, 0) + 1
            deduped.append(p)
        if len(deduped) >= max_parlays:
            break
    return deduped


# ── Main entry point ─────────────────────────────────────────────────────────

async def build_bankroll_picks(
    db: AsyncSession,
    request: Request,
    match_date: date | list[date],
    tour_filter: Optional[str] = None,
    max_singles: int = 15,
    max_parlays: int = 10,
) -> BankrollBuilderResult:
    """Scan all today's matches and return ranked singles + 2-leg parlays."""

    # 1. Predictions
    predictions = await predict_today(db, request.app.state.registry, match_date)
    if tour_filter:
        predictions = [p for p in predictions if p.tour.upper() == tour_filter.upper()]

    _result_date = min(match_date) if isinstance(match_date, list) else match_date
    if not predictions:
        return BankrollBuilderResult(date=_result_date, total_matches_scanned=0, singles=[], parlays=[])

    # 2. Overlay live moneyline for any missing odds
    from app.routers.tennis import _overlay_live_moneyline
    try:
        await _overlay_live_moneyline(predictions)
    except Exception:
        pass

    # 3. Batch-fetch all market odds (moneyline, total_games, set_handicap, etc.)
    match_ids = [p.match_id for p in predictions]
    all_market_odds = await match_repo.get_all_market_odds_batch(db, match_ids)

    # 4. Get matches for player IDs, then batch-fetch rolling stats
    matches = await match_repo.get_upcoming(db, match_date)
    match_map = {m.id: m for m in matches}

    all_player_ids = list({
        pid
        for mid in match_ids
        if mid in match_map
        for pid in (match_map[mid].p1_id, match_map[mid].p2_id)
    })
    stats_cache = await player_repo.get_rolling_stats_batch_all_surfaces(db, all_player_ids) if all_player_ids else {}

    # 5. Generate picks across all bet types for every match
    all_picks: list[BankrollPick] = []

    for pred in predictions:
        match_odds = all_market_odds.get(pred.match_id, {})
        match = match_map.get(pred.match_id)

        # ML picks
        all_picks.extend(_generate_ml_picks(pred))

        # Set-based picks (straight sets and underdog set cover)
        all_picks.extend(_generate_set_picks(pred, match_odds))

        # Total games picks (need rolling stats for both players)
        if match:
            surface = pred.surface
            p1_stats = stats_cache.get((match.p1_id, surface)) or stats_cache.get((match.p1_id, None))
            p2_stats = stats_cache.get((match.p2_id, surface)) or stats_cache.get((match.p2_id, None))
            all_picks.extend(_generate_total_picks(pred, match_odds, p1_stats, p2_stats))

    # 6. Filter: strict EV + LEAN or better
    all_picks = [p for p in all_picks if p.confidence in _CONF_MULT and p.ev >= MIN_EV]

    # 7. Rank by composite score
    all_picks.sort(key=lambda p: p.rank_score, reverse=True)
    singles = all_picks[:max_singles]

    # 8. Generate parlays from the ranked singles
    parlays = _generate_parlays(all_picks, max_parlays)

    return BankrollBuilderResult(
        date=_result_date,
        total_matches_scanned=len(predictions),
        singles=singles,
        parlays=parlays,
    )
