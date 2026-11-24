"""The inverse of `compact_slate`, mirroring `web/src/utils/nflSlateWire.ts`, for tests."""
from typing import cast

from app.core.nfl_slate_wire import SAMPLE_FIELDS, JsonObject


def expand_slate(body: JsonObject) -> JsonObject:
    samples = cast(list[object], body["samples"])
    games = [
        {**game, "lines": [
            {key: samples[value] if key in SAMPLE_FIELDS and isinstance(value, int) else value
             for key, value in line.items()}
            for line in cast(list[JsonObject], game["lines"])
        ]}
        for game in cast(list[JsonObject], body["games"])
    ]
    return {key: value for key, value in body.items() if key != "samples"} | {"games": games}
