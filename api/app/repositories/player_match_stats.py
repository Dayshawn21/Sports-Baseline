from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.box_score_join import (
    WINDOW_AFTER,
    WINDOW_BEFORE,
    BoxScoreCandidate,
    JoinResult,
    join_box_score,
    winner_first,
)


@dataclass(frozen=True)
class PlayerMatchStat:
    player_id: int
    source_match_key: str
    match_date: date
    surface: Optional[str]
    result: Optional[str]
    aces: Optional[int]
    double_faults: Optional[int]
    service_games: Optional[int]
    break_points_faced: Optional[int]
    break_points_saved: Optional[int]
    break_chances_created: Optional[int]
    break_points_converted: Optional[int]
    opponent_name: Optional[str] = None
    round: Optional[str] = None
    tournament: Optional[str] = None
    score: Optional[str] = None


async def upsert_player_match_stats(db: AsyncSession, stats: list[PlayerMatchStat]) -> None:
    """Store player-oriented raw match statistics without duplicating a source row."""
    if not stats:
        return
    await db.execute(
        text(
            """
            INSERT INTO player_match_stats (
                player_id, source, source_match_key, match_date, surface, result,
                aces, double_faults, service_games, break_points_faced,
                break_points_saved, break_chances_created, break_points_converted,
                opponent_name, round, tournament, score, fetched_at
            ) VALUES (
                :player_id, 'tennisabstract', :source_match_key, :match_date, :surface, :result,
                :aces, :double_faults, :service_games, :break_points_faced,
                :break_points_saved, :break_chances_created, :break_points_converted,
                :opponent_name, :round, :tournament, :score, now()
            )
            ON CONFLICT ON CONSTRAINT uq_player_match_stats_source DO UPDATE SET
                -- One row now lives through placeholder, score-only and full stats, and
                -- TennisAbstract never retracts what it published: a blank never erases.
                match_date = EXCLUDED.match_date,
                surface = COALESCE(EXCLUDED.surface, player_match_stats.surface),
                result = COALESCE(EXCLUDED.result, player_match_stats.result),
                aces = COALESCE(EXCLUDED.aces, player_match_stats.aces),
                double_faults = COALESCE(EXCLUDED.double_faults, player_match_stats.double_faults),
                service_games = COALESCE(EXCLUDED.service_games, player_match_stats.service_games),
                break_points_faced = COALESCE(EXCLUDED.break_points_faced, player_match_stats.break_points_faced),
                break_points_saved = COALESCE(EXCLUDED.break_points_saved, player_match_stats.break_points_saved),
                break_chances_created = COALESCE(EXCLUDED.break_chances_created, player_match_stats.break_chances_created),
                break_points_converted = COALESCE(EXCLUDED.break_points_converted, player_match_stats.break_points_converted),
                opponent_name = EXCLUDED.opponent_name,
                round = EXCLUDED.round,
                tournament = EXCLUDED.tournament,
                score = COALESCE(EXCLUDED.score, player_match_stats.score),
                fetched_at = now()
            """
        ),
        [
            {
                "player_id": stat.player_id,
                "source_match_key": stat.source_match_key,
                "match_date": stat.match_date,
                "surface": stat.surface,
                "result": stat.result,
                "aces": stat.aces,
                "double_faults": stat.double_faults,
                "service_games": stat.service_games,
                "break_points_faced": stat.break_points_faced,
                "break_points_saved": stat.break_points_saved,
                "break_chances_created": stat.break_chances_created,
                "break_points_converted": stat.break_points_converted,
                "opponent_name": stat.opponent_name,
                "round": stat.round,
                "tournament": stat.tournament,
                "score": stat.score,
            }
            for stat in stats
        ],
    )


@dataclass(frozen=True)
class BoxScoreContext:
    """What join_box_score needs for one player in one settled match."""

    match_date: date
    result: str
    opponent_name: str
    match_score_winner_first: str | None
    candidates: list[BoxScoreCandidate] = field(default_factory=list)

    def join(self) -> JoinResult:
        return join_box_score(
            self.match_date, self.result, self.opponent_name, self.match_score_winner_first, self.candidates,
        )


def group_candidate_rows(rows: list[dict]) -> dict[tuple[int, int], BoxScoreContext]:
    """One context per (player, match); a pair with no box score in the window keeps an empty list."""
    grouped: dict[tuple[int, int], BoxScoreContext] = {}
    for row in rows:
        key = (row["player_id"], row["match_id"])
        if key not in grouped:
            grouped[key] = BoxScoreContext(
                match_date=row["match_date"],
                result=row["result"],
                opponent_name=row["opponent_name"],
                match_score_winner_first=winner_first(row["match_score"], row["p1_won"]),
            )
        if row["stats_id"] is not None:
            grouped[key].candidates.append(BoxScoreCandidate(
                stats_id=row["stats_id"],
                match_date=row["stats_date"],
                result=row["stats_result"],
                opponent_name=row["stats_opponent_name"],
                score=row["stats_score"],
                aces=row["aces"],
                double_faults=row["double_faults"],
                break_points_converted=row["break_points_converted"],
                break_chances_created=row["break_chances_created"],
                break_points_faced=row.get("break_points_faced"),
                break_points_saved=row.get("break_points_saved"),
            ))
    return grouped


async def get_box_score_candidates(
    db: AsyncSession, pairs: list[tuple[int, int]],
) -> dict[tuple[int, int], BoxScoreContext]:
    """Every box score a settled (player, match) pair could belong to, with the match's own facts.

    The window is wide on purpose; join_box_score narrows it by opponent and score.
    """
    if not pairs:
        return {}
    rows = await db.execute(
        text("""
            WITH pairs AS (
                SELECT * FROM unnest(CAST(:player_ids AS bigint[]), CAST(:match_ids AS bigint[]))
                    AS t(player_id, match_id)
            )
            SELECT
                pr.player_id, pr.match_id, m.match_date, m.score AS match_score,
                (m.winner_id = m.p1_id) AS p1_won,
                CASE WHEN m.winner_id = pr.player_id THEN 'W' ELSE 'L' END AS result,
                opp.name AS opponent_name,
                s.id AS stats_id, s.match_date AS stats_date, s.result AS stats_result,
                s.opponent_name AS stats_opponent_name, s.score AS stats_score,
                s.aces, s.double_faults, s.break_points_converted, s.break_chances_created,
                s.break_points_faced, s.break_points_saved
            FROM pairs pr
            JOIN matches m ON m.id = pr.match_id AND m.winner_id IS NOT NULL
            JOIN players opp ON opp.id = CASE WHEN m.p1_id = pr.player_id THEN m.p2_id ELSE m.p1_id END
            LEFT JOIN player_match_stats s
              ON s.player_id = pr.player_id
             AND s.match_date BETWEEN m.match_date - CAST(:days_before AS int)
                                  AND m.match_date + CAST(:days_after AS int)
            ORDER BY pr.player_id, pr.match_id, s.id
        """),
        {
            "player_ids": [player_id for player_id, _ in pairs],
            "match_ids": [match_id for _, match_id in pairs],
            "days_before": WINDOW_BEFORE.days,
            "days_after": WINDOW_AFTER.days,
        },
    )
    return group_candidate_rows([dict(r) for r in rows.mappings().all()])
