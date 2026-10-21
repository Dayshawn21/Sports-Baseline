"""Validate ESPN's current NBA injury feed without I/O (42c)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal, cast
from urllib.parse import urlsplit


# Verified against ESPN's NBA team directory; injury groups omit healthy teams.
ESPN_NBA_TEAMS = dict(zip(
    map(str, range(1, 31)),
    ("ATL", "BOS", "NO", "CHI", "CLE", "DAL", "DEN", "DET", "GS", "HOU",
     "IND", "LAC", "LAL", "MIA", "MIL", "MIN", "BKN", "NY", "ORL", "PHI",
     "PHX", "POR", "SAC", "SA", "OKC", "UTAH", "WSH", "TOR", "MEM", "CHA"),
))
_ATHLETE_PATH = re.compile(r"/nba/player/(?:[a-z]+/)?_/id/([1-9][0-9]*)(?:/|$)")


@dataclass(frozen=True)
class NbaInjuryEntry:
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
class NbaInjuryFeed:
    source_timestamp: datetime
    injuries: tuple[NbaInjuryEntry, ...]


@dataclass(frozen=True)
class LinkedNbaInjury:
    injury: NbaInjuryEntry
    player_id: int | None


@dataclass(frozen=True)
class NbaInjurySnapshot:
    fetched_at: datetime
    injuries: tuple[LinkedNbaInjury, ...]


def injury_freshness(
    fetched_at: datetime | None, start_utc: datetime | None, as_of: datetime,
) -> Literal["fresh", "stale", "unavailable"]:
    times = [time for time in (fetched_at, start_utc, as_of) if time is not None]
    if any(time.utcoffset() is None for time in times):
        raise ValueError("Injury context requires timezone-aware timestamps")
    if fetched_at is None or start_utc is None or fetched_at >= start_utc or fetched_at > as_of:
        return "unavailable"
    return "stale" if min(as_of, start_utc) - fetched_at > timedelta(hours=6) else "fresh"


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
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be an aware ISO timestamp")
    return parsed.astimezone(timezone.utc)


def _athlete_id(athlete: dict[str, object]) -> str:
    ids = set()
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
        raise ValueError("athlete must have one unambiguous ESPN NBA id")
    return ids.pop()


def _team(value: object) -> tuple[str, str]:
    team = _object(value, "athlete.team")
    team_id = _id(team.get("id"), "athlete.team.id")
    code = ESPN_NBA_TEAMS.get(team_id)
    if code is None or team.get("abbreviation") != code:
        raise ValueError("athlete.team id/code is not a verified NBA team")
    return team_id, code


def _detail(entry: dict[str, object], details: dict[str, object]) -> str | None:
    parts = [_text(details.get(key), f"details.{key}") for key in ("side", "type", "detail")]
    body = " ".join(part for part in parts if part and part != "Not Specified")
    comment = _text(entry.get("shortComment"), "shortComment")
    return ". ".join(part for part in (body, comment) if part) or None


def _entry(value: object, team_id: str) -> NbaInjuryEntry:
    entry = _object(value, "injury")
    athlete = _object(entry.get("athlete"), "athlete")
    details_value = entry.get("details")
    details = _object(details_value if details_value is not None else {}, "details")
    athlete_team_id = _team(athlete["team"])[0] if athlete.get("team") is not None else None
    return NbaInjuryEntry(
        espn_team_id=team_id, team_code=ESPN_NBA_TEAMS[team_id],
        espn_athlete_id=_athlete_id(athlete),
        player_name=_required_text(athlete.get("displayName"), "athlete.displayName"),
        status=_required_text(entry.get("status"), "injury.status"),
        detail=_detail(entry, details),
        source_updated_at=_timestamp(entry.get("date"), "injury.date"),
        return_date=_text(details.get("returnDate"), "details.returnDate"),
        athlete_team_id=athlete_team_id,
    )


def parse_injury_feed(payload: object) -> NbaInjuryFeed:
    """Fail the whole snapshot on malformed data; absence is meaningful only on success."""
    root = _object(payload, "feed")
    if root.get("status") != "success":
        raise ValueError("injury feed did not report success")
    timestamp = _timestamp(root.get("timestamp"), "feed.timestamp")
    if timestamp is None:
        raise ValueError("feed.timestamp is required")
    groups = _list(root.get("injuries"), "feed.injuries")
    entries: dict[tuple[str, str], NbaInjuryEntry] = {}
    teams: set[str] = set()
    for value in groups:
        group = _object(value, "injury team group")
        team_id = _id(group.get("id"), "injury team group id")
        if team_id not in ESPN_NBA_TEAMS or team_id in teams:
            raise ValueError("unknown or repeated NBA injury team group")
        teams.add(team_id)
        for item in _list(group.get("injuries"), "team injuries"):
            injury = _entry(item, team_id)
            key = (team_id, injury.espn_athlete_id)
            if key in entries and entries[key] != injury:
                raise ValueError("conflicting duplicate NBA injury")
            entries[key] = injury
    return NbaInjuryFeed(timestamp, tuple(entries.values()))
