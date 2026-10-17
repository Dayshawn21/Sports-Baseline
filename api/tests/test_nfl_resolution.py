import datetime as dt

from app.core.nfl_resolution import (
    PlayerCandidate, Resolution, find_game_id, index_candidates, resolve_player,
)

JAMESON = PlayerCandidate(1, "Jameson Williams", team="DET", position="WR")
JAVONTE = PlayerCandidate(2, "Javonte Williams", team="DEN", position="RB")
WADDLE = PlayerCandidate(4, "Jaylen Waddle", team="MIA", position="WR")
ST_BROWN = PlayerCandidate(5, "Amon-Ra St. Brown", team="DET", position="WR")
GODWIN = PlayerCandidate(6, "Chris Godwin Jr.", team="TB", position="WR")
AJ_BROWN = PlayerCandidate(7, "A.J. Brown", team="PHI", position="WR")
BIJAN = PlayerCandidate(8, "Bijan Robinson", team="ATL", position="RB")
BRIAN = PlayerCandidate(9, "Brian Robinson", team="ATL", position="RB")
OKONKWO = PlayerCandidate(10, "Chigoziem Okonkwo", team="TEN", position="TE")
# NFLverse carries genuinely duplicate full names, e.g. two "Jonah Williams".
JONAH_OT = PlayerCandidate(11, "Jonah Williams", team="ARI", position="OT")
JONAH_DE = PlayerCandidate(12, "Jonah Williams", team="LA", position="DE")

ROSTER = index_candidates([
    JAMESON, JAVONTE, WADDLE, ST_BROWN, GODWIN, AJ_BROWN, BIJAN, BRIAN, OKONKWO,
    JONAH_OT, JONAH_DE,
])


def resolve(name, team=None, position=None, aliases=None):
    return resolve_player(name, team, position, ROSTER, aliases)


def outcome(result):
    return result.player_id, result.reason


def test_a_unique_name_resolves_without_any_other_signal() -> None:
    assert outcome(resolve("Jaylen Waddle")) == (4, Resolution.UNIQUE_NAME)


def test_names_containing_periods_resolve() -> None:
    # Keying roster names in the old "A.St. Brown" shape split these on the
    # first period, so all three were unmatchable.
    assert outcome(resolve("Amon-Ra St. Brown")) == (5, Resolution.UNIQUE_NAME)
    assert outcome(resolve("Chris Godwin Jr.")) == (6, Resolution.UNIQUE_NAME)
    assert outcome(resolve("A.J. Brown")) == (7, Resolution.UNIQUE_NAME)


def test_a_missing_suffix_still_resolves() -> None:
    assert outcome(resolve("Chris Godwin")) == (6, Resolution.UNIQUE_NAME)


def test_full_name_separates_players_sharing_an_initial_and_team() -> None:
    # Same key, team, and position, so only the first name can decide.
    assert outcome(resolve("Bijan Robinson", "ATL", "RB")) == (8, Resolution.FULL_NAME)
    assert outcome(resolve("Brian Robinson", "ATL", "RB")) == (9, Resolution.FULL_NAME)


def test_full_name_decides_without_team_or_position() -> None:
    assert outcome(resolve("Jameson Williams")) == (1, Resolution.FULL_NAME)


def test_a_nickname_falls_back_to_the_shared_key() -> None:
    assert outcome(resolve("Chig Okonkwo", "TEN", "TE")) == (10, Resolution.UNIQUE_NAME)


def test_position_breaks_a_duplicate_full_name() -> None:
    assert outcome(resolve("Jonah Williams", "LA", "DE")) == (12, Resolution.POSITION_TIEBREAK)


def test_team_breaks_the_tie_position_cannot() -> None:
    twin = PlayerCandidate(13, "Jonah Williams", team="CIN", position="OT")
    index = index_candidates([JONAH_OT, twin])
    result = resolve_player("Jonah Williams", "CIN", "OT", index)
    assert outcome(result) == (13, Resolution.TEAM_TIEBREAK)


def test_a_duplicate_full_name_with_no_distinguishing_signal_is_refused() -> None:
    assert outcome(resolve("Jonah Williams")) == (None, Resolution.AMBIGUOUS)


def test_a_tie_still_unresolved_after_both_filters_is_refused() -> None:
    twin = PlayerCandidate(13, "Jonah Williams", team="ARI", position="OT")
    index = index_candidates([JONAH_OT, twin])
    result = resolve_player("Jonah Williams", "ARI", "OT", index)
    assert outcome(result) == (None, Resolution.AMBIGUOUS)


def test_a_player_absent_from_the_roster_returns_no_candidate() -> None:
    # The 2025 rookie case: no amount of matching invents a missing row.
    assert outcome(resolve("Emeka Egbuka", "TB", "WR")) == (None, Resolution.NO_CANDIDATE)


def test_a_contradicting_position_is_refused_rather_than_ignored() -> None:
    # No J.Williams is a QB, so this is evidence of a different player.
    assert outcome(resolve("Jalen Williams", "DET", "QB")) == (None, Resolution.CONTRADICTED)


def test_a_stale_team_narrows_but_never_vetoes() -> None:
    """Rosters move between seasons, so a team mismatch is not a contradiction.

    Both twins are OT, so position cannot decide, and the provider's current team
    matches neither stored team. That is stale data, not a different player, so it
    must read as undecided rather than as positive evidence against.
    """
    twin = PlayerCandidate(13, "Jonah Williams", team="CIN", position="OT")
    index = index_candidates([JONAH_OT, twin])
    result = resolve_player("Jonah Williams", "BUF", "OT", index)
    assert outcome(result) == (None, Resolution.AMBIGUOUS)


CHASE_BROWN = PlayerCandidate(20, "Chase Brown", team="CIN", position="RB")
JOSH_PALMER = PlayerCandidate(21, "Josh Palmer", team="BUF", position="WR")
LONE_ROSTER = index_candidates([CHASE_BROWN, JOSH_PALMER])


def test_a_lone_match_differing_in_full_name_and_team_is_refused() -> None:
    # Camden Brown is not stored, so "C. Brown" has one candidate: the wrong player.
    result = resolve_player("Camden Brown", "DAL", "WR", LONE_ROSTER)

    assert outcome(result) == (None, Resolution.NAME_TEAM_CONFLICT)
    assert result.matched is False


def test_a_lone_match_with_a_nickname_on_the_same_team_resolves() -> None:
    assert outcome(resolve_player("Joshua Palmer", "BUF", "WR", LONE_ROSTER)) == (21, Resolution.UNIQUE_NAME)


def test_a_lone_match_with_the_same_full_name_on_another_team_resolves() -> None:
    # A traded player, or a stored team that has not caught up: not a different person.
    assert outcome(resolve_player("Chase Brown", "DAL", "RB", LONE_ROSTER)) == (20, Resolution.UNIQUE_NAME)


def test_a_team_alias_is_not_a_team_conflict() -> None:
    hunter = PlayerCandidate(22, "Travis Hunter", team="JAX", position="CB")
    index = index_candidates([hunter])

    assert outcome(resolve_player("Trav Hunter", "JAC", "WR", index)) == (22, Resolution.UNIQUE_NAME)


def test_a_lone_match_without_a_team_on_either_side_resolves_as_before() -> None:
    teamless = index_candidates([PlayerCandidate(23, "Chase Brown", team=None, position="RB")])

    assert outcome(resolve_player("Camden Brown", None, "WR", LONE_ROSTER)) == (20, Resolution.UNIQUE_NAME)
    assert outcome(resolve_player("Camden Brown", "DAL", "WR", teamless)) == (23, Resolution.UNIQUE_NAME)


def test_an_unkeyable_name_is_reported_not_guessed() -> None:
    assert outcome(resolve("Cher")) == (None, Resolution.UNKEYABLE_NAME)


def test_an_alias_wins_over_automatic_matching() -> None:
    # The override exists so a human can correct a wrong automatic match.
    assert outcome(resolve("Jameson Williams", aliases={"j.williams": 99})) == (99, Resolution.ALIAS)


def test_an_alias_resolves_a_name_the_roster_cannot() -> None:
    assert outcome(resolve("Emeka Egbuka", aliases={"e.egbuka": 77})) == (77, Resolution.ALIAS)


def test_matched_property_reflects_the_outcome() -> None:
    assert resolve("Jaylen Waddle").matched is True
    assert resolve("Jonah Williams").matched is False


def test_indexing_skips_candidates_whose_name_cannot_be_keyed() -> None:
    index = index_candidates([PlayerCandidate(1, ""), WADDLE])
    assert list(index) == ["j.waddle"]


GAMES = {
    ("MIA", dt.date(2026, 9, 14)): 100,
    ("DEN", dt.date(2026, 9, 20)): 200,
}


def _utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=dt.timezone.utc)


def test_a_daytime_kickoff_matches_its_own_utc_date() -> None:
    assert find_game_id("DEN", _utc(2026, 9, 20, 17, 0), GAMES) == 200


def test_an_evening_kickoff_matches_the_previous_local_day() -> None:
    # 20:15 ET Monday-night kickoff is 00:15 UTC the next day, but game_date is
    # the local day, so matching only the UTC date would miss every night game.
    assert find_game_id("MIA", _utc(2026, 9, 15, 0, 15), GAMES) == 100


def test_team_casing_from_the_provider_does_not_matter() -> None:
    assert find_game_id("mia", _utc(2026, 9, 15, 0, 15), GAMES) == 100


def test_a_game_that_is_not_loaded_returns_none() -> None:
    assert find_game_id("BUF", _utc(2026, 9, 20, 17, 0), GAMES) is None


def test_provider_team_aliases_find_the_nflverse_game() -> None:
    # PrizePicks sends JAC and LAR; NFLverse schedules store JAX and LA.
    games = {("JAX", dt.date(2026, 9, 20)): 300, ("LA", dt.date(2026, 9, 21)): 400}

    assert find_game_id("JAC", _utc(2026, 9, 20, 17, 0), games) == 300
    assert find_game_id("LAR", _utc(2026, 9, 22, 0, 15), games) == 400
    assert find_game_id("LA", _utc(2026, 9, 22, 0, 15), games) == 400


def test_a_provider_team_alias_narrows_to_the_nflverse_team() -> None:
    twin = PlayerCandidate(13, "Jonah Williams", team="JAX", position="OT")
    index = index_candidates([JONAH_OT, twin])

    assert outcome(resolve_player("Jonah Williams", "JAC", "OT", index)) == (13, Resolution.TEAM_TIEBREAK)


def test_missing_team_or_kickoff_returns_none() -> None:
    assert find_game_id(None, _utc(2026, 9, 20, 17, 0), GAMES) is None
    assert find_game_id("DEN", None, GAMES) is None
