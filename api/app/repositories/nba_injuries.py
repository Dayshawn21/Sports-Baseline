"""Immutable NBA injury batches; callers own the transaction."""
from __future__ import annotations

from dataclasses import asdict, fields
from datetime import datetime

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.nba_injuries import LinkedNbaInjury, NbaInjuryEntry, NbaInjuryFeed, NbaInjurySnapshot

_ENTRY_COLUMNS = ", ".join(field.name for field in fields(NbaInjuryEntry))


async def unresolved_athletes(db: AsyncSession, feed: NbaInjuryFeed) -> tuple[str, ...]:
    ids = sorted({row.espn_athlete_id for row in feed.injuries})
    if not ids:
        return ()
    result = await db.execute(text("""
        SELECT source_player_id FROM sport_players
        WHERE sport = 'nba' AND source_player_id IN :ids
    """).bindparams(bindparam("ids", expanding=True)), {"ids": ids})
    matched = set(result.scalars().all())
    return tuple(player_id for player_id in ids if player_id not in matched)


async def _existing_snapshot(db: AsyncSession, feed: NbaInjuryFeed, fetched_at: datetime) -> int:
    result = await db.execute(text("""
        SELECT id, source_timestamp, entry_count FROM nba_injury_snapshots
        WHERE fetched_at = :fetched_at AND source = 'ESPN'
    """), {"fetched_at": fetched_at})
    header = result.mappings().one()
    rows = await db.execute(text(f"""
        SELECT {_ENTRY_COLUMNS} FROM nba_player_injuries WHERE snapshot_id = :snapshot_id
    """), {"snapshot_id": header["id"]})
    stored = {NbaInjuryEntry(**row) for row in rows.mappings().all()}
    if (header["source_timestamp"] != feed.source_timestamp
            or header["entry_count"] != len(feed.injuries) or stored != set(feed.injuries)):
        raise ValueError("NBA injury batch timestamp already has different contents")
    return int(header["id"])


async def store_snapshot(db: AsyncSession, feed: NbaInjuryFeed, fetched_at: datetime) -> int:
    """Append one batch atomically with the caller's commit; never replace old entries."""
    if fetched_at.utcoffset() is None or feed.source_timestamp.utcoffset() is None:
        raise ValueError("NBA injury snapshot timestamps must be timezone-aware")
    keys = {(row.espn_team_id, row.espn_athlete_id) for row in feed.injuries}
    if len(keys) != len(feed.injuries):
        raise ValueError("NBA injury batch contains duplicate identities")
    result = await db.execute(text("""
        INSERT INTO nba_injury_snapshots (fetched_at, source, source_timestamp, entry_count)
        VALUES (:fetched_at, 'ESPN', :source_timestamp, :entry_count)
        ON CONFLICT (fetched_at) DO NOTHING RETURNING id
    """), {"fetched_at": fetched_at, "source_timestamp": feed.source_timestamp, "entry_count": len(feed.injuries)})
    snapshot_id = result.scalar_one_or_none()
    if snapshot_id is None:
        return await _existing_snapshot(db, feed, fetched_at)
    if feed.injuries:
        placeholders = ", ".join(f":{field.name}" for field in fields(NbaInjuryEntry))
        await db.execute(text(f"""
            INSERT INTO nba_player_injuries (snapshot_id, {_ENTRY_COLUMNS})
            VALUES (:snapshot_id, {placeholders})
        """), [{"snapshot_id": snapshot_id, **asdict(row)} for row in feed.injuries])
    return int(snapshot_id)


async def get_game_snapshots(
    db: AsyncSession, game_ids: list[int], as_of: datetime,
) -> dict[int, NbaInjurySnapshot]:
    """One stored pre-tip batch per served NBA game, in one query for the whole date."""
    if not game_ids:
        return {}
    result = await db.execute(text(f"""
        SELECT g.id AS game_id, s.id AS snapshot_id, s.fetched_at,
               {', '.join('i.' + field.name for field in fields(NbaInjuryEntry))}, p.id AS player_id
        FROM sport_games g
        JOIN sport_teams away ON away.id = g.away_team_id AND away.sport = 'nba'
        JOIN sport_teams home ON home.id = g.home_team_id AND home.sport = 'nba'
        LEFT JOIN LATERAL (
            SELECT id, fetched_at FROM nba_injury_snapshots
            WHERE source = 'ESPN' AND fetched_at < g.start_utc AND fetched_at <= :as_of
            ORDER BY fetched_at DESC LIMIT 1
        ) s ON true
        LEFT JOIN nba_player_injuries i ON i.snapshot_id = s.id
            AND i.team_code IN (away.team_code, home.team_code)
        LEFT JOIN sport_players p ON p.sport = 'nba' AND p.source_player_id = i.espn_athlete_id
        WHERE g.sport = 'nba' AND g.game_type IN ('REG', 'PIN', 'PST') AND g.id IN :game_ids
        ORDER BY g.id, i.team_code, i.player_name, i.espn_athlete_id
    """).bindparams(bindparam("game_ids", expanding=True)), {"game_ids": game_ids, "as_of": as_of})
    fetched: dict[int, datetime] = {}
    entries: dict[int, list[LinkedNbaInjury]] = {}
    for row in result.mappings().all():
        if row["snapshot_id"] is None:
            continue
        game_id = int(row["game_id"])
        fetched[game_id] = row["fetched_at"]
        entries.setdefault(game_id, [])
        if row["espn_athlete_id"] is not None:
            entry = NbaInjuryEntry(**{field.name: row[field.name] for field in fields(NbaInjuryEntry)})
            entries[game_id].append(LinkedNbaInjury(entry, row["player_id"]))
    return {game_id: NbaInjurySnapshot(time, tuple(entries[game_id])) for game_id, time in fetched.items()}
