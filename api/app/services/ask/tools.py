"""Ask Lineform tool executors (47a). Each calls the same service as the page it
cites, trims the response in `app.core.ask_results`, and returns a ToolResult.
Missing data is a `note` on the result, never an exception, so the model can
say what is not covered."""
from __future__ import annotations

import datetime as dt
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from zoneinfo import ZoneInfo

from pydantic import JsonValue, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ask_detail import (
    first_matching,
    nfl_lines,
    trim_clv_record,
    trim_nba_game,
    trim_nfl_game,
    trim_nfl_player,
    trim_ranking_record,
    trim_tennis_grading,
    trim_tennis_match,
    trim_tennis_player,
)
from app.core.ask_find import Candidate, match_candidates
from app.core.ask_links import AskSport, game_path, model_path, player_path, slate_path
from app.core.ask_results import (
    Row,
    trim_nba_gaps,
    trim_nba_slate,
    trim_nfl_slate,
    trim_tennis_picks,
    trim_tennis_slate,
)
from app.ml.registry import ModelRegistry
from app.repositories import nba as nba_repo
from app.repositories import nfl as nfl_repo
from app.core.nfl_targets_projection import NFL_TARGETS_MODEL_VERSION
from app.schemas.ask import (
    FindInput,
    GetGameDetailInput,
    GetModelTrackRecordInput,
    GetPlayerInput,
    GetSlateInput,
    GetTopPropsInput,
    TOOL_INPUTS,
    ToolResult,
    tool_definitions,
)
from app.services.nba import track_record as nba_track_record
from app.services.nba.game_detail import build_game_detail as build_nba_game
from app.services.nba.props import build_props as build_nba_props
from app.services.nba.slate import build_slate as build_nba_slate
from app.services.nba.slate_gaps import build_slate_gaps
from app.services.nfl import track_record as nfl_track_record
from app.services.nfl.game_detail import build_game_detail as build_nfl_game
from app.services.nfl.game_notes import build_game_notes
from app.services.nfl.player_detail import build_player_detail as build_nfl_player
from app.services.nfl.slate_cache import cached_slate_json
from app.services.tennis import track_record as tennis_track_record
from app.services.tennis.best_picks_response import PredictionsUnavailable, best_picks_for, slate_predictions
from app.services.tennis.match_detail import build_match_detail
from app.services.tennis.player_detail import build_player_detail as build_tennis_player
from app.services.tennis.player_detail import build_player_matches

EASTERN = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class ToolContext:
    db: AsyncSession
    registry: ModelRegistry | None
    now: dt.datetime
    production: bool

    @property
    def nba_today(self) -> dt.date:
        return self.now.astimezone(EASTERN).date()


def _result(
    tool: str, sport: str, url: str | None, ctx: ToolContext,
    data: JsonValue = None, note: str | None = None, truncated: bool = False,
) -> ToolResult:
    if truncated and note is None:
        note = "More rows exist than shown; narrow the request (a tour, market or date) to see others."
    return ToolResult(tool=tool, sport=sport, url=url, as_of=ctx.now, note=note, truncated=truncated, data=data)


async def _nfl_slate(ctx: ToolContext, week: int | None) -> tuple[int, int, list[dict[str, object]]] | None:
    """(season, week, games) from the stored slate; production never builds one on request."""
    current = await nfl_repo.get_current_week(ctx.db, ctx.now)
    if current is None:
        return None
    season, current_week = current
    week = week or current_week
    return season, week, await _nfl_week_games(ctx, season, week)


async def _nfl_week_games(ctx: ToolContext, season: int, week: int) -> list[dict[str, object]]:
    body = await cached_slate_json(ctx.db, season, week, ctx.production)
    return [] if body is None else json.loads(body)["games"]


async def _tennis_predictions(ctx: ToolContext, date: dt.date | None) -> list[dict[str, object]] | None:
    if ctx.registry is None:
        return None
    try:
        predictions = await slate_predictions(ctx.db, ctx.registry, date, dt.date.today())
    except PredictionsUnavailable:
        return None
    return [asdict(p) for p in predictions]


async def get_slate(inp: GetSlateInput, ctx: ToolContext) -> ToolResult:
    if inp.sport == "nba":
        slate = await build_nba_slate(ctx.db, inp.date, ctx.nba_today)
        rows, truncated = trim_nba_slate([g.model_dump(mode="json") for g in slate.games])
        note = None if rows else f"No NBA games on {slate.date}."
        return _result("get_slate", "nba", slate_path("nba", date=slate.date), ctx, rows, note, truncated)
    if inp.sport == "nfl":
        loaded = await _nfl_slate(ctx, inp.week)
        if loaded is None:
            return _result("get_slate", "nfl", slate_path("nfl"), ctx, [], "No NFL regular-season games are loaded.")
        season, week, games = loaded
        rows, truncated = trim_nfl_slate(games)
        note = None if rows else f"The NFL slate for {season} week {week} is not available yet."
        return _result("get_slate", "nfl", slate_path("nfl", season=season, week=week), ctx, rows, note, truncated)
    predictions = await _tennis_predictions(ctx, inp.date)
    if predictions is None:
        return _result("get_slate", "tennis", slate_path("tennis"), ctx, [], "Tennis predictions are unavailable right now.")
    if inp.tour:
        predictions = [p for p in predictions if str(p["tour"]).upper() == inp.tour]
    rows, truncated = trim_tennis_slate(predictions, ctx.now)
    note = None if rows else "No tennis matches found for that day."
    return _result("get_slate", "tennis", slate_path("tennis"), ctx, rows, note, truncated)


async def get_top_props(inp: GetTopPropsInput, ctx: ToolContext) -> ToolResult:
    if inp.sport == "nba":
        date = inp.date or ctx.nba_today
        # One extra row tells the trimmer whether more exist.
        gaps = await build_slate_gaps(ctx.db, date, ctx.now, inp.market, inp.limit + 1)
        rows, truncated = trim_nba_gaps([i.model_dump(mode="json") for i in gaps.items], inp.limit)
        note = None if rows else f"No upcoming NBA modelled lines on {date} (games may have tipped or lines not posted)."
        return _result("get_top_props", "nba", slate_path("nba", date=date), ctx, rows, note, truncated)
    picks = await best_picks_for(ctx.db, ctx.registry, inp.date, dt.date.today()) if ctx.registry else None
    if picks is None:
        return _result("get_top_props", "tennis", slate_path("tennis"), ctx, [], "Tennis picks are unavailable right now.")
    rows, truncated = trim_tennis_picks(
        [m.model_dump(mode="json") for m in picks.matches], inp.market, inp.limit, ctx.now
    )
    note = None if rows else "No upcoming tennis picks match that request."
    return _result("get_top_props", "tennis", slate_path("tennis"), ctx, rows, note, truncated)


def _team_and_game_candidates(sport: AskSport, games: Sequence[Row]) -> list[Candidate]:
    candidates: list[Candidate] = []
    for game in games:
        game_id = int(str(game["game_id"]))
        url = game_path(sport, game_id)
        candidates.append(Candidate("game", str(game["matchup"]), url, game_id, game_id))
        for team in str(game["matchup"]).split(" @ "):
            candidates.append(Candidate("team", team, url, None, game_id))
    return candidates


async def _nba_roster_candidates(ctx: ToolContext, games: Sequence[Row]) -> list[Candidate]:
    """Full team names, and every rostered player, so a player with no posted line still reaches the game."""
    candidates: list[Candidate] = []
    team_games: dict[str, int] = {}
    for game in games:
        game_id = int(str(game["game_id"]))
        for side in ("away", "home"):
            team_games[str(game[f"{side}_team"])] = game_id
            candidates.append(Candidate("team", str(game[f"{side}_team_name"]), game_path("nba", game_id), None, game_id))
    for player in await nba_repo.get_team_players(ctx.db, list(team_games)):
        game_id = team_games[str(player["team"])]
        candidates.append(
            Candidate("player", str(player["player_name"]), game_path("nba", game_id), int(str(player["player_id"])), game_id)
        )
    return candidates


async def _find_candidates(inp: FindInput, ctx: ToolContext) -> tuple[list[Candidate], str]:
    if inp.sport == "nba":
        date = inp.date or ctx.nba_today
        slate = await build_nba_slate(ctx.db, date, ctx.nba_today)
        games = [g.model_dump(mode="json") for g in slate.games]
        rows, _ = trim_nba_slate(games)
        candidates = _team_and_game_candidates("nba", rows)
        candidates += await _nba_roster_candidates(ctx, games)
        for game_id, lines in (await nba_repo.get_date_modelled_lines(ctx.db, slate.date)).items():
            candidates += [
                Candidate("player", str(line["player_name"]), game_path("nba", game_id), int(str(line["player_id"])), game_id)
                for line in lines
            ]
        return candidates, slate_path("nba", date=slate.date)
    if inp.sport == "nfl":
        loaded = await _nfl_slate(ctx, inp.week)
        if loaded is None:
            return [], slate_path("nfl")
        season, week, games = loaded
        rows, _ = trim_nfl_slate(games)
        candidates = _team_and_game_candidates("nfl", rows)
        for game in games:
            lines = game.get("lines")
            candidates += [
                Candidate("player", str(line["playerName"]), player_path("nfl", int(str(line["playerId"]))),
                          int(str(line["playerId"])), int(str(game["gameId"])))
                for line in (lines if isinstance(lines, list) else []) if isinstance(line, dict)
            ]
        return candidates, slate_path("nfl", season=season, week=week)
    candidates: list[Candidate] = []
    for p in await _tennis_predictions(ctx, inp.date) or []:
        match_id = int(str(p["match_id"]))
        url = game_path("tennis", match_id)
        candidates.append(Candidate("game", f"{p['p1_name']} vs {p['p2_name']}", url, match_id, match_id))
        for side in ("p1", "p2"):
            player_id = p.get(f"{side}_id")
            player_url = player_path("tennis", int(str(player_id))) if player_id is not None else url
            entity = int(str(player_id)) if player_id is not None else None
            candidates.append(Candidate("player", str(p[f"{side}_name"]), player_url, entity, match_id))
        if p.get("tournament"):
            candidates.append(Candidate("tournament", str(p["tournament"]), slate_path("tennis"), None, match_id))
    return candidates, slate_path("tennis")


async def find(inp: FindInput, ctx: ToolContext) -> ToolResult:
    candidates, url = await _find_candidates(inp, ctx)
    matches = match_candidates(inp.query, candidates)
    rows: list[Row] = [
        {"kind": c.kind, "name": c.name, "id": c.entity_id, "game_id": c.game_id, "url": c.url, "signal": "none"}
        for c in matches
    ]
    note = None
    if not rows:
        note = f"Nothing named {inp.query!r} on this {inp.sport} slate. It may play on another day or week."
    elif len(rows) > 1:
        note = "Several matches; pick the one the user means, or ask them."
    return _result("find", inp.sport, url, ctx, rows, note)


def _not_found(tool: str, sport: str, what: str, ctx: ToolContext) -> ToolResult:
    return _result(tool, sport, None, ctx, None, f"not_found: no {sport} {what} with that id")


def _plain(obj: object) -> dict[str, JsonValue]:
    """A dataclass as JSON-ready values (dates and datetimes become strings)."""
    return json.loads(json.dumps(asdict(obj), default=str))


async def get_game_detail(inp: GetGameDetailInput, ctx: ToolContext) -> ToolResult:
    url = game_path(inp.sport, inp.game_id)
    if inp.sport == "nba":
        detail = await build_nba_game(ctx.db, inp.game_id)
        if detail is None:
            return _not_found("get_game_detail", "nba", "game", ctx)
        props = await build_nba_props(ctx.db, inp.game_id)
        data, note = trim_nba_game(
            detail.model_dump(mode="json"), props.model_dump(mode="json") if props else None, inp.player_id
        )
        return _result("get_game_detail", "nba", url, ctx, data, note)
    if inp.sport == "nfl":
        detail = await build_nfl_game(ctx.db, inp.game_id)
        if detail is None:
            return _not_found("get_game_detail", "nfl", "game", ctx)
        games = await _nfl_week_games(ctx, detail.season, detail.week)
        notes = await build_game_notes(ctx.db, detail.season, detail.week)
        data, note = trim_nfl_game(
            detail.model_dump(mode="json"),
            first_matching(games, "gameId", inp.game_id),
            first_matching([g.model_dump(mode="json") for g in notes.games], "game_id", inp.game_id),
            inp.player_id,
        )
        return _result("get_game_detail", "nfl", url, ctx, data, note)
    if ctx.registry is None:
        return _result("get_game_detail", "tennis", url, ctx, None, "Tennis match detail is unavailable right now.")
    match = await build_match_detail(ctx.db, ctx.registry, inp.game_id, dt.date.today())
    if match is None:
        return _not_found("get_game_detail", "tennis", "match", ctx)
    return _result("get_game_detail", "tennis", url, ctx, trim_tennis_match(_plain(match)))


async def get_player(inp: GetPlayerInput, ctx: ToolContext) -> ToolResult:
    url = player_path(inp.sport, inp.player_id)
    if inp.sport == "nfl":
        detail = await build_nfl_player(ctx.db, inp.player_id, ctx.now)
        if detail is None:
            return _not_found("get_player", "nfl", "player", ctx)
        games = await _nfl_week_games(ctx, detail.season, detail.week)
        this_week = [line for game in games for line in nfl_lines(game) if line["player_id"] == inp.player_id]
        return _result("get_player", "nfl", url, ctx, trim_nfl_player(detail.model_dump(mode="json"), this_week))
    today = dt.date.today()
    detail = await build_tennis_player(ctx.db, inp.player_id, today)
    if detail is None:
        return _not_found("get_player", "tennis", "player", ctx)
    matches = await build_player_matches(ctx.db, inp.player_id, 8, today)
    data = trim_tennis_player(_plain(detail), _plain(matches) if matches else None)
    return _result("get_player", "tennis", url, ctx, data)


UNAVAILABLE_RECORD = "The track record is being computed or failed; try again shortly."


async def _nba_record(inp: GetModelTrackRecordInput, ctx: ToolContext) -> ToolResult:
    url = model_path("nba")
    season = inp.season or await nba_track_record.nba_season(ctx.db, ctx.now)
    record = await nba_track_record.get_ranking_record(ctx.db, season) if season else None
    if record is None:
        return _result("get_model_track_record", "nba", url, ctx, None, UNAVAILABLE_RECORD)
    data = trim_ranking_record(_plain(record), "nba", "NBA forward ranking check (frozen pre-tip predictions)")
    return _result("get_model_track_record", "nba", url, ctx, data)


async def _nfl_record(inp: GetModelTrackRecordInput, ctx: ToolContext) -> ToolResult:
    url = model_path("nfl")
    current = await nfl_repo.get_current_week(ctx.db, ctx.now)
    season = inp.season or (current[0] if current else None)
    if season is None:
        return _result("get_model_track_record", "nfl", url, ctx, None, "No NFL season is loaded.")
    v4 = await nfl_track_record.get_ranking_record(ctx.db, season)
    targets = await nfl_track_record.get_ranking_record(ctx.db, season, NFL_TARGETS_MODEL_VERSION)
    clv = await nfl_track_record.get_clv_record(ctx.db, season)
    data: dict[str, JsonValue] = {
        "prop_ranking": trim_ranking_record(_plain(v4), "nfl", "NFL prop ranking check (nine v4 markets)") if v4 else None,
        "rec_targets_ranking": trim_ranking_record(
            _plain(targets), "nfl", "NFL Rec Targets, graded separately; no P(over), so no probability picks"
        ) if targets else None,
        "game_line_clv": trim_clv_record(_plain(clv)) if clv else None,
    }
    return _result("get_model_track_record", "nfl", url, ctx, data, None if v4 and clv else UNAVAILABLE_RECORD)


async def _tennis_record(inp: GetModelTrackRecordInput, ctx: ToolContext) -> ToolResult:
    predictions = await tennis_track_record.get_prediction_grading(ctx.db)
    tiers = await tennis_track_record.get_tier_grading(ctx.db)
    data = trim_tennis_grading(_plain(predictions) if predictions else None, _plain(tiers) if tiers else None)
    note = "Tennis grading covers every season; the season input is ignored." if inp.season else None
    if predictions is None or tiers is None:
        note = UNAVAILABLE_RECORD
    return _result("get_model_track_record", "tennis", model_path("tennis"), ctx, data, note)


async def get_model_track_record(inp: GetModelTrackRecordInput, ctx: ToolContext) -> ToolResult:
    if inp.sport == "nba":
        return await _nba_record(inp, ctx)
    if inp.sport == "nfl":
        return await _nfl_record(inp, ctx)
    return await _tennis_record(inp, ctx)


EXECUTORS: dict[str, Callable[..., Awaitable[ToolResult]]] = {
    "get_slate": get_slate,
    "get_top_props": get_top_props,
    "get_game_detail": get_game_detail,
    "get_player": get_player,
    "get_model_track_record": get_model_track_record,
    "find": find,
}

# The Messages API `tools` list, built once so every request sends identical bytes.
TOOLS = tool_definitions()


class UnknownToolError(Exception):
    """The model asked for a tool that does not exist."""


class ToolInputError(Exception):
    """The model's arguments failed validation; the message is written for the model."""


def validation_message(tool: str, error: ValidationError) -> str:
    """'get_slate: week applies to nfl only; ...' rather than pydantic's full report,
    which echoes the input back and links to its docs."""
    parts = []
    for issue in error.errors():
        message = str(issue["msg"]).removeprefix("Value error, ")
        field = ".".join(str(part) for part in issue["loc"])
        parts.append(f"{field}: {message}" if field else message)
    return f"{tool}: " + "; ".join(parts)


async def run_tool(name: str, raw_input: Mapping[str, object], ctx: ToolContext) -> ToolResult:
    """Validate and run one tool call. Raises UnknownToolError or ToolInputError,
    which the loop turns into an is_error tool_result the model can correct."""
    if name not in EXECUTORS:
        raise UnknownToolError(f"unknown tool {name!r}; available: {', '.join(EXECUTORS)}")
    try:
        inp = TOOL_INPUTS[name].model_validate(raw_input)
    except ValidationError as error:
        raise ToolInputError(validation_message(name, error)) from error
    return await EXECUTORS[name](inp, ctx)
