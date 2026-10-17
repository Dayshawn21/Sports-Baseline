"""A bundle is only served if its metadata proves it is safe to serve.

meta.json carries the training-row count and the missing-value convention. It was
gitignored, so a checkout had the v5 model files but no metadata, and the row floor
could not be applied: the registry served the 217-row bundle this whole rebuild
existed to replace. Absent metadata now disqualifies a bundle rather than excusing it.
"""

import json

import pytest

from app.ml.registry import MIN_TRAINING_ROWS, ModelRegistry


def _meta(tmp_path, name, rows, fill=None):
    body = {"rows": {"total": rows}}
    if fill:
        body["missing_value_fill"] = fill
    (tmp_path / f"{name}_meta.json").write_text(json.dumps(body))


class TestTrainingRows:
    def test_a_row_count_is_read_from_metadata(self):
        assert ModelRegistry._training_rows({"rows": {"total": 32512}}) == 32512

    def test_absent_metadata_yields_no_row_count(self):
        assert ModelRegistry._training_rows({}) is None

    def test_a_malformed_rows_block_yields_no_count(self):
        assert ModelRegistry._training_rows({"rows": "lots"}) is None
        assert ModelRegistry._training_rows({"rows": {}}) is None

    def test_the_floor_is_above_the_bundle_that_caused_it(self):
        # v5 trained on 217 ATP / 270 WTA rows.
        assert MIN_TRAINING_ROWS > 270


class TestMissingFill:
    def test_a_nan_declaration_is_honoured(self):
        import math
        assert math.isnan(ModelRegistry._missing_fill({"missing_value_fill": "nan"}))

    def test_bundles_without_a_declaration_keep_zero_fill(self):
        # v4 predates the key and was trained with fillna(0.0).
        assert ModelRegistry._missing_fill({}) == 0.0

    def test_an_unknown_declaration_is_treated_as_zero_fill(self):
        assert ModelRegistry._missing_fill({"missing_value_fill": "median"}) == 0.0


class TestUnreadableMetadata:
    def test_a_missing_file_reads_as_empty(self, tmp_path):
        r = ModelRegistry.__new__(ModelRegistry)
        assert r._meta(tmp_path / "nope_meta.json") == {}

    def test_corrupt_json_reads_as_empty_rather_than_raising(self, tmp_path):
        p = tmp_path / "bad_meta.json"
        p.write_text("{not json")
        r = ModelRegistry.__new__(ModelRegistry)
        assert r._meta(p) == {}


class TestBundleSelection:
    def _bundle(self, d, version, tour, rows=None, fill=None):
        stem = f"lgbm_tennis_{version}_{tour}"
        # A real Booster file is not needed to test the guard: selection happens first.
        (d / f"{stem}.txt").write_text("dummy")
        (d / f"{stem}_features.txt").write_text("d_elo\n")
        if rows is not None:
            _meta(d, stem, rows, fill)

    def test_a_bundle_without_metadata_is_skipped(self, tmp_path, caplog):
        self._bundle(tmp_path, "v5", "atp", rows=None)
        r = ModelRegistry.__new__(ModelRegistry)
        r._dir = tmp_path
        r._lgbm_versions, r._missing_fills = {}, {}
        model, _, _ = r._load_lgbm_bundle("ATP")
        assert model is None

    def test_an_undertrained_bundle_is_skipped(self, tmp_path):
        self._bundle(tmp_path, "v5", "atp", rows=217)
        r = ModelRegistry.__new__(ModelRegistry)
        r._dir = tmp_path
        r._lgbm_versions, r._missing_fills = {}, {}
        model, _, _ = r._load_lgbm_bundle("ATP")
        assert model is None


class TestLineEndings:
    """A CRLF checkout aborts the LightGBM loader, so it is caught before the load."""

    def _model(self, d, newline: bytes):
        stem = "lgbm_tennis_v6_atp"
        (d / f"{stem}.txt").write_bytes(b"tree" + newline + b"num_leaves=8" + newline)
        (d / f"{stem}_features.txt").write_text("d_elo\n")
        _meta(d, stem, MIN_TRAINING_ROWS + 1)
        return d / f"{stem}.txt"

    def test_crlf_is_detected(self, tmp_path):
        assert ModelRegistry._has_crlf(self._model(tmp_path, b"\r\n")) is True

    def test_lf_is_accepted(self, tmp_path):
        assert ModelRegistry._has_crlf(self._model(tmp_path, b"\n")) is False

    def test_a_crlf_bundle_is_skipped_rather_than_loaded(self, tmp_path):
        self._model(tmp_path, b"\r\n")
        r = ModelRegistry.__new__(ModelRegistry)
        r._dir = tmp_path
        r._lgbm_versions, r._missing_fills = {}, {}
        # Reaching lgb.Booster with this file would kill the process, not raise.
        model, _, _ = r._load_lgbm_bundle("ATP")
        assert model is None
