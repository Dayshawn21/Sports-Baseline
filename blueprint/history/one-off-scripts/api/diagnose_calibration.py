"""How the confidence tier distributes under the EV model. Read-only."""
import asyncio
import sys
from collections import Counter, defaultdict

from app.db.pool import SessionLocal
from app.repositories.props import get_today_props
from app.routers.props import _enrich_props

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

TIERS = ("LOCK", "STRONG", "LEAN", "PASS")


def fmt(counter: Counter) -> str:
    total = sum(counter.values())
    parts = "  ".join(f"{k}={counter.get(k, 0):<4}" for k in TIERS)
    lock_pct = 100.0 * counter.get("LOCK", 0) / total if total else 0.0
    return f"n={total:<5} {parts}  LOCK%={lock_pct:5.1f}"


async def main() -> None:
    async with SessionLocal() as db:
        props = await get_today_props(db, source="prizepicks")
        enriched = await _enrich_props(db, props)

        by_tier: dict[str, Counter] = defaultdict(Counter)
        by_stat: dict[str, Counter] = defaultdict(Counter)
        ev_by_conf: dict[str, list[float]] = defaultdict(list)
        graded = 0
        for p in enriched:
            if p.confidence is None:
                continue
            graded += 1
            by_tier[(p.odds_type or "none").lower()][p.confidence] += 1
            by_stat[p.stat_type][p.confidence] += 1
            if p.ev_pct is not None:
                ev_by_conf[p.confidence].append(float(p.ev_pct))

        overall = Counter()
        for c in by_tier.values():
            overall.update(c)

        print("=" * 76)
        print(f"OVERALL   {fmt(overall)}   (graded {graded} of {len(enriched)})")
        print("=" * 76)

        print("\nBY PRIZEPICKS TIER   (was: goblin 36.7% LOCK, demon 0.6% LOCK)")
        for tier in ("standard", "goblin", "demon", "none"):
            if tier in by_tier:
                print(f"  {tier:<12}{fmt(by_tier[tier])}")

        print("\nBY STAT TYPE")
        for stat, counter in sorted(by_stat.items(), key=lambda kv: -sum(kv[1].values())):
            print(f"  {stat:<24}{fmt(counter)}")

        print("\nEV%% BY CONFIDENCE  (must be monotone — the old edge_pct was not)")
        for conf in TIERS:
            vals = sorted(ev_by_conf.get(conf, []))
            if not vals:
                continue
            med = vals[len(vals) // 2]
            print(f"  {conf:<8} n={len(vals):<5} min={vals[0]:>7.1f}  median={med:>7.1f}  max={vals[-1]:>7.1f}")

        playable = [p for p in enriched if p.confidence in ("LOCK", "STRONG")]
        playable.sort(key=lambda p: -(p.ev_pct or 0))
        print(f"\nTOP 12 PLAYABLE PICKS  ({len(playable)} total LOCK+STRONG)")
        print(f"  {'player':<22}{'stat':<18}{'line':>6}{'tier':<10}{'hit%':>7}{'need%':>7}{'EV%':>8}  conf")
        for p in playable[:12]:
            print(f"  {(p.player_name or '?')[:20]:<22}{p.stat_type[:16]:<18}{float(p.line):>6.1f}"
                  f"{(p.odds_type or '-'):<10}{(p.hit_probability or 0) * 100:>7.1f}"
                  f"{p.break_even_pct or 0:>7.1f}{p.ev_pct or 0:>8.1f}  {p.confidence}")


if __name__ == "__main__":
    asyncio.run(main())
