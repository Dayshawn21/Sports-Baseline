import asyncio
from dataclasses import asdict
from datetime import timedelta
import json

from app.repositories import tennis_elo_report as repo
from app.repositories.tennis_elo_comparison import EXPERIMENT
from tests.test_tennis_elo_comparison_repository import NOW, pair


def json_payload():
    return json.loads(json.dumps(asdict(pair()), default=str))


class Result:
    def __init__(self, rows): self.rows = rows
    def mappings(self): return self
    def all(self): return self.rows


class Session:
    def __init__(self, pairs=(), cycles=(), results=()):
        self.pairs, self.cycles, self.results, self.calls = pairs, cycles, results, []

    async def execute(self, sql, params):
        query = " ".join(str(sql).split())
        self.calls.append((query, params))
        if "FROM tennis_elo_comparisons" in query: return Result(self.pairs)
        if "FROM tennis_elo_freeze_cycles" in query: return Result(self.cycles)
        return Result(self.results)


def row():
    value = pair()
    return {"match_id": 50, "p1_id": 1, "p2_id": 2, "comparison_group": "ATP", "frozen_at": NOW,
            "kickoff": value.kickoff, "payload": json_payload(), "current_p1": 1, "current_p2": 2,
            "current_kickoff": value.kickoff, "status": "completed", "tour": "ATP",
            "tournament": "Synthetic", "round": "R16", "best_of": 3}


def test_decoder_roundtrips_all_frozen_provenance_including_signed_weights_and_dates():
    assert repo.decode_comparison(json_payload()) == pair()


def test_count_queries_are_experiment_scoped_without_score_or_winner_columns():
    session = Session([row()])
    inputs = asyncio.run(repo.get_report_inputs(session))
    assert len(inputs.cases) == 1 and inputs.cases[0].probabilities is None
    assert inputs.invalid_payloads == 0
    assert len(session.calls) == 2
    for query, params in session.calls:
        assert "winner_id" not in query and "m.score" not in query
        assert params == {"experiment": EXPERIMENT} and "experiment_version=:experiment" in query


def test_probability_loading_remains_separate_from_result_loading():
    session = Session([row()])
    inputs = asyncio.run(repo.get_report_inputs(session, include_probabilities=True))
    assert inputs.cases[0].probabilities.candidate == .5
    assert all("winner_id" not in q for q, _ in session.calls)


def test_explicit_result_loader_queries_only_the_requested_frozen_ids():
    session = Session(results=[(50, "completed", 1, "6-4 6-4")])
    assert asyncio.run(repo.get_report_results(session, [50]))[50].winner_id == 1
    assert session.calls[0][1] == {"ids": [50]} and "id=ANY(:ids)" in session.calls[0][0]
    session.calls.clear()
    assert asyncio.run(repo.get_report_results(session, [])) == {} and session.calls == []


def test_bad_payloads_or_conflicting_columns_are_counted_and_never_graded():
    bad_source, bad_column, incomplete = row(), row(), row()
    bad_source["payload"]["candidate_ratings"][0]["source"] = "tennisabstract"
    bad_column["p1_id"] = 99
    del incomplete["payload"]["market"]["fetched_at"]
    session = Session([bad_source, bad_column, incomplete])
    inputs = asyncio.run(repo.get_report_inputs(session))
    assert inputs.cases == () and inputs.invalid_payloads == 3


def test_coverage_only_missing_source_attempts_survive_loading():
    session = Session(cycles=[{
        "cycle_key": NOW, "frozen_at": NOW,
        "attempts": [{"match_id": 51, "group": "ATP", "kickoff": (NOW + timedelta(hours=1)).isoformat(),
                      "incumbent_eligible": True, "candidate_available": False,
                      "reason": "missing_candidate", "experiment_sha256": "e" * 64}],
    }])
    inputs = asyncio.run(repo.get_report_inputs(session))
    assert len(inputs.coverage) == 1 and inputs.coverage[0].incumbent_eligible
    assert not inputs.coverage[0].candidate_available and inputs.coverage[0].observed_at == NOW
