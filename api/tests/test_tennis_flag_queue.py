from app.core.tennis_flag_queue import missing_surfaces, refine_player_flags


def _refine(flags, *, has_elo=False, stat_surfaces=(), match_surfaces=()):
    return refine_player_flags(
        flags, has_elo=has_elo, stat_surfaces=set(stat_surfaces), match_surfaces=match_surfaces,
    )


def test_a_player_missing_only_surface_stats_keeps_the_stats_flag():
    assert _refine({"ml_features_partial"}, stat_surfaces={None, "Hard"}, match_surfaces={"Clay"}) == {
        "ml_features_partial"
    }


def test_a_player_with_overall_and_surface_stats_clears_it():
    assert _refine({"ml_features_partial"}, stat_surfaces={None, "Clay"}, match_surfaces={"Clay"}) == set()


def test_a_player_missing_overall_stats_keeps_it():
    assert _refine({"ml_features_partial"}, stat_surfaces={"Clay"}, match_surfaces={"Clay"}) == {
        "ml_features_partial"
    }


def test_every_flagging_match_surface_must_be_covered():
    assert _refine({"ml_features_partial"}, stat_surfaces={None, "Clay"}, match_surfaces={"Clay", "Grass"}) == {
        "ml_features_partial"
    }


def test_a_match_without_a_surface_does_not_hold_the_flag():
    assert _refine({"ml_features_partial"}, stat_surfaces={None}, match_surfaces={None}) == set()


def test_elo_flags_clear_once_the_player_has_elo():
    flags = {"elo_missing", "p1_elo_missing", "ml_features_partial"}
    assert _refine(flags, has_elo=True, match_surfaces={"Hard"}) == {"ml_features_partial"}
    assert _refine(flags, has_elo=False, match_surfaces={"Hard"}) == flags


def test_missing_surfaces_names_each_uncovered_match_surface_once_sorted():
    assert missing_surfaces({None, "Hard"}, ["Grass", "Clay", "Hard", "Clay"]) == ["Clay", "Grass"]


def test_missing_surfaces_ignores_a_match_without_a_surface():
    assert missing_surfaces({None}, [None]) == []
