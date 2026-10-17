"""
Source selection for TennisAbstract fetches.

Two real hazards are covered here:
  1. /jsmatches/ is frozen around 2018 for men. Routing a man there produced
     "Insufficient data — fewer than 3 matches in last 52 weeks (found 89 total)"
     even though his classic page had 413 matches through last week.
  2. player-classic.cgi does NOT 404 on a name it cannot find — `?p=LoisBoisson`
     returns Benoit Paire's career. Accepting that would write one player's stats
     into another's row.
"""
import json
from datetime import date, timedelta

import pytest

from app.ingest import player_stats as ps


def _page(fullname: str, dates: list[str]) -> str:
    """Minimal TennisAbstract page: identity marker + a matchmx array."""
    rows = [[d] + [""] * (ps.I_OCHANCES) for d in dates]
    return f"var fullname = '{fullname}';\nvar matchmx = {json.dumps(rows)};\n"


class _Resp:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code


@pytest.fixture
def fetched(monkeypatch):
    """Record which URLs were requested, serving canned pages per URL substring."""
    calls: list[str] = []
    pages: dict[str, _Resp] = {}

    def fake_get(url, **kwargs):
        calls.append(url)
        for key, resp in pages.items():
            if key in url:
                return resp
        return _Resp(status_code=404)

    monkeypatch.setattr(ps._session, "get", fake_get)
    monkeypatch.setattr(ps.time, "sleep", lambda *_: None)
    return calls, pages


def _recent() -> str:
    return (date.today() - timedelta(days=5)).strftime("%Y%m%d")


# =============================================================================
# Identity guard
# =============================================================================

def test_identity_rejects_a_different_player():
    assert ps._identity_ok("var fullname = 'Benoit Paire';", "LoisBoisson") is False


def test_identity_accepts_the_requested_player():
    assert ps._identity_ok("var fullname = 'Lois Boisson';", "LoisBoisson") is True


def test_identity_ignores_accents_and_punctuation():
    assert ps._identity_ok("var fullname = 'Félix Auger-Aliassime';", "FelixAugerAliassime") is True


def test_identity_tolerates_generational_suffixes():
    # TA_SLUG_OVERRIDES maps some names to Jr/Sr slugs the page itself omits.
    assert ps._identity_ok("var fullname = 'Martin Damm';", "MartinDammJr") is True


def test_identity_passes_when_the_page_has_no_marker():
    assert ps._identity_ok("<html>nothing here</html>", "AnySlug") is True


# =============================================================================
# Source selection
# =============================================================================

def test_man_on_challenger_gets_the_classic_page_not_stale_jsmatches(fetched):
    """The reported bug: tour was CHALLENGER, so he was sent to the 2018 mirror."""
    calls, pages = fetched
    pages["player-classic.cgi"] = _Resp(_page("Andrea Guerrieri", [_recent()] * 5))
    pages["jsmatches"] = _Resp(_page("Andrea Guerrieri", ["20181001"] * 89))

    rows = ps._fetch_matches("Andrea Guerrieri", tour="CHALLENGER")

    assert rows is not None and len(rows) == 5
    assert ps._newest_date(rows) == _recent()
    # Fresh on the first source, so the second is never paid for.
    assert len(calls) == 1


def test_woman_on_challenger_is_not_given_the_wrong_players_career(fetched):
    calls, pages = fetched
    pages["player-classic.cgi"] = _Resp(_page("Benoit Paire", [_recent()] * 1076))
    pages["jsmatches"] = _Resp(_page("Lois Boisson", [_recent()] * 54))

    rows = ps._fetch_matches("Lois Boisson", tour="CHALLENGER")

    assert rows is not None and len(rows) == 54
    assert len(calls) == 2  # classic rejected on identity, fell through


def test_wta_still_hits_jsmatches_first(fetched):
    calls, pages = fetched
    pages["jsmatches"] = _Resp(_page("Aryna Sabalenka", [_recent()] * 125))

    rows = ps._fetch_matches("Aryna Sabalenka", tour="WTA")

    assert rows is not None and len(rows) == 125
    assert len(calls) == 1
    assert "jsmatches" in calls[0]


def test_stale_first_source_falls_through_to_the_fresh_one(fetched):
    calls, pages = fetched
    pages["player-classic.cgi"] = _Resp(_page("Someone Old", ["20181001"] * 89))
    pages["jsmatches"] = _Resp(_page("Someone Old", [_recent()] * 40))

    rows = ps._fetch_matches("Someone Old", tour="CHALLENGER")

    assert len(rows) == 40
    assert len(calls) == 2


def test_when_every_source_is_stale_the_richest_one_is_still_returned(fetched):
    """Thin data beats no data — the caller reports 'insufficient', not a crash."""
    calls, pages = fetched
    pages["player-classic.cgi"] = _Resp(_page("Retired Player", ["20150101"] * 10))
    pages["jsmatches"] = _Resp(_page("Retired Player", ["20181001"] * 89))

    rows = ps._fetch_matches("Retired Player", tour="CHALLENGER")

    assert len(rows) == 89  # the newer of the two stale mirrors
    assert len(calls) == 2


def test_missing_everywhere_returns_none(fetched):
    calls, pages = fetched
    rows = ps._fetch_matches("Nobody At All", tour="CHALLENGER")
    assert rows is None
    assert len(calls) == 2


def test_empty_match_array_is_not_treated_as_data(fetched):
    calls, pages = fetched
    pages["player-classic.cgi"] = _Resp("var fullname = 'Nobody';\nvar matchmx = [];\n")
    pages["jsmatches"] = _Resp(_page("Nobody", [_recent()] * 7))

    rows = ps._fetch_matches("Nobody", tour="CHALLENGER")

    assert rows is not None and len(rows) == 7
