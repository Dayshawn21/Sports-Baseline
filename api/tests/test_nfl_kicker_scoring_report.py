from datetime import UTC, datetime, timedelta

from app.backtest.nfl_kicker_scoring import PREREGISTRATION_COMMIT, build_sample, report
from app.core.nfl_kicking import CANDIDATE_FORMULAS, FLAT_KICKING, kicking_points
from app.repositories.nfl import KICKER_SCORING_STAT_COLUMNS, KickerGameLines

DISTANCE = next(f for f in CANDIDATE_FORMULAS if f.name == "distance_pat1_fgmiss0_patmiss0")
KICKOFF = datetime(2026, 10, 4, 17, 0, tzinfo=UTC)


def _stats(i: int) -> dict[str, int | None]:
    long_40 = i % 2
    return {
        **{column: 0 for column in KICKER_SCORING_STAT_COLUMNS},
        "fg_made": 2 + long_40, "fg_made_30_39": 2, "fg_made_40_49": long_40,
        "fg_missed_40_49": (i + 1) % 2, "pat_made": 2 + i % 3, "pat_missed": int(i % 4 == 0),
    }


def _row(i: int, **overrides: object) -> KickerGameLines:
    stats = _stats(i)
    flat = kicking_points(FLAT_KICKING, stats)
    true = kicking_points(DISTANCE, stats)
    assert flat is not None and true is not None
    kicking_line = flat + (0.5 if i % 2 else -0.5)
    fantasy_line = kicking_line + (true - flat) + (0.25 if i % 4 < 2 else -0.25)
    values: dict[str, object] = {
        "player_id": i, "game_id": 100 + i, "week": 1 + i % 8,
        "fantasy_line": fantasy_line, "fantasy_fetched_at": KICKOFF - timedelta(minutes=90),
        "kicking_line": kicking_line, "kicking_fetched_at": KICKOFF - timedelta(minutes=60),
        "stats": stats,
    } | overrides
    return KickerGameLines(**values)  # type: ignore[arg-type]


def _rows() -> list[KickerGameLines]:
    return [
        *(_row(i) for i in range(64)),
        _row(64, kicking_line=None, kicking_fetched_at=None),
        _row(65, fantasy_line=None, fantasy_fetched_at=None),
        _row(66, stats=None),
        _row(67, stats=_stats(67) | {"fg_made_50_59": None}),
    ]


def test_the_sample_splits_coverage_and_keeps_every_complete_fantasy_line() -> None:
    sample = build_sample(_rows())
    assert sample.counts == {
        "loaded": 68, "matched": 64, "fantasy only": 1, "kicking only": 1, "no stat row or a NULL column": 2,
    }
    assert len(sample.matched) == 64
    assert len(sample.fantasy_lines) == 65
    assert sample.median_fetch_gap_minutes == 30.0


def test_the_report_prints_coverage_candidates_and_the_verdict() -> None:
    text = report(2026, build_sample(_rows()))
    assert "Kicker scoring check, 2026 weeks 1-8" in text
    assert f"pre-registered {PREREGISTRATION_COMMIT[:8]}" in text
    assert "  matched                           64" in text
    [distance_line] = [line for line in text.splitlines() if line.startswith("  distance_pat1_fgmiss0_patmiss0 ")]
    assert distance_line.split()[1:5] == ["64", "+0.000", "0.031", "yes"]
    assert "Anchor: kicking-points over rate under flat scoring 50.0%" in text
    assert "Verdict: pinned distance_pat1_fgmiss0_patmiss0" in text


def test_a_short_sample_reports_that_nothing_is_pinned() -> None:
    text = report(2026, build_sample(_rows()[:10]))
    assert "Verdict: insufficient" in text
    assert "nothing pinned" in text
