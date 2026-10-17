"""The snapshot has to survive json.dumps, because insert_prediction serializes it.

A value that cannot be encoded would raise inside the nightly prediction run and lose
every prediction in the batch, so _snapshot drops offenders rather than propagating them.
"""

import json
import math
from decimal import Decimal

from app.services.tennis.predictor import _snapshot


class TestSnapshot:
    def test_plain_floats_pass_through(self):
        assert _snapshot({"d_elo": 42.5, "d_rank_log": -0.3}) == {"d_elo": 42.5, "d_rank_log": -0.3}

    def test_ints_become_floats(self):
        assert _snapshot({"h2h_total_matches": 3}) == {"h2h_total_matches": 3.0}

    def test_decimals_are_coerced(self):
        assert _snapshot({"d_first_in_pct": Decimal("0.62")}) == {"d_first_in_pct": 0.62}

    def test_none_values_are_dropped_rather_than_stored_as_null(self):
        assert _snapshot({"d_elo": 1.0, "d_age": None}) == {"d_elo": 1.0}

    def test_non_numeric_values_are_dropped(self):
        assert _snapshot({"d_elo": 1.0, "surface": "hard"}) == {"d_elo": 1.0}

    def test_nan_and_infinity_are_dropped_because_json_cannot_round_trip_them(self):
        out = _snapshot({"a": math.nan, "b": math.inf, "c": -math.inf, "d": 1.0})
        assert out == {"d": 1.0}

    def test_booleans_are_dropped_rather_than_becoming_one_and_zero(self):
        assert _snapshot({"has_p1_elo": True, "d_elo": 2.0}) == {"d_elo": 2.0}

    def test_result_is_json_serialisable(self):
        messy = {"d_elo": Decimal("1.5"), "bad": math.nan, "name": "x", "n": None, "ok": 2}
        assert json.loads(json.dumps(_snapshot(messy))) == {"d_elo": 1.5, "ok": 2.0}

    def test_an_empty_vector_produces_an_empty_dict(self):
        assert _snapshot({}) == {}
