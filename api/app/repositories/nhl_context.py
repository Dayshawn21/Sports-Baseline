"""Append complete NHL context batches; the caller owns the outer commit."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, fields
from datetime import date, datetime, timedelta
from typing import Literal, cast, get_args

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nhl_context import NhlGoalieFeed, NhlGoalieObservation, NhlInjuryEntry, NhlInjuryFeed
from app.core.nhl_context_resolution import (
    ContextGameCandidate, ContextPlayerCandidate, EventLink, EventLinkReason, PlayerLink, PlayerLinkReason,
)
from app.core.nhl_context_snapshots import GoalieSnapshot, InjurySnapshot, StoredGoalie, StoredInjury
from app.repositories import nhl

Identity = tuple[str, str]
_INJURY_COLUMNS = tuple(field.name for field in fields(NhlInjuryEntry)) + ("player_id", "link_reason")
_GOALIE_COLUMNS = tuple(field.name for field in fields(NhlGoalieObservation)) + (
    "player_id", "player_link_reason", "game_id", "game_link_reason",
)


async def prepare_dry_run(db: AsyncSession) -> None:
    await db.execute(text("SET TRANSACTION READ ONLY"))
    await db.execute(text("SET LOCAL statement_timeout = '15s'"))


async def get_context_players(db: AsyncSession) -> list[ContextPlayerCandidate]:
    return [ContextPlayerCandidate(player_id, "nhl", name, team, position)
            for player_id, name, team, position in await nhl.get_player_candidates(db)]


async def get_context_games(db: AsyncSession, scope_date: date) -> list[ContextGameCandidate]:
    result = await db.execute(text("""
        SELECT g.id AS game_id, g.sport, g.game_type, g.start_utc,
               away.team_code AS away_team, home.team_code AS home_team
        FROM sport_games g
        JOIN sport_teams away ON away.id = g.away_team_id AND away.sport = 'nhl'
        JOIN sport_teams home ON home.id = g.home_team_id AND home.sport = 'nhl'
        WHERE g.sport = 'nhl' AND g.game_type IN ('REG', 'PST')
          AND g.game_date BETWEEN :first_date AND :last_date
        ORDER BY g.start_utc, g.id
    """), {"first_date": scope_date - timedelta(days=1), "last_date": scope_date + timedelta(days=1)})
    return [ContextGameCandidate(**row) for row in result.mappings().all()]


@dataclass(frozen=True)
class _Batch:
    kind: Literal["injuries", "goalies"]
    scope_date: date | None
    fetched_at: datetime
    source_timestamp: datetime | None
    rows: Sequence[dict[str, object]]

    @property
    def table(self) -> str:
        return "nhl_player_injuries" if self.kind == "injuries" else "nhl_goalie_observations"

    @property
    def columns(self) -> tuple[str, ...]:
        return _INJURY_COLUMNS if self.kind == "injuries" else _GOALIE_COLUMNS


def _aware(*values: datetime | None) -> None:
    if any(value is not None and value.utcoffset() is None for value in values):
        raise ValueError("NHL context timestamps must be timezone-aware")


def _link(link: PlayerLink | EventLink) -> None:
    identity = link.player_id if isinstance(link, PlayerLink) else link.game_id
    reasons = get_args(PlayerLinkReason if isinstance(link, PlayerLink) else EventLinkReason)
    if link.reason not in reasons or (identity is not None) != (link.reason == "matched"):
        raise ValueError("NHL context link id and reason disagree")
    if identity is not None and (isinstance(identity, bool) or not isinstance(identity, int) or identity <= 0):
        raise ValueError("NHL context links require positive internal IDs")


def _coverage(keys: Sequence[Identity], links: Mapping[Identity, PlayerLink]) -> None:
    if len(set(keys)) != len(keys):
        raise ValueError("NHL context batch contains duplicate identities")
    if set(keys) != set(links):
        raise ValueError("NHL context frozen links must cover source entries exactly")


async def store_injury_snapshot(
    db: AsyncSession, feed: NhlInjuryFeed, fetched_at: datetime,
    links: Mapping[Identity, PlayerLink],
) -> int:
    _aware(fetched_at, feed.source_timestamp, *(row.source_updated_at for row in feed.injuries))
    _coverage([(row.espn_team_id, row.espn_athlete_id) for row in feed.injuries], links)
    rows: list[dict[str, object]] = []
    for row in feed.injuries:
        link = links[(row.espn_team_id, row.espn_athlete_id)]
        _link(link)
        if link.reason == "not_reported" or (row.team_mismatch and link.player_id is not None):
            raise ValueError("injury source identity contradicts frozen player link")
        rows.append({**asdict(row), "player_id": link.player_id, "link_reason": link.reason})
    return await _store_snapshot(db, _Batch("injuries", None, fetched_at, feed.source_timestamp, rows))


def _goalie_rows(
    feed: NhlGoalieFeed, links: Mapping[Identity, PlayerLink], games: Mapping[str, EventLink],
) -> list[dict[str, object]]:
    _coverage([(row.espn_event_id, row.espn_team_id) for row in feed.observations], links)
    if {row.espn_event_id for row in feed.observations} != set(games):
        raise ValueError("NHL context frozen game links must cover source events exactly")
    rows: list[dict[str, object]] = []
    for row in feed.observations:
        _aware(row.start_utc)
        if row.event_date != feed.scope_date:
            raise ValueError("goalie observation does not belong to batch scope date")
        player, game = links[(row.espn_event_id, row.espn_team_id)], games[row.espn_event_id]
        _link(player)
        _link(game)
        if game.game_id is not None and not row.time_valid:
            raise ValueError("unknown event start cannot have a frozen game link")
        if player.player_id is not None and (row.team_mismatch or row.source_position not in (None, "G")):
            raise ValueError("goalie source identity contradicts frozen player link")
        if (row.status == "not_reported") != (player.reason == "not_reported"):
            raise ValueError("goalie announcement and player link reason disagree")
        rows.append({**asdict(row), "player_id": player.player_id, "player_link_reason": player.reason,
                     "game_id": game.game_id, "game_link_reason": game.reason})
    for event in games:
        competitors = [row for row in feed.observations if row.espn_event_id == event]
        first = competitors[0]
        if (len(competitors) != 2 or {row.team_code for row in competitors} != {first.home_team, first.away_team}
                or any((row.start_utc, row.time_valid, row.home_team, row.away_team) !=
                       (first.start_utc, first.time_valid, first.home_team, first.away_team) for row in competitors)):
            raise ValueError("goalie event must preserve both consistent competitors")
    return rows


async def store_goalie_snapshot(
    db: AsyncSession, feed: NhlGoalieFeed, fetched_at: datetime,
    links: Mapping[Identity, PlayerLink], games: Mapping[str, EventLink],
) -> int:
    _aware(fetched_at, feed.source_timestamp)
    rows = _goalie_rows(feed, links, games)
    return await _store_snapshot(db, _Batch("goalies", feed.scope_date, fetched_at, feed.source_timestamp, rows))


async def _validate_foreign_links(db: AsyncSession, batch: _Batch) -> None:
    players = {row["player_id"] for row in batch.rows if row["player_id"] is not None}
    if players:
        position = "AND position = 'G'" if batch.kind == "goalies" else ""
        result = await db.execute(text(f"""
            SELECT id FROM sport_players WHERE sport = 'nhl' {position} AND id IN :ids FOR SHARE
        """).bindparams(bindparam("ids", expanding=True)), {"ids": sorted(players)})
        if set(result.scalars().all()) != players:
            raise ValueError("frozen player links must reference existing NHL players (goalies must be G)")
    games = {row["game_id"] for row in batch.rows if batch.kind == "goalies" and row["game_id"] is not None}
    if games:
        result = await db.execute(text("""
            SELECT id FROM sport_games WHERE sport = 'nhl' AND game_type IN ('REG', 'PST')
            AND id IN :ids FOR SHARE
        """).bindparams(bindparam("ids", expanding=True)), {"ids": sorted(games)})
        if set(result.scalars().all()) != games:
            raise ValueError("frozen game links must reference existing NHL REG/PST games")


async def _existing_snapshot(db: AsyncSession, batch: _Batch) -> int:
    result = await db.execute(text("""
        SELECT id, source_timestamp, entry_count FROM nhl_context_snapshots
        WHERE source = 'ESPN' AND kind = :kind AND scope_date IS NOT DISTINCT FROM :scope_date
        AND fetched_at = :fetched_at
    """), {"kind": batch.kind, "scope_date": batch.scope_date, "fetched_at": batch.fetched_at})
    header = result.mappings().one()
    result = await db.execute(text(f"""
        SELECT {', '.join(batch.columns)} FROM {batch.table} WHERE snapshot_id = :snapshot_id
    """), {"snapshot_id": header["id"]})
    stored = result.mappings().all()
    expected = {tuple(row[column] for column in batch.columns) for row in batch.rows}
    actual = {tuple(row[column] for column in batch.columns) for row in stored}
    if (header["source_timestamp"] != batch.source_timestamp or header["entry_count"] != len(batch.rows)
            or len(stored) != len(batch.rows) or actual != expected):
        raise ValueError("NHL context batch identity already has different contents or frozen links")
    return int(header["id"])


async def _store_snapshot(db: AsyncSession, batch: _Batch) -> int:
    async with db.begin_nested():
        result = await db.execute(text("""
            INSERT INTO nhl_context_snapshots (source, kind, scope_date, fetched_at, source_timestamp, entry_count)
            VALUES ('ESPN', :kind, :scope_date, :fetched_at, :source_timestamp, :entry_count)
            ON CONFLICT ON CONSTRAINT uq_nhl_context_batch DO NOTHING RETURNING id
        """), {"kind": batch.kind, "scope_date": batch.scope_date, "fetched_at": batch.fetched_at,
               "source_timestamp": batch.source_timestamp, "entry_count": len(batch.rows)})
        snapshot_id = result.scalar_one_or_none()
        if snapshot_id is None:
            return await _existing_snapshot(db, batch)
        await _validate_foreign_links(db, batch)
        if batch.rows:
            columns = ("snapshot_id", *batch.columns)
            await db.execute(text(f"""
                INSERT INTO {batch.table} ({', '.join(columns)})
                VALUES ({', '.join(':' + column for column in columns)})
            """), [{"snapshot_id": snapshot_id, **row} for row in batch.rows])
        return int(snapshot_id)


async def _selected_rows(
    db: AsyncSession, game_ids: list[int], as_of: datetime, kind: Literal["injuries", "goalies"],
) -> Sequence[Mapping[str, object]]:
    _aware(as_of)
    if not game_ids:
        return []
    scope = "candidate.scope_date IS NULL" if kind == "injuries" else "candidate.scope_date = g.game_date"
    table = "nhl_player_injuries" if kind == "injuries" else "nhl_goalie_observations"
    columns = _INJURY_COLUMNS if kind == "injuries" else _GOALIE_COLUMNS
    entries = "e.team_code IN (s.away_team, s.home_team)" if kind == "injuries" else "e.game_id = s.served_game_id"
    result = await db.execute(text(f"""
        WITH selected AS (
            SELECT g.id AS served_game_id, away.team_code AS away_team, home.team_code AS home_team,
                   s.id AS snapshot_id, s.fetched_at AS snapshot_fetched_at,
                   s.source_timestamp AS snapshot_source_timestamp
            FROM sport_games g
            JOIN sport_teams away ON away.id = g.away_team_id AND away.sport = 'nhl'
            JOIN sport_teams home ON home.id = g.home_team_id AND home.sport = 'nhl'
            LEFT JOIN nhl_context_snapshots s ON s.id = (
                SELECT candidate.id FROM nhl_context_snapshots candidate
                WHERE candidate.source = 'ESPN' AND candidate.kind = :kind AND {scope}
                  AND candidate.fetched_at < g.start_utc AND candidate.fetched_at <= :as_of
                ORDER BY candidate.fetched_at DESC, candidate.id DESC LIMIT 1
            )
            WHERE g.sport = 'nhl' AND g.game_type IN ('REG', 'PST') AND g.id IN :game_ids
        )
        SELECT s.served_game_id, s.snapshot_id, s.snapshot_fetched_at, s.snapshot_source_timestamp,
               {', '.join('e.' + column for column in columns)}
        FROM selected s LEFT JOIN {table} e ON e.snapshot_id = s.snapshot_id AND {entries}
        ORDER BY s.served_game_id, e.team_code, e.espn_athlete_id
    """).bindparams(bindparam("game_ids", expanding=True)), {"game_ids": game_ids, "as_of": as_of, "kind": kind})
    return result.mappings().all()


def _stored_time(value: object) -> datetime | None:
    if value is None:
        return None
    parsed = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    _aware(parsed)
    return parsed


def _metadata(row: Mapping[str, object]) -> tuple[datetime, datetime | None]:
    fetched = _stored_time(row["snapshot_fetched_at"])
    if fetched is None:
        raise ValueError("stored NHL snapshot has no fetched timestamp")
    return fetched, _stored_time(row["snapshot_source_timestamp"])


async def get_injury_snapshots(db: AsyncSession, game_ids: list[int], as_of: datetime) -> dict[int, InjurySnapshot]:
    metadata: dict[int, tuple[datetime, datetime | None]] = {}
    entries: dict[int, list[StoredInjury]] = {}
    for row in await _selected_rows(db, game_ids, as_of, "injuries"):
        if row["snapshot_id"] is None:
            continue
        game_id = int(str(row["served_game_id"]))
        metadata[game_id] = _metadata(row)
        entries.setdefault(game_id, [])
        if row["espn_athlete_id"] is not None:
            values = {field.name: row[field.name] for field in fields(NhlInjuryEntry)}
            values["source_updated_at"] = _stored_time(row["source_updated_at"])
            player_id = int(str(row["player_id"])) if row["player_id"] is not None else None
            entries[game_id].append(StoredInjury(NhlInjuryEntry(**values), PlayerLink(
                player_id, cast(PlayerLinkReason, row["link_reason"]),
            )))
    return {game_id: InjurySnapshot(*times, tuple(entries[game_id])) for game_id, times in metadata.items()}


async def get_goalie_snapshots(db: AsyncSession, game_ids: list[int], as_of: datetime) -> dict[int, GoalieSnapshot]:
    metadata: dict[int, tuple[datetime, datetime | None]] = {}
    entries: dict[int, list[StoredGoalie]] = {}
    for row in await _selected_rows(db, game_ids, as_of, "goalies"):
        if row["snapshot_id"] is None:
            continue
        game_id = int(str(row["served_game_id"]))
        metadata[game_id] = _metadata(row)
        entries.setdefault(game_id, [])
        if row["espn_event_id"] is not None:
            values = {field.name: row[field.name] for field in fields(NhlGoalieObservation)}
            values.update(start_utc=_stored_time(row["start_utc"]), time_valid=bool(row["time_valid"]),
                          event_date=date.fromisoformat(str(row["event_date"])))
            player_id = int(str(row["player_id"])) if row["player_id"] is not None else None
            entries[game_id].append(StoredGoalie(
                NhlGoalieObservation(**values), PlayerLink(player_id, cast(PlayerLinkReason, row["player_link_reason"])),
                EventLink(int(str(row["game_id"])), cast(EventLinkReason, row["game_link_reason"])),
            ))
    return {game_id: GoalieSnapshot(*times, tuple(entries[game_id])) for game_id, times in metadata.items()}
