"""Trimmers for Ask Lineform's detail tools (47a): one game, one player, one
sport's track record. Same contract as `ask_results`: plain mappings in, small
rows out, every row with a `url` and a `signal`.

Game props are listed by player then market, never by gap: NBA game-page props
are unranked (20g2), and only the slate digest may sort a gap.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from pydantic import JsonValue

from app.core.ask_links import game_path, model_path, player_path
from app.core.ask_results import Row, Source, ct_label, signal_for

MAX_GAME_PROPS = 20
MAX_INJURIES = 12
MAX_LOG = 6

VERDICT_MEANING = {
    "insufficient": "still accruing: too few settled picks for a verdict, so the slice is not validated",
    "accruing": "still accruing: too few settled picks for a verdict, so it is not validated",
    "adopt": "passed its pre-registered check",
    "pass": "passed its pre-registered check",
    "reject": "failed its pre-registered check; final for this model version",
}


def _map(value: object) -> Source:
    return value if isinstance(value, Mapping) else {}


def _list(value: object) -> list[Source]:
    return [item for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _num(value: object, places: int) -> float | None:
    return round(float(value), places) if isinstance(value, (int, float)) else None


def _short(text: object, limit: int = 140) -> str | None:
    if not isinstance(text, str):
        return None
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def _props_note(shown: int, total: int, filtered: bool) -> str | None:
    if shown == total:
        return None
    if filtered:
        return f"{total} lines for this player; showing {shown}."
    return f"{total} lines; showing {shown} standard lines by player. Pass player_id for one player's full lines."


def _game_props(lines: list[Row], player_id: int | None) -> tuple[list[Row], str | None]:
    if player_id is not None:
        chosen = [line for line in lines if line["player_id"] == player_id]
    else:
        chosen = [line for line in lines if line["odds_type"] in ("standard", None)]
    chosen.sort(key=lambda line: (str(line["player"]), str(line["market"]), float(str(line["line"]))))
    shown = chosen[:MAX_GAME_PROPS]
    total = len(chosen) if player_id is not None else len(lines)
    return shown, _props_note(len(shown), total, player_id is not None)


def _nba_injuries(report: Source) -> JsonValue:
    rows: list[JsonValue] = [
        {"player": i.get("player_name"), "team": i.get("team"), "status": i.get("status"),
         "detail": _short(i.get("detail")), "signal": "none"}
        for i in _list(report.get("injuries"))[:MAX_INJURIES]
    ]
    return {"source": report.get("source"), "freshness": report.get("freshness"), "players": rows}


def _nba_team_stats(stats: Source) -> JsonValue:
    out: dict[str, JsonValue] = {}
    for side in ("away", "home"):
        team = _map(stats.get(side))
        out[str(team.get("team", side))] = {
            name: {
                "for": _map(pair.get("for_") or pair.get("for")).get("per_game"),
                "for_rank": _map(pair.get("for_") or pair.get("for")).get("rank"),
                "allowed": _map(pair.get("allowed")).get("per_game"),
                "allowed_rank": _map(pair.get("allowed")).get("rank"),
            }
            for name, pair in _map(team.get("stats")).items() if isinstance(pair, Mapping)
        }
    return out or None


def trim_nba_game(detail: Source, props: Source | None, player_id: int | None) -> tuple[JsonValue, str | None]:
    """From NbaGameDetailResponse and NbaPropsResponse, dumped with field names."""
    game_id = int(str(detail["game_id"]))
    url = game_path("nba", game_id)
    moneyline, spread, total = _map(detail.get("moneyline")), _map(detail.get("spread")), _map(detail.get("total"))
    lines: list[Row] = [
        {
            "player_id": line["player_id"], "player": line["player_name"], "team": line.get("team"),
            "market": line["market"], "odds_type": line.get("odds_type"), "line": line["line"],
            "projection": _num(line.get("projection"), 2), "gap": _num(line.get("gap"), 2),
            "p_over": _num(line.get("p_over"), 3), "flags": line.get("flags") or [],
            "last_5": [r.get("value") for r in _list(line.get("recent"))[:5]],
            "url": url, "signal": signal_for("nba", "model"),
        }
        for line in _list(_map(props).get("lines"))
    ]
    shown, note = _game_props(lines, player_id)
    data: dict[str, JsonValue] = {
        "game": {
            "game_id": game_id, "matchup": f"{detail['away_team']} @ {detail['home_team']}",
            "start": ct_label(detail.get("start_utc")), "status": detail.get("status"),
            "away_score": detail.get("away_score"), "home_score": detail.get("home_score"),
            "book": moneyline.get("book") or spread.get("book"),
            "home_moneyline": moneyline.get("home_odds"), "away_moneyline": moneyline.get("away_odds"),
            "market_home_win_probability": _num(moneyline.get("home_win_probability"), 3),
            "home_spread": spread.get("home_line"), "total": total.get("line"),
            "line_movement": [
                {"market": m.get("market"), "open": m.get("open_line"), "current": m.get("current_line")}
                for m in _list(detail.get("line_movement"))
            ],
            "url": url, "signal": signal_for("nba", "fact"),
        },
        "injuries": _nba_injuries(_map(detail.get("injury_report"))),
        "team_stats_per_game": _nba_team_stats(_map(detail.get("team_stats"))),
        "props": shown,
        "props_label": "reference projections; gap = projection minus line; P(over) shown for assists only",
    }
    return data, note


def _nfl_form(form: Source) -> JsonValue:
    recent = [
        f"{r.get('result')} {r.get('points_for')}-{r.get('points_against')} {'vs' if r.get('is_home') else 'at'} {r.get('opponent')}"
        for r in _list(form.get("recent"))
    ]
    return {"rest_days": form.get("rest_days"), "short_week": form.get("short_week"), "last_3": recent}


def _nfl_stats(stats: Source) -> JsonValue:
    return {
        name: {"value": _num(value.get("value"), 2), "rank": value.get("rank")}
        for name, value in stats.items() if isinstance(value, Mapping) and "value" in value
    }


def _nfl_line(line: Source) -> Row:
    return {
        "player_id": line["playerId"], "player": line["playerName"], "position": line.get("position"),
        "market": line["market"], "odds_type": line.get("oddsType"), "line": line.get("line"),
        "projection": _num(line.get("projection"), 2), "gap": _num(line.get("edge"), 2),
        "p_over": _num(line.get("pOver"), 3), "games_in_sample": line.get("gamesInSample"),
        "url": player_path("nfl", int(str(line["playerId"]))), "signal": signal_for("nfl", "model"),
    }


def nfl_lines(slate_game: Source) -> list[Row]:
    """Full-game lines from one stored NFL slate game (camelCase)."""
    return [_nfl_line(line) for line in _list(slate_game.get("lines")) if line.get("segment", "full_game") == "full_game"]


def trim_nfl_game(
    detail: Source, slate_game: Source | None, notes: Source | None, player_id: int | None,
) -> tuple[JsonValue, str | None]:
    """From NflGameDetailResponse (snake), the stored slate game (camelCase) and its game notes (snake)."""
    game_id = int(str(detail["game_id"]))
    slate, game_notes = _map(slate_game), _map(notes)
    odds, model = _map(slate.get("odds")), _map(slate.get("model"))
    shown, note = _game_props(nfl_lines(slate) if slate else [], player_id)
    data: dict[str, JsonValue] = {
        "game": {
            "game_id": game_id, "matchup": f"{detail['away_team']} @ {detail['home_team']}",
            "season": detail.get("season"), "week": detail.get("week"),
            "start": ct_label(detail.get("start_utc")), "status": detail.get("status"),
            "book": odds.get("book"), "home_moneyline": odds.get("homeMoneyline"),
            "away_moneyline": odds.get("awayMoneyline"), "home_spread": odds.get("homeSpread"), "total": odds.get("total"),
            "model_not_a_pick": {
                "home_spread": _num(model.get("homeSpread"), 1), "total": _num(model.get("total"), 1),
                "home_win_probability": _num(model.get("homeWinProbability"), 3),
            } if model else None,
            "line_movement": [
                {"market": m.get("market"), "open": m.get("open_line"), "current": m.get("current_line")}
                for m in _list(game_notes.get("line_movement"))
            ],
            "url": game_path("nfl", game_id), "signal": signal_for("nfl", "model" if model else "fact"),
        },
        "injuries": [
            {"player": i.get("player_name"), "team": i.get("team"), "position": i.get("position"),
             "status": i.get("injury_status"), "practice": i.get("practice_status"), "injury": i.get("injury"),
             "signal": "none"}
            for i in _list(game_notes.get("injuries"))[:MAX_INJURIES]
        ],
        "depth_changes": [
            {"player": d.get("player_name"), "team": d.get("team"), "position": d.get("depth_position"),
             "rank": d.get("depth_rank"), "previous_rank": d.get("previous_depth_rank"), "change": d.get("change")}
            for d in _list(game_notes.get("depth_changes"))[:8]
        ],
        "away_form": _nfl_form(_map(game_notes.get("away_form"))),
        "home_form": _nfl_form(_map(game_notes.get("home_form"))),
        "away_team_stats": _nfl_stats(_map(game_notes.get("away_stats"))),
        "home_team_stats": _nfl_stats(_map(game_notes.get("home_stats"))),
        "props": shown,
        "props_label": "reference projections, not picks; gap = projection minus line",
    }
    if not slate:
        note = "The stored NFL slate for this week is not available, so market, model and props are missing."
    return data, note


def trim_tennis_match(detail: Source) -> JsonValue:
    """From the tennis MatchDetail dataclass (asdict)."""
    match, meta, prediction = _map(detail.get("match")), _map(detail.get("meta")), _map(detail.get("prediction"))
    match_id = int(str(match["id"]))
    players = {}
    for side in ("p1", "p2"):
        p = _map(detail.get(side))
        players[side] = {
            "name": p.get("name"), "rank": p.get("rank"), "elo": _num(p.get("elo"), 0),
            "surface_elo": _num(p.get("elo_surface"), 0),
            "url": player_path("tennis", int(str(p["player_id"]))) if p.get("player_id") else game_path("tennis", match_id),
        }
    h2h, h2h_surface = _map(detail.get("h2h")), _map(detail.get("h2h_surface"))
    return {
        "match": {
            "game_id": match_id, "matchup": f"{players['p1']['name']} vs {players['p2']['name']}",
            "tour": detail.get("tour_label") or match.get("tour"), "tournament": match.get("tournament"),
            "round": match.get("round"), "surface": match.get("surface"), "indoor": meta.get("indoor"),
            "best_of": detail.get("best_of"), "start": ct_label(match.get("start_utc")),
            "status": match.get("status"), "score": meta.get("score"),
            "url": game_path("tennis", match_id), "signal": signal_for("tennis", "fact"),
        },
        "players": players,
        "head_to_head": f"{h2h.get('p1_wins', 0)}-{h2h.get('p2_wins', 0)}",
        "head_to_head_this_surface": f"{h2h_surface.get('p1_wins', 0)}-{h2h_surface.get('p2_wins', 0)}" if h2h_surface else None,
        "model": {
            "p1_win_probability": _num(prediction.get("p1_win_prob"), 3),
            "p1_market_probability": _num(prediction.get("p1_market_prob"), 3),
            "p1_elo_probability": _num(prediction.get("p1_elo_prob"), 3),
            "p1_moneyline": prediction.get("p1_odds_american"), "p2_moneyline": prediction.get("p2_odds_american"),
            "model_version": detail.get("model_version"), "quality_flags": prediction.get("quality_flags") or [],
            "label": "market-anchored forecast; tennis moneyline picks are off, so this is not a pick",
            "url": game_path("tennis", match_id), "signal": signal_for("tennis", "model"),
        } if prediction else None,
    }


def trim_nfl_player(detail: Source, this_week: list[Row]) -> JsonValue:
    """From NflPlayerDetailResponse (snake) and the player's lines on the stored slate."""
    player_id = int(str(detail["player_id"]))
    url = player_path("nfl", player_id)
    summary, focus = _map(detail.get("summary")), detail.get("focus_market")
    log = [
        {
            "season": g.get("season"), "week": g.get("week"), "opponent": g.get("opponent"),
            "score": f"{g.get('team_score')}-{g.get('opponent_score')}", "snap_pct": _num(g.get("snap_pct"), 2),
            str(focus): g.get(str(focus)), "line": g.get("focus_line"), "result_vs_line": g.get("focus_outcome"),
        }
        for g in _list(detail.get("game_log"))[:MAX_LOG]
    ]
    return {
        "player": {
            "player_id": player_id, "name": detail.get("name"), "position": detail.get("position"),
            "team": detail.get("team"), "depth": f"{detail.get('depth_position')}{detail.get('depth_rank')}"
            if detail.get("depth_rank") else None,
            "injury_status": detail.get("injury_status"), "injury": detail.get("injury"),
            "focus_market": focus, "games": summary.get("games"),
            "focus_per_game": _num(summary.get("focus_per_game"), 1), "snap_share": _num(summary.get("snap_share"), 2),
            "url": url, "signal": "none",
        },
        "recent_games": log,
        "past_lines_vs_break_even": [
            {"market": p.get("market"), "overs": p.get("overs"), "decided": p.get("decided")}
            for p in _list(detail.get("past_lines"))
        ],
        "past_lines_label": "anecdote, not graded evidence; see get_model_track_record",
        "this_week_lines": this_week[:MAX_GAME_PROPS],
    }


def trim_tennis_player(detail: Source, matches: Source | None) -> JsonValue:
    """From the tennis PlayerDetail and PlayerMatches dataclasses (asdict)."""
    header, elo, next_match = _map(detail.get("header")), _map(detail.get("elo")), _map(detail.get("next_match"))
    history = _list(elo.get("history"))
    log = [
        {"date": str(m.get("match_date")), "tournament": m.get("tournament"), "round": m.get("round"),
         "opponent": m.get("opponent_name"), "opponent_rank": m.get("opponent_rank"),
         "result": "W" if m.get("won") else "L", "score": m.get("score")}
        for m in (_map(entry.get("match")) for entry in _list(_map(matches).get("log"))[:MAX_LOG + 2])
    ]
    record = _map(_map(matches).get("record"))
    return {
        "player": {
            "player_id": header.get("id"), "name": header.get("name"), "tour": header.get("tour"),
            "rank": detail.get("rank"), "elo": _num(history[-1].get("overall"), 0) if history else None,
            "elo_tour_rank": elo.get("tour_rank"),
            "url": player_path("tennis", int(str(header["id"]))), "signal": "none",
        },
        "next_match": {
            "opponent": next_match.get("opponent_name"), "tournament": next_match.get("tournament"),
            "round": next_match.get("round"), "start": ct_label(next_match.get("start_utc")),
            "url": game_path("tennis", int(str(next_match["match_id"]))),
        } if next_match.get("match_id") else None,
        "recent_matches": log,
        "record_52_weeks": {
            key: f"{_map(value).get('wins', 0)}-{_map(value).get('losses', 0)}"
            for key, value in record.items() if isinstance(value, Mapping)
        },
    }


def _ranking_slices(record: Source, sport: str) -> list[Row]:
    url = model_path("nba" if sport == "nba" else "nfl")
    return [
        {
            "slice": f"{s.get('odds_type')} {s.get('side')}", "verdict": s.get("verdict"),
            "meaning": VERDICT_MEANING.get(str(s.get("verdict")), str(s.get("verdict"))),
            "picks_graded": s.get("n"), "picks_needed": _map(record.get("rule")).get("min_picks"),
            "weeks": s.get("weeks"), "hit_rate": _num(s.get("hit_rate"), 3),
            "standard_error": _num(s.get("standard_error"), 3), "break_even": _num(s.get("break_even"), 3),
            "url": url, "signal": "none",
        }
        for s in _list(record.get("slices"))
    ]


def trim_ranking_record(record: Source, sport: str, label: str) -> JsonValue:
    """From a prop RankingRecord (NBA, or one NFL model version)."""
    funnel = _map(record.get("funnel"))
    return {
        "label": label, "season": record.get("season"), "model_version": record.get("model_version"),
        "over_probability_version": record.get("over_probability_version"),
        "last_settled_week": record.get("last_settled_week"),
        "settled_calls": funnel.get("calls"), "probability_picks": funnel.get("picks"),
        "slices": _ranking_slices(record, sport),
    }


def trim_clv_record(record: Source) -> JsonValue:
    rows: list[JsonValue] = []
    for market in _list(record.get("markets")):
        headline = _map(market.get("headline"))
        rows.append({
            "market": market.get("market"), "model_version": market.get("model_version"),
            "verdict": market.get("verdict"),
            "meaning": VERDICT_MEANING.get(str(market.get("verdict")), str(market.get("verdict"))),
            "picks": headline.get("n"), "picks_needed": _map(record.get("rule")).get("verdict_picks"),
            "mean_clv_points": _num(headline.get("mean_clv"), 2), "standard_error": _num(headline.get("standard_error"), 2),
            "record_vs_entry_line": f"{headline.get('wins')}-{headline.get('losses')}-{headline.get('pushes')}",
            "url": model_path("nfl"), "signal": "none",
        })
    return {"label": "NFL game-line closing-line value (does the close move toward the model?)", "markets": rows}


def trim_tennis_grading(predictions: Source | None, tiers: Source | None) -> JsonValue:
    """From the tennis PredictionGrading and TierGrading dataclasses (asdict)."""
    groups: list[JsonValue] = []
    for group in _list(_map(predictions).get("groups")):
        ensemble = next((c for c in _list(group.get("components")) if c.get("name") == "ensemble"), None)
        if ensemble is None:
            continue
        versus = _map(ensemble.get("vs_market"))
        groups.append({
            "group": group.get("group"), "matches": group.get("n"),
            "log_loss_vs_market": _num(versus.get("mean"), 4), "standard_error": _num(versus.get("standard_error"), 4),
            "url": model_path("tennis"), "signal": "none",
        })
    tier_grading = _map(tiers)
    tier_rows: list[JsonValue] = [
        {
            "tier": t.get("tier"), "verdict": t.get("verdict"),
            "meaning": VERDICT_MEANING.get(str(t.get("verdict")), str(t.get("verdict"))),
            "decided": t.get("decided"), "hit_rate": _num(t.get("hit_rate"), 3),
            "standard_error": _num(t.get("standard_error"), 3), "verdict_sample_needed": tier_grading.get("verdict_sample"),
            "url": model_path("tennis"), "signal": "none",
        }
        for t in _list(tier_grading.get("tiers"))
    ]
    return {
        "model_version": _map(predictions).get("model_version"),
        "ensemble_vs_market": groups,
        "ensemble_vs_market_label": "log loss minus the de-vigged market's; above zero means worse than the market",
        "prop_tiers": tier_rows,
        "prop_tiers_label": (
            f"retired PrizePicks tier record ({tier_grading.get('projection_version')}), history only: "
            "tennis props carry no tier since 2026-10-28 and are rated by P(over) against break-even"
        ),
        "prop_tier_break_even": _num(tier_grading.get("break_even"), 3),
    }


def first_matching(rows: Sequence[Source], key: str, value: int) -> Source | None:
    return next((row for row in rows if row.get(key) == value), None)
