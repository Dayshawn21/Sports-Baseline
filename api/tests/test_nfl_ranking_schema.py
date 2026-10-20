from collections import Counter
from dataclasses import replace

import pytest
from pydantic import TypeAdapter, ValidationError

from app.schemas.nba import NbaModelRankingResponse
from app.schemas.nfl import NflModelRankingResponse, NflRankingModelVersion
from app.services.nba import track_record as nba
from app.services.nfl import track_record as nfl
from app.services.prop_ranking import RankingCalls
from tests.test_nfl_track_record_service import GRADED_AT, _call, _inputs


@pytest.mark.parametrize("version, probability_version", [
    ("opponent-dvp-tg-blend-usage-snap-v4", "nfl-pover-v1"), ("nfl-targets-v1", None),
])
def test_each_api_selector_resolves_to_the_same_service_identity(
    version: str, probability_version: str | None,
) -> None:
    selected = TypeAdapter(NflRankingModelVersion).validate_python(version)
    source = nfl.ranking_source(selected)
    assert (source.model_version, source.over_probability_version) == (version, probability_version)


@pytest.mark.parametrize("version", ["all", "nfl-targets-v2", "", None])
def test_unsupported_model_selectors_are_rejected(version: str | None) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(NflRankingModelVersion).validate_python(version)


def test_targets_response_serializes_a_required_json_null_probability_version() -> None:
    inputs = RankingCalls([], Counter(), 0, {}, set())
    record = nfl.build_ranking_record(inputs, 2026, GRADED_AT, "nfl-targets-v1")
    payload = NflModelRankingResponse.model_validate(record).model_dump(mode="json", by_alias=True)

    assert payload["modelVersion"] == "nfl-targets-v1" and payload["overProbabilityVersion"] is None
    assert "over_probability_version" not in payload
    assert payload["funnel"] == {"calls": 0, "withPOver": 0, "picks": 0, "bets": 0}
    assert len(payload["slices"]) == 4
    assert all(s["hitRate"] is None and s["standardError"] is None for s in payload["slices"])
    assert NflModelRankingResponse.model_fields["over_probability_version"].is_required()


def test_v4_and_nba_keep_their_named_probability_versions() -> None:
    inputs = _inputs([_call(i) for i in range(3)])
    v4 = NflModelRankingResponse.model_validate(nfl.build_ranking_record(inputs, 2026, GRADED_AT))
    nba_record = nba.build_ranking_record(inputs, 2026, GRADED_AT)
    nba_response = NbaModelRankingResponse.model_validate(nba_record)

    assert v4.over_probability_version == "nfl-pover-v1"
    assert nba_response.over_probability_version == "nba-pover-v1"
    with pytest.raises(ValidationError):
        NbaModelRankingResponse.model_validate(replace(nba_record, over_probability_version=None))
