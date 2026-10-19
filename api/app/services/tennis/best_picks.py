"""
Best-picks generator: for each matchup, score all available angles and return the top 3.

Pick sources:
 1. Moneyline value — ensemble prob vs market odds (EV / Kelly edge)
 2. Prop-line edges — aces, break points, total games, etc. (Poisson + rolling stats)
 3. Derived picks — 2-0 sweep, match goes 3 sets, underdog wins a set (from win prob math)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.core.bettable_criteria import assess_bettable_pick
from app.core.kelly import expected_value, kelly_fraction as compute_kelly_fraction
from app.core.odds import american_to_prob, devig_two_way
from app.core.poisson import confidence_tier
from app.core.prop_probs import total_games_probs
from app.core.prop_projection import compute_stat_avg as _compute_stat_avg
from app.core.tennis_first_set import FIRST_SET_STATS
from app.core.tennis_sets import set_outcomes
from app.repositories.players import PlayerRollingStats
from app.schemas.props import PropLine
from app.services.tennis.predictor import PredictionOutput

# 26d's holdout: betting the served blend's moneyline gaps at the close lost
# (WTA -0.5% on 1,824, Challenger -2.2% on 7,504; ATP never gaps 3 points).
MONEYLINE_PICKS_ENABLED = False

# Confidence multiplier for scoring
_CONF_MULT = {"LOCK": 2.0, "STRONG": 1.5, "LEAN": 1.0, "PASS": 0.3}

STAT_LABELS = {
    "aces": "Aces",
    "double_faults": "Double Faults",
    "total_games": "Total Games",
    "total_games_won": "Games Won",
    "break_points_converted": "Break Points",
    "break_points_won": "Break Points Won",
    "fantasy_score": "Fantasy Score",
    "total_sets": "Total Sets",
    "total_tie_breaks": "Tie Breaks",
    "game_spread": "Game Spread",
    "set_handicap": "Set Handicap",
}


@dataclass
class BestPick:
    pick_type: str        # "moneyline" | "prop" | "derived"
    label: str            # display label, e.g. "Moneyline", "Aces OVER 5.5"
    pick: str             # short pick text, e.g. "Sinner ML", "OVER 5.5"
    player_name: Optional[str]
    edge_pct: float       # edge expressed as percentage (higher = better)
    confidence: str       # LOCK / STRONG / LEAN / PASS
    reasoning: str        # one-line explanation
    odds_american: Optional[int] = None  # American odds for this specific pick
    # Expected return %: prob * decimal odds - 1. Set only for priced picks, i.e.
    # those with real book odds. edge_pct is NOT comparable across pick types —
    # it is a prob-vs-market edge for moneyline but a projection-vs-line delta
    # for props and a delta vs a hardcoded baseline for derived picks. ev_pct is
    # the one axis on which picks can be ranked against each other, so unpriced
    # picks are left None rather than given a fabricated value.
    ev_pct: Optional[float] = None
    model_prob: Optional[float] = None
    market_prob: Optional[float] = None
    kelly_fraction: Optional[float] = None
    data_quality_flags: tuple[str, ...] = ()
    odds_source: str = "posted"
    score: float = 0.0    # internal ranking score (not exposed to frontend)


def _f(v) -> Optional[float]:
    return float(v) if v is not None else None



def _score_pick(edge_pct: float, confidence: str, sample_size: Optional[int] = None) -> float:
    """Compute composite score for ranking picks."""
    base = abs(edge_pct)
    conf_mult = _CONF_MULT.get(confidence, 0.5)
    sample_bonus = 1.0
    if sample_size is not None:
        if sample_size >= 20:
            sample_bonus = 1.2
        elif sample_size >= 10:
            sample_bonus = 1.0
        elif sample_size >= 5:
            sample_bonus = 0.8
        else:
            sample_bonus = 0.5
    return base * conf_mult * sample_bonus


def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _poisson_diff_cover_probs(
    mean_a: float,
    mean_b: float,
    line_from_a_perspective: float,
) -> tuple[float, float]:
    """Approximate cover probabilities for a two-way spread using a Skellam-normal approximation."""
    mean_diff = mean_a - mean_b
    variance = max(mean_a + mean_b, 1e-6)
    sigma = math.sqrt(variance)
    z = ((-line_from_a_perspective) - mean_diff) / sigma
    p_a = 1.0 - _normal_cdf(z)
    p_a = max(0.0, min(1.0, p_a))
    return p_a, 1.0 - p_a


def generate_ml_pick(pred: PredictionOutput) -> Optional[BestPick]:
    """Generate a moneyline value pick if our model has positive EV."""
    if pred.p1_win_prob is None or pred.p1_odds_american is None or pred.p2_odds_american is None:
        return None

    # Check P1 edge
    p1_ev = expected_value(pred.p1_win_prob, pred.p1_odds_american)
    p2_ev = expected_value(pred.p2_win_prob, pred.p2_odds_american)

    # Pick the side with more EV
    if p1_ev > p2_ev:
        ev = p1_ev
        player = pred.p1_name
        odds = pred.p1_odds_american
        our_prob = pred.p1_win_prob
    else:
        ev = p2_ev
        player = pred.p2_name
        odds = pred.p2_odds_american
        our_prob = pred.p2_win_prob

    # Market implied
    market_p1, _ = devig_two_way(
        american_to_prob(pred.p1_odds_american),
        american_to_prob(pred.p2_odds_american),
    )
    market_prob = market_p1 if player == pred.p1_name else 1 - market_p1

    edge_pct = round((our_prob - market_prob) / market_prob * 100, 1)
    ev_pct = round(ev * 100, 1)
    kelly = compute_kelly_fraction(our_prob, odds)

    assessment = assess_bettable_pick(
        our_prob,
        ev,
        kelly,
        data_quality_flags=getattr(pred, "quality_flags", []) or [],
        odds_source="posted",
    )
    if assessment is None:
        return None
    conf = assessment.confidence
    odds_str = f"+{odds}" if odds > 0 else str(odds)

    last_name = player.split()[-1]
    h2h_note = ""
    total_h2h = pred.h2h_p1_wins + pred.h2h_p2_wins
    if total_h2h >= 3:
        player_h2h = pred.h2h_p1_wins if player == pred.p1_name else pred.h2h_p2_wins
        opp_h2h = pred.h2h_p2_wins if player == pred.p1_name else pred.h2h_p1_wins
        if player_h2h > opp_h2h:
            h2h_note = f" | H2H {player_h2h}-{opp_h2h} edge"
    reasoning = (
        f"Model gives {last_name} {our_prob:.0%} win prob vs {market_prob:.0%} implied — "
        f"{ev_pct}% EV at {odds_str}{h2h_note}"
    )

    score = _score_pick(edge_pct, conf)

    return BestPick(
        pick_type="moneyline",
        label="Moneyline",
        pick=f"{last_name} ML ({odds_str})",
        player_name=player,
        edge_pct=edge_pct,
        confidence=conf,
        reasoning=reasoning,
        odds_american=odds,
        ev_pct=ev_pct,
        model_prob=round(our_prob, 4),
        market_prob=round(market_prob, 4),
        kelly_fraction=round(kelly, 4),
        data_quality_flags=assessment.data_quality_flags,
        odds_source=assessment.odds_source,
        score=score,
    )


def _pick_stats_for_player(
    player_id: Optional[int],
    surface: Optional[str],
    all_stats: dict,
) -> Optional[PlayerRollingStats]:
    if player_id is None:
        return None
    surface_stats = all_stats.get((player_id, surface))
    if surface_stats is not None and (surface_stats.matches_count or 0) >= 10:
        return surface_stats
    return all_stats.get((player_id, None))


def generate_prop_picks(pred: PredictionOutput, prop_lines: list[PropLine]) -> list[BestPick]:
    """Prop picks from the board's own assessment of each line (`_enrich`).

    Side, hit probability, tier and flags are read, never recomputed, so a card
    cannot outrank the board row or the props-v2 snapshot it came from.
    """
    picks: list[BestPick] = []

    for line in prop_lines:
        if line.match_id != pred.match_id or line.line is None:
            continue
        if line.recommendation is None or line.confidence in (None, "PASS"):
            continue
        stat_key = line.stat_type.strip().lower().replace(" ", "_")
        # Ungraded (16e): the props page caps them at LEAN, so they are no best pick.
        if stat_key in FIRST_SET_STATS:
            continue
        if line.hit_probability is None or line.stat_avg is None or line.edge_pct is None:
            continue

        line_f = float(line.line)
        direction = line.recommendation
        prob = line.hit_probability
        stat_label = STAT_LABELS.get(stat_key, line.stat_type)
        player_last = (line.player_name or "").split()[-1] if line.player_name else "Unknown"

        avg_word = "projects for" if stat_key in ("fantasy_score", "total_games_won", "games_won") else "averages"
        reasoning = (
            f"{player_last} {avg_word} {line.stat_avg:.1f} {stat_label.lower()} vs {line_f:.1f} line — "
            f"{prob:.0%} probability {direction.lower()}"
        )
        if line.matches_count and line.matches_count < 10:
            reasoning += " (small sample)"

        # Only a real book price earns an EV here. The board's PrizePicks EV is
        # against assumed payouts, which the card has always shown as unpriced.
        pick_odds = line.p1_odds if direction == "OVER" else line.p2_odds
        ev_pct = line.ev_pct if pick_odds is not None else None
        kelly = compute_kelly_fraction(prob, pick_odds) if pick_odds is not None else None

        picks.append(BestPick(
            pick_type="prop",
            label=stat_label,
            pick=f"{player_last} {stat_label} {direction} {line_f:.1f}",
            player_name=line.player_name,
            edge_pct=line.edge_pct,
            confidence=line.confidence,
            reasoning=reasoning,
            odds_american=pick_odds,
            ev_pct=ev_pct,
            model_prob=round(prob, 4),
            market_prob=None,
            kelly_fraction=round(kelly, 4) if kelly is not None else None,
            data_quality_flags=tuple(line.data_quality_flags),
            odds_source="posted" if pick_odds is not None else "unpriced",
            score=_score_pick(ev_pct if ev_pct is not None else line.edge_pct, line.confidence, line.matches_count),
        ))

    return picks


def generate_market_odds_picks(
    pred: PredictionOutput,
    props: list,
    rolling_stats: dict,
    match_player_ids: tuple[Optional[int], Optional[int]] | None = None,
    market_total_games_map: dict | None = None,
) -> list[BestPick]:
    """Generate picks from live match odds markets like total games and game spread."""
    picks: list[BestPick] = []
    if match_player_ids is None:
        return picks

    p1_id, p2_id = match_player_ids
    p1_stats = _pick_stats_for_player(p1_id, pred.surface, rolling_stats) if p1_id else None
    p2_stats = _pick_stats_for_player(p2_id, pred.surface, rolling_stats) if p2_id else None
    mtg_map = market_total_games_map or {}

    for prop in props:
        if prop.match_id != pred.match_id or prop.line is None:
            continue

        stat_type = prop.stat_type.strip().lower().replace(" ", "_")
        line = float(prop.line)
        # Spread lines are signed — the favorite's side is negative by
        # definition, so a blanket "line <= 0" drops half of every spread market.
        # The positivity guard only makes sense for count-style totals.
        if stat_type != "game_spread" and line <= 0:
            continue

        market_total = mtg_map.get(prop.match_id) if prop.match_id is not None else None

        if stat_type == "total_games":
            if line < 17.0:
                continue
            # With a book total on file, both projections below return that line, so
            # the pick would grade the market against itself.
            if market_total is not None and market_total >= 17.0:
                continue

            p1_expected = _compute_stat_avg("total_games", p1_stats, win_prob=pred.p1_win_prob, surface=pred.surface, market_total_games=market_total, best_of=pred.best_of) if p1_stats else None
            p2_expected = _compute_stat_avg("total_games", p2_stats, win_prob=pred.p2_win_prob, surface=pred.surface, market_total_games=market_total, best_of=pred.best_of) if p2_stats else None
            if p1_expected is not None and p2_expected is not None:
                expected_total = (p1_expected + p2_expected) / 2.0
            elif p1_expected is not None:
                expected_total = p1_expected
            elif p2_expected is not None:
                expected_total = p2_expected
            else:
                continue

            # Total games is a mixture over set count, so it needs the chance the match
            # goes the distance. This stays on 2*p*(1-p) rather than the fitted
            # tennis_sets curve until the stored book total lines it is checked
            # against are trustworthy.
            wp = pred.p1_win_prob
            p_deciding = (2 * wp * (1 - wp)) if wp is not None else None
            tg = total_games_probs(line, expected_total, p_deciding, pred.best_of)
            p_over, p_under = tg.p_over, tg.p_under
            directions = [
                ("OVER", p_over, prop.p1_odds, "Expected"),
                ("UNDER", p_under, prop.p2_odds, "Expected"),
            ]
            mkt_over = mkt_under = None
            if prop.p1_odds is not None and prop.p2_odds is not None:
                mkt_over, mkt_under = devig_two_way(
                    american_to_prob(prop.p1_odds),
                    american_to_prob(prop.p2_odds),
                )

            for direction, prob, odds, _ in directions:
                if odds is None:
                    continue
                ev = expected_value(prob, odds)
                kelly = compute_kelly_fraction(prob, odds)
                market_prob = mkt_over if direction == "OVER" else mkt_under
                assessment = assess_bettable_pick(prob, ev, kelly, odds_source="posted")
                if assessment is None:
                    continue
                conf = assessment.confidence
                edge_pct = round(((prob - (market_prob or 0.5)) / max(market_prob or 0.5, 0.01)) * 100, 1)
                picks.append(BestPick(
                    pick_type="prop",
                    label="Total Games",
                    pick=f"{direction} {line:.1f} Games",
                    player_name=None,
                    edge_pct=edge_pct,
                    confidence=conf,
                    reasoning=(
                        f"Expected {expected_total:.1f} total games vs {line:.1f} line - "
                        f"{prob:.0%} probability {direction.lower()}"
                    ),
                    odds_american=odds,
                    ev_pct=round(ev * 100, 1),
                    model_prob=round(prob, 4),
                    market_prob=round(market_prob, 4) if market_prob is not None else None,
                    kelly_fraction=round(kelly, 4),
                    data_quality_flags=assessment.data_quality_flags,
                    odds_source=assessment.odds_source,
                    score=_score_pick(ev * 100, conf),
                ))

        elif stat_type == "game_spread":
            if p1_stats is None or p2_stats is None:
                continue

            p1_games = _compute_stat_avg(
                "total_games_won",
                p1_stats,
                opponent_stats=p2_stats,
                win_prob=pred.p1_win_prob,
                surface=pred.surface,
                market_total_games=market_total,
                best_of=pred.best_of,
            )
            p2_games = _compute_stat_avg(
                "total_games_won",
                p2_stats,
                opponent_stats=p1_stats,
                win_prob=pred.p2_win_prob,
                surface=pred.surface,
                market_total_games=market_total,
                best_of=pred.best_of,
            )
            if p1_games is None or p2_games is None:
                continue

            p1_cover, p2_cover = _poisson_diff_cover_probs(p1_games, p2_games, line)
            mkt_p1 = mkt_p2 = None
            if prop.p1_odds is not None and prop.p2_odds is not None:
                mkt_p1, mkt_p2 = devig_two_way(
                    american_to_prob(prop.p1_odds),
                    american_to_prob(prop.p2_odds),
                )

            for player_name, player_last, spread_line, prob, odds, market_prob in [
                (pred.p1_name, pred.p1_name.split()[-1], line, p1_cover, prop.p1_odds, mkt_p1),
                (pred.p2_name, pred.p2_name.split()[-1], -line, p2_cover, prop.p2_odds, mkt_p2),
            ]:
                if odds is None:
                    continue
                ev = expected_value(prob, odds)
                kelly = compute_kelly_fraction(prob, odds)
                assessment = assess_bettable_pick(prob, ev, kelly, odds_source="posted")
                if assessment is None:
                    continue
                conf = assessment.confidence
                edge_pct = round(((prob - (market_prob or 0.5)) / max(market_prob or 0.5, 0.01)) * 100, 1)
                sign = "+" if spread_line > 0 else ""
                picks.append(BestPick(
                    pick_type="prop",
                    label="Game Spread",
                    pick=f"{player_last} {sign}{spread_line:.1f} Games",
                    player_name=player_name,
                    edge_pct=edge_pct,
                    confidence=conf,
                    reasoning=(
                        f"Projected game margin {p1_games - p2_games:+.1f} vs {line:+.1f} spread - "
                        f"{prob:.0%} probability {player_last} covers"
                    ),
                    odds_american=odds,
                    ev_pct=round(ev * 100, 1),
                    model_prob=round(prob, 4),
                    market_prob=round(market_prob, 4) if market_prob is not None else None,
                    kelly_fraction=round(kelly, 4),
                    data_quality_flags=assessment.data_quality_flags,
                    odds_source=assessment.odds_source,
                    score=_score_pick(ev * 100, conf),
                ))

    return picks


def generate_serve_edge_picks(
    pred: PredictionOutput,
    rolling_stats: dict,
    match_player_ids: tuple[Optional[int], Optional[int]] | None = None,
) -> list[BestPick]:
    """Generate serve-edge picks when a player's 1st-serve win% significantly exceeds opponent return%."""
    picks: list[BestPick] = []
    if match_player_ids is None:
        return picks

    p1_id, p2_id = match_player_ids
    p1_stats = _pick_stats_for_player(p1_id, pred.surface, rolling_stats) if p1_id else None
    p2_stats = _pick_stats_for_player(p2_id, pred.surface, rolling_stats) if p2_id else None

    for player_name, player_stats, opp_stats in [
        (pred.p1_name, p1_stats, p2_stats),
        (pred.p2_name, p2_stats, p1_stats),
    ]:
        if player_stats is None or opp_stats is None:
            continue
        fwp = _f(player_stats.first_won_pct)
        opp_ret = _f(opp_stats.ret_pts_won)
        if fwp is None or opp_ret is None:
            continue
        if fwp > 0.78 and opp_ret < 0.35:
            edge_pct = round((fwp - 0.78) / 0.78 * 100, 1)
            conf = confidence_tier(fwp)
            if conf == "PASS":
                continue
            player_last = player_name.split()[-1]
            picks.append(BestPick(
                pick_type="derived",
                label="Serve Edge",
                pick=f"{player_last} serve edge",
                player_name=player_name,
                edge_pct=edge_pct,
                confidence=conf,
                reasoning=(
                    f"{player_last} wins {fwp:.0%} of 1st serves vs opponent returning "
                    f"only {opp_ret:.0%} — strong serve edge favoring hold dominance"
                ),
                model_prob=round(fwp, 4),
                data_quality_flags=(),
                odds_source="unpriced",
                score=_score_pick(edge_pct, conf, player_stats.matches_count),
            ))
    return picks


def generate_derived_picks(
    pred: PredictionOutput,
    p1_stats: Optional[PlayerRollingStats] = None,
    p2_stats: Optional[PlayerRollingStats] = None,
) -> list[BestPick]:
    """Generate set-score and upset picks from win probability and optional player stats."""
    picks: list[BestPick] = []
    if pred.p1_win_prob is None:
        return picks

    p = pred.p1_win_prob  # favorite probability (may or may not be P1)
    fav_name = pred.p1_name if p >= 0.5 else pred.p2_name
    dog_name = pred.p2_name if p >= 0.5 else pred.p1_name
    fav_p = max(p, 1 - p)
    dog_p = 1 - fav_p
    fav_last = fav_name.split()[-1]
    dog_last = dog_name.split()[-1]

    fav_stats = p1_stats if fav_name == pred.p1_name else p2_stats

    # Every set-score derivation below is best-of-3 math: a sweep is 2-0, a long
    # match is exactly 3 sets, and "wins a set" is the complement of a 2-0. None
    # of that holds in an ATP slam main draw, where the same formulas would quote
    # confident numbers for the wrong format. Serve Dominance is format-agnostic
    # and stays.
    best_of_three = pred.best_of <= 3

    dr_boost = 0.0
    if fav_stats is not None:
        dr = _f(fav_stats.dominance_ratio)
        if dr is not None and dr > 1.3:
            dr_boost = min((dr - 1.3) * 0.1, 0.08)

    if not best_of_three:
        p_fav_straight = min(fav_p ** 3 + dr_boost, 0.95)
        p_dog_straight = dog_p ** 3
        p_four_plus = max(0.0, min(0.98, 1 - p_fav_straight - p_dog_straight))
        p_five_sets = min(0.75, 3 * fav_p * dog_p * min(fav_p, dog_p))

        if p_fav_straight >= 0.25:
            conf = confidence_tier(p_fav_straight)
            edge = round((p_fav_straight - 0.25) / 0.25 * 100, 1)
            picks.append(BestPick(
                pick_type="derived",
                label="Set Score 3-0",
                pick=f"{fav_last} wins 3-0",
                player_name=fav_name,
                edge_pct=edge,
                confidence=conf,
                reasoning=(
                    f"{fav_last} at {fav_p:.0%} win prob has a "
                    f"{p_fav_straight:.0%} best-of-5 straight-sets estimate"
                ),
                model_prob=round(p_fav_straight, 4),
                odds_source="unpriced",
                score=_score_pick(edge, conf),
            ))

        if p_four_plus >= 0.45:
            conf = confidence_tier(p_four_plus)
            edge = round((p_four_plus - 0.45) / 0.45 * 100, 1)
            picks.append(BestPick(
                pick_type="derived",
                label="Total Sets",
                pick="Match goes 4+ sets",
                player_name=None,
                edge_pct=edge,
                confidence=conf,
                reasoning=(
                    f"Best-of-5 set mix gives a {p_four_plus:.0%} estimate "
                    "that the match reaches at least four sets"
                ),
                model_prob=round(p_four_plus, 4),
                odds_source="unpriced",
                score=_score_pick(edge, conf),
            ))

        p_dog_set = 1 - p_fav_straight
        if p_dog_set >= 0.55 and dog_p >= 0.15:
            conf = confidence_tier(p_dog_set)
            edge = round((p_dog_set - 0.50) / 0.50 * 100, 1)
            picks.append(BestPick(
                pick_type="derived",
                label="Win a Set",
                pick=f"{dog_last} wins a set",
                player_name=dog_name,
                edge_pct=edge,
                confidence=conf,
                reasoning=(
                    f"{dog_last} has a {p_dog_set:.0%} best-of-5 estimate "
                    "to take at least one set"
                ),
                model_prob=round(p_dog_set, 4),
                odds_source="unpriced",
                score=_score_pick(edge, conf),
            ))

        if p_five_sets >= 0.30:
            conf = confidence_tier(p_five_sets)
            edge = round((p_five_sets - 0.30) / 0.30 * 100, 1)
            picks.append(BestPick(
                pick_type="derived",
                label="Total Sets",
                pick="Match goes 5 sets",
                player_name=None,
                edge_pct=edge,
                confidence=conf,
                reasoning=(
                    f"Close best-of-5 matchup gives a {p_five_sets:.0%} "
                    "estimate to reach a fifth set"
                ),
                model_prob=round(p_five_sets, 4),
                odds_source="unpriced",
                score=_score_pick(edge, conf),
            ))

    outcomes = set_outcomes(fav_p)

    # ── 2-0 Sweep ──
    # Boost slightly if favorite has dominant serve-vs-return ratio
    p_fav_sweep = min(outcomes.favorite_straight + dr_boost, 0.95)
    if best_of_three and p_fav_sweep >= 0.40:  # only suggest if reasonably likely
        conf = confidence_tier(p_fav_sweep)
        edge = round((p_fav_sweep - 0.40) / 0.40 * 100, 1)  # edge vs ~40% baseline
        picks.append(BestPick(
            pick_type="derived",
            label="Set Score 2-0",
            pick=f"{fav_last} wins 2-0",
            player_name=fav_name,
            edge_pct=edge,
            confidence=conf,
            reasoning=f"{fav_last} at {fav_p:.0%} win prob → {p_fav_sweep:.0%} chance of a straight-sets win",
            model_prob=round(p_fav_sweep, 4),
            odds_source="unpriced",
            score=_score_pick(edge, conf),
        ))

    # ── Match Goes 3 Sets ──
    p_three_sets = outcomes.three_sets
    if best_of_three and p_three_sets >= 0.35:
        conf = confidence_tier(p_three_sets)
        edge = round((p_three_sets - 0.30) / 0.30 * 100, 1) if p_three_sets > 0.30 else 0.0
        picks.append(BestPick(
            pick_type="derived",
            label="Total Sets",
            pick="Match goes 3 sets",
            player_name=None,
            edge_pct=edge,
            confidence=conf,
            reasoning=f"Close matchup ({fav_p:.0%}/{dog_p:.0%}) → {p_three_sets:.0%} chance of a 3-set match",
            model_prob=round(p_three_sets, 4),
            odds_source="unpriced",
            score=_score_pick(edge, conf),
        ))

    # ── Underdog Wins a Set ──
    # P(dog wins >= 1 set) = 1 - P(fav sweeps 2-0)
    p_dog_set = 1 - p_fav_sweep
    if best_of_three and p_dog_set >= 0.55 and dog_p >= 0.20:
        conf = confidence_tier(p_dog_set)
        edge = round((p_dog_set - 0.50) / 0.50 * 100, 1) if p_dog_set > 0.50 else 0.0
        picks.append(BestPick(
            pick_type="derived",
            label="Win a Set",
            pick=f"{dog_last} wins a set",
            player_name=dog_name,
            edge_pct=edge,
            confidence=conf,
            reasoning=f"{dog_last} has a {p_dog_set:.0%} chance of taking at least one set",
            model_prob=round(p_dog_set, 4),
            odds_source="unpriced",
            score=_score_pick(edge, conf),
        ))

    # ── Serve Dominance (dominance_ratio ≥ 1.4) ──
    if fav_stats is not None:
        dr = _f(fav_stats.dominance_ratio)
        if dr is not None and dr >= 1.4:
            edge = round((dr - 1.0) / 1.0 * 100, 1)
            conf = confidence_tier(min(fav_p + (dr - 1.4) * 0.1, 0.85))
            if conf != "PASS":
                picks.append(BestPick(
                    pick_type="derived",
                    label="Serve Dominance",
                    pick=f"{fav_last} serve dominance",
                    player_name=fav_name,
                    edge_pct=edge,
                    confidence=conf,
                    reasoning=(
                        f"{fav_last} dominance ratio {dr:.2f} — significantly stronger "
                        f"serving than returning, favoring straight-sets control"
                    ),
                    model_prob=round(min(fav_p + (dr - 1.4) * 0.1, 0.85), 4),
                    odds_source="unpriced",
                    score=_score_pick(edge, conf),
                ))

    return picks


@dataclass
class MatchBestPicks:
    match_id: int
    start_utc: Optional[str]
    p1_name: str
    p2_name: str
    tour: str
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    p1_win_prob: Optional[float]
    p2_win_prob: Optional[float]
    p1_odds_american: Optional[int]
    p2_odds_american: Optional[int]
    h2h_p1_wins: int = 0
    h2h_p2_wins: int = 0
    tour_label: str = ""
    picks: list[BestPick] = field(default_factory=list)


def build_best_picks(
    pred: PredictionOutput,
    props: list,
    rolling_stats: dict,
    prop_lines: list[PropLine] | None = None,
    match_player_ids: tuple[Optional[int], Optional[int]] | None = None,
    market_total_games_map: dict | None = None,
) -> MatchBestPicks:
    """Build ranked best picks for a single match: top 3 ML/derived + top 3 prop picks."""

    p1_id, p2_id = match_player_ids if match_player_ids else (None, None)
    p1_stats = _pick_stats_for_player(p1_id, pred.surface, rolling_stats) if p1_id else None
    p2_stats = _pick_stats_for_player(p2_id, pred.surface, rolling_stats) if p2_id else None

    # Bucket A: Moneyline + Derived (top 3). Priced picks lead: a derived pick's
    # score is an edge against a hardcoded baseline, not a price, so it cannot be
    # allowed to push a priced moneyline pick out of the list.
    ml_pick = generate_ml_pick(pred) if MONEYLINE_PICKS_ENABLED else None
    derived_picks = generate_derived_picks(pred, p1_stats=p1_stats, p2_stats=p2_stats)
    serve_edge_picks = generate_serve_edge_picks(pred, rolling_stats, match_player_ids)
    ml_derived: list[BestPick] = sorted(
        ([ml_pick] if ml_pick else []) + derived_picks + serve_edge_picks,
        key=lambda p: (p.ev_pct is not None, p.score),
        reverse=True,
    )[:3]

    # Bucket B: Prop picks (top 3 by score)
    prop_picks: list[BestPick] = sorted(
        generate_prop_picks(pred, prop_lines or [])
        + generate_market_odds_picks(pred, props, rolling_stats, match_player_ids, market_total_games_map),
        key=lambda p: p.score,
        reverse=True,
    )[:3]

    final = ml_derived + prop_picks

    return MatchBestPicks(
        match_id=pred.match_id,
        start_utc=pred.start_utc.isoformat() if pred.start_utc else None,
        p1_name=pred.p1_name,
        p2_name=pred.p2_name,
        tour=pred.tour,
        tour_label=pred.tour_label or pred.tour,
        surface=pred.surface,
        tournament=pred.tournament,
        round=pred.round,
        p1_win_prob=pred.p1_win_prob,
        p2_win_prob=pred.p2_win_prob,
        p1_odds_american=pred.p1_odds_american,
        p2_odds_american=pred.p2_odds_american,
        h2h_p1_wins=pred.h2h_p1_wins,
        h2h_p2_wins=pred.h2h_p2_wins,
        picks=final,
    )
