"""PrizePicks prop-line ingest for any sport behind a `PropLineSource` (17c).

Fetches the sport's board leagues, keeps lines in its supported markets, links
each to a player and game through the sport's resolver, and appends them to
`sport_prop_lines`. `relink` re-resolves stored lines without a provider request.
"""
from __future__ import annotations

import asyncio
import logging
from collections import Counter
from decimal import Decimal

import httpx

from app.core.prop_sports import SportPropConfig, board_leagues, market_for_stat
from app.ingest.prizepicks import _fetch_leagues, _fetch_projections, _parse_projections
from app.repositories import sport_props
from app.services.sport_props import LineLinkage, PropLineSource, ProviderLine

PROVIDER = "prizepicks"
REQUEST_PACE_SECONDS = 1.0

BoardLine = tuple[dict, str, str]


class PrizePicksRateLimited(RuntimeError):
    """Raised when every league request for a sport exhausted its retry budget on HTTP 429."""


def _logger(config: SportPropConfig) -> logging.Logger:
    return logging.getLogger(f"prizepicks_{config.code}_ingest")


def unmapped_stat_counts(items: list[dict], config: SportPropConfig) -> Counter[str]:
    """Stat names the ingest skips, so a provider rename shows up in the log."""
    return Counter(item["stat_type"] for item in items if market_for_stat(item["stat_type"], config) is None)


async def fetch_board(config: SportPropConfig) -> list[BoardLine]:
    """(item, market, segment) for every supported line on the sport's board leagues."""
    async with httpx.AsyncClient() as client:
        leagues = board_leagues(await _fetch_leagues(client), config)
        if not leagues:
            # PrizePicks always carries an in-season sport, so an empty catalog
            # means the league request failed (usually throttled), not "no games today".
            raise PrizePicksRateLimited(
                f"PrizePicks returned no {config.league_prefix} leagues, so the league catalog request failed. "
                "No lines were stored; retry after the provider window clears."
            )
        lines: list[BoardLine] = []
        throttled: list[str] = []
        unmapped: Counter[str] = Counter()
        for index, (league_id, league_name, segment) in enumerate(leagues):
            try:
                raw = await _fetch_projections(client, league_id)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429:
                    raise
                # One throttled league must not discard the leagues that did answer.
                throttled.append(league_name)
                continue
            parsed = _parse_projections(raw, league_id)
            unmapped.update(unmapped_stat_counts(parsed, config))
            for item in parsed:
                market = market_for_stat(item["stat_type"], config)
                if market is not None:
                    # _parse_projections does not echo the league back, so carry
                    # the request's league through for auditability.
                    lines.append(({**item, "league_id": league_id, "league_name": league_name}, market, segment))
            if index < len(leagues) - 1:
                await asyncio.sleep(REQUEST_PACE_SECONDS)
    if unmapped:
        _logger(config).warning("skipped unsupported stat types: %s", ", ".join(
            f"{name} ({count})" for name, count in unmapped.most_common()
        ))
    if throttled and not lines:
        raise PrizePicksRateLimited(
            f"PrizePicks rate-limited every {config.league_prefix} league request ({throttled}). "
            "No lines were stored; retry after the provider window clears."
        )
    return lines


async def run(source: PropLineSource, dry_run: bool = False) -> int:
    from app.db.pool import SessionLocal

    config = source.config
    lines = await fetch_board(config)
    if dry_run:
        return len(lines)
    async with SessionLocal() as db:
        resolve = await source.load_resolver(db)
        linkages: list[LineLinkage] = []
        for item, market, segment in lines:
            linkage = resolve(ProviderLine(
                item.get("player_name") or "", item.get("player_team"), item.get("player_position"),
                item["start_time"],
            ))
            linkages.append(linkage)
            await sport_props.insert_prop_line(
                db, config.code, provider=PROVIDER,
                provider_prop_id=str((item["raw_json"] or {}).get("id", "")), market=str(market),
                segment=str(segment), line=Decimal(str(item["line"])), start_time=item["start_time"],
                player_id=linkage.player_id, game_id=linkage.game_id, odds_type=item.get("odds_type"),
                raw={
                    "player_name": item.get("player_name"), "stat_type": item.get("stat_type"),
                    "player_team": item.get("player_team"), "player_position": item.get("player_position"),
                    "league_id": item.get("league_id"), "league_name": item.get("league_name"),
                    "source": item.get("raw_json"),
                },
            )
        await db.commit()
        _log_linkages(config, linkages)
    return len(lines)


def _log_linkages(config: SportPropConfig, linkages: list[LineLinkage]) -> None:
    """Report why each line linked or did not, so an unlinked board is explainable."""
    logger = _logger(config)
    logger.warning("linked %d/%d lines to players", sum(linkage.matched for linkage in linkages), len(linkages))
    for reason, count in Counter(linkage.reason for linkage in linkages).most_common():
        logger.warning("  %-18s %4d", reason, count)


async def relink(source: PropLineSource) -> int:
    """Re-resolve stored lines without refetching from the provider.

    Ingest only ever INSERTs, so rows written before linking existed would stay
    NULL forever. This also re-runs after an alias is added, without spending a
    provider request.
    """
    from app.db.pool import SessionLocal

    config = source.config
    async with SessionLocal() as db:
        resolve = await source.load_resolver(db)
        lines = await sport_props.get_lines_for_relink(db, config.code)
        linkages: list[LineLinkage] = []
        changed = 0
        for line in lines:
            linkage = resolve(ProviderLine(
                line["player_name"] or "", line["player_team"], line["player_position"], line["start_time"],
            ))
            linkages.append(linkage)
            odds_type = line["odds_type"] or line["provider_odds_type"]
            current = (line["player_id"], line["game_id"], line["odds_type"])
            if (linkage.player_id, linkage.game_id, odds_type) != current:
                await sport_props.set_line_linkage(
                    db, config.code, line["id"], linkage.player_id, linkage.game_id, odds_type,
                )
                changed += 1
        await db.commit()

    _log_linkages(config, linkages)
    _logger(config).warning("rows changed: %d", changed)
    return changed
