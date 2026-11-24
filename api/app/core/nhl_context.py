"""Validate ESPN NHL context without I/O; source IDs remain separate from NHL IDs."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Literal, TypedDict, cast
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo


# Verified against ESPN's NHL team directory on 2026-10-24.
ESPN_NHL_TEAMS = {
    "1": "BOS", "2": "BUF", "3": "CGY", "4": "CHI", "5": "DET", "6": "EDM",
    "7": "CAR", "8": "LAK", "9": "DAL", "10": "MTL", "11": "NJD", "12": "NYI",
    "13": "NYR", "14": "OTT", "15": "PHI", "16": "PIT", "17": "COL", "18": "SJS",
    "19": "STL", "20": "TBL", "21": "TOR", "22": "VAN", "23": "WSH", "25": "ANA",
    "26": "FLA", "27": "NSH", "28": "WPG", "29": "CBJ", "30": "MIN", "37": "VGK",
    "124292": "SEA", "129764": "UTA",
}
_TEAM_ALIASES = {"LA": "LAK", "NJ": "NJD", "SJ": "SJS", "TB": "TBL", "UTAH": "UTA"}
_ATHLETE_PATH = re.compile(r"/nhl/player/(?:[a-z]+/)?_/id/([1-9][0-9]*)(?:/|$)")
EASTERN = ZoneInfo("America/New_York")
GoalieStatus = Literal["expected", "confirmed", "unknown", "not_reported"]


@dataclass(frozen=True)
class NhlInjuryEntry:
    espn_team_id: str
    team_code: str
    espn_athlete_id: str
    player_name: str
    status: str
    detail: str | None
    source_updated_at: datetime | None
    return_date: str | None
    athlete_team_id: str | None

    @property
    def team_mismatch(self) -> bool:
        return self.athlete_team_id is not None and self.athlete_team_id != self.espn_team_id


@dataclass(frozen=True)
class NhlInjuryFeed:
    source_timestamp: datetime
    injuries: tuple[NhlInjuryEntry, ...]


@dataclass(frozen=True)
class NhlGoalieObservation:
    espn_event_id: str
    event_date: date
    start_utc: datetime
    time_valid: bool
    home_team: str
    away_team: str
    espn_team_id: str
    team_code: str
    espn_athlete_id: str | None
    player_name: str | None
    status: GoalieStatus
    raw_status: str | None
    athlete_team_id: str | None
    source_position: str | None

    @property
    def team_mismatch(self) -> bool:
        return self.athlete_team_id is not None and self.athlete_team_id != self.espn_team_id


@dataclass(frozen=True)
class NhlGoalieFeed:
    scope_date: date
    source_timestamp: datetime | None
    observations: tuple[NhlGoalieObservation, ...]


class _GoalieFields(TypedDict):
    espn_athlete_id: str | None
    player_name: str | None
    status: GoalieStatus
    raw_status: str | None
    athlete_team_id: str | None
    source_position: str | None


def espn_nhl_team_code(code: str | None) -> str | None:
    if not code or not code.strip():
        return None
    upper = code.strip().upper()
    return _TEAM_ALIASES.get(upper, upper)


def _object(value: object, field: str) -> dict[str, object]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        raise ValueError(f"{field} must be an object")
    return cast(dict[str, object], value)


def _list(value: object, field: str) -> list[object]:
    if not isinstance(value, list):
        raise ValueError(f"{field} must be a list")
    return cast(list[object], value)


def _text(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text")
    return value.strip() or None


def _required_text(value: object, field: str) -> str:
    text = _text(value, field)
    if text is None:
        raise ValueError(f"{field} is required")
    return text


def _id(value: object, field: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError(f"{field} must be a positive ESPN id")
    text = str(value)
    if not re.fullmatch(r"[1-9][0-9]*", text):
        raise ValueError(f"{field} must be a positive ESPN id")
    return text


def _timestamp(value: object, field: str) -> datetime | None:
    text = _text(value, field)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be an aware ISO timestamp") from exc
    if parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an aware ISO timestamp")
    return parsed.astimezone(timezone.utc)


def _team_id(value: object) -> str:
    team = _object(value, "athlete.team")
    team_id = _id(team.get("id"), "athlete.team.id")
    if team_id not in ESPN_NHL_TEAMS:
        raise ValueError("unknown ESPN NHL team id")
    if "abbreviation" in team:
        code = _required_text(team["abbreviation"], "team.abbreviation")
        if espn_nhl_team_code(code) != ESPN_NHL_TEAMS[team_id]:
            raise ValueError("ESPN NHL team id/code disagree")
    return team_id


def _athlete_id(athlete: dict[str, object]) -> str:
    ids: set[str] = set()
    if athlete.get("id") is not None:
        ids.add(_id(athlete["id"], "athlete.id"))
    for value in _list(athlete.get("links", []), "athlete.links"):
        link = _object(value, "athlete link")
        href = _text(link.get("href"), "athlete link href")
        if not href:
            continue
        url = urlsplit(href)
        if url.scheme not in {"http", "https"} or url.hostname not in {"espn.com", "www.espn.com"}:
            continue
        match = _ATHLETE_PATH.match(url.path)
        if match:
            ids.add(match[1])
    if len(ids) != 1:
        raise ValueError("athlete must have one unambiguous ESPN NHL id")
    return ids.pop()


def _detail(entry: dict[str, object], details: dict[str, object]) -> str | None:
    parts = [_text(details.get(key), f"details.{key}") for key in ("side", "type", "detail")]
    body = " ".join(part for part in parts if part and part != "Not Specified")
    comment = _text(entry.get("shortComment"), "shortComment")
    return ". ".join(part for part in (body, comment) if part) or None


def _injury(value: object, team_id: str) -> NhlInjuryEntry:
    entry = _object(value, "injury")
    athlete = _object(entry.get("athlete"), "athlete")
    details_value = entry.get("details")
    details = _object(details_value if details_value is not None else {}, "details")
    return NhlInjuryEntry(
        espn_team_id=team_id, team_code=ESPN_NHL_TEAMS[team_id],
        espn_athlete_id=_athlete_id(athlete),
        player_name=_required_text(athlete.get("displayName"), "athlete.displayName"),
        status=_required_text(entry.get("status"), "injury.status"),
        detail=_detail(entry, details),
        source_updated_at=_timestamp(entry.get("date"), "injury.date"),
        return_date=_text(details.get("returnDate"), "details.returnDate"),
        athlete_team_id=_team_id(athlete["team"]) if athlete.get("team") is not None else None,
    )


def parse_injury_feed(payload: object) -> NhlInjuryFeed:
    """Reject malformed batches so missing records cannot clear an older report."""
    root = _object(payload, "feed")
    if root.get("status") != "success":
        raise ValueError("injury feed did not report success")
    timestamp = _timestamp(root.get("timestamp"), "feed.timestamp")
    if timestamp is None:
        raise ValueError("feed.timestamp is required")
    entries: dict[tuple[str, str], NhlInjuryEntry] = {}
    for value in _list(root.get("injuries"), "feed.injuries"):
        group = _object(value, "injury team group")
        team_id = _id(group.get("id"), "injury team group id")
        if team_id not in ESPN_NHL_TEAMS:
            raise ValueError("unknown ESPN NHL injury team group")
        for item in _list(group.get("injuries"), "team injuries"):
            injury = _injury(item, team_id)
            key = (team_id, injury.espn_athlete_id)
            if key in entries and entries[key] != injury:
                raise ValueError("conflicting duplicate NHL injury")
            entries[key] = injury
    return NhlInjuryFeed(timestamp, tuple(entries.values()))


def _goalie_status(value: object) -> tuple[str, GoalieStatus]:
    status = _object(value, "probable.status")
    name = _required_text(status.get("name"), "probable.status.name")
    kind = _text(status.get("type"), "probable.status.type")
    normalized: GoalieStatus = "unknown"
    # Conflicting labels must never upgrade an announcement to Confirmed.
    if name == "Expected" and kind in (None, "expected"):
        normalized = "expected"
    elif name == "Confirmed" and kind in (None, "confirmed"):
        normalized = "confirmed"
    return name, normalized


def _goalie_fields(competitor: dict[str, object]) -> _GoalieFields:
    probables = _list(competitor.get("probables", []), "competitor.probables")
    found: _GoalieFields | None = None
    for value in probables:
        probable = _object(value, "probable")
        if _required_text(probable.get("name"), "probable.name") != "probableStartingGoalie":
            continue
        athlete = _object(probable.get("athlete"), "probable.athlete")
        athlete_id = _athlete_id(athlete)
        if "playerId" in probable and _id(probable["playerId"], "probable.playerId") != athlete_id:
            raise ValueError("probable playerId and athlete id disagree")
        raw, status = _goalie_status(probable.get("status"))
        fields: _GoalieFields = {
            "espn_athlete_id": athlete_id,
            "player_name": _required_text(athlete.get("displayName"), "athlete.displayName"),
            "status": status, "raw_status": raw,
            "athlete_team_id": _team_id(athlete["team"]) if athlete.get("team") is not None else None,
            "source_position": _text(athlete.get("position"), "athlete.position"),
        }
        if found is not None and found != fields:
            raise ValueError("conflicting duplicate starting goalie")
        found = fields
    return found or {
        "espn_athlete_id": None, "player_name": None, "status": "not_reported",
        "raw_status": None, "athlete_team_id": None, "source_position": None,
    }


def _competitors(competition: dict[str, object]) -> dict[str, dict[str, object]]:
    sides: dict[str, dict[str, object]] = {}
    for value in _list(competition.get("competitors"), "competition.competitors"):
        competitor = _object(value, "competitor")
        side = _required_text(competitor.get("homeAway"), "competitor.homeAway")
        if side not in ("home", "away") or side in sides:
            raise ValueError("competition must have one home and one away competitor")
        team_id = _team_id(competitor.get("team"))
        if _id(competitor.get("id"), "competitor.id") != team_id:
            raise ValueError("competitor id and team id disagree")
        sides[side] = competitor
    if set(sides) != {"home", "away"}:
        raise ValueError("competition must have two competitors")
    if sides["home"]["id"] == sides["away"]["id"]:
        raise ValueError("competition cannot contain the same team twice")
    return sides


def _event_goalies(event: dict[str, object], scope_date: date) -> tuple[NhlGoalieObservation, ...]:
    event_id = _id(event.get("id"), "event.id")
    start = _timestamp(event.get("date"), "event.date")
    if start is None or start.astimezone(EASTERN).date() != scope_date:
        raise ValueError("scoreboard event does not belong to the requested Eastern date")
    season = _object(event.get("season"), "event.season")
    season_type = season.get("type")
    if isinstance(season_type, bool) or not isinstance(season_type, int) or season_type not in (1, 2, 3):
        raise ValueError("unknown ESPN NHL season type")
    competitions = _list(event.get("competitions"), "event.competitions")
    if len(competitions) != 1:
        raise ValueError("NHL event must contain exactly one competition")
    competition = _object(competitions[0], "competition")
    if _id(competition.get("id"), "competition.id") != event_id:
        raise ValueError("competition id and event id disagree")
    if _timestamp(competition.get("date"), "competition.date") != start:
        raise ValueError("competition and event start disagree")
    time_valid = competition.get("timeValid")
    if not isinstance(time_valid, bool):
        raise ValueError("competition.timeValid must be boolean")
    sides = _competitors(competition)
    home, away = (ESPN_NHL_TEAMS[_team_id(sides[side]["team"])] for side in ("home", "away"))
    if home == away:
        raise ValueError("competition cannot contain the same team twice")
    rows = []
    for competitor in sides.values():
        team_id = _team_id(competitor["team"])
        rows.append(NhlGoalieObservation(
            espn_event_id=event_id, event_date=scope_date, start_utc=start, time_valid=time_valid,
            home_team=home, away_team=away, espn_team_id=team_id, team_code=ESPN_NHL_TEAMS[team_id],
            **_goalie_fields(competitor),
        ))
    return () if season_type == 1 else tuple(rows)


def parse_goalie_feed(payload: object, scope_date: date, *, request_limit: int = 100) -> NhlGoalieFeed:
    """Parse one requested Eastern date, rejecting detectable partial responses."""
    if isinstance(request_limit, bool) or not isinstance(request_limit, int) or request_limit < 1:
        raise ValueError("scoreboard request limit must be a positive integer")
    root = _object(payload, "scoreboard")
    leagues = _list(root.get("leagues"), "scoreboard.leagues")
    if len(leagues) != 1:
        raise ValueError("scoreboard must identify the NHL league")
    league = _object(leagues[0], "scoreboard league")
    if _id(league.get("id"), "league.id") != "90" or league.get("slug") != "nhl":
        raise ValueError("scoreboard league is not NHL")
    events = _list(root.get("events"), "scoreboard.events")
    if len(events) >= request_limit:
        raise ValueError("scoreboard reached request limit; coverage may be truncated")
    entries: dict[tuple[str, str], NhlGoalieObservation] = {}
    event_rows: dict[str, tuple[NhlGoalieObservation, ...]] = {}
    for value in events:
        event = _object(value, "event")
        event_id = _id(event.get("id"), "event.id")
        rows = _event_goalies(event, scope_date)
        ordered = tuple(sorted(rows, key=lambda row: row.espn_team_id))
        if event_id in event_rows and event_rows[event_id] != ordered:
            raise ValueError("conflicting duplicate scoreboard event")
        event_rows[event_id] = ordered
        for row in rows:
            entries[(row.espn_event_id, row.espn_team_id)] = row
    return NhlGoalieFeed(
        scope_date, _timestamp(root.get("timestamp"), "scoreboard.timestamp"), tuple(entries.values()),
    )
