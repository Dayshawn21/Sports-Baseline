"""The stored and served NFL slate JSON, with each history sample written once.

A player's history samples describe the player's market or the opponent's
position, not a line, so every demon, goblin and standard line repeated them:
over half of a 25 MB week (2026-11-08). The wire body lists each distinct
sample once in `samples`, and each line points at it by index. Identical
samples share an index, so nothing depends on which key they came from.
`web/src/utils/nflSlateWire.ts` puts them back before anything reads a line.
"""
from __future__ import annotations

import json
from typing import cast

JsonObject = dict[str, object]

SAMPLE_FIELDS = ("recentForm", "recentFormLong", "opponentHistory", "opponentAllowedHistory")


class _Samples:
    def __init__(self) -> None:
        self.values: list[object] = []
        self._index: dict[str, int] = {}

    def ref(self, sample: object) -> int | None:
        if sample is None:
            return None
        key = json.dumps(sample, sort_keys=True, separators=(",", ":"))
        if key not in self._index:
            self._index[key] = len(self.values)
            self.values.append(sample)
        return self._index[key]


def compact_slate(body: JsonObject) -> JsonObject:
    """`body` (the camelCase slate) with every line's history samples replaced by indexes."""
    samples = _Samples()
    games = [
        {**game, "lines": [
            {key: samples.ref(value) if key in SAMPLE_FIELDS else value for key, value in line.items()}
            for line in cast(list[JsonObject], game["lines"])
        ]}
        for game in cast(list[JsonObject], body["games"])
    ]
    return {**body, "games": games, "samples": samples.values}


def _is_home_line(line: JsonObject) -> bool:
    return line["segment"] == "full_game" and line["oddsType"] == "standard"


def _prop_row_key(line: JsonObject) -> tuple[object, object, object]:
    """The web's `groupNflPropRows` key, so the count matches the NFL page's."""
    return line["playerId"], line["market"], line["segment"]


def home_slate(body: JsonObject) -> JsonObject:
    """The home page's compact slice of the camelCase slate (14.2 MB down to about 1 MB, week 11 of 2026).

    Every rateable row is a standard full-game line, so keeping all of them, null
    edges included, leaves each row's primary and each category's median line as
    the full week has them. `propRowCount` counts rows over every line.
    """
    games = cast(list[JsonObject], body["games"])
    rows = {_prop_row_key(line) for game in games for line in cast(list[JsonObject], game["lines"])}
    sliced = [
        {**game, "lines": [line for line in cast(list[JsonObject], game["lines"]) if _is_home_line(line)]}
        for game in games
    ]
    return {**compact_slate({**body, "games": sliced}), "propRowCount": len(rows)}
