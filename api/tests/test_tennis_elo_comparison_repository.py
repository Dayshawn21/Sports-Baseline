import asyncio
from copy import deepcopy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from typing import cast

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.tennis_elo import TennisEloRating
from app.repositories.tennis_elo import SOURCE, TennisEloSnapshot
from app.repositories.tennis_elo_comparison import (
    CoverageAttempt, FreezeCycle, FrozenComparison, FrozenForecast, FrozenIncumbentRating,
    FrozenMarket, freeze_cycle, get_frozen_match_ids,
)

NOW = datetime(2026, 10, 21, 13, 30, tzinfo=timezone.utc)
KICKOFF = NOW + timedelta(hours=2)
DAY = NOW.date()


def pair(match_id: int = 50) -> FrozenComparison:
    candidates = tuple(TennisEloSnapshot(
        player_id=player_id, source=SOURCE, as_of_date=DAY,
        rating=TennisEloRating(1600.0, 1580.0, None, None, 20, 10, 0, 0),
        provider_namespace="ATP", provider_player_id=f"A{player_id}", computed_at=NOW - timedelta(hours=1),
        source_downloaded_at=NOW - timedelta(hours=2), replay_cutoff=DAY,
        method_version=SOURCE, manifest_sha256="a" * 64,
    ) for player_id in (1, 2))
    incumbents = tuple(FrozenIncumbentRating(i, DAY, 1600.0, 1580.0, None, None, 20) for i in (1, 2))
    forecast = FrozenForecast(0.5, 0.5, (("market", 0.8), ("elo", 0.2)), (), False)
    return FrozenComparison(
        match_id, 1, 2, "ATP", "Hard", KICKOFF, NOW, "ensemble-v3",
        "b" * 64, "c" * 64, "d" * 64,
        FrozenMarket(match_id, 100, "bet365", NOW - timedelta(minutes=10), -110, -110, 0.5),
        incumbents, candidates, forecast, forecast, None, "e" * 64, NOW - timedelta(days=1), DAY,
    )


def attempt(match_id: int = 50) -> CoverageAttempt:
    return CoverageAttempt(match_id, "ATP", KICKOFF, True, True, "paired")


def cycle(*attempts: CoverageAttempt, frozen_at: datetime = NOW) -> FreezeCycle:
    return FreezeCycle(frozen_at.replace(minute=0), frozen_at, tuple(attempts))


class Result:
    def __init__(self, value=None):
        self.value = value

    def scalar_one_or_none(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalars(self):
        return self.value


class Savepoint:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        self.backup = deepcopy((self.session.cycles, self.session.pairs))

    async def __aexit__(self, exc_type, exc, traceback):
        if exc_type:
            self.session.cycles, self.session.pairs = self.backup


class Session:
    def __init__(self):
        self.cycles = {}
        self.pairs = {}
        self.calls = []
        self.now = NOW + timedelta(seconds=1)
        self.changed_matches = set()
        self.fail_on_match = None
        self.commit_calls = 0

    def begin_nested(self):
        return Savepoint(self)

    async def execute(self, statement, params=None):
        sql = " ".join(str(statement).split())
        self.calls.append((sql, params))
        if sql.startswith("SELECT pg_advisory"):
            return Result()
        if sql.startswith("SELECT clock_timestamp"):
            return Result(self.now)
        if sql.startswith("SELECT plan_sha256"):
            return Result(self.cycles.get(params["cycle_key"], {}).get("plan_sha256"))
        if sql.startswith("SELECT match_id"):
            return Result(list(self.pairs))
        if sql.startswith("SELECT DISTINCT payload"):
            hashes = [json.loads(p["payload"])["experiment_sha256"] for p in self.pairs.values()]
            hashes += [a["experiment_sha256"] for c in self.cycles.values() for a in json.loads(c["attempts"])
                       if a.get("experiment_sha256") is not None]
            return Result(hashes)
        if sql.startswith("SELECT id FROM matches"):
            return Result(None if params["match_id"] in self.changed_matches else params["match_id"])
        if sql.startswith("INSERT INTO tennis_elo_freeze_cycles"):
            self.cycles[params["cycle_key"]] = params
            return Result()
        if sql.startswith("INSERT INTO tennis_elo_comparisons"):
            match_id = params["match_id"]
            if match_id == self.fail_on_match:
                raise RuntimeError("simulated insert failure")
            if self.now >= params["kickoff"] or match_id in self.pairs:
                return Result()
            self.pairs[match_id] = params
            return Result(match_id)
        raise AssertionError(sql)

    async def commit(self):
        self.commit_calls += 1


def freeze(session, ledger, pairs=()):
    return asyncio.run(freeze_cycle(cast(AsyncSession, session), ledger, pairs))


def test_cycle_preserves_missing_candidate_in_denominator_and_pins_complete_payload():
    session = Session()
    missing = CoverageAttempt(51, "ATP", KICKOFF, True, False, "missing_candidate")
    excluded = CoverageAttempt(52, None, None, False, False, "unknown_kickoff")
    ledger = cycle(attempt(), missing, excluded)
    assert freeze(session, ledger, [pair()]) == 1
    attempts = json.loads(next(iter(session.cycles.values()))["attempts"])
    assert len(attempts) == 3 and sum(a["incumbent_eligible"] for a in attempts) == 2
    assert attempts[1]["candidate_available"] is False
    payload = json.loads(session.pairs[50]["payload"])
    assert payload["market"]["row_id"] == 100 and payload["market"]["p1_probability"] == 0.5
    assert payload["candidate_ratings"][0]["manifest_sha256"] == "a" * 64
    assert payload["incumbent_ratings"][0]["as_of_date"] == DAY.isoformat()
    assert payload["coefficient_sha256"] == "b" * 64 and payload["identity_sha256"] == "d" * 64
    assert session.commit_calls == 0
    assert session.calls[0][0].startswith("SELECT pg_advisory_xact_lock")
    assert all("UPDATE" not in sql and "DELETE" not in sql and "INSERT INTO predictions" not in sql
               for sql, _ in session.calls)


def test_identical_retry_in_any_order_is_noop_and_changed_cycle_fails():
    session = Session()
    ledger = cycle(attempt(50), attempt(51))
    assert freeze(session, ledger, [pair(50), pair(51)]) == 2
    original = deepcopy((session.cycles, session.pairs))
    assert freeze(session, replace(ledger, attempts=tuple(reversed(ledger.attempts))), [pair(51), pair(50)]) == 0
    assert (session.cycles, session.pairs) == original
    changed = replace(pair(), candidate=replace(pair().candidate, win_probability=0.51))
    with pytest.raises(ValueError, match="already frozen"):
        freeze(session, ledger, [changed, pair(51)])
    assert (session.cycles, session.pairs) == original


def test_first_pair_wins_across_later_cycles_without_replacing_forecast():
    session = Session()
    assert freeze(session, cycle(attempt()), [pair()]) == 1
    original = deepcopy(session.pairs[50])
    later = NOW + timedelta(minutes=5)
    session.now = later
    changed = replace(pair(), frozen_at=later, candidate=replace(pair().candidate, win_probability=0.52))
    assert freeze(session, FreezeCycle(later, later, (attempt(),)), [changed]) == 0
    assert session.pairs[50] == original and len(session.cycles) == 2
    assert json.loads(session.cycles[later]["attempts"])[0]["reason"] == "already_frozen"
    assert asyncio.run(get_frozen_match_ids(cast(AsyncSession, session))) == {50}


def test_missing_sources_can_freeze_a_coverage_only_cycle():
    session = Session()
    missing = CoverageAttempt(50, "ATP", KICKOFF, True, False, "missing_candidate")
    assert freeze(session, cycle(missing)) == 0
    assert len(session.cycles) == 1 and session.pairs == {}
    assert freeze(session, cycle(missing)) == 0


def test_failure_rolls_back_both_ledger_and_all_new_pairs():
    session = Session()
    session.fail_on_match = 51
    with pytest.raises(RuntimeError, match="insert failure"):
        freeze(session, cycle(attempt(50), attempt(51)), [pair(50), pair(51)])
    assert session.cycles == {} and session.pairs == {}


@pytest.mark.parametrize("now", [NOW - timedelta(seconds=1), KICKOFF, KICKOFF + timedelta(seconds=1)])
def test_database_time_rejects_future_observation_or_late_write(now):
    session = Session()
    session.now = now
    with pytest.raises(ValueError, match="persisted"):
        freeze(session, cycle(attempt()), [pair()])
    assert session.cycles == {} and session.pairs == {}


def test_late_coverage_only_cycle_cannot_add_an_eligible_denominator_member():
    session = Session()
    session.now = KICKOFF
    missing = CoverageAttempt(50, "ATP", KICKOFF, True, False, "missing_candidate")
    with pytest.raises(ValueError, match="after kickoff"):
        freeze(session, cycle(missing))
    assert session.cycles == {}


def test_match_recheck_rejects_schedule_orientation_or_result_race():
    session = Session()
    session.changed_matches = {50}
    with pytest.raises(ValueError, match="Match changed"):
        freeze(session, cycle(attempt()), [pair()])
    assert session.cycles == {} and session.pairs == {}
    query = next(sql for sql, _ in session.calls if sql.startswith("SELECT id FROM matches"))
    assert "status = 'scheduled'" in query and "winner_id IS NULL" in query and "FOR SHARE" in query


@pytest.mark.parametrize("change", [
    {"p1_id": 2}, {"group": "WTA_125"}, {"match_id": 0}, {"incumbent_model_version": ""},
    {"coefficient_sha256": "wrong"}, {"gate_sha256": "wrong"}, {"identity_sha256": "wrong"},
    {"frozen_at": KICKOFF}, {"kickoff": NOW}, {"frozen_at": NOW.replace(tzinfo=None)},
    {"ml_probability": float("nan")}, {"ml_probability": 1.0},
])
def test_pair_rejects_invalid_identity_timing_and_version_provenance(change):
    with pytest.raises(ValueError):
        replace(pair(), **change)


@pytest.mark.parametrize("which, change", [
    ("market", {"fetched_at": NOW + timedelta(seconds=1)}),
    ("market", {"fetched_at": NOW - timedelta(hours=6, seconds=1)}),
    ("market", {"match_id": 51}),
    ("incumbent_ratings", {"as_of_date": DAY + timedelta(days=1)}),
    ("candidate_ratings", {"computed_at": NOW + timedelta(seconds=1)}),
    ("candidate_ratings", {"manifest_sha256": "f" * 64}),
    ("candidate_ratings", {"provider_namespace": "WTA"}),
    ("candidate_ratings", {"provider_player_id": "A2"}),
])
def test_pair_rejects_unavailable_mixed_or_inconsistent_source_inputs(which, change):
    value = pair()
    if which == "market":
        replacement = replace(value.market, **change)
    else:
        ratings = getattr(value, which)
        replacement = (replace(ratings[0], **change), ratings[1])
    with pytest.raises(ValueError):
        replace(value, **{which: replacement})


def test_pair_rejects_previous_day_candidate_insufficient_history_and_reversed_players():
    value = pair()
    old = tuple(replace(r, as_of_date=DAY - timedelta(days=1), replay_cutoff=DAY - timedelta(days=1),
                        computed_at=r.computed_at - timedelta(days=1),
                        source_downloaded_at=r.source_downloaded_at - timedelta(days=1))
                for r in value.candidate_ratings)
    thin = replace(value.candidate_ratings[0], rating=TennisEloRating(1500, None, None, None, 9, 0, 0, 0))
    for ratings in (old, (thin, value.candidate_ratings[1]), tuple(reversed(value.candidate_ratings))):
        with pytest.raises(ValueError):
            replace(value, candidate_ratings=ratings)
    with pytest.raises(ValueError):
        replace(value, incumbent_ratings=tuple(reversed(value.incumbent_ratings)))
    with pytest.raises(ValueError):
        replace(value.incumbent_ratings[0], prior_matches=9)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -0.1, 0.0, 1.0, 1.1])
def test_nonfinite_or_boundary_forecast_probabilities_are_rejected(value):
    with pytest.raises(ValueError):
        replace(pair().candidate, win_probability=value)
    with pytest.raises(ValueError):
        replace(pair().candidate, elo_probability=value)


def test_market_cannot_swap_odds_or_forge_probability():
    with pytest.raises(ValueError, match="oriented odds"):
        replace(pair().market, p1_odds=-200)
    with pytest.raises(ValueError):
        replace(pair().market, p1_odds=0)


@pytest.mark.parametrize("change", [
    {"weights": (("market", float("nan")),)}, {"weights": (("market", float("inf")),)},
    {"weights": (("market", 1.0), ("market", 1.0))}, {"weights": ()},
    {"weights": [("market", 1.0)]}, {"quality_flags": ["elo_unreliable"]},
    {"quality_flags": ("",)}, {"elo_unreliable": None},
])
def test_forecast_payload_is_finite_and_deeply_immutable(change):
    with pytest.raises(ValueError):
        replace(pair().candidate, **change)


def test_pair_and_cycle_cannot_drop_add_or_duplicate_coverage_members():
    session = Session()
    missing = CoverageAttempt(50, "ATP", KICKOFF, True, False, "missing_candidate")
    for ledger, pairs in ((cycle(attempt()), []), (cycle(missing), [pair()]),
                          (cycle(attempt()), [pair(), pair()])):
        with pytest.raises(ValueError, match="exactly one"):
            freeze(session, ledger, pairs)
    assert session.calls == []
    with pytest.raises(ValueError):
        cycle(attempt(), attempt())
    with pytest.raises(ValueError):
        replace(attempt(), reason="paired", candidate_available=False)
    with pytest.raises(ValueError):
        replace(attempt(), group=None)
    with pytest.raises(ValueError):
        replace(attempt(), kickoff=None)
    with pytest.raises(ValueError):
        cycle(replace(attempt(), kickoff=NOW))


def test_metadata_and_snapshot_must_be_shared_across_entire_cycle():
    session = Session()
    for changed in (replace(pair(51), group="ATP_CHALLENGER"),
                    replace(pair(51), frozen_at=NOW + timedelta(seconds=1)),
                    replace(pair(51), coefficient_sha256="f" * 64)):
        with pytest.raises(ValueError):
            freeze(session, cycle(attempt(50), attempt(51)), [pair(50), changed])
    assert session.calls == []


def test_equivalent_timezone_display_does_not_change_cycle_identity():
    session = Session()
    assert freeze(session, cycle(attempt()), [pair()]) == 1
    offset = timezone(timedelta(hours=-5))
    shifted = replace(cycle(attempt()), cycle_key=cycle().cycle_key.astimezone(offset),
                      frozen_at=NOW.astimezone(offset))
    assert freeze(session, shifted, [pair()]) == 0


def test_fitted_signed_coefficients_are_preserved_without_normalizing_or_rejecting_them():
    forecast = replace(pair().incumbent, weights=(("market", 1.139189), ("elo", -.078181)))
    assert dict(forecast.weights)["elo"] == -.078181


def test_per_group_incumbent_versions_can_differ_with_one_shared_experiment_pin():
    session = Session()
    challenger = replace(pair(51), group="ATP_CHALLENGER", incumbent_model_version="ensemble-v3+lgbm-none")
    ledger = cycle(attempt(), replace(attempt(51), group="ATP_CHALLENGER"))
    assert freeze(session, ledger, [pair(), challenger]) == 2


def test_changing_experiment_config_after_first_pair_is_rejected():
    session = Session()
    assert freeze(session, cycle(attempt()), [pair()]) == 1
    later = NOW + timedelta(minutes=5)
    session.now = later
    with pytest.raises(ValueError, match="configuration changed"):
        freeze(session, FreezeCycle(later, later, (attempt(),)),
               [replace(pair(), frozen_at=later, experiment_sha256="f" * 64)])
    assert len(session.cycles) == 1


def test_inactive_preview_payload_can_never_reach_the_database():
    session = Session()
    preview = replace(pair(), activated_at=None, eligible_from=None)
    with pytest.raises(ValueError, match="Inactive"):
        freeze(session, cycle(attempt()), [preview])
    assert session.calls == []


def test_coverage_only_cycles_also_pin_the_experiment_before_any_successful_pair():
    session = Session()
    missing = CoverageAttempt(50, "ATP", KICKOFF, True, False, "missing_candidate", "e" * 64)
    assert freeze(session, cycle(missing)) == 0
    later = NOW + timedelta(minutes=5)
    session.now = later
    with pytest.raises(ValueError, match="configuration changed"):
        freeze(session, FreezeCycle(later, later, (replace(missing, experiment_sha256="f" * 64),)))
    assert len(session.cycles) == 1 and session.pairs == {}
