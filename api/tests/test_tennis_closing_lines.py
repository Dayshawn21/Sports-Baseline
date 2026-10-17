"""The 26c backtest loads Valuebetennis season files and builds leak-free, oriented cases."""
import re
from datetime import date, timedelta
from itertools import count
from pathlib import Path

import pytest

from app.backtest.tennis_closing_lines import (
    ClosingLineCase, LoadSummary, build_cases, flat_stake, load_valuebetennis, report, verdict,
)
from app.core.tennis_grading import PairedDifference
from app.core.valuebetennis import VbtMatch

HEADER = (
    "match_id;date;tournoi;tournoi_id;categorie;genre;surface;tour;joueur1;joueur1_id;"
    "joueur2;joueur2_id;cote1_ouverture;cote2_ouverture;cote1_cloture;cote2_cloture;"
    "vainqueur_id;score;duree_min"
)
ROWS = [
    '1;"2022-05-03 11:00:00";"Madrid";100;Masters;wta;"terre battue";5;"A B";11;"C D";22;1.8;2.05;1.7;2.2;22;"4-6 6-3 3-6";130',
    '2;"2022-05-03 12:00:00";"Madrid";100;Masters;atp;"terre battue";5;"E F";33;"G H";44;;;;;33;"6-4 6-4";80',
    '3;"2022-05-03 13:00:00";"Madrid";100;Masters;atp;"terre battue";5;"I J";55;"K L";66;;;;;77;"6-4 6-4";80',
    '4;"";"Madrid";100;Masters;atp;"terre battue";5;"M N";88;"O P";99;;;;;88;"6-4 6-4";80',
]


def _write(folder: Path, name: str, rows: list[str]) -> None:
    # The real files carry a UTF-8 BOM, which the loader must strip from the first header.
    (folder / name).write_text("﻿" + "\n".join([HEADER, *rows]) + "\n", encoding="utf-8")


def test_loads_every_season_file_with_per_file_counts(tmp_path):
    _write(tmp_path, "valuebetennis-matchs-2022.csv", ROWS)
    _write(tmp_path, "valuebetennis-matchs-2021.csv", ROWS[:1])
    (tmp_path / "notes.csv").write_text("ignored", encoding="utf-8")

    matches, summaries = load_valuebetennis(tmp_path)

    assert [s.file for s in summaries] == ["valuebetennis-matchs-2021.csv", "valuebetennis-matchs-2022.csv"]
    assert (summaries[0].rows, summaries[0].parsed, dict(summaries[0].skipped)) == (1, 1, {})
    later = summaries[1]
    assert (later.rows, later.parsed) == (4, 2)
    assert dict(later.skipped) == {"winner_not_a_player": 1, "no_date": 1}
    assert [m.match_id for m in matches] == [1, 1, 2]
    assert matches[0].p1_close == 1.7 and matches[2].p1_close is None


def test_empty_folder_raises_naming_the_folder_and_download(tmp_path):
    with pytest.raises(FileNotFoundError, match="valuebetennis-matchs") as raised:
        load_valuebetennis(tmp_path)
    assert str(tmp_path) in str(raised.value) and "Step 1" in str(raised.value)


def test_missing_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_valuebetennis(tmp_path / "absent")


def _match(match_id: int, p1: int, p2: int, winner: int, day: date, *, tour="ATP", category="Main tour",
           close: tuple[float, float] | None = None, opening: tuple[float, float] | None = None) -> VbtMatch:
    return VbtMatch(
        match_id=match_id, tour=tour, category=category, round_code=4, match_date=day, season=day.year,
        tournament="Test Open", surface="hard", best_of=3, p1_id=p1, p2_id=p2, winner_id=winner,
        score="6-4 6-4", completed=True, truncated=False,
        p1_open=opening[0] if opening else None, p2_open=opening[1] if opening else None,
        p1_close=close[0] if close else None, p2_close=close[1] if close else None,
    )


def _history(games: int = 10) -> list[VbtMatch]:
    """Players 1 and 2 play `games` earlier matches against fresh opponents; 1 wins all, 2 wins half."""
    ids = count(10_000)
    rows = []
    for g in range(games):
        day = START + timedelta(days=g)
        first, second = next(ids), next(ids)
        rows.append(_match(next(ids), 1, first, 1, day))
        rows.append(_match(next(ids), 2, second, 2 if g % 2 else second, day))
    return rows


START = date(2022, 3, 1)
TARGET_DAY = START + timedelta(days=30)


def _target(cases: list[ClosingLineCase], p1: int, p2: int) -> ClosingLineCase:
    return next(c for c in cases if {c.p1_id, c.p2_id} == {p1, p2} and c.match_date == TARGET_DAY)


def test_same_day_matches_do_not_feed_each_other():
    earlier = [_match(1, 1, 2, 1, START)]
    same_day = [_match(2, 1, 3, 1, TARGET_DAY), _match(3, 1, 2, 2, TARGET_DAY)]
    with_both = _target(build_cases(earlier + same_day), 1, 2)
    without_first = _target(build_cases(earlier + same_day[1:]), 1, 2)
    assert with_both.elo_prob is not None
    assert with_both.elo_prob == without_first.elo_prob


def test_p1_is_the_lower_id_whoever_won():
    case = build_cases([_match(1, 50, 10, 50, START, close=(1.5, 2.5), opening=(1.4, 2.9))])[0]
    assert (case.p1_id, case.p2_id, case.p1_won) == (10, 50, False)
    assert (case.p1_close_decimal, case.p2_close_decimal) == (2.5, 1.5)
    unflipped = build_cases([_match(1, 10, 50, 50, START, close=(2.5, 1.5), opening=(2.9, 1.4))])[0]
    assert (unflipped.p1_id, unflipped.p1_won, unflipped.market_prob) == (10, False, case.market_prob)


def test_close_and_open_are_devigged_proportionally():
    case = build_cases([_match(1, 1, 2, 1, START, close=(1.5, 2.5), opening=(2.0, 2.0))])[0]
    # 1/1.5 = 0.6667 and 1/2.5 = 0.4, summing to 1.0667.
    assert case.market_prob == pytest.approx(0.625)
    assert case.open_prob == pytest.approx(0.5)


def test_first_match_has_no_elo():
    case = build_cases([_match(1, 1, 2, 1, START, close=(1.9, 1.9))])[0]
    assert case.elo_prob is None
    assert case.blend_prob == pytest.approx(0.5)


# Player 1 at about 0.78 on these prices: near the replayed ELO (about 0.84), not equal to it.
NEAR_ELO = (1.25, 4.4)


def _blend_case(close: tuple[float, float], *, category="Main tour", tour="ATP", games=10) -> ClosingLineCase:
    rows = _history(games) + [_match(1, 1, 2, 1, TARGET_DAY, tour=tour, category=category, close=close)]
    return _target(build_cases(rows), 1, 2)


def test_atp_blend_uses_the_hand_set_weights_when_elo_is_reliable():
    case = _blend_case(NEAR_ELO)
    assert case.elo_prob is not None and case.market_prob is not None
    assert 0.03 < abs(case.elo_prob - case.market_prob) < 0.15
    assert case.blend_prob == pytest.approx((0.35 * case.elo_prob + 0.25 * case.market_prob) / 0.60)


def test_wta_blend_uses_wta_weights():
    case = _blend_case(NEAR_ELO, tour="WTA")
    assert case.blend_prob == pytest.approx((0.40 * case.elo_prob + 0.15 * case.market_prob) / 0.55)


def test_challenger_takes_the_live_predictors_fallback_weights():
    case = _blend_case(NEAR_ELO, category="Challenger")
    assert case.blend_prob == pytest.approx((0.40 * case.elo_prob + 0.20 * case.market_prob) / 0.60)


def test_blend_is_the_market_when_a_player_has_few_prior_matches():
    case = _blend_case(NEAR_ELO, games=3)
    assert case.elo_prob is not None
    assert case.blend_prob == pytest.approx(case.market_prob)


def test_blend_is_the_market_when_elo_and_market_disagree_by_15_points():
    case = _blend_case((1.95, 1.95))
    assert abs(case.elo_prob - case.market_prob) >= 0.15
    assert case.blend_prob == pytest.approx(case.market_prob)


def test_high_overround_shrinks_the_market_weight():
    case = _blend_case((1.2, 3.6))
    assert case.blend_prob == pytest.approx(
        (0.35 * case.elo_prob + 0.25 * 0.75 * case.market_prob) / (0.35 + 0.25 * 0.75)
    )


def _case(season: int = 2022, *, tour="ATP", category="Main tour", round_code=4, tournament="Test Open",
          completed=True, truncated=False, elo=0.6, market=0.55, opening=0.5, won=True,
          close=(1.7, 2.2)) -> ClosingLineCase:
    return ClosingLineCase(
        tour=tour, category=category, round_code=round_code, tournament=tournament, season=season,
        match_date=date(season, 6, 1), p1_id=1, p2_id=2, p1_won=won, completed=completed, truncated=truncated,
        elo_prob=elo, market_prob=market, open_prob=opening,
        blend_prob=None if elo is None or market is None else (0.35 * elo + 0.25 * market) / 0.60,
        p1_close_decimal=close[0], p2_close_decimal=close[1],
    )


def _development_cases() -> list[ClosingLineCase]:
    return [
        _case(won=True), _case(won=False, elo=0.4), _case(tour="WTA", won=True), _case(tour="WTA", won=False),
        _case(truncated=True),
        _case(category="Challenger"), _case(category="Challenger", won=False),
        _case(category="ITF"),
        _case(round_code=2),
        _case(tournament="Laver Cup - London"),
        _case(completed=False),
        _case(market=None),
        _case(elo=None),
        _case(season=2021),
        _case(season=2026),
    ]


def _exclusions(text: str) -> dict[str, int]:
    block = text.split("Exclusions\n")[1].split("\n\n")[0]
    counts = {}
    for line in block.splitlines():
        label, number = re.match(r"\s+(.+?)\s+(\d+)(?:\s|$)", line).groups()
        counts[label] = int(number)
    return counts


SUMMARIES = [LoadSummary(file="valuebetennis-matchs-2022.csv", rows=15, parsed=15)]


def test_development_report_has_every_section_and_exclusion_count():
    text = report(_development_cases(), SUMMARIES, holdout=False)
    for header in ("Tennis closing-line backtest (26c) - development seasons 2022", "CC BY 4.0", "Exclusions",
                   "Log loss and Brier", "Paired log-loss difference vs the close", "Calibration, ATP+WTA",
                   "Flat-stake ROI", "Open-to-close CLV", "Challenger (secondary"):
        assert header in text
    assert _exclusions(text) == {
        "burn-in or excluded season": 2, "category not scored": 3, "qualifying": 1, "Laver Cup": 1,
        "not completed": 1, "no closing price": 1, "missing ELO": 1, "scored": 5,
    }
    assert "completed by the truncation rule: 1" in text
    assert "Verdict" not in text


def test_development_report_never_shows_the_holdout():
    holdout = [_case(season=2023, won=False, elo=0.9), _case(season=2024, tour="WTA"), _case(season=2025, market=0.2)]
    assert report(_development_cases() + holdout, SUMMARIES, holdout=False) == report(
        _development_cases(), SUMMARIES, holdout=False)


def test_holdout_report_scores_the_holdout_and_prints_verdicts():
    holdout = [_case(season=2023, won=w, elo=e) for w, e in ((True, 0.6), (False, 0.45), (True, 0.7), (False, 0.5))]
    text = report(_development_cases() + holdout, SUMMARIES, holdout=True)
    assert "HOLDOUT seasons 2023, 2024, 2025" in text
    assert _exclusions(text)["scored"] == 4
    verdict_lines = text.split("Verdict")[1].splitlines()
    assert any(line.strip().startswith("elo (computed)") for line in verdict_lines)
    assert any(line.strip().startswith("blend") for line in verdict_lines)


@pytest.mark.parametrize(
    "mean, se, expected",
    [
        (-0.0300, 0.0100, "beats the close"),
        (0.0300, 0.0100, "rejected against the close"),
        (0.0050, 0.0100, "inconclusive"),
        (-0.0200, 0.0100, "inconclusive"),
        (0.0200, 0.0100, "inconclusive"),
    ],
)
def test_verdict_needs_more_than_two_standard_errors(mean, se, expected):
    assert verdict(PairedDifference(n=1000, mean=mean, standard_error=se)) == expected


def test_flat_stake_bets_the_side_the_blend_favors_at_the_close():
    p1_value = _case(elo=0.8, market=0.5, close=(2.0, 2.0), won=True)
    assert flat_stake(p1_value) == pytest.approx(1.0)
    p2_value = _case(elo=0.2, market=0.5, close=(2.0, 2.5), won=True)
    assert flat_stake(p2_value) == -1.0
    assert flat_stake(_case(elo=0.56, market=0.55)) is None


def test_elo_is_reliable_when_the_live_gate_keeps_it():
    assert _blend_case(NEAR_ELO).elo_reliable


def test_elo_is_unreliable_with_few_prior_matches():
    assert not _blend_case(NEAR_ELO, games=3).elo_reliable


def test_elo_is_unreliable_at_a_15_point_gap_to_the_close():
    assert not _blend_case((1.95, 1.95)).elo_reliable


def test_elo_is_unreliable_without_a_close():
    rows = _history() + [_match(1, 1, 2, 1, TARGET_DAY, close=None)]
    assert not _target(build_cases(rows), 1, 2).elo_reliable
