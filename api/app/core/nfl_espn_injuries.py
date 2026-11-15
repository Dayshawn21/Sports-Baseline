"""ESPN's current NFL injury feed, and the downgrade-only merge with the official report.

ESPN picks up game-day rulings (a Saturday "ruled out") hours or days before the
nflverse file does. Display only, like every NFL injury status. Pure: no DB, no I/O.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

_ATHLETE_PATH = re.compile(r"/nfl/player/(?:[a-z]+/)?_/id/([1-9][0-9]*)(?:/|$)")

# ESPN wording to the official report's three statuses; anything else (Active,
# Suspension, a new label) carries no status rather than a guessed one.
_STATUS = {"Out": "Out", "Injured Reserve": "Out", "Doubtful": "Doubtful", "Questionable": "Questionable"}

SEVERITY = {"Out": 3, "Doubtful": 2, "Questionable": 1}


@dataclass(frozen=True)
class EspnNflInjury:
    espn_athlete_id: str
    player_name: str
    status: str
    injury: str | None
    comment: str | None
    espn_updated_at: datetime | None


def _text(value: object) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _athlete_id(athlete: dict) -> str | None:
    for link in athlete.get("links") or []:
        match = _ATHLETE_PATH.search(_text(link.get("href")) or "") if isinstance(link, dict) else None
        if match:
            return match.group(1)
    return None


def _timestamp(value: object) -> datetime | None:
    text = _text(value)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.astimezone(timezone.utc) if parsed.tzinfo is not None else None


def _entry(raw: object) -> EspnNflInjury | None:
    if not isinstance(raw, dict) or not isinstance(raw.get("athlete"), dict):
        return None
    status = _STATUS.get(_text(raw.get("status")) or "")
    athlete_id = _athlete_id(raw["athlete"])
    if status is None or athlete_id is None:
        return None
    details = raw.get("details") if isinstance(raw.get("details"), dict) else {}
    return EspnNflInjury(
        espn_athlete_id=athlete_id,
        player_name=_text(raw["athlete"].get("displayName")) or "",
        status=status,
        injury=_text(details.get("type")),
        comment=_text(raw.get("shortComment")),
        espn_updated_at=_timestamp(raw.get("date")),
    )


def parse_injury_feed(payload: object) -> tuple[int, list[EspnNflInjury]]:
    """Team groups in the feed, and the entries that carry an Out, Doubtful or Questionable.

    A malformed entry is skipped, not fatal. An athlete listed twice keeps the
    more severe status.
    """
    groups = payload.get("injuries") if isinstance(payload, dict) else None
    if not isinstance(groups, list):
        raise ValueError("ESPN injury feed has no injuries list")
    by_athlete: dict[str, EspnNflInjury] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        for raw in group.get("injuries") or []:
            entry = _entry(raw)
            if entry is None:
                continue
            current = by_athlete.get(entry.espn_athlete_id)
            if current is None or SEVERITY[entry.status] > SEVERITY[current.status]:
                by_athlete[entry.espn_athlete_id] = entry
    return len(groups), list(by_athlete.values())


def more_severe(official: str | None, espn: str | None) -> str | None:
    """The status to show: ESPN can downgrade the official report, never clear it."""
    if SEVERITY.get(espn or "", 0) > SEVERITY.get(official or "", 0):
        return espn
    return official
