from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.player_match_stats import get_box_score_candidates


@dataclass
class Match:
    id: int
    match_key: str
    match_date: date
    start_utc: Optional[datetime]
    tour: str
    surface: Optional[str]
    tournament: Optional[str]
    round: Optional[str]
    best_of: Optional[int]
    p1_id: int
    p2_id: int
    p1_rank: Optional[int]
    p2_rank: Optional[int]
    winner_id: Optional[int]
    status: str
    sofascore_id: Optional[int]
    livetennis_id: Optional[int] = None


@dataclass(frozen=True)
class MatchPlayer:
    id: int
    name: str


@dataclass(frozen=True)
class RecentMatchResult:
    match_date: date
    opponent_name: str
    score: Optional[str]
    result: str
    aces: Optional[int] = None
    double_faults: Optional[int] = None
    break_chances_created: Optional[int] = None
    break_points_converted: Optional[int] = None


async def get_match_players(db: AsyncSession, match_id: int) -> tuple[date, list[MatchPlayer]] | None:
    row = await db.execute(
        text("""
            SELECT m.match_date, p1.id, p1.name, p2.id, p2.name
            FROM matches m
            JOIN players p1 ON p1.id = m.p1_id
            JOIN players p2 ON p2.id = m.p2_id
            WHERE m.id = :match_id
        """),
        {"match_id": match_id},
    )
    result = row.fetchone()
    if result is None:
        return None
    return result[0], [MatchPlayer(id=result[1], name=result[2]), MatchPlayer(id=result[3], name=result[4])]


def _flip_score(score: str | None) -> str | None:
    """Stored scores read from p1's side; "3-6 5-7" for p2 is "6-3 7-5"."""
    if score is None:
        return None
    return " ".join("-".join(reversed(part.split("-"))) if part.count("-") == 1 else part for part in score.split())


@dataclass(frozen=True)
class MatchMeeting:
    match_date: date
    tournament: Optional[str]
    round: Optional[str]
    surface: Optional[str]
    # Winner first, the way tennis scores are read; p1 first when the winner is unknown.
    score: Optional[str]
    # "p1" or "p2" of the match being viewed, not of the stored meeting.
    winner_side: Optional[str]


def orient_meeting(
    stored_p1_id: int,
    winner_id: Optional[int],
    score: Optional[str],
    p1_id: int,
    p2_id: int,
) -> tuple[Optional[str], Optional[str]]:
    """(winner_side, score) for a past meeting, whichever way round it was stored."""
    if winner_id == p1_id:
        side = "p1"
    elif winner_id == p2_id:
        side = "p2"
    else:
        side = None
    reference = winner_id if side else p1_id
    return side, score if stored_p1_id == reference else _flip_score(score)


async def get_meetings(
    db: AsyncSession, p1_id: int, p2_id: int, before: date
) -> list[MatchMeeting]:
    """Completed matches between two players dated before `before`, newest first."""
    rows = await db.execute(
        text("""
            SELECT match_date, tournament, round, surface, score, winner_id, p1_id
            FROM matches
            WHERE status = 'completed'
              AND ((p1_id = :a AND p2_id = :b) OR (p1_id = :b AND p2_id = :a))
              AND match_date < :before
            ORDER BY match_date DESC, id DESC
        """),
        {"a": p1_id, "b": p2_id, "before": before},
    )
    meetings = []
    for match_date, tournament, round_name, surface, score, winner_id, stored_p1 in rows.fetchall():
        side, oriented = orient_meeting(stored_p1, winner_id, score, p1_id, p2_id)
        meetings.append(MatchMeeting(match_date, tournament, round_name, surface, oriented, side))
    return meetings


async def get_recent_completed_matches(
    db: AsyncSession, player_ids: list[int], before_date: date, limit: int = 5
) -> dict[int, list[RecentMatchResult]]:
    if not player_ids:
        return {}
    rows = await db.execute(
        text("""
            WITH player_matches AS (
                SELECT m.id, m.match_date, m.score, m.p1_id AS player_id, FALSE AS is_p2,
                       p2.name AS opponent_name,
                       CASE WHEN m.winner_id = m.p1_id THEN 'W' ELSE 'L' END AS result
                FROM matches m
                JOIN players p2 ON p2.id = m.p2_id
                WHERE m.p1_id = ANY(:player_ids)
                  AND m.status = 'completed'
                  AND m.winner_id IS NOT NULL
                  AND m.match_date < :before_date
                UNION ALL
                SELECT m.id, m.match_date, m.score, m.p2_id AS player_id, TRUE AS is_p2,
                       p1.name AS opponent_name,
                       CASE WHEN m.winner_id = m.p2_id THEN 'W' ELSE 'L' END AS result
                FROM matches m
                JOIN players p1 ON p1.id = m.p1_id
                WHERE m.p2_id = ANY(:player_ids)
                  AND m.status = 'completed'
                  AND m.winner_id IS NOT NULL
                  AND m.match_date < :before_date
            ), ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY match_date DESC, id DESC) AS row_number
                FROM player_matches
            )
            SELECT player_id, match_date, opponent_name, score, result, is_p2, id
            FROM ranked
            WHERE row_number <= :limit
            ORDER BY player_id, match_date DESC, id DESC
        """),
        {"player_ids": player_ids, "before_date": before_date, "limit": limit},
    )
    recent = rows.fetchall()
    # Box scores are dated by tournament start, so an exact-date join found few
    # and could attach another round's numbers; join_box_score matches by
    # opponent and set score instead.
    joins = {
        pair: context.join()
        for pair, context in (await get_box_score_candidates(
            db, [(row[0], row[6]) for row in recent], sources=("tennisabstract", "tennismylife"),
        )).items()
    }
    result: dict[int, list[RecentMatchResult]] = {player_id: [] for player_id in player_ids}
    for player_id, match_date, opponent_name, score, outcome, is_p2, match_id in recent:
        joined = joins.get((player_id, match_id))
        box = joined.candidate if joined else None
        result[player_id].append(
            RecentMatchResult(
                match_date=match_date, opponent_name=opponent_name,
                score=_flip_score(score) if is_p2 else score, result=outcome,
                aces=box.aces if box else None,
                double_faults=box.double_faults if box else None,
                break_chances_created=box.break_chances_created if box else None,
                break_points_converted=box.break_points_converted if box else None,
            )
        )
    return result


def _orient_h2h_record(
    requested_p1_id: int,
    requested_p2_id: int,
    row_p1_id: int,
    row_p2_id: int,
    p1_wins: int,
    p2_wins: int,
) -> Optional[dict]:
    if requested_p1_id == row_p1_id and requested_p2_id == row_p2_id:
        return {"p1_wins": p1_wins, "p2_wins": p2_wins}
    if requested_p1_id == row_p2_id and requested_p2_id == row_p1_id:
        return {"p1_wins": p2_wins, "p2_wins": p1_wins}
    return None


async def get_upcoming(db: AsyncSession, match_date: date | list[date]) -> list[Match]:
    dates = match_date if isinstance(match_date, list) else [match_date]
    rows = await db.execute(
        text("""
            SELECT id, match_key, match_date, start_utc, tour, surface, tournament, round, best_of,
                   p1_id, p2_id, p1_rank, p2_rank, winner_id, status, sofascore_id, livetennis_id
            FROM matches
            WHERE match_date = ANY(:dates)
              AND status IN ('scheduled', 'live')
            ORDER BY start_utc ASC NULLS LAST
        """),
        {"dates": dates},
    )
    return [Match(*r) for r in rows.fetchall()]


@dataclass(frozen=True)
class MatchMeta:
    """Match columns the predictor never reads, kept out of the positional `Match`."""
    indoor: Optional[bool]
    score: Optional[str]


async def get_match(db: AsyncSession, match_id: int) -> tuple[Match, MatchMeta] | None:
    """One match in any status, for the match page."""
    rows = await db.execute(
        text("""
            SELECT id, match_key, match_date, start_utc, tour, surface, tournament, round, best_of,
                   p1_id, p2_id, p1_rank, p2_rank, winner_id, status, sofascore_id, livetennis_id,
                   indoor, score
            FROM matches
            WHERE id = :mid
        """),
        {"mid": match_id},
    )
    r = rows.fetchone()
    if r is None:
        return None
    return Match(*r[:17]), MatchMeta(indoor=r[17], score=r[18])


@dataclass(frozen=True)
class OddsHistoryRow:
    book: str
    p1_odds: Optional[int]
    p2_odds: Optional[int]
    line: Optional[float]
    fetched_at: datetime


async def get_odds_history(
    db: AsyncSession, match_id: int, market: str, before: Optional[datetime]
) -> list[OddsHistoryRow]:
    """Every stored price for one market, oldest first, capped at the start when known."""
    rows = await db.execute(
        text("""
            SELECT book, p1_odds, p2_odds, line, fetched_at
            FROM match_odds
            WHERE match_id = :mid AND market = :mkt
              AND (CAST(:before AS timestamptz) IS NULL OR fetched_at < :before)
            ORDER BY fetched_at ASC, book ASC
        """),
        {"mid": match_id, "mkt": market, "before": before},
    )
    return [
        OddsHistoryRow(book=r[0], p1_odds=r[1], p2_odds=r[2],
                       line=float(r[3]) if r[3] is not None else None, fetched_at=r[4])
        for r in rows.fetchall()
    ]


async def get_match_by_key(db: AsyncSession, match_key: str) -> Optional[Match]:
    row = await db.execute(
        text("""
            SELECT id, match_key, match_date, start_utc, tour, surface, tournament, round, best_of,
                   p1_id, p2_id, p1_rank, p2_rank, winner_id, status, sofascore_id, livetennis_id
            FROM matches WHERE match_key = :key
        """),
        {"key": match_key},
    )
    r = row.fetchone()
    return Match(*r) if r else None


async def upsert_match(
    db: AsyncSession,
    match_key: str,
    match_date: date,
    tour: str,
    p1_id: int,
    p2_id: int,
    surface: Optional[str] = None,
    tournament: Optional[str] = None,
    round_: Optional[str] = None,
    best_of: Optional[int] = None,
    p1_rank: Optional[int] = None,
    p2_rank: Optional[int] = None,
    sofascore_id: Optional[int] = None,
    status: str = "scheduled",
    start_utc=None,
    winner_id: Optional[int] = None,
    score: Optional[str] = None,
    livetennis_id: Optional[int] = None,
    indoor: Optional[bool] = None,
    tournament_id: Optional[str] = None,
    p1_ranking_points: Optional[int] = None,
    p2_ranking_points: Optional[int] = None,
    p1_ranking_movement: Optional[str] = None,
    p2_ranking_movement: Optional[str] = None,
) -> int:
    if livetennis_id is not None:
        # Same guard as upsert_player: idx_matches_livetennis_id is UNIQUE, and a
        # match whose key changed (re-resolved player names shift match_key) would
        # otherwise collide with the row still holding its provider id and abort
        # the run.
        await db.execute(
            text(
                "UPDATE matches SET livetennis_id = NULL "
                "WHERE livetennis_id = :lt AND match_key <> :key"
            ),
            {"lt": livetennis_id, "key": match_key},
        )
    row = await db.execute(
        text("""
            INSERT INTO matches
              (match_key, match_date, start_utc, tour, surface, tournament, round, best_of,
               p1_id, p2_id, p1_rank, p2_rank, sofascore_id, status, winner_id, score, livetennis_id,
               indoor, tournament_id, p1_ranking_points, p2_ranking_points,
               p1_ranking_movement, p2_ranking_movement)
            VALUES
              (:key, :dt, :start_utc, :tour, :surf, :tourn, :round, :best_of,
               :p1, :p2, :p1r, :p2r, :ss_id, :status, :winner_id, :score, :lt_id,
               :indoor, :tourn_id, :p1rp, :p2rp, :p1rm, :p2rm)
            ON CONFLICT (match_key) DO UPDATE
              SET match_date   = EXCLUDED.match_date,
                  start_utc    = EXCLUDED.start_utc,
                  surface      = COALESCE(EXCLUDED.surface, matches.surface),
                  tournament   = COALESCE(EXCLUDED.tournament, matches.tournament),
                  round        = COALESCE(EXCLUDED.round, matches.round),
                  best_of      = COALESCE(EXCLUDED.best_of, matches.best_of),
                  p1_rank      = COALESCE(EXCLUDED.p1_rank, matches.p1_rank),
                  p2_rank      = COALESCE(EXCLUDED.p2_rank, matches.p2_rank),
                  sofascore_id = COALESCE(EXCLUDED.sofascore_id, matches.sofascore_id),
                  livetennis_id= COALESCE(EXCLUDED.livetennis_id, matches.livetennis_id),
                  winner_id    = COALESCE(EXCLUDED.winner_id, matches.winner_id),
                  score        = COALESCE(EXCLUDED.score, matches.score),
                  indoor       = COALESCE(EXCLUDED.indoor, matches.indoor),
                  tournament_id= COALESCE(EXCLUDED.tournament_id, matches.tournament_id),
                  p1_ranking_points = COALESCE(EXCLUDED.p1_ranking_points, matches.p1_ranking_points),
                  p2_ranking_points = COALESCE(EXCLUDED.p2_ranking_points, matches.p2_ranking_points),
                  p1_ranking_movement = COALESCE(EXCLUDED.p1_ranking_movement, matches.p1_ranking_movement),
                  p2_ranking_movement = COALESCE(EXCLUDED.p2_ranking_movement, matches.p2_ranking_movement),
                  status       = EXCLUDED.status,
                  updated_at   = now()
            RETURNING id
        """),
        {
            "key": match_key, "dt": match_date, "start_utc": start_utc, "tour": tour.upper(),
            "surf": surface, "tourn": tournament, "round": round_, "best_of": best_of,
            "p1": p1_id, "p2": p2_id, "p1r": p1_rank, "p2r": p2_rank,
            "ss_id": sofascore_id, "status": status,
            "winner_id": winner_id, "score": score, "lt_id": livetennis_id,
            "indoor": indoor, "tourn_id": tournament_id,
            "p1rp": p1_ranking_points, "p2rp": p2_ranking_points,
            "p1rm": p1_ranking_movement, "p2rm": p2_ranking_movement,
        },
    )
    return row.scalar_one()


async def mark_completed(db: AsyncSession, match_id: int, winner_id: int, score: str) -> None:
    await db.execute(
        text("""
            UPDATE matches
            SET winner_id = :wid, score = :score, status = 'completed', updated_at = now()
            WHERE id = :mid
        """),
        {"wid": winner_id, "score": score, "mid": match_id},
    )


async def upsert_odds(
    db: AsyncSession,
    match_id: int,
    book: str,
    market: str,
    p1_odds: Optional[int],
    p2_odds: Optional[int],
    line: Optional[float] = None,
) -> None:
    await db.execute(
        text("""
            INSERT INTO match_odds (match_id, book, market, p1_odds, p2_odds, line)
            VALUES (:mid, :book, :market, :p1, :p2, :line)
        """),
        {"mid": match_id, "book": book, "market": market, "p1": p1_odds, "p2": p2_odds, "line": line},
    )


# Every book in one odds run shares a fetched_at (the run commits once), so the book
# must break the tie or DISTINCT ON picks one arbitrarily. Bet365 was stored as
# betonline.ag before it got its own name, so both spellings share a rank.
_BOOK_PRIORITY_SQL = """
    CASE LOWER(book)
        WHEN 'draftkings' THEN 0
        WHEN 'bet365' THEN 1
        WHEN 'betonline.ag' THEN 1
        WHEN 'betonline' THEN 1
        WHEN 'betfair exchange' THEN 2
        ELSE 3
    END
"""


async def get_latest_odds(db: AsyncSession, match_id: int, market: str = "moneyline") -> Optional[dict]:
    row = await db.execute(
        text("""
            SELECT book, p1_odds, p2_odds, line, fetched_at
            FROM match_odds
            WHERE match_id = :mid AND market = :mkt
            ORDER BY fetched_at DESC, """ + _BOOK_PRIORITY_SQL + """
            LIMIT 1
        """),
        {"mid": match_id, "mkt": market},
    )
    r = row.fetchone()
    if not r:
        return None
    return {"book": r[0], "p1_odds": r[1], "p2_odds": r[2], "line": r[3], "fetched_at": r[4]}


async def find_match_for_player(
    db: AsyncSession, player_id: int, match_date: date, start_time: Optional[datetime] = None
) -> Optional[int]:
    """Return the match_id for a player on a given date, or None if not found."""
    if start_time is not None:
        # An unplayed candidate within 12h, mirroring the relink lateral in
        # repositories/props.py. Without these, a prop whose day was resolved one
        # date early matched the player's finished match from the day before,
        # 21h away, and every projection then ran on that match's odds and
        # opponent. 12h keeps the legitimate late links and excludes the
        # wrong-day cluster past 21h.
        row = await db.execute(
            text("""
                SELECT id FROM matches
                WHERE (p1_id = :pid OR p2_id = :pid)
                  AND match_date = :dt
                  AND status NOT IN ('completed', 'cancelled')
                  -- A match with no start time still ranks last in the ORDER BY.
                  AND (
                        start_utc IS NULL
                     OR ABS(EXTRACT(EPOCH FROM (start_utc - :start_time))) <= 12 * 3600
                  )
                ORDER BY
                  CASE WHEN start_utc IS NULL THEN 1 ELSE 0 END,
                  ABS(EXTRACT(EPOCH FROM (start_utc - :start_time))) ASC,
                  id ASC
                LIMIT 1
            """),
            {"pid": player_id, "dt": match_date, "start_time": start_time},
        )
        r = row.fetchone()
        return r[0] if r else None

    row = await db.execute(
        text("""
            SELECT id FROM matches
            WHERE (p1_id = :pid OR p2_id = :pid)
              AND match_date = :dt
            ORDER BY start_utc ASC NULLS LAST
            LIMIT 1
        """),
        {"pid": player_id, "dt": match_date},
    )
    r = row.fetchone()
    return r[0] if r else None


async def get_h2h(db: AsyncSession, p1_id: int, p2_id: int, surface: Optional[str] = None) -> dict:
    row = await db.execute(
        text("""
            SELECT p1_id, p2_id, p1_wins, p2_wins FROM h2h
            WHERE ((p1_id = :p1 AND p2_id = :p2) OR (p1_id = :p2 AND p2_id = :p1))
              AND (surface = :surf OR (:surf IS NULL AND surface IS NULL))
            ORDER BY CASE WHEN p1_id = :p1 AND p2_id = :p2 THEN 0 ELSE 1 END
        """),
        {"p1": p1_id, "p2": p2_id, "surf": surface},
    )
    for r in row.fetchall():
        oriented = _orient_h2h_record(p1_id, p2_id, r[0], r[1], r[2], r[3])
        if oriented is not None:
            return oriented
    return {"p1_wins": 0, "p2_wins": 0}


async def get_player_match_history(
    db: AsyncSession, player_id: int, before_date: date
) -> dict:
    """Fetch match history stats for a player: rest days, experience, streak,
    and recent match counts (10d, 30d).

    Returns dict with keys: rest_days, experience, streak, matches_10d, matches_30d
    """
    # Single query for aggregate stats
    agg_row = await db.execute(
        text("""
            SELECT
                MAX(match_date) AS last_match_date,
                COUNT(*) AS total_matches,
                COUNT(*) FILTER (WHERE match_date >= :dt - 10) AS m10d,
                COUNT(*) FILTER (WHERE match_date >= :dt - 30) AS m30d
            FROM matches
            WHERE (p1_id = :pid OR p2_id = :pid)
              AND status = 'completed'
              AND match_date < :dt
        """),
        {"pid": player_id, "dt": before_date},
    )
    agg = agg_row.fetchone()

    rest_days = None
    if agg and agg[0] is not None:
        rest_days = float((before_date - agg[0]).days)

    experience = float(agg[1]) if agg else 0.0
    matches_10d = float(agg[2]) if agg else 0.0
    matches_30d = float(agg[3]) if agg else 0.0

    # Streak + last surface: fetch last 20 results
    streak_rows = await db.execute(
        text("""
            SELECT winner_id, surface FROM matches
            WHERE (p1_id = :pid OR p2_id = :pid)
              AND status = 'completed'
              AND match_date < :dt
              AND winner_id IS NOT NULL
            ORDER BY match_date DESC, id DESC
            LIMIT 20
        """),
        {"pid": player_id, "dt": before_date},
    )
    streak = 0.0
    last_surface = None
    results = streak_rows.fetchall()
    if results:
        last_surface = results[0][1]  # surface of most recent match
        first_won = results[0][0] == player_id
        count = 0
        for r in results:
            if (r[0] == player_id) == first_won:
                count += 1
            else:
                break
        streak = float(count) if first_won else float(-count)

    return {
        "rest_days": rest_days,
        "experience": experience,
        "matches_10d": matches_10d,
        "matches_30d": matches_30d,
        "streak": streak,
        "last_surface": last_surface,
    }


async def get_latest_odds_batch(
    db: AsyncSession, match_ids: list[int], market: str = "moneyline"
) -> dict[int, dict]:
    """Fetch most recent odds for multiple matches in one query."""
    if not match_ids:
        return {}
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (match_id)
                match_id, book, p1_odds, p2_odds, line, fetched_at
            FROM match_odds
            WHERE match_id = ANY(:ids) AND market = :mkt
            ORDER BY match_id, fetched_at DESC, """ + _BOOK_PRIORITY_SQL + """
        """),
        {"ids": match_ids, "mkt": market},
    )
    result = {}
    for r in rows.fetchall():
        result[r[0]] = {"book": r[1], "p1_odds": r[2], "p2_odds": r[3], "line": r[4], "fetched_at": r[5]}
    return result


async def get_all_market_odds_batch(
    db: AsyncSession, match_ids: list[int],
) -> dict[int, dict[str, dict]]:
    """Fetch latest odds for ALL markets for multiple matches.

    Returns: {match_id: {market: {book, p1_odds, p2_odds, line, fetched_at}}}
    """
    if not match_ids:
        return {}
    rows = await db.execute(
        text("""
            SELECT DISTINCT ON (match_id, market)
                match_id, market, book, p1_odds, p2_odds, line, fetched_at
            FROM match_odds
            WHERE match_id = ANY(:ids)
            ORDER BY match_id, market, fetched_at DESC, """ + _BOOK_PRIORITY_SQL + """
        """),
        {"ids": match_ids},
    )
    result: dict[int, dict[str, dict]] = {}
    for r in rows.fetchall():
        mid, mkt = r[0], r[1]
        if mid not in result:
            result[mid] = {}
        result[mid][mkt] = {
            "book": r[2], "p1_odds": r[3], "p2_odds": r[4],
            "line": r[5], "fetched_at": r[6],
        }
    return result


async def get_h2h_batch(
    db: AsyncSession,
    pairs: list[tuple[int, int, Optional[str]]],
) -> dict[tuple[int, int, Optional[str]], dict]:
    """Fetch h2h records for multiple (p1_id, p2_id, surface) pairs in one query."""
    if not pairs:
        return {}
    # One id list for both sides: an h2h row is stored in whichever order the
    # players first met, which need not match the order they appear in a match.
    # Splitting these into p1/p2 lists silently dropped every reversed row.
    player_ids = list({pid for pair in pairs for pid in pair[:2]})
    rows = await db.execute(
        text("""
            SELECT p1_id, p2_id, surface, p1_wins, p2_wins FROM h2h
            WHERE p1_id = ANY(:ids) AND p2_id = ANY(:ids)
        """),
        {"ids": player_ids},
    )
    requested = set(pairs)
    result: dict[tuple, dict] = {}
    for r in rows.fetchall():
        direct_key = (r[0], r[1], r[2])
        reverse_key = (r[1], r[0], r[2])
        if direct_key in requested and direct_key not in result:
            result[direct_key] = {"p1_wins": r[3], "p2_wins": r[4]}
        if reverse_key in requested and reverse_key not in result:
            result[reverse_key] = {"p1_wins": r[4], "p2_wins": r[3]}
    return result


async def get_player_match_history_batch(
    db: AsyncSession, player_ids: list[int], before_date: date
) -> dict[int, dict]:
    """Fetch match history stats for multiple players in 2 queries."""
    if not player_ids:
        return {}

    agg_rows = await db.execute(
        text("""
            WITH pm AS (
                SELECT p1_id AS player_id, match_date FROM matches
                WHERE p1_id = ANY(:pids) AND status = 'completed' AND match_date < :dt
                UNION ALL
                SELECT p2_id AS player_id, match_date FROM matches
                WHERE p2_id = ANY(:pids) AND status = 'completed' AND match_date < :dt
            )
            SELECT
                player_id,
                MAX(match_date) AS last_match_date,
                COUNT(*) AS total_matches,
                COUNT(*) FILTER (WHERE match_date >= :dt - 10) AS m10d,
                COUNT(*) FILTER (WHERE match_date >= :dt - 30) AS m30d
            FROM pm
            GROUP BY player_id
        """),
        {"pids": player_ids, "dt": before_date},
    )
    agg_data: dict[int, dict] = {}
    for r in agg_rows.fetchall():
        agg_data[r[0]] = {"last_match_date": r[1], "total_matches": r[2], "m10d": r[3], "m30d": r[4]}

    streak_rows = await db.execute(
        text("""
            WITH pm AS (
                SELECT p1_id AS player_id, match_date, winner_id, surface, id FROM matches
                WHERE p1_id = ANY(:pids) AND status = 'completed' AND match_date < :dt AND winner_id IS NOT NULL
                UNION ALL
                SELECT p2_id AS player_id, match_date, winner_id, surface, id FROM matches
                WHERE p2_id = ANY(:pids) AND status = 'completed' AND match_date < :dt AND winner_id IS NOT NULL
            ),
            ranked AS (
                SELECT *, ROW_NUMBER() OVER (PARTITION BY player_id ORDER BY match_date DESC, id DESC) AS rn
                FROM pm
            )
            SELECT player_id, winner_id, surface FROM ranked WHERE rn <= 20
            ORDER BY player_id, match_date DESC, id DESC
        """),
        {"pids": player_ids, "dt": before_date},
    )
    from collections import defaultdict
    player_results: dict[int, list[tuple]] = defaultdict(list)
    for r in streak_rows.fetchall():
        player_results[r[0]].append((r[1], r[2]))  # (winner_id, surface)

    result: dict[int, dict] = {}
    default_history = {"rest_days": None, "experience": 0.0, "matches_10d": 0.0, "matches_30d": 0.0, "streak": 0.0, "last_surface": None}
    for pid in player_ids:
        agg = agg_data.get(pid)
        rest_days = None
        if agg and agg["last_match_date"] is not None:
            rest_days = float((before_date - agg["last_match_date"]).days)

        results_list = player_results.get(pid, [])
        streak = 0.0
        last_surface = None
        if results_list:
            last_surface = results_list[0][1]
            first_won = results_list[0][0] == pid
            count = 0
            for r in results_list:
                if (r[0] == pid) == first_won:
                    count += 1
                else:
                    break
            streak = float(count) if first_won else float(-count)

        result[pid] = {
            "rest_days": rest_days,
            "experience": float(agg["total_matches"]) if agg else 0.0,
            "matches_10d": float(agg["m10d"]) if agg else 0.0,
            "matches_30d": float(agg["m30d"]) if agg else 0.0,
            "streak": streak,
            "last_surface": last_surface,
        }
    return result


async def upsert_h2h(db: AsyncSession, p1_id: int, p2_id: int, p1_wins: int, p2_wins: int,
                     surface: Optional[str] = None) -> None:
    # Rows are stored with the lower id first (migration 0013 enforces it with a
    # CHECK), so the same pairing cannot land under two orientations and drift
    # apart. Callers pass match order, which is arbitrary; both readers reorient.
    if p1_id > p2_id:
        p1_id, p2_id = p2_id, p1_id
        p1_wins, p2_wins = p2_wins, p1_wins

    await db.execute(
        text("""
            INSERT INTO h2h (p1_id, p2_id, surface, p1_wins, p2_wins)
            VALUES (:p1, :p2, :surf, :w1, :w2)
            ON CONFLICT (p1_id, p2_id, surface) DO UPDATE
              SET p1_wins = EXCLUDED.p1_wins,
                  p2_wins = EXCLUDED.p2_wins,
                  updated_at = now()
        """),
        {"p1": p1_id, "p2": p2_id, "surf": surface, "w1": p1_wins, "w2": p2_wins},
    )


@dataclass(frozen=True)
class CompletedMatchScore:
    match_id: int
    tour: str
    best_of: int
    p1_id: int
    p2_id: int
    score: str


async def get_completed_match_scores(db: AsyncSession, since: date) -> list[CompletedMatchScore]:
    """Completed ATP and WTA matches with a score, on or after `since`."""
    rows = await db.execute(
        text("""
            SELECT m.id, m.tour, COALESCE(m.best_of, 3), m.p1_id, m.p2_id, m.score
            FROM matches m
            WHERE m.status = 'completed' AND m.winner_id IS NOT NULL AND m.score IS NOT NULL
              AND m.tour IN ('ATP', 'WTA') AND m.match_date >= :since
            ORDER BY m.match_date, m.id
        """),
        {"since": since},
    )
    return [CompletedMatchScore(*row) for row in rows.fetchall()]


@dataclass(frozen=True)
class NextMatch:
    match_id: int
    start_utc: Optional[datetime]
    match_date: date
    tournament: Optional[str]
    round: Optional[str]
    surface: Optional[str]
    opponent_id: int
    opponent_name: str


async def get_next_match(db: AsyncSession, player_id: int, today: date) -> Optional[NextMatch]:
    """The player's live match, else the earliest scheduled one from today on."""
    rows = await db.execute(
        text("""
            SELECT m.id, m.start_utc, m.match_date, m.tournament, m.round, m.surface, o.id, o.name
            FROM matches m
            JOIN players o ON o.id = CASE WHEN m.p1_id = :pid THEN m.p2_id ELSE m.p1_id END
            WHERE :pid IN (m.p1_id, m.p2_id)
              AND (m.status = 'live' OR (m.status = 'scheduled' AND m.match_date >= :today))
            ORDER BY (m.status = 'live') DESC, m.start_utc NULLS LAST, m.id
            LIMIT 1
        """),
        {"pid": player_id, "today": today},
    )
    r = rows.fetchone()
    return NextMatch(*r) if r else None


async def get_latest_rank(db: AsyncSession, player_id: int) -> Optional[int]:
    """The player's rank on their most recent match row that carries one."""
    rows = await db.execute(
        text("""
            SELECT rank FROM (
                SELECT CASE WHEN p1_id = :pid THEN p1_rank ELSE p2_rank END AS rank, match_date, id
                FROM matches
                WHERE :pid IN (p1_id, p2_id)
            ) ranked
            WHERE rank IS NOT NULL
            ORDER BY match_date DESC, id DESC
            LIMIT 1
        """),
        {"pid": player_id},
    )
    return rows.scalar()


@dataclass(frozen=True)
class PlayerMatchLogRow:
    match_id: int
    match_date: date
    tournament: Optional[str]
    round: Optional[str]
    surface: Optional[str]
    best_of: int
    opponent_id: int
    opponent_name: str
    opponent_rank: Optional[int]
    won: bool
    score: Optional[str]
    """Oriented to the player."""


async def get_player_matches(
    db: AsyncSession, player_id: int, *, limit: Optional[int] = None, since: Optional[date] = None,
) -> list[PlayerMatchLogRow]:
    """The player's completed matches with a winner, newest first."""
    rows = await db.execute(
        text("""
            SELECT m.id, m.match_date, m.tournament, m.round, m.surface, COALESCE(m.best_of, 3),
                   o.id, o.name,
                   CASE WHEN m.p1_id = :pid THEN m.p2_rank ELSE m.p1_rank END,
                   (m.winner_id = :pid), m.score, (m.p2_id = :pid)
            FROM matches m
            JOIN players o ON o.id = CASE WHEN m.p1_id = :pid THEN m.p2_id ELSE m.p1_id END
            WHERE :pid IN (m.p1_id, m.p2_id)
              AND m.status = 'completed'
              AND m.winner_id IS NOT NULL
              AND (CAST(:since AS date) IS NULL OR m.match_date >= CAST(:since AS date))
            ORDER BY m.match_date DESC, m.id DESC
            LIMIT :limit
        """),
        {"pid": player_id, "limit": limit, "since": since},
    )
    return [
        PlayerMatchLogRow(*r[:10], score=_flip_score(r[10]) if r[11] else r[10])
        for r in rows.fetchall()
    ]
