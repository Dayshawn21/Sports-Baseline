"""Shared fixtures and builders, first written for `test_tennis_elo_report.py`."""
from dataclasses import replace
from datetime import date, datetime, time, timedelta, timezone


from app.core import tennis_elo_report as report


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
