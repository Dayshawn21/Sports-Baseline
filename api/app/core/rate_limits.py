"""Which per-client rate limit a request path falls under, and which client it counts."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

# Render fronts every service with Cloudflare, which writes this header at its edge.
# Not X-Forwarded-For (nor `request.client.host`, which uvicorn's --proxy-headers
# takes from it): Render appends to whatever the client sent, so its leftmost
# entry is client text and its rightmost a Cloudflare edge address (F-19).
CLIENT_IP_HEADER = "cf-connecting-ip"

# Each of these replays grading or a whole slate per cold request (tens of seconds),
# except /admin/session, the one route a key guesser needs, and /ask, a paid model call.
# The slates build one date at a time behind a five-date cache, so a client cycling
# dates in the default bucket would keep evicting today's entry (F-45).
HEAVY_PREFIXES = ("/nfl/model/", "/tennis/model/", "/nba/model/", "/nhl/model/")
HEAVY_PATHS = frozenset({"/nfl/slate", "/nba/slate", "/nba/slate/gaps", "/nhl/slate", "/admin/session", "/ask"})
# Platform health probes poll often and cost nothing.
EXEMPT_PATHS = frozenset({"/health"})


@dataclass(frozen=True)
class RateRule:
    limit: str
    scope: str


def client_key(headers: Mapping[str, str], peer: str | None) -> str:
    """The address a per-client limit counts against: Cloudflare's, else the socket peer (local dev)."""
    forwarded = headers.get(CLIENT_IP_HEADER, "").strip()
    return forwarded or peer or "unknown"


def rule_for_path(path: str, default_limit: str, heavy_limit: str) -> RateRule | None:
    """Heavy routes get their own bucket per path; everything else shares one."""
    if path in EXEMPT_PATHS:
        return None
    if path in HEAVY_PATHS or path.startswith(HEAVY_PREFIXES):
        return RateRule(heavy_limit, path)
    return RateRule(default_limit, "default")
