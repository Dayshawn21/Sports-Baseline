from app.core.ask_find import MAX_MATCHES, Candidate, fold, match_candidates


def _player(name: str, entity_id: int) -> Candidate:
    return Candidate("player", name, f"/nfl/player/{entity_id}", entity_id, 1)


def test_fold_ignores_accents_case_and_punctuation():
    assert fold("Egor Dëmin") == fold("egor demin") == "egor demin"
    assert fold("De'Aaron  Fox") == "de aaron fox"


def test_exact_beats_word_prefix_beats_substring():
    candidates = [_player("Jalen Williams", 1), _player("Jaylin Williams", 2), _player("Williams", 3)]
    names = [c.name for c in match_candidates("williams", candidates)]
    assert names[0] == "Williams"
    assert set(names[1:]) == {"Jalen Williams", "Jaylin Williams"}


def test_partial_surname_and_first_name_prefix_match():
    candidates = [_player("Patrick Mahomes", 1), _player("Pat Freiermuth", 2)]
    assert [c.name for c in match_candidates("mahom", candidates)] == ["Patrick Mahomes"]
    assert [c.name for c in match_candidates("pat mah", candidates)] == ["Patrick Mahomes"]


def test_accented_names_match_plain_queries():
    assert match_candidates("demin", [_player("Egor Dëmin", 7)])[0].entity_id == 7


def test_one_entry_per_entity_and_ambiguity_is_kept():
    candidates = [_player("Jalen Williams", 1), _player("Jalen Williams", 1), _player("Jalen Williams", 9)]
    assert [c.entity_id for c in match_candidates("jalen williams", candidates)] == [1, 9]


def test_no_match_and_empty_query_return_nothing():
    assert match_candidates("zzz", [_player("Patrick Mahomes", 1)]) == []
    assert match_candidates("--", [_player("Patrick Mahomes", 1)]) == []


def test_results_are_capped():
    candidates = [_player(f"Smith {n}", n) for n in range(MAX_MATCHES + 5)]
    assert len(match_candidates("smith", candidates)) == MAX_MATCHES
