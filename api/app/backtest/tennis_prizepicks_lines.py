"""Settle stored PrizePicks tennis lines against final scores and box scores (26b, 26e).

Read-only: it grades PrizePicks' lines, not the app's projections, whose
confidence tiers are computed on page load and cannot be recovered leak-free
(26f). Score-derived stats settle from the match score; aces, double faults and
break points settle only when exactly one box score joins the match.

Run from api/: python -m app.backtest.tennis_prizepicks_lines
"""
from __future__ import annotations

import asyncio
import sys
from collections import Counter
from dataclasses import dataclass
from math import sqrt

from app.core.box_score_join import JoinResult
from app.core.prop_ev import break_even_probability, leg_decimal_odds
from app.core.prop_projection import normalize_stat_type
from app.core.prop_settlement import LineOutcome, resolve_actual, settle
from app.core.tennis_grading import is_completed_score
from app.repositories.props import PrizePicksCoverage, PrizePicksLineRow

Pair = tuple[int, int]

ODDS_TYPES = ("standard", "goblin", "demon")
TOURS = ("ATP", "WTA", "CHALLENGER")


@dataclass(frozen=True)
class SettledLine:
    row: PrizePicksLineRow
    stat: str
    odds_type: str
    actual: int
    outcome: LineOutcome


@dataclass(frozen=True)
class Exclusions:
    live: int
    promo: int
    not_settleable: Counter[str]
    incomplete_score: int
    unjoined: Counter[str]
    """Box-score lines left unsettled, by join reason."""


def settle_rows(
    rows: list[PrizePicksLineRow], joins: dict[Pair, JoinResult] | None = None,
) -> tuple[list[SettledLine], Exclusions]:
    joins = joins or {}
    settled: list[SettledLine] = []
    live = promo = incomplete = 0
    not_settleable: Counter[str] = Counter()
    unjoined: Counter[str] = Counter()
    for row in rows:
        stat = normalize_stat_type(row.stat_type)
        if row.is_live:
            live += 1
            continue
        if row.is_promo:
            promo += 1
            continue
        if not is_completed_score(row.score, row.best_of or 3):
            incomplete += 1
            continue
        actual, reason = resolve_actual(stat, row.score, row.player_is_p1, joins.get((row.player_id, row.match_id)))
        if actual is None:
            if reason == "not_settleable":
                not_settleable[stat] += 1
            else:
                unjoined[str(reason)] += 1
            continue
        odds_type = (row.odds_type or "standard").lower()
        settled.append(SettledLine(row, stat, odds_type, actual, settle(actual, row.line)))
    return settled, Exclusions(live, promo, not_settleable, incomplete, unjoined)


def _row(label: str, lines: list[SettledLine], odds_type: str) -> str:
    n = len(lines)
    counts = Counter(line.outcome for line in lines)
    player_matches = len({(line.row.player_id, line.row.match_id) for line in lines})
    mean_diff = sum(line.actual - line.row.line for line in lines) / n
    decided = counts["over"] + counts["under"]
    hit = counts["over"] / decided if decided else None
    hit_text = "  n/a" if hit is None else f"{hit:6.1%}"
    # Goblin and demon lines stack several per player-stat and move together, so
    # a binomial error bar would claim far more evidence than they carry.
    se_text = f" +/- {sqrt(hit * (1 - hit) / decided):.1%}" if hit is not None and odds_type == "standard" else ""
    decimal = leg_decimal_odds(odds_type, source="prizepicks")
    break_even = f"{break_even_probability(decimal):.1%}" if decimal else "n/a"
    return (f"  {label:<26}{n:>6} {player_matches:>6}  {counts['over'] / n:6.1%} {counts['under'] / n:6.1%} "
            f"{counts['push'] / n:6.1%}  {mean_diff:+6.2f}   {hit_text}{se_text:<10}  {break_even:>6}")


_HEADER = (f"  {'stat':<26}{'lines':>6} {'p-m':>6}  {'over':>6} {'under':>6} {'push':>6}  {'act-ln':>6}   "
           f"{'over hit':<16}  {'b/even':>6}")


def _table(title: str, settled: list[SettledLine], odds_types: tuple[str, ...]) -> list[str]:
    lines = [title, _HEADER]
    for odds_type in odds_types:
        of_type = [line for line in settled if line.odds_type == odds_type]
        lines.append(f" {odds_type} ({len(of_type)} lines)")
        for stat in sorted({line.stat for line in of_type}):
            lines.append(_row(stat, [line for line in of_type if line.stat == stat], odds_type))
    return lines


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.1%}" if whole else "n/a"


def _join_lines(rows: list[PrizePicksLineRow], joins: dict[Pair, JoinResult]) -> list[str]:
    tours = {(row.player_id, row.match_id): row.tour for row in rows}
    lines = []
    for label, group in (("all", None), *((tour, tour) for tour in TOURS)):
        pairs = [pair for pair in joins if group is None or tours.get(pair) == group]
        joined = sum(joins[pair].reason == "joined" for pair in pairs)
        lines.append(f"    {label:<11}{joined:>5} of {len(pairs):>5} ({_share(joined, len(pairs))})")
    return lines


def _coverage_section(
    coverage: PrizePicksCoverage, rows: list[PrizePicksLineRow], joins: dict[Pair, JoinResult],
) -> list[str]:
    settled = coverage.player_matches_settled
    return [
        "Coverage",
        f"  PrizePicks snapshots stored:               {coverage.rows}",
        f"  linked to a player and a match:            {coverage.rows_linked} ({_share(coverage.rows_linked, coverage.rows)})",
        f"  distinct linked player-matches:            {coverage.player_matches}",
        f"  settled (completed, with a winner):        {settled}",
        f"  box score on the exact match date:         {coverage.box_score_exact_date}"
        f" ({_share(coverage.box_score_exact_date, settled)})",
        f"  exactly one box score in [d-14, d+3]:      {coverage.box_score_unique_in_window}"
        f" ({_share(coverage.box_score_unique_in_window, settled)})",
        "  exactly one box score by opponent and score (26e), of player-matches with a closing line:",
        *_join_lines(rows, joins),
    ]


def _exclusion_section(rows: list[PrizePicksLineRow], settled: list[SettledLine], excluded: Exclusions) -> list[str]:
    lines = [
        "Closing pre-start lines",
        f"  lines in the last snapshot before the start: {len(rows)}",
        f"  excluded, live or in-game when fetched:      {excluded.live}",
        f"  excluded, promo or flash-sale:               {excluded.promo}",
        f"  excluded, retirement, walkover or bad score: {excluded.incomplete_score}",
        f"  excluded, box-score stat with no join:       {sum(excluded.unjoined.values())}",
    ]
    for reason, count in excluded.unjoined.most_common():
        lines.append(f"    {reason:<40}{count:>6}")
    lines.append(f"  excluded, no settlement source:             {sum(excluded.not_settleable.values())}")
    for stat, count in excluded.not_settleable.most_common():
        lines.append(f"    {stat:<40}{count:>6}")
    lines.append(f"  settled:                                     {len(settled)}")
    return lines


def report(
    rows: list[PrizePicksLineRow], coverage: PrizePicksCoverage, joins: dict[Pair, JoinResult] | None = None,
) -> str:
    joins = joins or {}
    settled, excluded = settle_rows(rows, joins)
    standard = [line for line in settled if line.odds_type == "standard"]
    sections = [
        ["PrizePicks line settlement (score-derived and box-score stats)"],
        _coverage_section(coverage, rows, joins),
        _exclusion_section(rows, settled, excluded),
        _table("Settlement by stat and odds type (over hit excludes pushes; b/even is the app's assumed "
               "break-even, not PrizePicks')", settled, ODDS_TYPES),
    ]
    for tour in TOURS:
        sections.append(_table(f"Standard lines, {tour}", [line for line in standard if line.row.tour == tour],
                               ("standard",)))
    return "\n\n".join("\n".join(section) for section in sections)


async def _main() -> None:
    from app.db.pool import SessionLocal
    from app.repositories.player_match_stats import get_box_score_candidates
    from app.repositories.props import get_prizepicks_link_coverage, get_settleable_prizepicks_lines

    async with SessionLocal() as db:
        rows = await get_settleable_prizepicks_lines(db)
        coverage = await get_prizepicks_link_coverage(db)
        contexts = await get_box_score_candidates(db, sorted({(row.player_id, row.match_id) for row in rows}))
    print(report(rows, coverage, {pair: context.join() for pair, context in contexts.items()}))


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
