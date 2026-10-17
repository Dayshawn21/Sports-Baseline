"""Provider boundary for live NFL prop lines.

PrizePicks is intentionally not implemented until its endpoint, authentication
method, and response shape are confirmed. Keeping this boundary provider-neutral
prevents provider payload details from leaking into storage or prediction code.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from app.nfl.markets import NflPropMarket

DEFAULT_PRIZEPICKS_POLL_INTERVAL_MINUTES = 120

# The future PrizePicks adapter must persist every successful board as a new
# `sport_prop_lines` snapshot, return cached data inside this window, and never
# make a provider call more frequently than this default. A scheduler may widen
# the interval but must not narrow it without an explicit provider-limit review.


@dataclass(frozen=True)
class NflPropLineInput:
    provider_prop_id: str
    player_provider_id: str | None
    player_name: str
    game_provider_id: str | None
    market: NflPropMarket
    line: Decimal
    start_time: datetime | None
    over_odds: int | None
    under_odds: int | None
    fetched_at: datetime
    raw_payload: dict[str, object]


class NflPropsProvider(Protocol):
    """Fetch normalized NFL lines without coupling callers to a provider."""

    async def fetch_nfl_props(self) -> list[NflPropLineInput]:
        """Return the provider's current NFL player-prop board."""
