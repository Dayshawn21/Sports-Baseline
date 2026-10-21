"""Parser tests for the livetennisapi ingest.

Pure unit tests — no DB, no network. The `real_matches` fixture is a genuine
`GET /matches?status=upcoming&draw=singles` payload captured from the API, so
these tests fail if the provider's shape drifts.
"""
import asyncio
import datetime as dt
import json
from pathlib import Path

import httpx
import pytest

from app.ingest import livetennis
from app.services.tennis.feature_builder import ROUND_ORDINALS

FIXTURE = Path(__file__).parent / "fixtures" / "livetennis_matches.json"


@pytest.fixture(scope="module")
def real_matches():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))["data"]


# =============================================================================
# Field mapping
# =============================================================================

@pytest.mark.parametrize(
    "raw,expected",
    [("atp", "ATP"), ("wta", "WTA"), ("challenger", "CHALLENGER"), ("ATP", "ATP")],
)
def test_map_tour_accepts_supported_tours(raw, expected):
    assert livetennis._map_tour(raw) == expected


@pytest.mark.parametrize("raw", ["itf", "juniors", "", None, "unknown"])
def test_map_tour_rejects_everything_else(raw):
    assert livetennis._map_tour(raw) is None


@pytest.mark.parametrize(
    "raw,expected", [("hard", "Hard"), ("clay", "Clay"), ("grass", "Grass"), (None, None)]
)
def test_map_surface_matches_feature_builder_vocabulary(raw, expected):
    assert livetennis._map_surface(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [("upcoming", "scheduled"), ("live", "live"), ("completed", "completed"),
     ("cancelled", "cancelled"), (None, "scheduled")],
)
def test_map_status(raw, expected):
    assert livetennis._map_status(raw) == expected


def test_map_status_lets_cancelled_event_status_override_upcoming():
    # Observed live: the lifecycle gate flips upcoming->cancelled late, so the
    # admin status is the earlier signal.
    assert livetennis._map_status("upcoming", "Cancelled") == "cancelled"


def test_map_status_ignores_undocumented_event_status_values():
    # "Finished" is returned by the API but absent from its documented enum.
    assert livetennis._map_status("live", "Finished") == "live"


def test_map_status_does_not_downgrade_a_completed_match():
    assert livetennis._map_status("completed", "Cancelled") == "completed"


@pytest.mark.parametrize("raw,expected", [("BO3", 3), ("BO5", 5), (None, None), ("BO7", None)])
def test_map_best_of(raw, expected):
    assert livetennis._map_best_of(raw) == expected


def test_parse_dt_normalizes_z_suffix_to_utc():
    parsed = livetennis._parse_dt("2026-08-24T14:00:00Z")
    assert parsed == dt.datetime(2026, 8, 24, 14, 0, tzinfo=dt.timezone.utc)


def test_parse_dt_returns_none_on_garbage():
    assert livetennis._parse_dt("not a date") is None
    assert livetennis._parse_dt(None) is None


# =============================================================================
# Score formatting
# =============================================================================

def test_format_score_reads_games_as_two_per_player_lists():
    # games is [games_p1, games_p2] - NOT a list of per-set pairs.
    score = {"games": [[6, 3, 3], [4, 6, 6]]}
    assert livetennis._format_score(score) == "6-4 3-6 3-6"


def test_format_score_handles_a_straight_sets_win():
    assert livetennis._format_score({"games": [[6, 7], [3, 5]]}) == "6-3 7-5"


def test_format_score_returns_none_for_an_unplayed_match():
    # Upcoming matches carry empty games arrays.
    assert livetennis._format_score({"games": [[], []]}) is None


@pytest.mark.parametrize(
    "score", [None, {}, {"games": None}, {"games": [[1, 2]]}, {"games": [1, 2]}]
)
def test_format_score_returns_none_on_unusable_shapes(score):
    assert livetennis._format_score(score) is None


def test_format_score_truncates_to_the_shorter_side():
    # A half-written set should not invent a game count for the other player.
    assert livetennis._format_score({"games": [[6, 4], [3]]}) == "6-3"


# =============================================================================
# Match normalization
# =============================================================================

def _match(**overrides):
    base = {
        "id": 1,
        "tour": "atp",
        "draw": "singles",
        "surface": "hard",
        "format": "BO3",
        "round_code": "R32",
        "status": "upcoming",
        "event_status": None,
        "scheduled_time": "2026-08-24T14:00:00Z",
        "tournament": "Winston-Salem",
        "score": None,
        "winner": None,
        "players": {
            "p1": {"id": 95, "name": "Roman Safiullin", "ranking": 103, "birthday": "1997-08-07"},
            "p2": {"id": 531, "name": "Marton Fucsovics", "ranking": 82, "birthday": "1992-02-08"},
        },
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize("tournament_id", ["14767", "14763"])
def test_normalize_match_corrects_lyon_surface(tournament_id: str) -> None:
    rec = livetennis.normalize_match(_match(
        tournament="Lyon", tournament_id=tournament_id, surface="clay", indoor=None,
    ))
    assert rec is not None
    assert rec["surface"] == "Hard"
    assert rec["indoor"] is True
    assert rec["tournament_id"] == tournament_id


def test_normalize_match_preserves_other_lyon_edition() -> None:
    rec = livetennis.normalize_match(_match(
        tournament="Lyon", tournament_id="99999", surface="clay", indoor=False,
    ))
    assert rec is not None
    assert rec["surface"] == "Clay"
    assert rec["indoor"] is False


def test_normalize_match_maps_every_stored_field():
    rec = livetennis.normalize_match(_match())
    assert rec["match_id"] == 1
    assert rec["tour"] == "ATP"
    assert rec["surface"] == "Hard"
    assert rec["best_of"] == 3
    assert rec["round_"] == "R32"
    assert rec["status"] == "scheduled"
    assert rec["day"] == dt.date(2026, 8, 24)
    assert rec["start_utc"] == dt.datetime(2026, 8, 24, 14, 0, tzinfo=dt.timezone.utc)
    assert rec["p1_name"] == "Roman Safiullin"
    assert rec["p1_rank"] == 103
    assert rec["p1_birth_date"] == dt.date(1997, 8, 7)
    assert rec["p2_lt_id"] == 531


def test_normalize_match_drops_doubles_and_team_ties():
    # Null draw means a team tie or unstated event type - not singles.
    assert livetennis.normalize_match(_match(draw="doubles")) is None
    assert livetennis.normalize_match(_match(draw=None)) is None


@pytest.mark.parametrize("tour", ["itf", "juniors", None])
def test_normalize_match_drops_unwanted_tours(tour):
    assert livetennis.normalize_match(_match(tour=tour)) is None


def test_normalize_match_drops_rows_without_a_scheduled_time():
    # match_date is NOT NULL, so a timeless row cannot be stored.
    assert livetennis.normalize_match(_match(scheduled_time=None)) is None


def test_normalize_match_drops_rows_missing_a_player_name():
    broken = _match()
    broken["players"]["p2"] = {"id": 531, "name": None}
    assert livetennis.normalize_match(broken) is None


def test_normalize_match_treats_unranked_as_none_not_zero():
    rec = livetennis.normalize_match(
        _match(players={
            "p1": {"id": 1, "name": "A Player", "ranking": 0},
            "p2": {"id": 2, "name": "B Player", "ranking": None},
        })
    )
    assert rec["p1_rank"] is None
    assert rec["p2_rank"] is None


def test_normalize_match_keeps_the_fields_the_ingest_used_to_discard():
    rec = livetennis.normalize_match(_match(
        indoor=True,
        tournament_id="11043",
        players={
            "p1": {"id": 1, "name": "A Player", "ranking": 3, "ranking_points": 7265,
                   "ranking_movement": "up", "hand": "R", "country": "ita"},
            "p2": {"id": 2, "name": "B Player", "ranking": 9, "ranking_points": 4689,
                   "ranking_movement": "same", "hand": "L", "country": "usa"},
        },
    ))
    assert rec["indoor"] is True
    assert rec["tournament_id"] == "11043"
    assert rec["p1_ranking_points"] == 7265
    assert rec["p2_ranking_points"] == 4689
    assert rec["p1_ranking_movement"] == "up"
    assert rec["p2_ranking_movement"] == "same"
    # Hand and country are normalized to upper so callers need not case-fold.
    assert rec["p1_hand"] == "R"
    assert rec["p2_hand"] == "L"
    assert rec["p1_country"] == "ITA"
    assert rec["p2_country"] == "USA"


def test_normalize_match_tolerates_a_payload_missing_every_new_field():
    # Coverage is 90-100%, not 100%, so an absent field must yield None rather
    # than raising and dropping an otherwise good match.
    rec = livetennis.normalize_match(_match())
    assert rec is not None
    for key in (
        "indoor", "tournament_id",
        "p1_ranking_points", "p2_ranking_points",
        "p1_ranking_movement", "p2_ranking_movement",
        "p1_hand", "p2_hand", "p1_country", "p2_country",
    ):
        assert rec[key] is None, key


def test_normalize_match_keeps_zero_ranking_points_but_drops_junk():
    # Unlike rank, 0 points is a real value for an unranked player, so the
    # rank guard's >0 test must not be copied onto points.
    rec = livetennis.normalize_match(_match(players={
        "p1": {"id": 1, "name": "A Player", "ranking": 0, "ranking_points": 0},
        "p2": {"id": 2, "name": "B Player", "ranking": None, "ranking_points": -5},
    }))
    assert rec["p1_rank"] is None
    assert rec["p1_ranking_points"] == 0
    assert rec["p2_ranking_points"] is None


@pytest.mark.parametrize("indoor", ["true", 1, None, "", "yes"])
def test_normalize_match_only_accepts_a_real_boolean_for_indoor(indoor):
    # A truthy string would silently mark every outdoor match indoors.
    assert livetennis.normalize_match(_match(indoor=indoor))["indoor"] is None


def test_normalize_match_keeps_winner_only_when_it_is_1_or_2():
    assert livetennis.normalize_match(_match(winner=2))["winner_code"] == 2
    assert livetennis.normalize_match(_match(winner=0))["winner_code"] is None
    assert livetennis.normalize_match(_match(winner=None))["winner_code"] is None


# =============================================================================
# Stub names
# =============================================================================

@pytest.mark.parametrize("name", ["V. Kopriva", "H. Seongchan", "J. Chin", "M. Guto"])
def test_is_stub_name_detects_unresolved_initials(name):
    assert livetennis._is_stub_name(name) is True


@pytest.mark.parametrize(
    "name",
    ["Vit Kopriva", "Coleman Chak Lam Wong", "Jo. Smith", "", "Max Purcell"],
)
def test_is_stub_name_leaves_real_names_alone(name):
    assert livetennis._is_stub_name(name) is False


# =============================================================================
# Round codes must stay compatible with the model's feature encoding
# =============================================================================

def test_round_codes_we_ingest_are_scorable_by_feature_builder():
    """
    The old Sofascore path stored long labels ("Round of 32"), none of which are
    ROUND_ORDINALS keys - so round_ordinal silently scored 0.0 for every match.
    Storing round_code fixes that only if the vocabularies actually agree.
    """
    provider_codes = {
        "F", "SF", "QF", "R16", "R32", "R64", "R128", "RR", "BR", "Q",
        "Q1", "Q2", "Q3", "Q4", "ER",
    }
    missing = provider_codes - set(ROUND_ORDINALS)
    assert not missing, f"ROUND_ORDINALS is missing provider round codes: {sorted(missing)}"


# =============================================================================
# H2H parsing
# =============================================================================

def test_parse_h2h_extracts_totals_and_real_surface_splits():
    payload = {
        "players": {"p1": {"name": "Novak Djokovic"}, "p2": {"name": "Carlos Alcaraz"}},
        "totals": {"p1_wins": 5, "p2_wins": 4, "meetings": 9, "undecided": 0},
        "by_surface": {
            "hard": {"p1": 3, "p2": 1},
            "clay": {"p1": 1, "p2": 2},
            "unknown": {"p1": 1, "p2": 1},
        },
    }
    parsed = livetennis.parse_h2h(payload)
    assert parsed["overall"] == (5, 4)
    # 'unknown' folds into the overall row rather than becoming a fake surface.
    assert parsed["by_surface"] == {"Hard": (3, 1), "Clay": (1, 2)}


def test_parse_h2h_returns_none_when_no_player_resolved():
    assert livetennis.parse_h2h({"players": None, "totals": {}}) is None


def test_parse_h2h_returns_none_when_they_have_never_met():
    payload = {"players": {"p1": {}, "p2": {}}, "totals": {"p1_wins": 0, "p2_wins": 0}}
    assert livetennis.parse_h2h(payload) is None


def test_parse_h2h_tolerates_a_missing_surface_block():
    payload = {"players": {"p1": {}, "p2": {}}, "totals": {"p1_wins": 2, "p2_wins": 1}}
    assert livetennis.parse_h2h(payload) == {"overall": (2, 1), "by_surface": {}}


def _history_match(p1_id, p2_id, winner, surface="hard", **overrides):
    row = {
        "status": "completed",
        "draw": "singles",
        "surface": surface,
        "winner": winner,
        "players": {"p1": {"id": p1_id}, "p2": {"id": p2_id}},
    }
    row.update(overrides)
    return row


def test_parse_history_h2h_filters_and_orients_exact_pair_results():
    rows = [
        _history_match(540, 649, 2, "hard"),
        _history_match(649, 540, 1, "clay"),
        _history_match(649, 540, 2, "grass"),
        _history_match(540, 649, 1, "indoor"),
        _history_match(540, 999, 1),
        _history_match(540, 649, None),
        _history_match(540, 649, 1, draw="doubles"),
        _history_match(540, 649, 1, status="scheduled"),
        _history_match([], 649, 1),
        _history_match(540, 649, "1"),
        {"status": "completed", "draw": "singles", "winner": 1, "players": None},
    ]

    assert livetennis.parse_history_h2h(rows, 540, 649) == {
        "overall": (2, 2),
        "by_surface": {
            "Hard": (0, 1),
            "Clay": (0, 1),
            "Grass": (1, 0),
        },
    }


def test_parse_history_h2h_returns_none_without_a_qualifying_meeting():
    rows = [
        _history_match(540, 999, 1),
        _history_match(540, 649, None),
        _history_match(540, 649, 1, status="scheduled"),
    ]

    assert livetennis.parse_history_h2h(rows, 540, 649) is None
    assert livetennis.parse_history_h2h(rows, 540, 540) is None


# =============================================================================
# Pagination envelope
# =============================================================================

def test_unwrap_reads_the_data_envelope():
    assert livetennis._unwrap({"data": [{"id": 1}], "meta": {}}) == [{"id": 1}]
    assert livetennis._unwrap([{"id": 1}]) == [{"id": 1}]
    assert livetennis._unwrap({"meta": {}}) == []


def test_has_more_prefers_meta_over_page_size():
    assert livetennis._has_more({"meta": {"has_more": False}}, livetennis.PAGE_LIMIT) is False
    assert livetennis._has_more({"meta": {"has_more": True}}, 1) is True
    # No usable meta: a full page implies more.
    assert livetennis._has_more({}, livetennis.PAGE_LIMIT) is True
    assert livetennis._has_more({}, 3) is False


# =============================================================================
# Request behaviour — these guard the daily call quota
# =============================================================================

def _client_returning(*statuses):
    """An httpx client whose successive calls return the given status codes."""
    calls = {"n": 0}

    def handler(request):
        i = min(calls["n"], len(statuses) - 1)
        calls["n"] += 1
        return httpx.Response(statuses[i], json={"detail": "x"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client, calls


def _run_fetch_h2h(handler, p1_lt_id=None, p2_lt_id=None):
    async def go():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await livetennis.fetch_h2h(
                client, "Maria Timofeeva", "Ann Li", p1_lt_id, p2_lt_id,
            )

    return asyncio.run(go())


def test_fetch_h2h_keeps_successful_direct_response_authoritative():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={
            "players": {"p1": {}, "p2": {}},
            "totals": {"p1_wins": 2, "p2_wins": 1},
        })

    assert _run_fetch_h2h(handler, 540, 649) == {
        "overall": (2, 1), "by_surface": {},
    }
    assert [request.url.path for request in calls] == [
        "/api/public/v1/h2h",
    ]


def test_fetch_h2h_uses_exact_id_history_for_ambiguous_name():
    calls = []

    def handler(request):
        calls.append(request)
        if request.url.path.endswith("/h2h"):
            return httpx.Response(400, json={
                "error": "ambiguous_name",
                "candidates": ["Ann Li", "Carolyn Ann Lim Hui"],
            })
        return httpx.Response(200, json={
            "data": [
                _history_match(540, 649, 2, "hard"),
                _history_match(649, 540, 2, "clay"),
            ],
            "meta": {"has_more": False},
        })

    assert _run_fetch_h2h(handler, 540, 649) == {
        "overall": (1, 1),
        "by_surface": {"Hard": (0, 1), "Clay": (1, 0)},
    }
    assert [request.url.path for request in calls] == [
        "/api/public/v1/h2h",
        "/api/public/v1/history/matches",
    ]
    history_params = calls[1].url.params
    assert history_params["player"] == "540"
    assert history_params["draw"] == "singles"
    assert history_params["from"] == "2023-01-01"
    assert history_params["limit"] == str(livetennis.PAGE_LIMIT)
    assert history_params["offset"] == "0"


@pytest.mark.parametrize(
    "error,p1_lt_id,p2_lt_id",
    [
        ("ambiguous_name", None, None),
        ("ambiguous_name", 540, None),
        ("bad_request", 540, 649),
    ],
)
def test_fetch_h2h_does_not_scan_history_without_exact_ambiguous_ids(
    error, p1_lt_id, p2_lt_id,
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(400, json={"error": error})

    assert _run_fetch_h2h(handler, p1_lt_id, p2_lt_id) is None
    assert [request.url.path for request in calls] == [
        "/api/public/v1/h2h",
    ]


def test_fetch_h2h_propagates_tier_block_without_history_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(403, json={"error": "upgrade_required"})

    with pytest.raises(livetennis.TierBlocked):
        _run_fetch_h2h(handler, 540, 649)
    assert [request.url.path for request in calls] == [
        "/api/public/v1/h2h",
    ]


def test_fetch_h2h_propagates_auth_error_without_history_request():
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(401, json={"error": "unauthorized"})

    with pytest.raises(livetennis.FatalStatus) as error:
        _run_fetch_h2h(handler, 540, 649)
    assert error.value.status_code == 401
    assert [request.url.path for request in calls] == [
        "/api/public/v1/h2h",
    ]


def test_get_does_not_retry_a_400():
    """
    An ambiguous /h2h name is a verdict, not a blip. Retrying it three times
    would triple the cost of every unresolvable pairing against a 100/day cap.
    """
    client, calls = _client_returning(400)

    async def go():
        async with client:
            with pytest.raises(livetennis.FatalStatus):
                await livetennis._get(client, "/h2h")

    asyncio.run(go())
    assert calls["n"] == 1


def test_get_raises_tier_blocked_on_403_without_retrying():
    client, calls = _client_returning(403)

    async def go():
        async with client:
            with pytest.raises(livetennis.TierBlocked):
                await livetennis._get(client, "/matches")

    asyncio.run(go())
    assert calls["n"] == 1


def test_get_retries_a_500_then_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(500, json={})
        return httpx.Response(200, json={"data": [{"id": 1}]})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def go():
        async with client:
            return await livetennis._get(client, "/matches")

    assert asyncio.run(go()) == {"data": [{"id": 1}]}
    assert calls["n"] == 2


# =============================================================================
# Against the captured real payload
# =============================================================================

def test_every_real_match_normalizes(real_matches):
    assert real_matches, "fixture is empty"
    recs = [livetennis.normalize_match(m) for m in real_matches]
    assert all(r is not None for r in recs)


def test_real_payload_produces_storable_rows(real_matches):
    for rec in (livetennis.normalize_match(m) for m in real_matches):
        # These four back NOT NULL columns.
        assert isinstance(rec["match_id"], int)
        assert isinstance(rec["day"], dt.date)
        assert rec["tour"] in {"ATP", "WTA", "CHALLENGER"}
        assert rec["p1_name"] and rec["p2_name"]
        assert rec["status"] in {"scheduled", "live", "completed", "cancelled"}
        assert rec["surface"] in {"Hard", "Clay", "Grass", None}
        assert rec["best_of"] in {3, 5, None}


def test_real_payload_round_codes_all_score(real_matches):
    for rec in (livetennis.normalize_match(m) for m in real_matches):
        if rec["round_"] is not None:
            assert rec["round_"] in ROUND_ORDINALS


def test_real_payload_carries_rankings_and_birthdays(real_matches):
    """
    These ride along on the match payload, which is why the ingest needs no
    per-player calls and why the Sofascore birthday scraper can be deleted.
    """
    recs = [livetennis.normalize_match(m) for m in real_matches]
    assert any(r["p1_rank"] or r["p2_rank"] for r in recs)
    assert any(r["p1_birth_date"] or r["p2_birth_date"] for r in recs)


class TestQualifyingBestOf:
    """A slam's qualifying draw carries the slam's name and its own round codes.

    US Open qualifying arrives as tournament "US Open" with rounds QF/SF/F, meaning the
    qualifying quarter, semi and final. Read as an ATP slam main draw that is best-of-5,
    when qualifying is best-of-3. The provider's is_qualifying flag is the only reliable
    signal, and it was being dropped: 15 matches were stored best-of-5 while PrizePicks
    priced them at 2.5 total sets, which a best-of-5 match cannot go under.
    """

    def _raw(self, **over):
        base = {
            "tour": "atp", "tournament": "US Open", "surface": "hard",
            "round_code": "F", "format": None, "is_qualifying": False,
            "status": "upcoming", "draw": "singles", "is_doubles": False,
            "id": 1, "players": {}, "score": None,
        }
        base.update(over)
        return base

    def test_the_provider_flag_is_read(self):
        from app.ingest.livetennis import _is_qualifying
        assert _is_qualifying({"is_qualifying": True})
        assert not _is_qualifying({"is_qualifying": False})
        assert not _is_qualifying({})

    def test_qualifying_at_a_slam_is_best_of_three(self):
        from app.core.tennis_format import infer_best_of_or_none
        from app.ingest.livetennis import _is_qualifying
        raw = self._raw(is_qualifying=True)
        best_of = 3 if _is_qualifying(raw) else infer_best_of_or_none(
            "ATP", raw["tournament"], raw["round_code"], None)
        assert best_of == 3

    def test_main_draw_at_a_slam_stays_best_of_five(self):
        from app.core.tennis_format import infer_best_of_or_none
        from app.ingest.livetennis import _is_qualifying
        raw = self._raw(is_qualifying=False)
        best_of = 3 if _is_qualifying(raw) else infer_best_of_or_none(
            "ATP", raw["tournament"], raw["round_code"], None)
        assert best_of == 5

    def test_an_explicit_provider_format_does_not_override_qualifying(self):
        from app.ingest.livetennis import _is_qualifying
        raw = self._raw(is_qualifying=True, format="BO5")
        assert _is_qualifying(raw)
