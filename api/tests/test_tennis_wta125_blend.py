"""WTA 125 membership and count-only inspection preserve the unscored holdout."""
from dataclasses import replace
import csv
from datetime import date
from pathlib import Path

import pytest

from app.backtest import tennis_closing_lines as closing
from app.backtest import tennis_wta125_blend as wta125
from app.core import tennis_grading
from app.core.tennis_grading import PairedDifference
from app.core.tennis_market_blend import BlendCoefficients
from app.core.valuebetennis import VbtMatch
from app.ml import elo_history

MATCH = VbtMatch(
    match_id=1, tour="WTA", category="Challenger", round_code=4,
    match_date=date(2022, 5, 10), season=2022, tournament="Trophee Lagardere - Paris",
    surface="clay", best_of=3, p1_id=1, p2_id=2, winner_id=1,
    score="6-4 6-4", completed=True, truncated=False,
    p1_open=1.9, p2_open=1.9, p1_close=1.9, p2_close=1.9,
)
CASE = closing.ClosingLineCase(
    tour=MATCH.tour, category=MATCH.category, round_code=MATCH.round_code,
    tournament=MATCH.tournament, season=MATCH.season, match_date=MATCH.match_date,
    p1_id=1, p2_id=2, p1_won=True, completed=True, truncated=False,
    elo_prob=0.5, market_prob=0.5, open_prob=0.5, blend_prob=0.5,
    p1_close_decimal=1.9, p2_close_decimal=1.9, elo_reliable=True,
)


def test_verified_wta125_main_draw_is_in_even_when_elo_is_gated() -> None:
    assert wta125.in_wta125(CASE)
    assert wta125.in_wta125(replace(CASE, elo_reliable=False))


@pytest.mark.parametrize("case", [
    replace(CASE, tour="ATP"),
    replace(CASE, category="Main tour"),
    replace(CASE, round_code=3),
    replace(CASE, market_prob=None),
    replace(CASE, elo_prob=None),
    replace(CASE, completed=False),
    replace(CASE, tournament="W35 Santa Margherita di Pula"),
    replace(CASE, tournament="Unverified Open - Paris"),
    replace(CASE, season=2026, match_date=date(2026, 5, 10)),
])
def test_outside_population_cases_are_out(case: closing.ClosingLineCase) -> None:
    assert not wta125.in_wta125(case)


def test_cross_year_canberra_and_historical_tier_changes() -> None:
    for season in (2023, 2024):
        assert wta125.in_wta125(replace(
            CASE, tournament="Canberra 125 - Canberra", season=season,
            match_date=date(season, 12, 31) if season == 2023 else date(2024, 1, 1),
        ))
    assert wta125.in_wta125(replace(CASE, tournament="BCR Iasi Open - Iasi"))
    assert not wta125.in_wta125(replace(
        CASE, tournament="BCR Iasi Open - Iasi", season=2024, match_date=date(2024, 7, 22),
    ))


def test_count_eligibility_matches_the_existing_case_exclusions() -> None:
    earlier = replace(MATCH, match_id=0, match_date=date(2021, 12, 1), season=2021, category="Main tour")
    variants = [
        MATCH, replace(MATCH, tour="ATP"), replace(MATCH, round_code=3),
        replace(MATCH, completed=False), replace(MATCH, p1_close=None),
        replace(MATCH, p2_close=None), replace(MATCH, p2_id=3, winner_id=3),
        replace(MATCH, p2_id=4), replace(MATCH, tournament="W25 Monastir"),
        replace(MATCH, tournament="Laver Cup", tour="ATP"),
    ]
    same_day = replace(MATCH, match_id=20, p1_id=3, p2_id=4, winner_id=3)
    matches = [*variants, earlier, same_day]
    first = wta125._first_dates(matches)
    cases = closing.build_cases(matches)
    for match, case in zip(matches, cases):
        if match.category not in closing.CHALLENGER_CATEGORIES:
            continue
        expected = ("not WTA 125" if match.tour == "WTA"
                    and (match.season, match.tournament) not in wta125.WTA125_EVENTS
                    else closing.exclusion(case, closing.CHALLENGER_CATEGORIES))
        assert wta125._count_exclusion(match, first) == expected
    assert wta125._count_exclusion(variants[6], first) == "missing ELO"
    assert wta125._count_exclusion(variants[7], first) == "missing ELO"


def test_count_reports_both_tours_and_itf_exclusions() -> None:
    history = replace(MATCH, category="Main tour", match_date=date(2021, 12, 1), season=2021)
    itf = replace(MATCH, tournament="W60+H Caldas da Rainha")
    matches = [history, MATCH, replace(MATCH, tour="ATP"), itf]
    report = wta125.count_report(matches, [closing.LoadSummary("fixture.csv", rows=4, parsed=4)])
    assert "2022: WTA 125 labels 1, rows 1; ITF labels 1, rows 1; unresolved labels 0" in report
    assert "2022   WTA       2        1  1 | 0 | 0 | 0 | 0 | 0" in report
    assert "2022   ATP       1        1  0 | 0 | 0 | 0 | 0 | 0" in report
    for season in wta125.SEASONS:
        assert f"{season}   WTA" in report and f"{season}   ATP" in report
    assert "Top 10 verified WTA 125 names" in report


def test_unlisted_non_itf_label_stops_for_review() -> None:
    with pytest.raises(ValueError, match="need tier review"):
        wta125.count_report([replace(MATCH, tournament="New Open - Paris")], [])


@pytest.mark.parametrize("flags", [[], ["--count"]])
def test_count_cli_never_computes_probabilities_outcomes_or_losses(
    flags: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("The count path must not compute probabilities, outcomes or losses")

    for name in ("score_component", "paired_loss_difference", "calibration_bins"):
        monkeypatch.setattr(tennis_grading, name, forbidden)
        monkeypatch.setattr(closing, name, forbidden)
    for name in ("build_cases", "flat_stake", "_outcomes", "_elo_prob", "_devig_decimal", "hand_set_blend"):
        monkeypatch.setattr(closing, name, forbidden)
    monkeypatch.setattr(elo_history, "expected_score", forbidden)
    monkeypatch.setattr(wta125, "build_cases", forbidden)
    monkeypatch.setattr(wta125, "fit_group", forbidden)
    monkeypatch.setattr(wta125, "served_prob", forbidden)
    monkeypatch.setattr(wta125, "score_component", forbidden)
    monkeypatch.setattr(wta125, "paired_loss_difference", forbidden)
    monkeypatch.setattr(wta125, "calibration_bins", forbidden)
    monkeypatch.setattr(wta125, "flat_stake", forbidden)
    monkeypatch.setattr(wta125, "load_valuebetennis", lambda folder: ([MATCH], []))
    for year in wta125.SEASONS:
        (tmp_path / f"valuebetennis-matchs-{year}.csv").write_text(
            ";".join(sorted(wta125.REQUIRED_COLUMNS)) + "\n", encoding="utf-8",
        )
    wta125.main([*flags, "--data-dir", str(tmp_path)])
    assert "COUNTS ONLY" in capsys.readouterr().out


def test_count_cli_refuses_an_incomplete_download(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as raised:
        wta125.main(["--data-dir", str(tmp_path)])
    assert raised.value.code == 2


def test_count_cli_stops_when_csv_layout_changes(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for year in wta125.SEASONS:
        (tmp_path / f"valuebetennis-matchs-{year}.csv").write_text("unexpected;columns\n", encoding="utf-8")
    with pytest.raises(SystemExit) as raised:
        wta125.main(["--data-dir", str(tmp_path)])
    assert raised.value.code == 2
    assert "CSV layout changed" in capsys.readouterr().err


PASS = (PairedDifference(300, -0.5, 0.125), PairedDifference(300, 0.0, 0.125))
FAIL = (PairedDifference(300, 0.0, 0.125), PASS[1])


@pytest.mark.parametrize(("gates", "expected"), [
    ({"A": FAIL}, "keep pooled"),
    ({"A": FAIL, "B": FAIL}, "keep pooled"),
    ({"A": PASS}, "adopt A"),
    ({"A": PASS, "B": FAIL}, "adopt A"),
    ({"A": FAIL, "B": PASS}, "adopt B"),
    ({"B": PASS, "A": PASS}, "adopt A"),
])
def test_decide_verdicts_and_a_over_b_tiebreak(
    gates: dict[str, tuple[PairedDifference, PairedDifference]], expected: wta125.Verdict,
) -> None:
    assert wta125.decide(300, gates) == expected


def test_decide_floor_is_300_and_does_not_inspect_gates_below_it() -> None:
    assert wta125.decide(0, {}) == "accruing"
    assert wta125.decide(299, {"A": PASS}) == "accruing"
    assert wta125.decide(300, {"A": PASS}) == "adopt A"


def test_g1_requires_strict_improvement_at_two_and_a_half_standard_errors() -> None:
    boundary = PairedDifference(300, -0.3125, 0.125)
    assert wta125.decide(300, {"A": (boundary, PASS[1])}) == "keep pooled"
    better = replace(boundary, mean=-0.3126)
    assert wta125.decide(300, {"A": (better, PASS[1])}) == "adopt A"


def test_g2_equality_passes_but_failure_blocks_a_g1_pass() -> None:
    boundary = PairedDifference(300, 0.25, 0.125)
    assert wta125.decide(300, {"A": (PASS[0], boundary)}) == "adopt A"
    worse = replace(boundary, mean=0.2501)
    assert wta125.decide(300, {"A": (PASS[0], worse)}) == "keep pooled"


@pytest.mark.parametrize("invalid", [
    replace(PASS[0], n=299), replace(PASS[0], standard_error=None),
    replace(PASS[0], mean=float("nan")), replace(PASS[0], mean=float("inf")),
    replace(PASS[0], standard_error=float("nan")), replace(PASS[0], standard_error=-0.1),
])
def test_decide_refuses_incomplete_or_invalid_paired_evidence(invalid: PairedDifference) -> None:
    with pytest.raises(ValueError, match="full scored sample"):
        wta125.decide(300, {"A": (invalid, PASS[1])})


@pytest.mark.parametrize(("n", "market_offset", "elo_offset", "matches"), [
    (5734, 0.0, 0.0, True), (5734, 0.00099, -0.00099, True),
    (5733, 0.0, 0.0, False), (5734, 0.0011, 0.0, False), (5734, 0.0, -0.0011, False),
])
def test_pooled_integrity_checks_both_coefficients_and_the_exact_sample_size(
    n: int, market_offset: float, elo_offset: float, matches: bool, monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = wta125.FIT_COEFFICIENTS["CHALLENGER"]
    fit = wta125.FitResult(n, BlendCoefficients(expected.market + market_offset, expected.elo + elo_offset), 0.01, 0.01)
    seen: list[closing.ClosingLineCase] = []

    def fake_fit(cases: list[closing.ClosingLineCase]) -> wta125.FitResult:
        seen.extend(cases)
        return fit

    monkeypatch.setattr(wta125, "fit_group", fake_fit)
    men = replace(CASE, tour="ATP")
    cases = [CASE, men, replace(CASE, category="Main tour"), replace(CASE, season=2026)]
    if matches:
        assert wta125.pooled_integrity(cases) == fit
    else:
        with pytest.raises(ValueError, match="MISMATCH; stop before candidate fitting"):
            wta125.pooled_integrity(cases)
    assert seen == [CASE, men]


def test_fit_builds_only_burn_in_and_development_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    history = replace(MATCH, season=2021, match_date=date(2021, 12, 1))
    future = [replace(MATCH, season=year, match_date=date(year, 5, 10)) for year in range(2023, 2027)]
    seen: list[VbtMatch] = []

    def fake_build(matches: list[VbtMatch]) -> list[closing.ClosingLineCase]:
        seen.extend(matches)
        return [CASE]

    fit = wta125.FitResult(5734, wta125.FIT_COEFFICIENTS["CHALLENGER"], 0.01, 0.01)
    monkeypatch.setattr(wta125, "build_cases", fake_build)
    monkeypatch.setattr(wta125, "pooled_integrity", lambda cases: fit)
    output = wta125.fit_report([history, MATCH, *future])
    assert seen == [history, MATCH]
    assert "Integrity MATCH" in output
    assert "B DROPPED: n=1" in output


def test_b_is_dropped_below_300_without_fitting(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(cases: list[closing.ClosingLineCase]) -> wta125.FitResult:
        raise AssertionError("B must be dropped before fitting below 300 reliable cases")

    monkeypatch.setattr(wta125, "fit_group", forbidden)
    assert wta125.fit_candidate_b([CASE] * 299) == (299, None)


def test_b_fits_at_300_and_only_uses_reliable_2022_wta125_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[closing.ClosingLineCase] = []
    fit = wta125.FitResult(300, BlendCoefficients(1.0, 0.1), 0.02, 0.03)

    def fake_fit(cases: list[closing.ClosingLineCase]) -> wta125.FitResult:
        seen.extend(cases)
        return fit

    excluded = [
        replace(CASE, elo_reliable=False), replace(CASE, tour="ATP"),
        replace(CASE, tournament="W35 Monastir"), replace(CASE, category="Main tour"),
        replace(CASE, completed=False), replace(CASE, market_prob=None),
        replace(CASE, season=2021), replace(CASE, season=2026),
    ]
    monkeypatch.setattr(wta125, "fit_group", fake_fit)
    assert wta125.fit_candidate_b([CASE] * 300 + excluded) == (300, fit)
    assert seen == [CASE] * 300


def test_in_sample_table_compares_every_blend_on_the_same_2022_cases(monkeypatch: pytest.MonkeyPatch) -> None:
    reliable = replace(CASE, market_prob=0.65, elo_prob=0.60)
    gated = replace(reliable, elo_prob=0.95, elo_reliable=False, p1_won=False)
    candidate = wta125.FitResult(300, BlendCoefficients(0.9, 0.3), 0.02, 0.03)
    observed: list[tuple[list[float], list[bool]]] = []

    def spy_score(probabilities: list[float], outcomes: list[bool]) -> tennis_grading.ComponentScore:
        observed.append((probabilities, outcomes))
        return tennis_grading.score_component(probabilities, outcomes)

    monkeypatch.setattr(wta125, "score_component", spy_score)
    cases = [reliable, gated, replace(reliable, season=2026), replace(reliable, tournament="W25 Monastir")]
    lines = wta125._in_sample_lines(cases, candidate)
    assert "IN-SAMPLE 2022" in lines[0]
    assert len(observed) == 3
    for probabilities, outcomes in observed:
        assert len(probabilities) == 2 and outcomes == [True, False]
        assert probabilities[1] == 0.65
    assert len({probabilities[0] for probabilities, _ in observed}) == 3


def test_dropped_b_is_absent_from_in_sample_table() -> None:
    lines = wta125._in_sample_lines([CASE], None)
    assert any(line.strip().startswith("incumbent") for line in lines)
    assert any(line.strip().startswith("A ") for line in lines)
    assert not any(line.strip().startswith("B ") for line in lines)


def test_integrity_failure_stops_before_b_can_be_fitted(monkeypatch: pytest.MonkeyPatch) -> None:
    def mismatch(cases: list[closing.ClosingLineCase]) -> wta125.FitResult:
        raise ValueError("integrity MISMATCH")

    def forbidden(cases: list[closing.ClosingLineCase]) -> tuple[int, wta125.FitResult | None]:
        raise AssertionError("B must not be fitted after an integrity mismatch")

    monkeypatch.setattr(wta125, "build_cases", lambda matches: [CASE])
    monkeypatch.setattr(wta125, "pooled_integrity", mismatch)
    monkeypatch.setattr(wta125, "fit_candidate_b", forbidden)
    with pytest.raises(ValueError, match="MISMATCH"):
        wta125.fit_report([MATCH])


SCORE_MATCH = replace(MATCH, season=2026, match_date=date(2026, 3, 10), tournament="Austin 125 - Austin")
SCORE_CASE = replace(CASE, season=2026, match_date=SCORE_MATCH.match_date,
                     tournament=SCORE_MATCH.tournament, market_prob=0.65, elo_prob=0.60)
SCORE_HISTORY = replace(SCORE_MATCH, season=2021, match_date=date(2021, 1, 1), category="Main tour")
CUTOFF = date(2026, 10, 19)


@pytest.mark.parametrize("n", [0, 299])
def test_score_below_300_does_not_build_probabilities_or_compute_losses(
    n: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Accruing must return before any probability, outcome or loss computation")

    for name in ("build_cases", "served_prob", "score_component", "paired_loss_difference",
                 "calibration_bins", "flat_stake", "fit_group"):
        monkeypatch.setattr(wta125, name, forbidden)
    future = replace(SCORE_MATCH, match_date=date(2026, 12, 1))
    output = wta125.score_report([SCORE_HISTORY, *([SCORE_MATCH] * n), future], CUTOFF)
    assert f"eligible WTA 125 cases: {n}" in output
    assert "Verdict: accruing" in output
    assert "scored reads added: 0" in output


def test_score_pairs_only_2026_wta125_and_never_refits(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_history: list[VbtMatch] = []
    comparisons: list[tuple[list[float], list[float], list[bool]]] = []
    gated = replace(SCORE_CASE, elo_reliable=False, elo_prob=0.95)
    women = [SCORE_CASE] * 299 + [gated]
    male = replace(SCORE_CASE, tour="ATP", tournament="Men's Challenger")
    ignored = [replace(SCORE_CASE, season=2025), replace(SCORE_CASE, tournament="W35 Monastir")]

    def fake_build(matches: list[VbtMatch]) -> list[closing.ClosingLineCase]:
        seen_history.extend(matches)
        return [*women, male, *ignored]

    def paired(candidate: list[float], baseline: list[float], outcomes: list[bool]) -> PairedDifference:
        comparisons.append((candidate, baseline, outcomes))
        return tennis_grading.paired_loss_difference(candidate, baseline, outcomes)

    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("The verdict must use frozen coefficients without refitting")

    monkeypatch.setattr(wta125, "build_cases", fake_build)
    monkeypatch.setattr(wta125, "paired_loss_difference", paired)
    for name in ("fit_group", "fit_candidate_b", "pooled_integrity"):
        monkeypatch.setattr(wta125, name, forbidden)
    replay = [replace(SCORE_HISTORY, season=year, match_date=date(year, 1, 1)) for year in (2023, 2024, 2025)]
    future = replace(SCORE_MATCH, match_date=date(2026, 12, 1))
    output = wta125.score_report([SCORE_HISTORY, *replay, *([SCORE_MATCH] * 300), future], CUTOFF)
    assert future not in seen_history and all(m in seen_history for m in replay)
    assert len(comparisons) == 4
    values = wta125._comparison_values(women)
    for (candidate, baseline, outcomes), (name, reference) in zip(
        comparisons, (("A", "incumbent"), ("A", "close"), ("B", "incumbent"), ("B", "close")), strict=True,
    ):
        assert candidate == values[name] and baseline == values[reference]
        assert len(candidate) == len(baseline) == len(outcomes) == 300
        assert candidate[-1] == baseline[-1] == 0.65
    assert "Verdict: adopt A" in output
    assert "Men's Challenger context only" in output
    assert "Calibration context only" in output and "Flat-stake ROI context only" in output


def test_score_stops_before_losses_if_count_and_replay_disagree(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("No loss may be computed after a population mismatch")

    monkeypatch.setattr(wta125, "build_cases", lambda matches: [SCORE_CASE] * 299)
    monkeypatch.setattr(wta125, "paired_loss_difference", forbidden)
    monkeypatch.setattr(wta125, "score_component", forbidden)
    with pytest.raises(ValueError, match="Count and replay populations differ"):
        wta125.score_report([SCORE_HISTORY, *([SCORE_MATCH] * 300)], CUTOFF)


def test_score_omits_b_when_it_was_dropped_before_the_verdict(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wta125, "WTA125_FIT_N", 299)
    monkeypatch.setattr(wta125, "build_cases", lambda matches: [SCORE_CASE] * 300)
    output = wta125.score_report([SCORE_HISTORY, *([SCORE_MATCH] * 300)], CUTOFF)
    assert "B dropped: fit n=299" in output
    assert "B G1" not in output and "B G2" not in output
    assert "Verdict: adopt A" in output


def test_score_cli_requires_a_snapshot_date_before_loading_any_data(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(folder: Path) -> None:
        raise AssertionError("Missing cutoff must be rejected before data loading")

    monkeypatch.setattr(wta125, "load_valuebetennis", forbidden)
    with pytest.raises(SystemExit) as raised:
        wta125.main(["--score"])
    assert raised.value.code == 2
    assert "--score requires --download-date" in capsys.readouterr().err


def test_score_cli_on_synthetic_csvs_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("Scoring cannot fit any model")

    monkeypatch.setattr(wta125, "fit_group", forbidden)
    for season in wta125.SEASONS:
        path = tmp_path / f"valuebetennis-matchs-{season}.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=sorted(wta125.REQUIRED_COLUMNS), delimiter=";")
            writer.writeheader()
            n = 300 if season == 2026 else 1 if season == 2021 else 0
            for i in range(n):
                writer.writerow({
                    "match_id": str(900000 + i), "date": f"{season}-03-10",
                    "tournoi": "Austin 125 - Austin" if season == 2026 else "Synthetic burn-in",
                    "categorie": "Challenger" if season == 2026 else "Main tour", "genre": "wta",
                    "surface": "dur", "tour": "4", "joueur1_id": "900001", "joueur2_id": "900002",
                    "vainqueur_id": "900001" if i % 2 else "900002", "score": "6-4 6-4",
                    "cote1_cloture": "1.9", "cote2_cloture": "1.9",
                })
    wta125.main(["--score", "--download-date", "2026-10-19", "--data-dir", str(tmp_path)])
    output = capsys.readouterr().out
    assert "eligible WTA 125 cases: 300" in output
    assert "Verdict: keep pooled" in output
    assert output.count("SHA-256") == 6
