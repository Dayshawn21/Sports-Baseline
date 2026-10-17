"""Manually store bounded, free Open-Meteo forecasts for outdoor NFL games."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys

import httpx

from app.db.pool import SessionLocal
from app.ingest.log_config import configure_ingest_logging
from app.nfl.weather import NflStadium, forecast_at_kickoff, stadium_for_home_team
from app.repositories import nfl as nfl_repo

logger = logging.getLogger("nfl_weather_ingest")
configure_ingest_logging()
BASE_URL = "https://api.open-meteo.com/v1/forecast"


async def _fetch_forecast(client: httpx.AsyncClient, stadium: NflStadium, kickoff: object) -> tuple[object, dict[str, object] | None]:
    response = await client.get(BASE_URL, params={"latitude": stadium.latitude, "longitude": stadium.longitude, "hourly": "temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m", "temperature_unit": "fahrenheit", "wind_speed_unit": "mph", "timezone": "UTC"}, timeout=20)
    response.raise_for_status()
    payload = response.json()
    forecast = forecast_at_kickoff(payload, kickoff) if isinstance(payload, dict) else None
    return forecast, payload if isinstance(payload, dict) else None


async def run(days_ahead: int = 7, dry_run: bool = False) -> dict[str, int]:
    """Fetch at most one free forecast per scheduled outdoor game in the window."""
    counts = {"outdoor": 0, "indoor": 0, "unavailable": 0, "stored": 0}
    async with SessionLocal() as db, httpx.AsyncClient() as client:
        for game in await nfl_repo.get_upcoming_games_needing_weather(db, days_ahead):
            stadium = stadium_for_home_team(game["home_team"])
            kickoff = game["start_utc"]
            if stadium is None or stadium.venue_type != "outdoor":
                counts["indoor"] += 1
                continue
            if kickoff is None:
                counts["unavailable"] += 1
                continue
            counts["outdoor"] += 1
            if dry_run:
                continue
            forecast, payload = await _fetch_forecast(client, stadium, kickoff)
            if forecast is None:
                counts["unavailable"] += 1
                continue
            await nfl_repo.insert_game_weather_snapshot(db, game["game_id"], stadium.venue_type, "open_meteo", forecast.forecast_for, forecast.temperature_f, forecast.wind_mph, forecast.wind_gust_mph, forecast.precipitation_probability, payload)
            counts["stored"] += 1
        if not dry_run:
            await db.commit()
    logger.info("NFL weather ingest: outdoor=%d indoor=%d unavailable=%d stored=%d dry_run=%s", counts["outdoor"], counts["indoor"], counts["unavailable"], counts["stored"], dry_run)
    return counts


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Store free weather snapshots for upcoming NFL games")
    parser.add_argument("--days-ahead", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    await run(args.days_ahead, args.dry_run)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
