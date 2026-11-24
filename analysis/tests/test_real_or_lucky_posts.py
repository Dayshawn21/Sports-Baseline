from dataclasses import replace

import pytest

from lib import real_or_lucky_posts as posts_lib
from lib import style, team_posts
from lib.nfl_team_report import (FieldGoalRank, OpponentAdjustment, ScoringRun, SeasonSnapshot, UnbeatenHistory,
                                 points_record, real_verdict)

SNAPSHOT = SeasonSnapshot(
    team="MIN", season=2026, through_week=7, games=6, wins=6, losses=0, ties=0, points_for=125,
    points_against=74, pythagorean_wins=4.66, one_score_wins=3, one_score_losses=0, turnover_margin=5,
    turnover_margin_rank=2, offense_epa_rank=27, defense_epa_rank=1, offense_success_rank=32,
    defense_success_rank=1, luck="lucky",
)

VARIANTS = [
    SNAPSHOT,
    replace(SNAPSHOT, team="DET", wins=5, losses=1, pythagorean_wins=4.9, luck="about right",
            offense_epa_rank=3, defense_epa_rank=8),
    replace(SNAPSHOT, team="TB", wins=4, losses=2, pythagorean_wins=4.6, luck="about right", one_score_wins=1),
    replace(SNAPSHOT, team="WAS", wins=2, losses=4, points_for=140, points_against=118, pythagorean_wins=3.6,
            luck="unlucky", one_score_wins=0, one_score_losses=3, turnover_margin=-4, turnover_margin_rank=28),
    replace(SNAPSHOT, team="NYJ", wins=4, losses=2, points_for=110, points_against=118, pythagorean_wins=2.7,
            luck="lucky", one_score_wins=1, one_score_losses=1, turnover_margin=-1, turnover_margin_rank=19,
            offense_epa_rank=20, defense_epa_rank=14),
    replace(SNAPSHOT, team="SF", games=7, wins=5, losses=1, ties=1, pythagorean_wins=5.0, luck="about right"),
]


def test_variants_cover_every_verdict():
    assert {real_verdict(s) for s in VARIANTS} == set(posts_lib.VERDICT_SENTENCES)


def posts_for(snapshot):
    return posts_lib.build_posts(snapshot, turnover_carryover=0.31)


def words(text):
    return len(text.split())


@pytest.mark.parametrize("snapshot", VARIANTS)
@pytest.mark.parametrize("size", ["feed", "vertical"])
def test_chart_title_fits_two_lines(snapshot, size):
    lines = style.wrap_title(posts_lib.chart_title(snapshot), style.layout(size).safe.width, style._title_width)
    assert len(lines) <= style.TITLE_MAX_LINES


@pytest.mark.parametrize(
    ("snapshot", "title"),
    [(SNAPSHOT, "The Vikings are 6-0, but their points say 5-1"),
     (VARIANTS[1], "The Lions are 5-1, and their points agree"),
     (VARIANTS[2], "The Buccaneers are 4-2, close to the 5-1 their points say"),
     (VARIANTS[3], "The Commanders are 2-4, but their points say 4-2")],
)
def test_chart_title_states_the_answer(snapshot, title):
    assert posts_lib.chart_title(snapshot) == title


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_linkedin_is_150_to_250_words(snapshot):
    assert 150 <= words(posts_for(snapshot).linkedin) <= 250


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_video_script_fits_45_to_60_seconds_of_voiceover(snapshot):
    assert 110 <= words(posts_for(snapshot).video_script) <= 160


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_no_em_dash_or_betting_language(snapshot):
    text = team_posts.all_text(posts_for(snapshot)) + posts_lib.chart_title(snapshot)
    assert "\u2014" not in text and "\u2013" not in text
    assert not team_posts.BANNED_WORDS.search(text)


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_no_betting_disclaimer_on_content_with_nothing_to_bet(snapshot):
    # The guide keeps "not betting advice" for prop and line content; a record-vs-points piece offers no bet.
    assert team_posts.DISCLAIMER not in team_posts.all_text(posts_for(snapshot))


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_first_sentence_states_the_record_and_the_points_record(snapshot):
    points = points_record(snapshot.pythagorean_wins, snapshot.games)
    for text in (posts_for(snapshot).video_script, posts_for(snapshot).linkedin):
        first = text.split(". ")[0]
        assert posts_lib.record(snapshot) in first and points in first


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_x_post_fits_280_characters(snapshot):
    assert len(posts_for(snapshot).x_post) <= 280


def test_surprising_fact_order():
    lopsided = posts_lib.surprising_fact(SNAPSHOT)
    assert lopsided.startswith("The Vikings are 6-0.")
    assert "defense ranks 1st in the league and their offense ranks 27th" in lopsided
    balanced = {"offense_epa_rank": 10, "defense_epa_rank": 12}
    assert "3-0 in games decided by one score" in posts_lib.surprising_fact(replace(SNAPSHOT, **balanced))
    assert "0-3 in games decided by one score" in posts_lib.surprising_fact(replace(VARIANTS[3], **balanced))
    assert "turnover margin is +5" in posts_lib.surprising_fact(VARIANTS[1])


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_text_posts_state_the_verdict_instead_of_asking(snapshot):
    posts = posts_for(snapshot)
    assert "?" not in posts.x_post and "?" not in posts.linkedin
    assert posts_lib.spoken_question(real_verdict(snapshot)) in posts.video_script


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_linkedin_is_split_into_paragraphs(snapshot):
    paragraphs = posts_for(snapshot).linkedin.split("\n\n")
    assert len(paragraphs) >= 4 and all(words(p) <= 80 for p in paragraphs)


GAPS = {"MIN": 1.1, "BUF": 1.5, "CLE": 1.5, "SF": 1.47, "DEN": 1.33, "KC": 1.12, "WAS": -1.6, "NYG": -0.4}


def test_league_luck_counts_teams_further_away_by_a_visible_margin():
    assert posts_lib.league_luck_sentence(SNAPSHOT, GAPS) == (
        "Their record is ahead of their points, but 4 teams' records are further ahead of theirs.")
    unlucky = replace(SNAPSHOT, team="NYG", luck="unlucky")
    assert posts_lib.league_luck_sentence(unlucky, GAPS) == (
        "Their record is behind their points, but 1 team's record is further behind theirs.")
    worst = replace(SNAPSHOT, team="WAS", luck="unlucky")
    assert posts_lib.league_luck_sentence(worst, GAPS) == "No team's record has run further behind its points."
    assert posts_lib.league_luck_sentence(VARIANTS[1], GAPS) is None


def test_linkedin_carries_the_league_luck_sentence_and_stays_in_length():
    linkedin = posts_lib.build_posts(SNAPSHOT, turnover_carryover=0.31, luck_gaps=GAPS).linkedin
    assert "4 teams' records are further ahead" in linkedin
    assert 150 <= words(linkedin) <= 250


def test_record_shows_ties_only_when_there_are_some():
    assert posts_lib.record(SNAPSHOT) == "6-0"
    assert posts_lib.record(VARIANTS[5]) == "5-1-1"


def test_markdown_has_every_section():
    text = posts_lib.to_markdown(SNAPSHOT, posts_for(SNAPSHOT))
    for heading in ("## Main video", "## Chart post", "**LinkedIn:**", "## Follow-up clip"):
        assert heading in text


def unbeaten_history(more_points=4, starts=15, fewer_points=0, fewer_allowed=3):
    return UnbeatenHistory(first_season=2012, last_season=2025, games=6, starts=starts, points_below_perfect=14,
                           more_points=more_points, rest_win_rate=0.6405, pythagorean_wins=[4.0] * starts,
                           fewer_points=fewer_points, fewer_allowed=fewer_allowed)


def unbeaten_posts(**history_args):
    return posts_lib.build_posts(SNAPSHOT, turnover_carryover=0.31, luck_gaps=GAPS,
                                 history=unbeaten_history(**history_args), last_unbeaten=True)


def test_history_sentences_state_the_counts_and_the_rest_of_season_rate():
    assert posts_lib.history_sentences(SNAPSHOT, unbeaten_history()) == [
        "Since 2012, 14 of the 15 teams that started 6-0 had points that said they should have lost at least once.",
        "Only 4 of them had better points than the Vikings.",
        "Together, they won 64% of their remaining games.",
    ]
    assert posts_lib.history_sentences(SNAPSHOT, unbeaten_history(more_points=0))[1] == (
        "None of them had better points than the Vikings.")
    assert posts_lib.history_sentences(SNAPSHOT, unbeaten_history(starts=0)) == []
    assert posts_lib.history_sentences(SNAPSHOT, None) == []


def test_unbeaten_posts_open_with_last_unbeaten_and_keep_their_limits():
    posts = unbeaten_posts()
    first = posts.video_script.split(". ")[0]
    assert "the NFL's last unbeaten team" in first and "6-0" in first and "5-1" in first
    assert "That is normal for an unbeaten team." in posts.video_script
    assert 110 <= words(posts.video_script) <= 180
    assert 150 <= words(posts.linkedin) <= 300
    assert len(posts.x_post) <= 280 and "14 of the 15 teams" in posts.x_post
    assert "a perfect record almost always runs ahead" in posts.linkedin
    assert "further ahead" not in posts.linkedin   # the history is the comparison; one is enough
    text = team_posts.all_text(posts)
    assert "\u2014" not in text and "\u2013" not in text and not team_posts.BANNED_WORDS.search(text)


def run(touchdowns=5, kick_points=56, points=86, games=5):
    return ScoringRun(games=games, first_week=2, last_week=7, touchdowns=touchdowns, kick_points=kick_points,
                      points=points)


def test_follow_up_leads_with_the_kicker_when_he_scored_at_least_half():
    assert posts_lib.surprising_fact(SNAPSHOT, run()) == (
        "The Vikings have scored 5 touchdowns in their last 5 games. Their kicker scored 56 of their 86 points "
        "in that stretch.")
    assert posts_lib.surprising_fact(SNAPSHOT, run(kick_points=43)).startswith("The Vikings have scored")
    assert posts_lib.surprising_fact(SNAPSHOT, run(kick_points=42)).startswith("The Vikings are 6-0.")
    whole = posts_lib.surprising_fact(SNAPSHOT, run(touchdowns=1, kick_points=40, points=50, games=6))
    assert whole.startswith("The Vikings have scored 1 touchdown in their 6 games.")
    assert posts_lib.surprising_fact(SNAPSHOT, run(kick_points=0, points=0)).startswith("The Vikings are 6-0.")


def test_scoring_adds_one_kicker_line_to_the_video_script_only():
    with_run = posts_lib.build_posts(SNAPSHOT, turnover_carryover=0.31, scoring=run())
    without = posts_for(SNAPSHOT)
    assert (with_run.x_post, with_run.linkedin) == (without.x_post, without.linkedin)
    line = "Their kicker scored 56 of their last 86 points."
    assert with_run.video_script == without.video_script.replace(
        posts_lib.per_play_sentence(SNAPSHOT), f"{posts_lib.per_play_sentence(SNAPSHOT)} {line}")
    assert with_run.followup_script.startswith("The Vikings have scored 5 touchdowns")


@pytest.mark.parametrize("snapshot", VARIANTS)
def test_video_script_keeps_its_limit_with_the_kicker_line(snapshot):
    script = posts_lib.build_posts(snapshot, turnover_carryover=0.31, scoring=run()).video_script
    assert 110 <= words(script) <= 160


def test_kicker_line_only_at_half_or_more_and_says_their_for_the_whole_season():
    script = lambda scoring: posts_lib.build_posts(SNAPSHOT, turnover_carryover=0.31, scoring=scoring).video_script
    assert "Their kicker scored 43 of their last 86 points." in script(run(kick_points=43))
    assert "kicker" not in script(run(kick_points=42))
    assert "Their kicker scored 40 of their 50 points." in script(run(kick_points=40, points=50, games=6))


RESEARCH = posts_lib.Research(
    adjustment=OpponentAdjustment(allowed_below=11.1, scored_vs_usual=-3.4, best_opponent="CHI", best_allowed=3,
                                  best_usual=29.5),
    opponents_record=(16, 19, 0),
    field_goals=FieldGoalRank(field_goals=15, rank=2, leader="IND", leader_field_goals=18),
)


def test_fewest_points_only_when_no_past_start_scored_fewer():
    assert posts_lib.fewest_points_sentence(SNAPSHOT, unbeaten_history()) == (
        "No team that started 6-0 since 2012 scored fewer than their 125 points, and only 3 allowed fewer than "
        "their 74.")
    assert posts_lib.fewest_points_sentence(SNAPSHOT, unbeaten_history(fewer_points=1)) is None
    assert "and none allowed fewer" in posts_lib.fewest_points_sentence(SNAPSHOT, unbeaten_history(fewer_allowed=0))
    assert posts_lib.fewest_points_sentence(SNAPSHOT, None) is None


def test_research_sentences():
    assert posts_lib.adjustment_sentence(RESEARCH.adjustment) == (
        "Their opponents scored 11.1 fewer points against them than in a typical game. The Bears usually score "
        "29.5 and scored 3.")
    whole = replace(RESEARCH.adjustment, best_usual=27.0)
    assert "The Bears usually score 27 and scored 3." in posts_lib.adjustment_sentence(whole)
    assert posts_lib.schedule_sentence((16, 19, 0)).endswith("16-19 in their other games, so the schedule has been "
                                                            "on the easy side.")
    assert posts_lib.schedule_sentence((10, 9, 1)).endswith("10-9-1 in their other games, so the schedule has been "
                                                           "on the hard side.")
    assert posts_lib.kicker_extra(-3.4, RESEARCH.field_goals) == (
        "They have made 15 field goals, the 2nd most in the league, and they score 3.4 fewer points a game than "
        "these defenses usually allow.")
    assert posts_lib.kicker_extra(1.0, None) is None


def test_full_unbeaten_posts_with_research_keep_their_limits():
    posts = posts_lib.build_posts(SNAPSHOT, turnover_carryover=0.31, luck_gaps=GAPS, history=unbeaten_history(),
                                  last_unbeaten=True, scoring=run(), research=RESEARCH)
    assert "scored fewer than their 125 points" in posts.video_script
    assert "Their kicker scored 56 of their last 86 points." in posts.video_script
    assert "They have scored 125 points and allowed 74." not in posts.video_script
    assert 110 <= words(posts.video_script) <= 180
    assert 150 <= words(posts.linkedin) <= 300
    assert "The Bears usually score 29.5 and scored 3." in posts.linkedin and "16-19" in posts.linkedin
    assert posts.followup_script.startswith("The Vikings have scored 5 touchdowns") and "15 field goals" in         posts.followup_script
    assert words(posts.followup_script) <= 55
    text = team_posts.all_text(posts)
    assert "—" not in text and "–" not in text and not team_posts.BANNED_WORDS.search(text)
