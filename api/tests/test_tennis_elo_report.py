from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.core import tennis_elo_report as report
from app.core.tennis_grading import PairedDifference

FIRST = date(2027, 1, 1)
NOW = datetime(2027, 2, 1, tzinfo=timezone.utc)
PINS = report.ReportPins("e" * 64, FIRST, "b" * 64, "c" * 64, "d" * 64,
                         (("ATP", "ensemble-v3+lgbm-v6"), ("WTA", "ensemble-v3+lgbm-v6"),
                          ("CHALLENGER", "ensemble-v3+lgbm-none")))


def case(mid=1, day=FIRST, group="ATP", probabilities=True):
    kickoff = datetime.combine(day, time(18), timezone.utc)
    tour = "CHALLENGER" if group == "ATP_CHALLENGER" else group
    return report.ReportCase(
        mid, 10, 20, group, report.EXPERIMENT, PINS.experiment_sha256, dict(PINS.model_versions).get(tour, "bad"),
        PINS.coefficient_sha256, PINS.gate_sha256, PINS.identity_sha256, report.SOURCE,
        kickoff - timedelta(hours=2), kickoff, FIRST,
        report.MatchState(10, 20, kickoff, "completed", tour, "Synthetic Open", "R16", 3),
        "Hard", False, False, report.Probabilities(.5, .5, .5, .5, .5) if probabilities else None,
    )


def result(c, **changes):
    return replace(report.ResultObservation(c.match_id, "completed", c.p1_id, "6-4 6-4"), **changes)


def observation(c, **changes):
    return replace(report.CoverageObservation(c.match_id, c.group, c.kickoff, c.frozen_at,
                                              True, True, "paired", PINS.experiment_sha256), **changes)


def series(daily=None, group="ATP"):
    values = []
    for day, size in enumerate(daily if daily is not None else [22] * 13 + [14]):
        for _ in range(size):
            values.append(case(len(values) + 1, FIRST + timedelta(days=day), group))
    return values


def selection(cases):
    return report.select_sample(cases, {c.match_id: result(c) for c in cases}, "ATP", NOW)


def test_three_complete_utc_days_begin_after_kickoff_cohort_day_closes():
    c = case()
    before = datetime(2027, 1, 4, 23, 59, 59, tzinfo=timezone.utc)
    boundary = before + timedelta(seconds=1)
    assert report.mature_through(before) == date(2026, 12, 31)
    assert report.mature_through(boundary) == FIRST
    assert report.count_summary([c], [observation(c)], PINS, "ATP", before).mature_pairs == 0
    assert report.count_summary([c], [observation(c)], PINS, "ATP", boundary).mature_pairs == 1
    local = boundary.astimezone(timezone(timedelta(hours=-5)))
    assert report.mature_through(local) == FIRST


@pytest.mark.parametrize("daily", [[22] * 13 + [13], [25] * 12, [300]])
def test_both_case_and_distinct_scored_day_floors_are_required(daily):
    chosen = selection(series(daily))
    assert chosen.cutoff is None
    with pytest.raises(ValueError, match="before locking"):
        report.score_sample(chosen, report.Coverage((), ()))


def test_exact_floor_and_first_full_resolved_day_include_all_cases_not_just_300():
    exact = selection(series())
    assert len(exact.cases) == 300 and exact.cutoff == FIRST + timedelta(days=13)
    values = series([22] * 13 + [15, 40])
    chosen = selection(list(reversed(values)))
    assert len(chosen.cases) == 301 and chosen.cutoff == exact.cutoff
    assert [c.match_id for c in chosen.cases] == list(range(1, 302))


def test_unresolved_earlier_day_cannot_be_skipped_to_reach_floor():
    values = series([22] * 15)
    results = {c.match_id: result(c) for c in values}
    del results[23]
    chosen = report.select_sample(values, results, "ATP", NOW)
    assert chosen.cutoff is None and chosen.blocked_day == FIRST + timedelta(days=1)
    assert len(chosen.cases) == 22


def test_unresolved_later_day_does_not_reopen_an_already_complete_prefix():
    values = series([22] * 13 + [14, 5])
    results = {c.match_id: result(c) for c in values[:300]}
    chosen = report.select_sample(values, results, "ATP", NOW)
    assert chosen.cutoff == FIRST + timedelta(days=13) and len(chosen.cases) == 300


@pytest.mark.parametrize("changes", [
    {"status": "live"}, {"status": "scheduled"}, {"winner_id": 99}, {"winner_id": None},
    {"score": None}, {"score": "6-4 4-2"},
])
def test_unknown_or_incomplete_results_block_cohort(changes):
    c = case()
    assert report.resolve(c, result(c, **changes)) == ("unresolved", None)


@pytest.mark.parametrize("changes", [
    {"status": "cancelled"}, {"status": "void"}, {"status": "retired"}, {"status": "walkover"},
    {"score": "6-4 6-4 RET"}, {"score": "W/O"}, {"score": "6-3 2-1 retired"},
])
def test_voids_and_retirements_are_excluded_without_guessing_outcomes(changes):
    c = case()
    assert report.resolve(c, result(c, **changes)) == ("void_or_retired", None)


def test_retirement_only_days_do_not_meet_distinct_scored_day_floor():
    values = series([25] * 12 + [1, 1])
    results = {c.match_id: result(c) for c in values}
    results[301], results[302] = result(values[300], status="retired"), result(values[301], status="cancelled")
    chosen = report.select_sample(values, results, "ATP", NOW)
    assert len(chosen.cases) == 300 and chosen.cutoff is None
    assert dict(chosen.excluded) == {"void_or_retired": 2}


def test_outcome_is_oriented_to_frozen_p1_even_if_current_order_is_reversed():
    c = case()
    reversed_order = replace(c, current=replace(c.current, p1_id=20, p2_id=10))
    assert report.capture_exclusion(reversed_order, PINS) is None
    assert report.resolve(reversed_order, result(c, winner_id=20)) == ("resolved", False)
    with pytest.raises(ValueError):
        report.resolve(c, result(c, match_id=999))


def test_slam_format_requires_three_won_sets_for_atp_main_draw():
    c = replace(case(), current=replace(case().current, tournament="Australian Open", best_of=None))
    assert report.resolve(c, result(c)) == ("unresolved", None)
    assert report.resolve(c, result(c, score="6-4 6-4 6-4")) == ("resolved", True)


@pytest.mark.parametrize("change, reason", [
    ({"experiment": "different"}, "other_source_or_experiment"),
    ({"candidate_source": "tennisabstract"}, "other_source_or_experiment"),
    ({"group": "WTA_125"}, "outside_group"),
    ({"eligible_from": FIRST - timedelta(days=1)}, "before_start_or_wrong_cohort"),
    ({"frozen_at": case().kickoff}, "late_capture"),
])
def test_invalid_capture_source_group_or_start_is_excluded(change, reason):
    assert report.capture_exclusion(replace(case(), **change), PINS) == reason


@pytest.mark.parametrize("field", ["experiment_sha256", "coefficient_sha256", "gate_sha256", "identity_sha256", "model_version"])
def test_pin_changes_stop_report_instead_of_pooling_versions(field):
    with pytest.raises(ValueError, match="stopped for review"):
        report.valid_cases([replace(case(), **{field: "changed"})], PINS)


@pytest.mark.parametrize("change, reason", [
    ({"p2_id": 99}, "participants_changed"), ({"kickoff": None}, "current_kickoff_missing"),
    ({"kickoff": case().frozen_at}, "rescheduled_before_freeze"),
    ({"tour": "CHALLENGER"}, "outside_population"), ({"round": "Q1"}, "outside_population"),
    ({"tournament": "ITF Synthetic"}, "outside_population"),
])
def test_revised_match_metadata_cannot_make_bad_capture_eligible(change, reason):
    c = case()
    assert report.capture_exclusion(replace(c, current=replace(c.current, **change)), PINS) == reason


def test_valid_later_reschedule_keeps_original_frozen_kickoff_cohort():
    c = case()
    moved = replace(c, current=replace(c.current, kickoff=c.kickoff + timedelta(days=2)))
    assert report.capture_exclusion(moved, PINS) is None
    assert report.utc_day(moved.kickoff) == FIRST


def test_later_actual_kickoff_must_also_clear_settlement_lag_and_blocks_earlier_cohort():
    values = series([22] * 15)
    values[0] = replace(values[0], current=replace(values[0].current, kickoff=NOW - timedelta(days=1)))
    results = {c.match_id: result(c) for c in values}
    chosen = report.select_sample(values, results, "ATP", NOW)
    assert chosen.cutoff is None and chosen.blocked_day == FIRST and not chosen.cases


def test_repeated_cycles_do_not_inflate_denominator_and_recovery_counts_availability():
    c = case()
    missing = observation(c, candidate_available=False, reason="missing_candidate")
    available = observation(c, observed_at=c.frozen_at + timedelta(minutes=10))
    cov = report.coverage([missing, available, available], [c], PINS, "ATP", FIRST)
    assert cov.eligible_ids == (1,) and cov.available_ids == (1,)


def test_coverage_includes_missing_source_cases_and_is_separate_from_outcome_exclusions():
    values = [case(1), case(2)]
    observations = [observation(values[0]), observation(values[1], candidate_available=False, reason="missing_candidate")]
    cov = report.coverage(observations, values[:1], PINS, "ATP", FIRST)
    assert len(cov.eligible_ids) == 2 and len(cov.available_ids) == 1 and not cov.passes


def test_successful_pair_selects_its_own_frozen_coverage_cohort_after_schedule_change():
    c = case(1, FIRST + timedelta(days=1))
    previous = observation(c, kickoff=c.kickoff - timedelta(days=1), observed_at=c.frozen_at - timedelta(days=1),
                           candidate_available=False, reason="missing_candidate")
    assert report.coverage([previous, observation(c)], [c], PINS, "ATP", FIRST).eligible_ids == ()
    assert report.coverage([previous, observation(c)], [c], PINS, "ATP", FIRST + timedelta(days=1)).eligible_ids == (1,)


def test_groups_and_experiments_are_not_pooled_for_sample_floors():
    atp = series([15] * 14)
    wta = [replace(c, match_id=c.match_id + 1000) for c in series([15] * 14, group="WTA")]
    assert selection(atp + wta).cutoff is None
    assert report.select_sample(atp + wta, {c.match_id: result(c) for c in atp + wta}, "WTA", NOW).cutoff is None
    assert report.coverage([observation(wta[0])], atp + wta, PINS, "ATP", NOW.date()).eligible_ids == ()


def test_exact_margin_and_coverage_boundaries_and_both_paired_gates():
    cov = report.Coverage(tuple(range(1000)), tuple(range(900)))
    exact = PairedDifference(300, .005, 0.)
    assert report.decision(300, 14, cov, exact, exact) == "pass"
    assert report.decision(299, 14, cov, None, None) == "accruing"
    assert report.decision(300, 13, cov, None, None) == "accruing"
    assert report.decision(300, 14, replace(cov, available_ids=tuple(range(899))), exact, exact) == "keep incumbent"
    fails = PairedDifference(300, .005000001, 0.)
    assert report.decision(300, 14, cov, fails, exact) == "keep incumbent"
    assert report.decision(300, 14, cov, exact, fails) == "keep incumbent"
    uncertainty = PairedDifference(300, 0., .002000001)
    assert report.decision(300, 14, cov, uncertainty, exact) == "keep incumbent"


@pytest.mark.parametrize("difference", [PairedDifference(300, 0., None), PairedDifference(299, 0., 0.),
                                        PairedDifference(300, float("nan"), 0.), PairedDifference(300, 0., -1.)])
def test_nonfinite_or_inconsistent_gate_statistics_cannot_produce_verdict(difference):
    with pytest.raises(ValueError):
        report.decision(300, 14, report.Coverage((1,), (1,)), difference, difference)


def test_count_path_never_calls_a_loss_or_outcome_function(monkeypatch):
    def forbidden(*args): raise AssertionError("Loss or outcome inspected in count mode")
    for name in ("paired_loss_difference", "score_component", "resolve"):
        monkeypatch.setattr(report, name, forbidden)
    values = series()
    summary = report.count_summary(values, [observation(c) for c in values], PINS, "ATP", NOW)
    assert summary.verdict == "accruing" and summary.potential_sample_floor


def test_locked_sample_context_and_gated_cases_use_same_full_sample():
    values = series()
    values[0] = replace(values[0], candidate_gated=True, incumbent_gated=True)
    chosen = selection(values)
    cov = report.coverage([observation(c) for c in values], values, PINS, "ATP", chosen.cutoff)
    scored = report.score_sample(chosen, cov)
    assert scored.verdict == "pass" and scored.cases == 300 and scored.days == 14
    assert scored.g1.mean == scored.g2.mean == 0 and scored.g1.standard_error == 0
    assert {name for name, _ in scored.components} == {"candidate", "incumbent", "market", "candidate_elo", "incumbent_elo"}
    assert scored.candidate_gated == scored.incumbent_gated == 1
    assert scored.surfaces == (("Hard", 300),)
    assert sum(b.n for b in dict(scored.calibration)["candidate"]) == 300


def test_absent_coverage_ledger_cannot_be_inferred_from_successful_pairs():
    with pytest.raises(ValueError, match="coverage ledger"):
        report.score_sample(selection(series()), report.Coverage((), ()))


def test_inactive_source_and_duplicate_captures_cannot_create_a_sample():
    assert report.capture_exclusion(case(), replace(PINS, eligible_from=None)) == "experiment_inactive"
    with pytest.raises(ValueError, match="Duplicate frozen"):
        report.valid_cases([case(), case()], PINS)


@pytest.mark.parametrize("change", [{"experiment_sha256": "f" * 64}, {"kickoff": None},
                                    {"observed_at": case().kickoff},
                                    {"observed_at": case().frozen_at - timedelta(days=1)}])
def test_invalid_or_changed_coverage_cannot_be_silently_removed_from_denominator(change):
    with pytest.raises(ValueError):
        report.coverage([observation(case(), **change)], [case()], PINS, "ATP", FIRST)
