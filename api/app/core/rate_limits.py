"""Which per-client rate limit a request path falls under."""
from __future__ import annotations

from dataclasses import dataclass

# Each of these replays grading or a whole slate per cold request (tens of seconds),
# except /admin/session, the one route a key guesser needs.
HEAVY_PREFIXES = ("/nfl/model/", "/tennis/model/", "/nba/model/")
HEAVY_PATHS = frozenset({"/nfl/slate", "/admin/session"})
# Platform health probes poll often and cost nothing.
EXEMPT_PATHS = frozenset({"/health"})


@dataclass(frozen=True)
class RateRule:
    limit: str
    scope: str


def rule_for_path(path: str, default_limit: str, heavy_limit: str) -> RateRule | None:
    """Heavy routes get their own bucket per path; everything else shares one."""
    if path in EXEMPT_PATHS:
        return None
    if path in HEAVY_PATHS or path.startswith(HEAVY_PREFIXES):
        return RateRule(heavy_limit, path)
    return RateRule(default_limit, "default")
