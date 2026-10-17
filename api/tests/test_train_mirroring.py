"""Mirroring makes the training set symmetric in p1/p2.

The model only sees p1-relative differences, so without a swapped copy of every row it
can learn that p1 wins more often, which is an artifact of how ingest orders players
rather than anything about tennis.
"""

import datetime as dt

import pandas as pd
import pytest

from train_model import _augment_mirrored, _mirror_feature

FEATURES = [
    "d_elo",
    "has_p1_elo",
    "has_p2_elo",
    "h2h_p1_win_pct",
    "h2h_total_matches",
    "market_ml_p1_no_vig",
    "market_ml_p2_no_vig",
    "p1_last90_matches",
    "p2_last90_matches",
    "is_clay",
]


def _frame() -> pd.DataFrame:
    return pd.DataFrame({
        "match_date": [dt.date(2025, 6, 1), dt.date(2025, 6, 2)],
        "tour": ["ATP", "ATP"],
        "label": [1.0, 0.0],
        "d_elo": [120.0, -40.0],
        "has_p1_elo": [1.0, 1.0],
        "has_p2_elo": [1.0, 0.0],
        "h2h_p1_win_pct": [0.75, 0.25],
        "h2h_total_matches": [4.0, 4.0],
        "market_ml_p1_no_vig": [0.65, 0.30],
        "market_ml_p2_no_vig": [0.35, 0.70],
        "p1_last90_matches": [12.0, 5.0],
        "p2_last90_matches": [7.0, 9.0],
        "is_clay": [1.0, 0.0],
    })


class TestMirrorFeature:
    def test_difference_features_are_negated(self):
        assert list(_mirror_feature("d_elo", _frame(), FEATURES)) == [-120.0, 40.0]

    def test_paired_p1_p2_features_swap(self):
        df = _frame()
        assert list(_mirror_feature("market_ml_p1_no_vig", df, FEATURES)) == [0.35, 0.70]
        assert list(_mirror_feature("market_ml_p2_no_vig", df, FEATURES)) == [0.65, 0.30]

    def test_prefix_paired_features_swap(self):
        df = _frame()
        assert list(_mirror_feature("p1_last90_matches", df, FEATURES)) == [7.0, 9.0]

    def test_elo_presence_flags_swap(self):
        df = _frame()
        assert list(_mirror_feature("has_p1_elo", df, FEATURES)) == [1.0, 0.0]

    def test_unpaired_p1_percentages_take_the_complement(self):
        assert list(_mirror_feature("h2h_p1_win_pct", _frame(), FEATURES)) == [0.25, 0.75]

    def test_symmetric_features_are_unchanged(self):
        df = _frame()
        assert list(_mirror_feature("h2h_total_matches", df, FEATURES)) == [4.0, 4.0]
        assert list(_mirror_feature("is_clay", df, FEATURES)) == [1.0, 0.0]


class TestAugment:
    def test_row_count_doubles(self):
        assert len(_augment_mirrored(_frame(), FEATURES)) == 4

    def test_labels_balance_out(self):
        out = _augment_mirrored(_frame(), FEATURES)
        assert out["label"].sum() == pytest.approx(len(out) / 2)

    def test_the_mirrored_row_is_the_original_reversed(self):
        out = _augment_mirrored(_frame(), FEATURES)
        first = out[out["d_elo"] == 120.0].iloc[0]
        mirror = out[out["d_elo"] == -120.0].iloc[0]
        assert first["label"] == 1.0 and mirror["label"] == 0.0
        assert mirror["market_ml_p1_no_vig"] == first["market_ml_p2_no_vig"]
        assert mirror["h2h_p1_win_pct"] == pytest.approx(1.0 - first["h2h_p1_win_pct"])

    def test_mirroring_twice_returns_the_original_values(self):
        df = _frame()
        once = pd.DataFrame({f: _mirror_feature(f, df, FEATURES) for f in FEATURES})
        once["label"] = 1.0 - df["label"]
        twice = pd.DataFrame({f: _mirror_feature(f, once, FEATURES) for f in FEATURES})
        for f in FEATURES:
            assert list(twice[f]) == list(df[f]), f

    def test_dates_are_preserved_so_the_split_is_unaffected(self):
        out = _augment_mirrored(_frame(), FEATURES)
        assert sorted(out["match_date"]) == sorted(list(_frame()["match_date"]) * 2)

    def test_an_empty_frame_is_returned_untouched(self):
        empty = _frame().iloc[0:0]
        assert _augment_mirrored(empty, FEATURES).empty
