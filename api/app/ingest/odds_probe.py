"""
ingest/odds_probe.py

Read-only diagnostic tool: shows which bookmakers on odds-api.io
have real tennis odds and which markets they offer (especially Set Betting).

Costs ~3-5 API credits per run (free plan friendly).

Run:
    python -m app.ingest.odds_probe
    python -m app.ingest.odds_probe --books "DraftKings,Betfair,FanDuel,WilliamHill"
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

import httpx

BASE_URL = "https://api.odds-api.io/v3"


def _get_api_key() -> str:
    key = os.getenv("ODDS_API_KEY", "").strip()
    if not key:
        # Try loading from .env next to this file tree
        env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ODDS_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip("'\"")
                        break
    return key


async def fetch_bookmakers(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    r = await client.get(f"{BASE_URL}/bookmakers", params={"sport": "tennis", "apiKey": api_key}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return data if isinstance(data, list) else (data.get("data") or [])


async def fetch_events(client: httpx.AsyncClient, api_key: str) -> list[dict]:
    r = await client.get(f"{BASE_URL}/events", params={"sport": "tennis", "apiKey": api_key}, timeout=15)
    r.raise_for_status()
    data = r.json()
    return (data.get("data") or data.get("events") or []) if isinstance(data, dict) else (data or [])


async def fetch_odds_one(
    client: httpx.AsyncClient, api_key: str, event_id: int, books: str
) -> dict:
    r = await client.get(
        f"{BASE_URL}/odds/multi",
        params={"eventIds": str(event_id), "bookmakers": books, "apiKey": api_key},
        timeout=15,
    )
    if r.status_code == 400:
        print(f"  400 error: {r.text[:200]}")
        return {}
    r.raise_for_status()
    data = r.json()
    results = (data.get("data") or data.get("events") or []) if isinstance(data, dict) else (data or [])
    return results[0] if results else {}


def _summarize_bookmaker(name: str, markets: list[dict]) -> dict:
    market_names = []
    set_betting_info = None
    for mkt in markets:
        mkt_name = str(mkt.get("name") or "").strip()
        if not mkt_name:
            continue
        market_names.append(mkt_name)
        if mkt_name.lower() == "set betting":
            odds_list = [o for o in (mkt.get("odds") or []) if isinstance(o, dict) and o]
            if odds_list:
                set_betting_info = odds_list  # has real odds
            else:
                set_betting_info = "empty"
    return {
        "bookmaker": name,
        "markets": market_names,
        "set_betting": set_betting_info,
        "count": len(market_names),
    }


def _print_table(summaries: list[dict]) -> None:
    print()
    print(f"{'Bookmaker':<20} {'Markets':<6} {'Market Names':<55} {'Set Betting'}")
    print("-" * 120)
    for s in sorted(summaries, key=lambda x: -x["count"]):
        names_short = ", ".join(s["markets"])
        if len(names_short) > 54:
            names_short = names_short[:51] + "..."
        sb = s["set_betting"]
        if sb is None:
            sb_str = "—"
        elif sb == "empty":
            sb_str = "listed but EMPTY [{}]"
        else:
            # Show first couple of lines
            lines = []
            for o in sb[:3]:
                parts = []
                if "home" in o:
                    parts.append(f"home={o['home']}")
                if "away" in o:
                    parts.append(f"away={o['away']}")
                if parts:
                    lines.append("{" + ", ".join(parts) + "}")
            sb_str = "✓ " + " | ".join(lines) if lines else "✓ (non-home/away format)"
        print(f"{s['bookmaker']:<20} {s['count']:<6} {names_short:<55} {sb_str}")
    print()


async def run(books: str | None = None) -> None:
    api_key = _get_api_key()
    if not api_key:
        print("ERROR: ODDS_API_KEY not found. Set it in api/app/.env or as env var.")
        sys.exit(1)

    async with httpx.AsyncClient() as client:
        # Step 1: list valid bookmaker keys
        print("Fetching valid bookmaker keys for tennis...")
        try:
            all_books = await fetch_bookmakers(client, api_key)
            if all_books:
                print(f"Valid tennis bookmakers ({len(all_books)}):")
                for b in all_books:
                    name = b.get("name") or b.get("key") or str(b)
                    print(f"  {name}")
            else:
                print("  (no bookmaker list returned — endpoint may not be supported on this plan)")
        except httpx.HTTPStatusError as e:
            print(f"  /bookmakers returned {e.response.status_code}: {e.response.text[:200]}")
            print("  Skipping bookmaker list — continuing with event probe.")

        print()

        # Step 2: get events with odds — try up to 10 events to find one with data
        print("Fetching upcoming tennis events...")
        events = await fetch_events(client, api_key)
        pending = [e for e in events if e.get("status") not in ("completed", "cancelled", "live")]
        if not pending:
            print("No upcoming tennis events found.")
            return
        # Prefer ATP/WTA events which are more likely to have odds
        def _is_atp_wta(ev: dict) -> bool:
            league = (ev.get("league") or {}).get("name") or ""
            return "ATP" in league or "WTA" in league
        atp_wta = [e for e in pending if _is_atp_wta(e)]
        ordered = atp_wta + [e for e in pending if not _is_atp_wta(e)]
        print(f"Found {len(pending)} pending events ({len(atp_wta)} ATP/WTA). Probing for one with odds...")

        probe_books = books or "DraftKings,FanDuel"
        print(f"Fetching odds for: {probe_books}")
        print()

        ev_data: dict = {}
        for ev in ordered[:30]:
            candidate = await fetch_odds_one(client, api_key, int(ev["id"]), probe_books)
            if candidate and candidate.get("bookmakers"):
                ev_data = candidate
                print(f"Using event: {ev.get('home')} vs {ev.get('away')} (id={ev.get('id')})")
                break
            else:
                print(f"  No odds: {ev.get('home')} vs {ev.get('away')}")

        if not ev_data:
            print("No odds data returned.")
            return

        bookmakers: Any = ev_data.get("bookmakers") or {}
        summaries = []

        if isinstance(bookmakers, dict):
            for bk_name, markets in bookmakers.items():
                if isinstance(markets, list):
                    summaries.append(_summarize_bookmaker(bk_name, markets))
        elif isinstance(bookmakers, list):
            for item in bookmakers:
                if isinstance(item, dict):
                    name = str(item.get("name") or item.get("key") or "")
                    mkts = item.get("markets") or []
                    if name and isinstance(mkts, list):
                        summaries.append(_summarize_bookmaker(name, mkts))

        if not summaries:
            print("No bookmaker data found in response. Raw response:")
            import json
            print(json.dumps(ev_data, indent=2)[:2000])
            return

        _print_table(summaries)
        print("Tip: Best book for Set Betting = one marked ✓ above.")
        print("Tip: Best book for market depth = highest Markets count.")


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Probe odds-api.io tennis bookmaker coverage")
    parser.add_argument(
        "--books",
        type=str,
        default=None,
        help="Comma-separated bookmaker names to probe (default: DraftKings,FanDuel)",
    )
    args = parser.parse_args()
    await run(books=args.books)


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(_main())
