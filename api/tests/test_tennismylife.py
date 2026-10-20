import csv
import hashlib
from datetime import date
from pathlib import Path

import pytest

from app.core.tennismylife import PlayerNameIndex, TmlBoxScore, parse_rows, resolve_name
from app.repositories.players import normalize_name


@pytest.fixture
def rows() -> list[dict[str, str]]:
    # Unaltered rows from https://stats.tennismylife.org/data/{2026,2000}.csv,
    # retrieved 2026-10-20: straight sets, tie-break, RET, W/O, no stats, Carpet.
    path = Path(__file__).parent / "fixtures" / "tennismylife.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def test_straight_sets_has_exact_player_oriented_counts(rows):
    winner, loser = parse_rows(rows[:1], "ATP")
    assert winner == TmlBoxScore(
        player_name="Sebastian Baez", tour="ATP",
        source_match_key=hashlib.sha256(b"tml-v1|2026-9900|RR|jaume munar").hexdigest(),
        match_date=date(2026, 1, 2), surface="Hard", result="W",
        aces=0, double_faults=2, service_games=10,
        break_points_faced=6, break_points_saved=4,
        break_chances_created=6, break_points_converted=4,
        opponent_name="Jaume Munar", round="RR", tournament="United Cup", score="6-4 6-4",
    )
    assert loser == TmlBoxScore(
        player_name="Jaume Munar", tour="ATP",
        source_match_key=hashlib.sha256(b"tml-v1|2026-9900|RR|sebastian baez").hexdigest(),
        match_date=date(2026, 1, 2), surface="Hard", result="L",
        aces=7, double_faults=0, service_games=10,
        break_points_faced=6, break_points_saved=2,
        break_chances_created=6, break_points_converted=2,
        opponent_name="Sebastian Baez", round="RR", tournament="United Cup", score="6-4 6-4",
    )


def test_tiebreak_score_stays_winner_first_on_both_sides(rows):
    winner, loser = parse_rows(rows[1:2], "ATP")
    assert winner.score == loser.score == "6-7(2) 7-6(3) 7-5"
    assert (winner.aces, loser.aces) == (12, 18)
    assert (winner.break_points_converted, loser.break_points_converted) == (1, 0)


def test_retirement_keeps_the_partial_stats_and_score(rows):
    winner, loser = parse_rows(rows[2:3], "ATP")
    assert winner.score == loser.score == "6-3 1-2 RET"
    assert (winner.aces, loser.aces) == (6, 6)
    assert (winner.service_games, loser.service_games) == (6, 6)


def test_walkover_is_skipped_even_if_counts_are_present(rows):
    assert parse_rows(rows[3:4], "ATP") == []
    row = dict(rows[3], w_ace="0", l_ace="0")
    assert parse_rows([row], "ATP") == []


def test_no_stats_is_skipped_per_side_and_zero_counts_are_kept(rows):
    assert parse_rows(rows[4:5], "ATP") == []
    row = dict(rows[4], w_ace="0")
    (winner,) = parse_rows([row], "ATP")
    assert winner.aces == 0
    assert winner.double_faults is None and winner.service_games is None


@pytest.mark.parametrize("surface, expected", [
    ("Hard", "Hard"), ("Clay", "Clay"), ("Grass", "Grass"), ("Carpet", None), ("", None),
])
def test_surface_mapping_and_tour_passthrough(rows, surface, expected):
    row = dict(rows[5], surface=surface)
    winner, loser = parse_rows([row], "WTA")
    assert winner.surface == loser.surface == expected
    assert winner.tour == loser.tour == "WTA"


@pytest.mark.parametrize("bad", [None, "", "NA", "NaN", "inf", "-1", "3.5", "bad"])
def test_bad_numbers_remain_missing_instead_of_zero(rows, bad):
    row = dict(rows[0], w_ace=bad, w_df=bad, w_bpFaced=bad, l_bpSaved=bad)
    winner, loser = parse_rows([row], "ATP")
    assert winner.aces is None and winner.double_faults is None
    assert winner.break_points_faced is None
    assert winner.break_points_converted is None
    assert loser.break_chances_created is None and loser.break_points_converted is None


def test_break_conversion_is_floored_at_zero(rows):
    row = dict(rows[0], l_bpSaved="8", l_bpFaced="6")
    winner, _ = parse_rows([row], "ATP")
    assert winner.break_chances_created == 6
    assert winner.break_points_converted == 0


def test_key_ignores_counts_and_score_and_trims_and_lowercases_opponent(rows):
    before = parse_rows(rows[:1], "ATP")[0]
    row = dict(rows[0], loser_name="  JAUME MUNAR  ", w_ace="12", score="6-3 6-3")
    after = parse_rows([row], "ATP")[0]
    assert before.source_match_key == after.source_match_key


@pytest.mark.parametrize("column", ["tourney_id", "round", "loser_name"])
def test_different_match_identity_changes_the_key(rows, column):
    before = parse_rows(rows[:1], "ATP")[0]
    row = dict(rows[0])
    row[column] += "other"
    assert parse_rows([row], "ATP")[0].source_match_key != before.source_match_key


@pytest.mark.parametrize("column", [
    "tourney_id", "tourney_name", "tourney_date", "surface", "round", "score",
    "winner_name", "loser_name", "w_ace", "w_df", "w_SvGms", "w_bpSaved", "w_bpFaced",
    "l_ace", "l_df", "l_SvGms", "l_bpSaved", "l_bpFaced",
])
def test_missing_required_column_fails_loudly(rows, column):
    row = dict(rows[0])
    del row[column]
    with pytest.raises(ValueError, match=f"Missing TennisMyLife columns: {column}"):
        parse_rows([row], "ATP")


@pytest.mark.parametrize("column, value", [
    ("tourney_date", "20260230"), ("tourney_id", ""), ("round", " "), ("winner_name", ""),
])
def test_bad_date_or_empty_identity_raises_for_the_ingest_to_skip(rows, column, value):
    row = dict(rows[0])
    row[column] = value
    with pytest.raises(ValueError):
        parse_rows([row], "ATP")


@pytest.mark.parametrize("tour, expected", [("ATP", 11), ("WTA", 22), ("atp", 11)])
def test_resolve_name_keeps_same_name_players_on_different_tours(tour: str, expected: int) -> None:
    index = PlayerNameIndex(canonical={("alex smith", "ATP"): 11, ("alex smith", "WTA"): 22}, aliases={})
    assert resolve_name(index, "alex smith", tour) == expected


def test_resolve_name_prefers_the_canonical_name_over_an_alias() -> None:
    index = PlayerNameIndex(canonical={("alex smith", "ATP"): 11}, aliases={"alex smith": 22})
    assert resolve_name(index, "alex smith", "ATP") == 11


@pytest.mark.parametrize("tour", ["ATP", "WTA"])
def test_resolve_name_falls_back_to_the_global_alias_like_resolve_player(tour: str) -> None:
    index = PlayerNameIndex(canonical={("alexander smith", "ATP"): 11}, aliases={"a smith": 11})
    assert resolve_name(index, "a smith", tour) == 11


@pytest.mark.parametrize("name, tour", [("unknown player", "ATP"), ("alex smith", "WTA")])
def test_resolve_name_returns_none_for_a_miss_or_wrong_canonical_tour(name: str, tour: str) -> None:
    index = PlayerNameIndex(canonical={("alex smith", "ATP"): 11}, aliases={})
    assert resolve_name(index, name, tour) is None


@pytest.mark.parametrize("name", ["  Joao\u00a0Sousa  ", "Jo\u00e3o Sousa"])
def test_resolve_name_accepts_names_normalized_by_the_repository(name: str) -> None:
    index = PlayerNameIndex(canonical={("joao sousa", "ATP"): 11}, aliases={})
    assert resolve_name(index, normalize_name(name), "ATP") == 11
