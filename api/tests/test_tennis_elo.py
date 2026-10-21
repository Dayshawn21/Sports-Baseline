import csv
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from app.core.tennis_elo import ExcludedMatch, TennisEloMatch, deduplicate, parse_row


@pytest.fixture
def rows() -> list[dict[str, str]]:
    path = Path(__file__).parent / "fixtures" / "tennis_elo_results.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_results_without_any_stats_are_kept(rows):
    match = parse_row(rows[0], "ATP")
    assert isinstance(match, TennisEloMatch)
    assert (match.winner_key, match.loser_key) == (("ATP", "A001"), ("ATP", "B002"))
    assert match.provider_date == date(2021, 1, 4)
    assert match.surface == "hard"
    assert len(match.source_key) == 64
    assert match.best_of == 3


def test_tiebreaks_and_a_five_set_match(rows):
    assert isinstance(parse_row(rows[1], "ATP"), TennisEloMatch)
    row = dict(rows[0], best_of="5", tourney_level="G", score="6-4 3-6 6-3 4-6 6-2")
    assert isinstance(parse_row(row, "ATP"), TennisEloMatch)


def test_match_tiebreak_is_known_but_not_accepted_by_the_completed_score_contract(rows):
    row = dict(rows[0], score="6-4 3-6 [10-7]")
    assert parse_row(row, "ATP") == ExcludedMatch("unfinished")


def test_only_the_verified_w_level_event_is_admitted(rows):
    row = dict(rows[0], tourney_level="W", tourney_id="2021-2033", tourney_name="Charleston 2")
    assert isinstance(parse_row(row, "WTA"), TennisEloMatch)
    with pytest.raises(ValueError, match="Unverified TennisMyLife W-level event"):
        parse_row(dict(row, tourney_id="2022-unknown"), "WTA")


@pytest.mark.parametrize("index, reason", [(2, "retirement"), (3, "walkover"), (4, "unfinished")])
def test_unfinished_or_nonplayed_matches_are_excluded(rows, index, reason):
    assert parse_row(rows[index], "ATP") == ExcludedMatch(reason)


@pytest.mark.parametrize("score, reason", [("", "unfinished"), ("6-4 6-3 DEF", "unfinished"),
                                        ("6-3 6-4 RET.", "retirement"), ("WO", "walkover")])
def test_status_markers_override_apparently_completed_scores(rows, score, reason):
    assert parse_row(dict(rows[0], score=score), "ATP") == ExcludedMatch(reason)


@pytest.mark.parametrize("column", ["winner_id", "loser_name"])
def test_doubles_are_excluded(rows, column):
    assert parse_row(dict(rows[0], **{column: "A / B"}), "ATP") == ExcludedMatch("doubles")


@pytest.mark.parametrize("level, reason", [("E", "exhibition"), ("125", "outside scope"), ("ITF", "outside scope")])
def test_unmodelled_competition_levels_are_excluded(rows, level, reason):
    assert parse_row(dict(rows[0], tourney_level=level), "WTA") == ExcludedMatch(reason)


def test_namespace_prevents_cross_tour_player_and_match_collisions(rows):
    atp, wta = parse_row(rows[0], "ATP"), parse_row(rows[0], "WTA")
    assert isinstance(atp, TennisEloMatch) and isinstance(wta, TennisEloMatch)
    assert atp.winner_key != wta.winner_key
    assert atp.source_key != wta.source_key


def test_qualifying_and_main_draw_keep_distinct_identity(rows):
    main = parse_row(rows[0], "ATP")
    qualifying = parse_row(dict(rows[0], round="Q1"), "ATP_QUALI")
    assert isinstance(main, TennisEloMatch) and isinstance(qualifying, TennisEloMatch)
    assert main.winner_key == qualifying.winner_key
    assert main.source_key != qualifying.source_key


def test_challenger_uses_the_mens_player_namespace(rows):
    match = parse_row(dict(rows[0], tourney_level="C"), "CHALLENGER")
    assert isinstance(match, TennisEloMatch)
    assert match.namespace == "ATP"


@pytest.mark.parametrize("value, expected", [(" Clay ", "clay"), ("GRASS", "grass"), ("Carpet", None), ("", None)])
def test_surface_normalization_preserves_unknown_surface(rows, value, expected):
    match = parse_row(dict(rows[0], surface=value), "ATP")
    assert isinstance(match, TennisEloMatch)
    assert match.surface == expected


@pytest.mark.parametrize("column", ["winner_id", "match_num", "tourney_date", "score", "best_of"])
def test_missing_columns_are_errors_not_intentional_exclusions(rows, column):
    row = dict(rows[0])
    del row[column]
    with pytest.raises(ValueError, match="Missing TennisMyLife ELO columns"):
        parse_row(row, "ATP")


@pytest.mark.parametrize("changes", [
    {"winner_id": ""}, {"winner_id": "B002"}, {"winner_id": "bad id"},
    {"winner_name": " "}, {"tourney_id": ""}, {"match_num": "0"}, {"match_num": "1.5"},
    {"tourney_date": "20210230"}, {"tourney_date": "202114"}, {"best_of": "2"},
    {"round": "Q1"}, {"round": "NEW"}, {"tourney_level": "NEW"},
    {"score": "bad score"}, {"score": "4-6 3-6"},
])
def test_malformed_identity_or_unverified_contract_raises(rows, changes):
    with pytest.raises(ValueError):
        parse_row(dict(rows[0], **changes), "ATP")


def test_duplicate_annual_and_ongoing_copies_count_once(rows):
    match = parse_row(rows[0], "ATP")
    assert isinstance(match, TennisEloMatch)
    assert deduplicate([match, replace(match)]) == [match]


@pytest.mark.parametrize("changes", [
    {"winner_id": "C003"}, {"score": "6-0 6-0"}, {"surface": "clay"},
    {"provider_date": date(2021, 1, 5)}, {"best_of": 5}, {"winner_name": "Other Player"},
])
def test_contradictory_duplicates_fail_even_when_the_key_is_unchanged(rows, changes):
    match = parse_row(rows[0], "ATP")
    assert isinstance(match, TennisEloMatch)
    with pytest.raises(ValueError, match="Conflicting TennisMyLife match"):
        deduplicate([match, replace(match, **changes)])


def test_distinct_rounds_and_matches_survive_and_input_order_does_not_matter(rows):
    first = parse_row(rows[0], "ATP")
    assert isinstance(first, TennisEloMatch)
    second = replace(first, match_number=2)
    last = replace(first, round="F")
    expected = [first, second, last]
    assert deduplicate([last, second, first, second]) == expected
    assert deduplicate(expected) == expected


def test_empty_batch_is_a_valid_empty_result():
    assert deduplicate([]) == []
