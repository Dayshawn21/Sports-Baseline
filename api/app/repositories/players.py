from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_player import EloSnapshot, ServeReturnStats

# Spelling variants that must collapse onto one canonical player.
#
# `players.name_norm` is UNIQUE and upsert_player conflicts on it, so an
# unmapped variant forks the player and splits their ELO and rolling stats.
# Every entry below was confirmed against the players table, not guessed —
# `python -m app.ingest.livetennis --dry-run` reports candidates for new ones.
KNOWN_NAME_NORM_ALIASES = {
    "catherine mcnally": "caty mcnally",
    # TennisAbstract ELO page drops hyphens
    "jan lennard struff": "jan-lennard struff",
    "elena gabriela ruse": "elena-gabriela ruse",
    "felix auger aliassime": "felix auger-aliassime",
    "martin damm": "martin damm jr",
    # livetennisapi — reordered name parts
    "constantin kouzmine bittoun": "constantin bittoun kouzmine",
    "daniel adolfo vallejo": "adolfo daniel vallejo",
    "guiomar zuleta de reales maristany": "guiomar maristany zuleta de reales",
    "josef schwaerzler joel": "joel schwaerzler",
    "marina ribera bassols": "marina bassols ribera",
    "mendez rodrigo pacheco": "rodrigo pacheco mendez",
    # livetennisapi — extra or dropped middle names
    "coleman chak lam wong": "coleman wong",
    # livetennisapi — abbreviated first name (each surname is unique in players)
    "d. lajovic": "dusan lajovic",
    "v. kopriva": "vit kopriva",
    # livetennisapi — transliteration and umlaut spellings
    "anastasiia sobolieva": "anastasiya soboleva",
    "jasmin ortenzi": "jazmin ortenzi",
    "marvin moeller": "marvin moller",  # Möller
}

def normalize_name(name: str) -> str:
    """Lowercase, strip accents, collapse whitespace (including non-breaking spaces)."""
    name = name.replace("\xa0", " ")  # non-breaking space → regular space
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_ = nfkd.encode("ascii", "ignore").decode("ascii")
    norm = " ".join(ascii_.lower().split())
    return KNOWN_NAME_NORM_ALIASES.get(norm, norm)


@dataclass
class Player:
    id: int
    name: str
    name_norm: str
    tour: str
    sofascore_id: Optional[int] = None
    ta_id: Optional[int] = None
    birth_date: Optional[date] = None
    ta_slug: Optional[str] = None  # custom TennisAbstract slug override
    livetennis_id: Optional[int] = None


@dataclass
class PlayerElo:
    player_id: int
    as_of_date: date
    elo: Optional[float]
    elo_hard: Optional[float]
    elo_clay: Optional[float]
    elo_grass: Optional[float]


@dataclass
class PlayerRollingStats:
    player_id: int
    surface: Optional[str]
    stat_period: str
    split_type: Optional[str]
    split_value: Optional[str]
    win_rate: Optional[float]
    svc_pts_won: Optional[float]
    ret_pts_won: Optional[float]
    aces_per_game: Optional[float]
    df_per_game: Optional[float]
    hold_pct: Optional[float]
    break_pct: Optional[float]
    matches_count: Optional[int]
    first_in_pct: Optional[float] = None
    first_won_pct: Optional[float] = None
    second_won_pct: Optional[float] = None
    dominance_ratio: Optional[float] = None
    computed_at: Optional[datetime] = None  # last ingestion timestamp (freshness check)
    # Opponent-allowed (defensive) stats — "what opponents achieve vs this player"
    allowed_aces_per_sp: Optional[float] = None
    allowed_df_per_sp: Optional[float] = None
    allowed_first_in_pct: Optional[float] = None
    allowed_first_won_pct: Optional[float] = None
    allowed_second_won_pct: Optional[float] = None
    allowed_hold_pct: Optional[float] = None
    break_points_created_per_return_game: Optional[float] = None
    allowed_break_points_per_service_game: Optional[float] = None

    def __post_init__(self) -> None:
        # The columns added after the original stat set are NUMERIC, so psycopg hands
        # them back as Decimal while the older DOUBLE PRECISION ones arrive as float.
        # Mixing the two raises TypeError in build_features whenever one player has a
        # value and the other falls back to 0.0, which silently drops the match from
        # the slate. Coerce here so the annotations above are actually true.
        for f, v in list(self.__dict__.items()):
            if isinstance(v, Decimal):
                setattr(self, f, float(v))


UNDEFINED_COLUMN_SQLSTATE = "42703"


def _missing_split_columns(exc: ProgrammingError) -> bool:
    # str(exc) embeds the SQL, which names split_type, so match only the
    # driver's primary message on a genuine undefined-column error.
    if getattr(exc.orig, "sqlstate", None) != UNDEFINED_COLUMN_SQLSTATE:
        return False
    diag = getattr(exc.orig, "diag", None)
    msg = (getattr(diag, "message_primary", None) or "").lower()
    return "split_type" in msg or "split_value" in msg


async def resolve_player(db: AsyncSession, name: str, tour: str) -> Optional[Player]:
    """Look up a player by name (tries canonical table then aliases)."""
    norm = normalize_name(name)
    row = await db.execute(
        text("SELECT id, name, name_norm, tour, sofascore_id, ta_id, birth_date, ta_slug, livetennis_id FROM players WHERE name_norm = :n AND tour = :t"),
        {"n": norm, "t": tour.upper()},
    )
    r = row.fetchone()
    if r:
        return Player(*r)

    # Try aliases
    row = await db.execute(
        text("""
            SELECT p.id, p.name, p.name_norm, p.tour, p.sofascore_id, p.ta_id, p.birth_date, p.ta_slug,
                   p.livetennis_id
            FROM player_aliases a
            JOIN players p ON p.id = a.canonical_player_id
            WHERE a.alias_name_norm = :n
        """),
        {"n": norm},
    )
    r = row.fetchone()
    return Player(*r) if r else None


async def upsert_player(
    db: AsyncSession,
    name: str,
    tour: str,
    sofascore_id: Optional[int] = None,
    ta_id: Optional[int] = None,
    birth_date: Optional[date] = None,
    livetennis_id: Optional[int] = None,
    hand: Optional[str] = None,
    country: Optional[str] = None,
) -> int:
    """Insert or update a player, return their id."""
    norm = normalize_name(name)
    if livetennis_id is not None:
        # idx_players_livetennis_id is UNIQUE, so if a *different* row already
        # holds this provider id (a name that forked into two players before the
        # alias table caught it), the upsert below would raise a unique violation
        # and roll back the whole ingest run. The id is provider metadata, not a
        # foreign key, so releasing it from the stale row is safe and lets the
        # fork self-heal on the next run.
        await db.execute(
            text(
                "UPDATE players SET livetennis_id = NULL "
                "WHERE livetennis_id = :lt AND name_norm <> :norm"
            ),
            {"lt": livetennis_id, "norm": norm},
        )
    row = await db.execute(
        text("""
            INSERT INTO players (name, name_norm, tour, sofascore_id, ta_id, birth_date, livetennis_id,
                                 hand, country)
            VALUES (:name, :norm, :tour, :sofascore_id, :ta_id, :birth_date, :livetennis_id,
                    :hand, :country)
            ON CONFLICT (name_norm) DO UPDATE
              SET sofascore_id  = COALESCE(EXCLUDED.sofascore_id, players.sofascore_id),
                  ta_id         = COALESCE(EXCLUDED.ta_id, players.ta_id),
                  birth_date    = COALESCE(EXCLUDED.birth_date, players.birth_date),
                  livetennis_id = COALESCE(EXCLUDED.livetennis_id, players.livetennis_id),
                  hand          = COALESCE(EXCLUDED.hand, players.hand),
                  country       = COALESCE(EXCLUDED.country, players.country)
            RETURNING id
        """),
        {"name": name, "norm": norm, "tour": tour.upper(), "sofascore_id": sofascore_id, "ta_id": ta_id,
         "birth_date": birth_date, "livetennis_id": livetennis_id, "hand": hand, "country": country},
    )
    return row.scalar_one()


async def update_birth_date(db: AsyncSession, player_id: int, birth_date: date) -> None:
    """Set birth_date for a player."""
    await db.execute(
        text("UPDATE players SET birth_date = :bd WHERE id = :id"),
        {"bd": birth_date, "id": player_id},
    )


async def upsert_alias(db: AsyncSession, canonical_id: int, alias_name: str, source: str) -> None:
    norm = normalize_name(alias_name)
    await db.execute(
        text("""
            INSERT INTO player_aliases (canonical_player_id, alias_name, alias_name_norm, source)
            VALUES (:pid, :alias, :norm, :source)
            ON CONFLICT (alias_name_norm) DO NOTHING
        """),
        {"pid": canonical_id, "alias": alias_name, "norm": norm, "source": source},
    )


async def upsert_elo(db: AsyncSession, player_id: int, as_of: date, elo: float,
                     elo_hard: Optional[float], elo_clay: Optional[float], elo_grass: Optional[float],
                     source: str = "tennisabstract") -> None:
    await db.execute(
        text("""
            INSERT INTO player_elo (player_id, as_of_date, elo, elo_hard, elo_clay, elo_grass, source)
            VALUES (:pid, :dt, :elo, :h, :c, :g, :src)
            ON CONFLICT (player_id, as_of_date) DO UPDATE
              SET elo      = EXCLUDED.elo,
                  elo_hard = EXCLUDED.elo_hard,
                  elo_clay = EXCLUDED.elo_clay,
                  elo_grass= EXCLUDED.elo_grass
        """),
        {"pid": player_id, "dt": as_of, "elo": elo, "h": elo_hard, "c": elo_clay, "g": elo_grass, "src": source},
    )


async def get_latest_elo(db: AsyncSession, player_id: int) -> Optional[PlayerElo]:
    row = await db.execute(
        text("""
            SELECT player_id, as_of_date, elo, elo_hard, elo_clay, elo_grass
            FROM player_elo
            WHERE player_id = :pid
            ORDER BY as_of_date DESC
            LIMIT 1
        """),
        {"pid": player_id},
    )
    r = row.fetchone()
    return PlayerElo(*r) if r else None


async def upsert_rolling_stats(db: AsyncSession, stats: PlayerRollingStats) -> None:
    params = {
        "pid": stats.player_id, "surf": stats.surface, "period": stats.stat_period,
        "split_type": stats.split_type, "split_value": stats.split_value,
        "wr": stats.win_rate, "svc": stats.svc_pts_won, "ret": stats.ret_pts_won,
        "ace": stats.aces_per_game, "df": stats.df_per_game,
        "hold": stats.hold_pct, "brk": stats.break_pct, "cnt": stats.matches_count,
        "fin": stats.first_in_pct, "fwon": stats.first_won_pct,
        "swon": stats.second_won_pct, "dr": stats.dominance_ratio,
        "a_ace": stats.allowed_aces_per_sp, "a_df": stats.allowed_df_per_sp,
        "a_fin": stats.allowed_first_in_pct, "a_fwon": stats.allowed_first_won_pct,
        "a_swon": stats.allowed_second_won_pct, "a_hold": stats.allowed_hold_pct,
        "bp_created": stats.break_points_created_per_return_game,
        "a_bp_allowed": stats.allowed_break_points_per_service_game,
    }
    try:
        await db.execute(
            text("""
                INSERT INTO player_rolling_stats
                  (player_id, surface, stat_period, computed_at,
                   split_type, split_value,
                   win_rate, svc_pts_won, ret_pts_won,
                   aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                   first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                   allowed_aces_per_sp, allowed_df_per_sp,
                   allowed_first_in_pct, allowed_first_won_pct,
                   allowed_second_won_pct, allowed_hold_pct,
                   break_points_created_per_return_game, allowed_break_points_per_service_game)
                VALUES
                  (:pid, :surf, :period, now(),
                   :split_type, :split_value,
                   :wr, :svc, :ret,
                   :ace, :df, :hold, :brk, :cnt,
                   :fin, :fwon, :swon, :dr,
                   :a_ace, :a_df,
                   :a_fin, :a_fwon,
                   :a_swon, :a_hold,
                   :bp_created, :a_bp_allowed)
                ON CONFLICT (player_id, stat_period, surface, split_type, split_value) DO UPDATE SET
                  computed_at    = now(),
                  split_type     = EXCLUDED.split_type,
                  split_value    = EXCLUDED.split_value,
                  win_rate       = EXCLUDED.win_rate,
                  svc_pts_won    = EXCLUDED.svc_pts_won,
                  ret_pts_won    = EXCLUDED.ret_pts_won,
                  aces_per_game  = EXCLUDED.aces_per_game,
                  df_per_game    = EXCLUDED.df_per_game,
                  hold_pct       = EXCLUDED.hold_pct,
                  break_pct      = EXCLUDED.break_pct,
                  matches_count  = EXCLUDED.matches_count,
                  first_in_pct   = EXCLUDED.first_in_pct,
                  first_won_pct  = EXCLUDED.first_won_pct,
                  second_won_pct = EXCLUDED.second_won_pct,
                  dominance_ratio = EXCLUDED.dominance_ratio,
                  allowed_aces_per_sp    = EXCLUDED.allowed_aces_per_sp,
                  allowed_df_per_sp      = EXCLUDED.allowed_df_per_sp,
                  allowed_first_in_pct   = EXCLUDED.allowed_first_in_pct,
                  allowed_first_won_pct  = EXCLUDED.allowed_first_won_pct,
                  allowed_second_won_pct = EXCLUDED.allowed_second_won_pct,
                  allowed_hold_pct       = EXCLUDED.allowed_hold_pct,
                  break_points_created_per_return_game = EXCLUDED.break_points_created_per_return_game,
                  allowed_break_points_per_service_game = EXCLUDED.allowed_break_points_per_service_game
            """),
            params,
        )
        return
    except ProgrammingError as exc:
        if not _missing_split_columns(exc):
            raise
        await db.rollback()

    # Older DBs may still be missing contextual split columns. Preserve ingest for
    # baseline overall rows and skip contextual variants until the migration lands.
    if (stats.split_type or "overall") != "overall" or (stats.split_value or "all") != "all":
        return

    await db.execute(
        text("""
            INSERT INTO player_rolling_stats
              (player_id, surface, stat_period, computed_at,
               win_rate, svc_pts_won, ret_pts_won,
               aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
               first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
               allowed_aces_per_sp, allowed_df_per_sp,
               allowed_first_in_pct, allowed_first_won_pct,
               allowed_second_won_pct, allowed_hold_pct,
               break_points_created_per_return_game, allowed_break_points_per_service_game)
            VALUES
              (:pid, :surf, :period, now(),
               :wr, :svc, :ret,
               :ace, :df, :hold, :brk, :cnt,
               :fin, :fwon, :swon, :dr,
               :a_ace, :a_df,
               :a_fin, :a_fwon,
               :a_swon, :a_hold,
               :bp_created, :a_bp_allowed)
            ON CONFLICT (player_id, stat_period, surface) DO UPDATE SET
              computed_at    = now(),
              win_rate       = EXCLUDED.win_rate,
              svc_pts_won    = EXCLUDED.svc_pts_won,
              ret_pts_won    = EXCLUDED.ret_pts_won,
              aces_per_game  = EXCLUDED.aces_per_game,
              df_per_game    = EXCLUDED.df_per_game,
              hold_pct       = EXCLUDED.hold_pct,
              break_pct      = EXCLUDED.break_pct,
              matches_count  = EXCLUDED.matches_count,
              first_in_pct   = EXCLUDED.first_in_pct,
              first_won_pct  = EXCLUDED.first_won_pct,
              second_won_pct = EXCLUDED.second_won_pct,
              dominance_ratio = EXCLUDED.dominance_ratio,
              allowed_aces_per_sp    = EXCLUDED.allowed_aces_per_sp,
              allowed_df_per_sp      = EXCLUDED.allowed_df_per_sp,
              allowed_first_in_pct   = EXCLUDED.allowed_first_in_pct,
              allowed_first_won_pct  = EXCLUDED.allowed_first_won_pct,
              allowed_second_won_pct = EXCLUDED.allowed_second_won_pct,
              allowed_hold_pct       = EXCLUDED.allowed_hold_pct,
              break_points_created_per_return_game = EXCLUDED.break_points_created_per_return_game,
              allowed_break_points_per_service_game = EXCLUDED.allowed_break_points_per_service_game
        """),
        params,
    )


async def get_rolling_stats(db: AsyncSession, player_id: int, surface: Optional[str],
                             stat_period: str = "last_52w") -> Optional[PlayerRollingStats]:
    try:
        row = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, surface, split_type, split_value)
                    player_id, surface, stat_period, split_type, split_value, win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = :pid
                  AND (surface = :surf OR (:surf IS NULL AND surface IS NULL))
                  AND stat_period = :period
                  AND split_type = 'overall'
                  AND split_value = 'all'
                ORDER BY player_id, surface, split_type, split_value, computed_at DESC
            """),
            {"pid": player_id, "surf": surface, "period": stat_period},
        )
    except ProgrammingError as exc:
        if not _missing_split_columns(exc):
            raise
        await db.rollback()
        row = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, surface)
                    player_id, surface, stat_period, 'overall' AS split_type, 'all' AS split_value,
                    win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = :pid
                  AND (surface = :surf OR (:surf IS NULL AND surface IS NULL))
                  AND stat_period = :period
                ORDER BY player_id, surface, computed_at DESC
            """),
            {"pid": player_id, "surf": surface, "period": stat_period},
        )
    r = row.fetchone()
    return PlayerRollingStats(*r) if r else None


async def get_rolling_stats_batch(
    db: AsyncSession,
    player_ids: list[int],
    stat_period: str = "last_52w",
) -> dict[int, "PlayerRollingStats"]:
    """Fetch all-surface rolling stats for a list of player IDs in one query.

    Returns a dict mapping player_id → PlayerRollingStats (latest computed_at per player).
    """
    if not player_ids:
        return {}
    try:
        rows = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, split_type, split_value)
                    player_id, surface, stat_period, split_type, split_value, win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = ANY(:pids)
                  AND surface IS NULL
                  AND stat_period = :period
                  AND split_type = 'overall'
                  AND split_value = 'all'
                ORDER BY player_id, split_type, split_value, computed_at DESC
            """),
            {"pids": player_ids, "period": stat_period},
        )
    except ProgrammingError as exc:
        if not _missing_split_columns(exc):
            raise
        await db.rollback()
        rows = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id)
                    player_id, surface, stat_period, 'overall' AS split_type, 'all' AS split_value,
                    win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = ANY(:pids)
                  AND surface IS NULL
                  AND stat_period = :period
                ORDER BY player_id, computed_at DESC
            """),
            {"pids": player_ids, "period": stat_period},
        )
    return {r[0]: PlayerRollingStats(*r) for r in rows.fetchall()}


async def get_player_by_id(db: AsyncSession, player_id: int) -> Optional[Player]:
    """Fetch a player by ID, including birth_date."""
    row = await db.execute(
        text("SELECT id, name, name_norm, tour, sofascore_id, ta_id, birth_date, ta_slug, livetennis_id FROM players WHERE id = :id"),
        {"id": player_id},
    )
    r = row.fetchone()
    return Player(*r) if r else None


@dataclass(frozen=True)
class PlayerProfile:
    id: int
    name: str
    tour: str
    hand: Optional[str]
    country: Optional[str]


async def get_player_profiles(db: AsyncSession, player_ids: list[int]) -> dict[int, PlayerProfile]:
    if not player_ids:
        return {}
    rows = await db.execute(
        text("SELECT id, name, tour, hand, country FROM players WHERE id = ANY(:ids)"),
        {"ids": player_ids},
    )
    return {r[0]: PlayerProfile(*r) for r in rows.fetchall()}


async def get_players_by_ids(db: AsyncSession, player_ids: list[int]) -> dict[int, "Player"]:
    """Fetch multiple players by ID in one query."""
    if not player_ids:
        return {}
    rows = await db.execute(
        text("SELECT id, name, name_norm, tour, sofascore_id, ta_id, birth_date, ta_slug, livetennis_id FROM players WHERE id = ANY(:ids)"),
        {"ids": player_ids},
    )
    return {r[0]: Player(*r) for r in rows.fetchall()}


async def get_latest_elo_batch(db: AsyncSession, player_ids: list[int]) -> dict[int, "PlayerElo"]:
    """Fetch most recent ELO for multiple players in one query."""
    if not player_ids:
        return {}
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (player_id)
                player_id, as_of_date, elo, elo_hard, elo_clay, elo_grass
            FROM player_elo
            WHERE player_id = ANY(:ids)
            ORDER BY player_id, as_of_date DESC
        """),
        {"ids": player_ids},
    )
    return {r[0]: PlayerElo(*r) for r in rows.fetchall()}


async def update_ta_slug(db: AsyncSession, player_id: int, ta_slug: str) -> None:
    """Persist a custom TennisAbstract slug override for a player."""
    await db.execute(
        text("UPDATE players SET ta_slug = :slug WHERE id = :id"),
        {"slug": ta_slug, "id": player_id},
    )


async def get_rolling_stats_batch_all_surfaces(
    db: AsyncSession,
    player_ids: list[int],
    stat_period: str = "last_52w",
) -> dict[tuple[int, Optional[str]], "PlayerRollingStats"]:
    """Fetch rolling stats for all surfaces (NULL + Hard/Clay/Grass) for a list of player IDs.

    Returns a dict mapping (player_id, surface) → PlayerRollingStats.
    surface=None is the all-surface row used as fallback.
    """
    if not player_ids:
        return {}
    try:
        rows = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, surface, split_type, split_value)
                    player_id, surface, stat_period, split_type, split_value, win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = ANY(:pids)
                  AND stat_period = :period
                  AND split_type = 'overall'
                  AND split_value = 'all'
                ORDER BY player_id, surface, split_type, split_value, computed_at DESC
            """),
            {"pids": player_ids, "period": stat_period},
        )
    except ProgrammingError as exc:
        if not _missing_split_columns(exc):
            raise
        await db.rollback()
        rows = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, surface)
                    player_id, surface, stat_period, 'overall' AS split_type, 'all' AS split_value,
                    win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = ANY(:pids)
                  AND stat_period = :period
                ORDER BY player_id, surface, computed_at DESC
            """),
            {"pids": player_ids, "period": stat_period},
        )
    result: dict[tuple[int, Optional[str]], "PlayerRollingStats"] = {}
    for r in rows.fetchall():
        stats = PlayerRollingStats(*r)
        result[(stats.player_id, stats.surface)] = stats
    return result


async def get_contextual_rolling_stats(
    db: AsyncSession,
    player_id: int,
    surface: Optional[str],
    stat_period: str,
    split_type: str,
    split_value: str,
) -> Optional[PlayerRollingStats]:
    try:
        row = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, surface, split_type, split_value)
                    player_id, surface, stat_period, split_type, split_value, win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = :pid
                  AND (surface = :surf OR (:surf IS NULL AND surface IS NULL))
                  AND stat_period = :period
                  AND split_type = :split_type
                  AND split_value = :split_value
                ORDER BY player_id, surface, split_type, split_value, computed_at DESC
            """),
            {
                "pid": player_id,
                "surf": surface,
                "period": stat_period,
                "split_type": split_type,
                "split_value": split_value,
            },
        )
    except ProgrammingError as exc:
        if not _missing_split_columns(exc):
            raise
        await db.rollback()
        return None
    r = row.fetchone()
    return PlayerRollingStats(*r) if r else None


async def get_contextual_rolling_stats_batch(
    db: AsyncSession,
    player_ids: list[int],
    stat_period: str,
    split_type: str,
    surface: Optional[str] = None,
    split_values: Optional[list[str]] = None,
) -> dict[tuple[int, Optional[str], str], "PlayerRollingStats"]:
    if not player_ids:
        return {}
    params = {
        "pids": player_ids,
        "period": stat_period,
        "split_type": split_type,
        "surf": surface,
        "split_values": split_values or [],
        "use_values": 1 if split_values else 0,
    }
    try:
        rows = await db.execute(
            text("""
                SELECT DISTINCT ON (player_id, surface, split_type, split_value)
                    player_id, surface, stat_period, split_type, split_value, win_rate, svc_pts_won, ret_pts_won,
                    aces_per_game, df_per_game, hold_pct, break_pct, matches_count,
                    first_in_pct, first_won_pct, second_won_pct, dominance_ratio,
                    computed_at,
                    allowed_aces_per_sp, allowed_df_per_sp,
                    allowed_first_in_pct, allowed_first_won_pct,
                    allowed_second_won_pct, allowed_hold_pct,
                    break_points_created_per_return_game, allowed_break_points_per_service_game
                FROM player_rolling_stats
                WHERE player_id = ANY(:pids)
                  AND (CAST(:surf AS text) IS NULL OR surface = :surf)
                  AND stat_period = :period
                  AND split_type = :split_type
                  AND (:use_values = 0 OR split_value = ANY(:split_values))
                ORDER BY player_id, surface, split_type, split_value, computed_at DESC
            """),
            params,
        )
    except ProgrammingError as exc:
        if not _missing_split_columns(exc):
            raise
        await db.rollback()
        return {}
    result: dict[tuple[int, Optional[str], str], "PlayerRollingStats"] = {}
    for r in rows.fetchall():
        stats = PlayerRollingStats(*r)
        result[(stats.player_id, stats.surface, stats.split_value or "")] = stats
    return result



@dataclass(frozen=True)
class PlayerHeader:
    id: int
    name: str
    tour: str
    hand: Optional[str]
    country: Optional[str]
    birth_date: Optional[date]


async def get_player_header(db: AsyncSession, player_id: int) -> Optional[PlayerHeader]:
    row = await db.execute(
        text("SELECT id, name, tour, hand, country, birth_date FROM players WHERE id = :id"),
        {"id": player_id},
    )
    r = row.fetchone()
    return PlayerHeader(*r) if r else None


async def get_elo_history(db: AsyncSession, player_id: int) -> list[EloSnapshot]:
    """Every stored ELO snapshot for the player, oldest first."""
    rows = await db.execute(
        text("""
            SELECT as_of_date, elo, elo_hard, elo_clay, elo_grass
            FROM player_elo
            WHERE player_id = :id
            ORDER BY as_of_date
        """),
        {"id": player_id},
    )
    return [EloSnapshot(*r) for r in rows.fetchall()]


async def get_elo_tour_rank(
    db: AsyncSession, player_id: int, tour: str, as_of: date,
) -> tuple[Optional[int], int]:
    """(rank, field size) by overall ELO among same-tour players on one snapshot date.

    Rank is 1 plus the number strictly higher, so tied ratings share a rank.
    """
    row = await db.execute(
        text("""
            WITH mine AS (
                SELECT elo FROM player_elo WHERE player_id = :id AND as_of_date = :as_of
            )
            SELECT
                CASE WHEN (SELECT elo FROM mine) IS NULL THEN NULL
                     ELSE 1 + COUNT(*) FILTER (WHERE e.elo > (SELECT elo FROM mine)) END,
                COUNT(*)
            FROM player_elo e
            JOIN players p ON p.id = e.player_id
            WHERE e.as_of_date = :as_of AND p.tour = :tour AND e.elo IS NOT NULL
        """),
        {"id": player_id, "tour": tour, "as_of": as_of},
    )
    rank, field_size = row.fetchone()
    return rank, field_size


async def get_player_aliases(db: AsyncSession, player_id: int) -> list[str]:
    rows = await db.execute(
        text("SELECT alias_name FROM player_aliases WHERE canonical_player_id = :id ORDER BY alias_name"),
        {"id": player_id},
    )
    return [r[0] for r in rows.fetchall()]


async def get_rolling_stats_computed_at(db: AsyncSession, player_id: int) -> Optional[datetime]:
    row = await db.execute(
        text("SELECT MAX(computed_at) FROM player_rolling_stats WHERE player_id = :id"),
        {"id": player_id},
    )
    return row.scalar()


@dataclass(frozen=True)
class SurfaceServeReturnRow:
    player_id: int
    surface: Optional[str]
    matches: int
    stats: ServeReturnStats


async def get_tour_serve_return_rows(db: AsyncSession, tour: str) -> list[SurfaceServeReturnRow]:
    """Each same-tour player's latest 52-week overall row, per surface (NULL = all surfaces)."""
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (r.player_id, r.surface)
                r.player_id, r.surface, COALESCE(r.matches_count, 0),
                r.hold_pct, r.break_pct, r.first_in_pct, r.first_won_pct, r.second_won_pct,
                r.ret_pts_won, r.aces_per_game, r.df_per_game
            FROM player_rolling_stats r
            JOIN players p ON p.id = r.player_id
            WHERE p.tour = :tour
              AND r.stat_period = 'last_52w'
              AND r.split_type = 'overall'
              AND r.split_value = 'all'
            ORDER BY r.player_id, r.surface, r.computed_at DESC
        """),
        {"tour": tour},
    )
    return [
        SurfaceServeReturnRow(r[0], r[1], r[2], ServeReturnStats(*(None if v is None else float(v) for v in r[3:])))
        for r in rows.fetchall()
    ]
