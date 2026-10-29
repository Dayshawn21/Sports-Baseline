"""Tennis prop projections read off one match simulation (48c, `props-v4`).

Every prop on a match reads the same draws, so a player's games won, the
match total and their fantasy score can never disagree with each other.
"""
from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.core.prop_ev import assess_prop
from app.core.prop_probs import PropProbabilities, prop_side
from app.core.prop_projection import (
    _BASELINE_HOLD_PCT,
    _SURFACE_ACE_FACTOR,
    _SURFACE_DF_FACTOR,
    ace_matchup_factor,
    double_fault_matchup_factor,
    normalize_stat_type,
    serve_hold,
)
from app.core.tennis_match_chain import SET_EFFECT_SD, solve_holds
from app.core.tennis_match_sim import ACE_RATE_SHAPE, DEFAULT_DRAWS, DF_RATE_SHAPE, MatchDraws, simulate_match
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.players import PlayerRollingStats, get_rolling_stats_batch_all_surfaces
from app.repositories.props import Prop
from app.routers.props import (
    MarketTotal,
    _fetch_market_totals,
    _fetch_market_win_probs,
    _fetch_opponent_ids,
    _fetch_win_probs,
    _pick_stats_for_player,
)
from app.schemas.props import PropLine

_StatReader = Callable[[MatchDraws, int], np.ndarray]


def _fantasy_score(draws: MatchDraws, player: int) -> np.ndarray:
    """PrizePicks tennis scoring, as `compute_stat_avg` uses it."""
    opponent = 1 - player
    return (
        10.0
        + draws.games_won[player] - draws.games_won[opponent]
        + 3.0 * (draws.sets_won[player] - draws.sets_won[opponent])
        + 0.5 * draws.aces[player] - 0.5 * draws.double_faults[player]
    )


_STATS: dict[str, _StatReader] = {
    "total_games": lambda draws, _: draws.total_games,
    "total_games_won": lambda draws, player: draws.games_won[player],
    "games_won": lambda draws, player: draws.games_won[player],
    "total_sets": lambda draws, _: draws.sets_won.sum(axis=0),
    "total_tie_breaks": lambda draws, _: draws.tie_breaks,
    "1st_set_total_games": lambda draws, _: draws.first_set_games.sum(axis=0),
    "1st_set_total_games_won": lambda draws, player: draws.first_set_games[player],
    "aces": lambda draws, player: draws.aces[player],
    "double_faults": lambda draws, player: draws.double_faults[player],
    # A break game is won on exactly one break point.
    "break_points_won": lambda draws, player: draws.breaks[player],
    "break_points_converted": lambda draws, player: draws.breaks[player],
    "fantasy_score": _fantasy_score,
}

SIM_STATS = frozenset(_STATS)
_LEVEL_ALIASES = {"games_won": "total_games_won", "break_points_converted": "break_points_won"}
# (stat, tour) pairs whose simulated mean missed completed matches by at least
# 48c step 8's pre-registered threshold (`tennis_match_sim --level`, 2026-10-29,
# 523 Bet365-era matches). Flagged, never tuned.
SIM_LEVEL_UNVERIFIED: frozenset[tuple[str, str]] = frozenset({
    ("total_games", "WTA"), ("total_games_won", "WTA"), ("aces", "WTA"),
    ("break_points_won", "ATP"), ("break_points_won", "WTA"),
    ("total_sets", "ATP"), ("total_sets", "WTA"), ("total_tie_breaks", "ATP"),
})


def level_stat(stat_type: str) -> str:
    """The name step 8's level check reports a stat under."""
    stat = normalize_stat_type(stat_type)
    return _LEVEL_ALIASES.get(stat, stat)


def stat_values(draws: MatchDraws, stat_type: str, player: int) -> np.ndarray | None:
    """One value per draw for `player` (0 is A, 1 is B), or None for a stat the simulation does not cover."""
    reader = _STATS.get(normalize_stat_type(stat_type))
    return reader(draws, player) if reader is not None else None


def line_probabilities(values: np.ndarray, line: float) -> PropProbabilities:
    """The exact share of draws over, under and on the line."""
    count = max(1, values.size)
    return PropProbabilities(
        float((values > line).sum()) / count,
        float((values < line).sum()) / count,
        float((values == line).sum()) / count,
    )


# _enrich's PrizePicks hard blocks: a row carrying one shows no projection.
_BLOCKING_FLAGS = frozenset({
    "missing_player", "missing_match", "missing_stats", "unsupported_stat",
    "match_finished", "match_link_invalid", "bo5_unsupported_stat",
})
_OVER_ONLY = frozenset({"demon", "goblin"})
_ACE_STATS = frozenset({"aces", "fantasy_score"})
_DF_STATS = frozenset({"double_faults", "fantasy_score"})


@dataclass(frozen=True)
class SimInputs:
    """What `enrich_with` already loads for the same props."""

    opponent_ids: dict[tuple[int, int], int]
    rolling_stats: dict[tuple[int, str | None], PlayerRollingStats]
    prediction_probs: dict[tuple[int, int], float]
    market_probs: dict[tuple[int, int], float]
    market_totals: dict[int, MarketTotal]


@dataclass(frozen=True)
class MatchSim:
    """One match's draws and the anchors they were solved from. Player A is the lower player id."""

    players: tuple[int, int]
    draws: MatchDraws
    holds: tuple[float, float]
    win_prob_a: float
    win_prob_source: str
    total_line: float | None
    total_over_prob: float | None
    clamped: bool
    seed: int
    missing_ace_rate: frozenset[int]
    missing_df_rate: frozenset[int]


def _serve_rate(
    rate: float | None, opponent: PlayerRollingStats | None, tour: str | None, surface: str | None, *, aces: bool,
) -> float | None:
    if rate is None:
        return None
    surface_key = (surface or "").title()
    if aces:
        return rate * ace_matchup_factor(opponent, tour) * _SURFACE_ACE_FACTOR.get(surface_key, 1.0)
    return rate * double_fault_matchup_factor(opponent, tour) * _SURFACE_DF_FACTOR.get(surface_key, 1.0)


def _seed(match_id: int, *anchors: float | None) -> int:
    """Stable across processes, unlike hash(), so a re-run reproduces the row."""
    return zlib.crc32(repr((match_id, *(None if a is None else round(a, 6) for a in anchors))).encode())


def _win_prob_a(players: tuple[int, int], match_id: int, inputs: SimInputs) -> tuple[float, str] | None:
    market = inputs.market_probs.get((players[0], match_id))
    if market is not None:
        return market, "market"
    ensemble = inputs.prediction_probs.get((players[0], match_id))
    return (ensemble, "ensemble") if ensemble is not None else None


def _player_rates(
    stats: list[PlayerRollingStats | None], prop: Prop, field: str, *, aces: bool,
) -> list[float | None]:
    """Each player's per-serve-point rate against the other, or None without the stat."""
    rates: list[float | None] = []
    for i in (0, 1):
        own = stats[i]
        rate = getattr(own, field) if own is not None else None
        rates.append(_serve_rate(
            float(rate) if rate is not None else None, stats[1 - i], prop.player_tour, prop.surface, aces=aces,
        ))
    return rates


def _total_anchor(total: MarketTotal | None) -> tuple[float | None, float | None]:
    if total is None:
        return None, None
    return total.line, total.p_over if total.p_over is not None else 0.5


def build_match_sim(prop: Prop, inputs: SimInputs) -> MatchSim | None:
    """The match's one simulation, or None when it has no win probability or no opponent."""
    if prop.player_id is None or prop.match_id is None:
        return None
    opponent_id = inputs.opponent_ids.get((prop.player_id, prop.match_id))
    if opponent_id is None:
        return None
    players = (min(prop.player_id, opponent_id), max(prop.player_id, opponent_id))
    anchor = _win_prob_a(players, prop.match_id, inputs)
    if anchor is None:
        return None
    win_prob, source = anchor
    best_of = prop.best_of or 3
    stats = [_pick_stats_for_player(player, prop.surface, inputs.rolling_stats) for player in players]
    line, p_over = _total_anchor(inputs.market_totals.get(prop.match_id))
    level = sum(serve_hold(s) if s is not None else _BASELINE_HOLD_PCT for s in stats) / 2.0
    solution = solve_holds(
        win_prob, best_of, total_line=line, p_over=p_over if p_over is not None else 0.5, stats_level=level,
    )
    aces = _player_rates(stats, prop, "aces_per_game", aces=True)
    faults = _player_rates(stats, prop, "df_per_game", aces=False)
    seed = _seed(prop.match_id, win_prob, line, p_over, level)
    draws = simulate_match(
        solution.hold_a, solution.hold_b, best_of,
        aces[0] or 0.0, aces[1] or 0.0, faults[0] or 0.0, faults[1] or 0.0, seed=seed,
        ace_shape=ACE_RATE_SHAPE, df_shape=DF_RATE_SHAPE,
    )
    return MatchSim(
        players, draws, (solution.hold_a, solution.hold_b), win_prob, source, line, p_over,
        solution.clamped, seed,
        frozenset(i for i in (0, 1) if aces[i] is None),
        frozenset(i for i in (0, 1) if faults[i] is None),
    )


def _projection_inputs(sim: MatchSim, player: int) -> dict[str, float | str]:
    inputs: dict[str, float | str] = {
        "sim_hold_player": round(sim.holds[player], 4),
        "sim_hold_opponent": round(sim.holds[1 - player], 4),
        "sim_win_prob": round(sim.win_prob_a if player == 0 else 1.0 - sim.win_prob_a, 4),
        "sim_win_prob_source": sim.win_prob_source,
        "sim_total_anchor": "book" if sim.total_line is not None else "stats",
        "sim_clamped": "true" if sim.clamped else "false",
        "sim_draws": float(DEFAULT_DRAWS),
        "sim_seed": float(sim.seed),
        "sim_set_effect_sd": SET_EFFECT_SD,
    }
    if sim.total_line is not None and sim.total_over_prob is not None:
        inputs["market_total_games"] = round(sim.total_line, 2)
        inputs["market_total_over_prob"] = round(sim.total_over_prob, 4)
    return inputs


def _sim_values(prop: Prop, line: PropLine, sim: MatchSim | None) -> tuple[int, np.ndarray] | None:
    if sim is None or prop.player_id not in sim.players or _BLOCKING_FLAGS.intersection(line.data_quality_flags):
        return None
    player = sim.players.index(prop.player_id)
    stat = normalize_stat_type(prop.stat_type)
    if (stat in _ACE_STATS and player in sim.missing_ace_rate) or (stat in _DF_STATS and player in sim.missing_df_rate):
        return None
    values = stat_values(sim.draws, stat, player)
    return (player, values) if values is not None else None


def _sim_line(prop: Prop, line: PropLine, sim: MatchSim | None) -> PropLine:
    """The v3 row with its projection replaced by the simulation's; flags and metadata stay."""
    flags = set(line.data_quality_flags)
    if sim is not None and sim.win_prob_source == "ensemble":
        flags.add("no_market_moneyline")
    if (level_stat(prop.stat_type), (prop.player_tour or "").upper()) in SIM_LEVEL_UNVERIFIED:
        flags.add("sim_level_unverified")
    cleared = {
        "stat_avg": None, "edge_pct": None, "p_over": None, "p_under": None, "p_push": None,
        "recommendation": None, "hit_probability": None, "ev_pct": None, "break_even_pct": None,
        "confidence": None, "projection_inputs": {}, "data_quality_flags": sorted(flags),
    }
    found = _sim_values(prop, line, sim)
    line_value = float(prop.line) if prop.line is not None else None
    if found is None or sim is None or line_value is None:
        # A match with no win probability is never simulated; every other gap is the stat's.
        unprojected = "missing_prediction" if sim is None else "unsupported_stat"
        status = line.projection_status if line.projection_status != "ok" else unprojected
        return line.model_copy(update={**cleared, "projection_status": status})
    player, values = found
    probs = line_probabilities(values, line_value)
    over_only = (prop.odds_type or "").lower() in _OVER_ONLY
    recommendation = "OVER" if over_only else prop_side(probs.p_over, probs.p_under)
    hit = probs.p_over / max(1e-9, 1.0 - probs.p_push) if over_only else probs.decision_probability
    side_odds = prop.p1_odds if recommendation == "OVER" else prop.p2_odds
    assessment = assess_prop(hit, prop.odds_type, american_odds=side_odds, source=prop.source)
    mean = float(values.mean())
    serve_points = sim.draws.serve_points_won[player] + sim.draws.serve_points_lost[player]
    return line.model_copy(update={
        **cleared,
        "stat_avg": round(mean, 2),
        "edge_pct": round((mean - line_value) / line_value * 100, 1) if line_value > 0 else None,
        "p_over": round(probs.p_over, 3),
        "p_under": round(probs.p_under, 3),
        "p_push": round(probs.p_push, 3),
        "recommendation": recommendation,
        "hit_probability": round(hit, 3),
        "ev_pct": assessment.ev_pct if assessment is not None else None,
        "break_even_pct": round(assessment.break_even_probability * 100.0, 1) if assessment is not None else None,
        "expected_service_points": round(float(serve_points.mean()), 2),
        "projection_inputs": _projection_inputs(sim, player),
        "projection_status": "ok",
    })


async def load_sim_inputs(db: AsyncSession, props: list[Prop]) -> SimInputs:
    """The inputs `enrich_props` loads, once, so v3 (`enrich_with`) and v4 read the same values."""
    opponent_ids = await _fetch_opponent_ids(db, props)
    player_ids = {p.player_id for p in props if p.player_id is not None} | set(opponent_ids.values())
    return SimInputs(
        opponent_ids=opponent_ids,
        rolling_stats=await get_rolling_stats_batch_all_surfaces(db, list(player_ids)),
        prediction_probs=await _fetch_win_probs(db, props),
        market_probs=await _fetch_market_win_probs(db, props),
        market_totals=await _fetch_market_totals(db, props),
    )


def sim_prop_lines(props: list[Prop], lines: list[PropLine], inputs: SimInputs) -> list[PropLine]:
    """The `props-v4` rows for the same props and v3 rows, in their order.

    One simulation per match, built when its first prop comes up and dropped
    once its props are done, so only one match's draws are held at a time.
    """
    pairs = list(zip(props, lines, strict=True))
    by_match: dict[int | None, list[int]] = {}
    for i, (prop, _) in enumerate(pairs):
        by_match.setdefault(prop.match_id, []).append(i)
    rows: list[PropLine | None] = [None] * len(pairs)
    for match_id, indices in by_match.items():
        sim = build_match_sim(pairs[indices[0]][0], inputs) if match_id is not None else None
        for i in indices:
            rows[i] = _sim_line(*pairs[i], sim)
    return [row for row in rows if row is not None]
