import pytest

from app.services.ask.preview import parse_arguments


def test_key_value_pairs_survive_any_shell():
    assert parse_arguments(["sport=nfl", "query=patrick mahomes"]) == {"sport": "nfl", "query": "patrick mahomes"}


def test_values_may_contain_equals_signs():
    assert parse_arguments(["query=a=b"]) == {"query": "a=b"}


def test_a_single_json_object_still_works():
    assert parse_arguments(['{"sport": "nba", "limit": 3}']) == {"sport": "nba", "limit": 3}


def test_no_arguments_is_an_empty_input():
    assert parse_arguments([]) == {}


@pytest.mark.parametrize("args", [["sport"], ["=nba"], ["[1, 2]"]])
def test_malformed_arguments_are_rejected(args):
    with pytest.raises(ValueError):
        parse_arguments(args)
