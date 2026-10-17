"""The feeds a `sport_game_odds` row can come from (`provider`, migration 0044).

`THE_ODDS_API_US` is every row stored before item 36a and the only feed
existing readers see: item 28's pre-registered CLV rule was written against it.
"""
from __future__ import annotations

THE_ODDS_API_US = "the_odds_api_us"
THE_ODDS_API_EU = "the_odds_api_eu"
ODDS_API_IO = "odds_api_io"

PROVIDERS = (THE_ODDS_API_US, THE_ODDS_API_EU, ODDS_API_IO)
