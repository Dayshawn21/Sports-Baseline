import pytest

from app.core.nfl_names import canonical_team_code, full_name_key, nflverse_name_key, provider_name_key


@pytest.mark.parametrize(("code", "expected"), [
    ("JAC", "JAX"), ("jac", "JAX"), ("LAR", "LA"), (" LAR ", "LA"),
    ("JAX", "JAX"), ("LA", "LA"), ("DAL", "DAL"),
    # Unknown codes pass through so they fail visibly rather than being guessed.
    ("XYZ", "XYZ"),
    (None, None), ("", None), ("  ", None),
])
def test_canonical_team_code_maps_only_known_provider_aliases(code: str | None, expected: str | None) -> None:
    assert canonical_team_code(code) == expected


@pytest.mark.parametrize(
    "nflverse, provider",
    [
        ("M.Pittman", "Michael Pittman Jr."),
        ("O.Beckham", "Odell Beckham Jr."),
        ("L.Burden", "Luther Burden III"),
        ("K.Walker", "Kenneth Walker III"),
        ("J.Smith-Njigba", "Jaxon Smith-Njigba"),
        ("C.Edwards-Helaire", "Clyde Edwards-Helaire"),
        ("A.O'Connell", "Aidan O'Connell"),
        ("J.Chase", "Ja'Marr Chase"),
        ("D.Achane", "De'Von Achane"),
        ("A.St. Brown", "Amon-Ra St. Brown"),
        ("J.Dobbins", "J.K. Dobbins"),
        ("W.Robinson", "Wan'Dale Robinson"),
    ],
)
def test_both_sources_reduce_to_the_same_key(nflverse: str, provider: str) -> None:
    assert nflverse_name_key(nflverse) == provider_name_key(provider)


def test_multi_word_surnames_survive() -> None:
    # Taking only the last token would key this as "a.brown" and match the wrong player.
    assert provider_name_key("Amon-Ra St. Brown") == "a.stbrown"
    assert nflverse_name_key("A.St. Brown") == "a.stbrown"


def test_the_key_cannot_disambiguate_shared_initials() -> None:
    """The reason resolution needs team or position, proven rather than assumed."""
    assert provider_name_key("Jameson Williams") == provider_name_key("Javonte Williams")
    assert nflverse_name_key("J.Williams") == provider_name_key("Jameson Williams")


def test_suffix_is_not_mistaken_for_a_surname() -> None:
    assert provider_name_key("Marvin Harrison Jr.") == "m.harrison"
    assert provider_name_key("James Cook III") == "j.cook"


def test_a_lone_suffix_like_token_is_kept_when_it_is_the_surname() -> None:
    # Two tokens means the second is the surname, even when it reads like a suffix.
    assert provider_name_key("Jared Verse") == "j.verse"


def test_unusable_names_return_none() -> None:
    for name in ("", "   ", "Cher", "."):
        assert provider_name_key(name) is None, name
        assert full_name_key(name) is None, name
    assert nflverse_name_key("") is None


def test_full_name_key_separates_what_the_short_key_merges() -> None:
    assert provider_name_key("Bijan Robinson") == provider_name_key("Brian Robinson")
    assert full_name_key("Bijan Robinson") != full_name_key("Brian Robinson")


def test_full_name_key_ignores_punctuation_and_suffixes() -> None:
    assert full_name_key("Chris Godwin Jr.") == full_name_key("Chris Godwin") == "chrisgodwin"
    assert full_name_key("A.J. Brown") == full_name_key("AJ Brown")
    assert full_name_key("Amon-Ra St. Brown") == "amonrastbrown"
