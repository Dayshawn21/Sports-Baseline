import pytest

from app.services.sport_registry import PROP_SOURCES, prop_source


def test_nfl_resolves_to_the_nfl_source() -> None:
    assert prop_source("nfl").config.code == "nfl"


def test_nba_resolves_to_the_nba_source() -> None:
    source = prop_source("nba")
    assert source.config.code == "nba"
    assert (source.model_version, source.over_probability_version) == ("nba-reference-v1", "nba-pover-v1")


def test_an_unknown_sport_names_the_known_ones() -> None:
    with pytest.raises(KeyError, match=r"'wnba'.*\['nba', 'nfl'\]"):
        prop_source("wnba")


@pytest.mark.parametrize("code", sorted(PROP_SOURCES))
def test_each_registered_source_is_keyed_by_its_own_sport(code: str) -> None:
    assert prop_source(code).config.code == code
