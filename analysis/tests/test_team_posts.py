from dataclasses import replace

import pandas as pd
import pytest

from lib import team_posts
from lib.nfl_team_report import PlayoffBar, TeamReport, playoff_bar

REPORT = TeamReport(
    team="DAL", season=2026, through_week=6, wins=2, losses=4, ties=0, points_for=150, points_against=158,
    pythagorean_wins=2.82, one_score_wins=1, one_score_losses=3, turnover_margin=-3, turnover_margin_rank=21,
    offense_epa_rank=8, defense_epa_rank=32, offense_success_rank=9, defense_success_rank=31, rating=-0.63,
    remaining_games=11, remaining_sos_rank=30, expected_final_wins=7.54,
    final_win_distribution={7: 0.5, 8: 0.5}, playoff_chance=0.204, luck="unlucky", verdict="long shot",
)
BAR = PlayoffBar(wins=10, made=15, teams=16)

VARIANTS = [
    REPORT,
    replace(REPORT, luck="about right", verdict="very unlikely", playoff_chance=0.004, offense_epa_rank=16,
            defense_epa_rank=20),
    replace(REPORT, team="PHI", luck="lucky", verdict="savable", playoff_chance=0.62, wins=5, losses=1,
            one_score_losses=0, offense_epa_rank=30, defense_epa_rank=3),
    replace(REPORT, ties=1, losses=3, turnover_margin=4, turnover_margin_rank=2),
]


def posts_for(report):
    return team_posts.build_posts(report, bar=BAR, turnover_carryover=0.31)


def words(text):
    return len(text.split())


@pytest.mark.parametrize("report", VARIANTS)
def test_linkedin_is_150_to_250_words(report):
    assert 150 <= words(posts_for(report).linkedin) <= 250


@pytest.mark.parametrize("report", VARIANTS)
def test_video_script_fits_45_to_60_seconds_of_voiceover(report):
    # About 2.5 spoken words a second.
    assert 110 <= words(posts_for(report).video_script) <= 160


@pytest.mark.parametrize("report", VARIANTS)
def test_no_em_dash_or_betting_language_outside_the_disclaimer(report):
    text = team_posts.all_text(posts_for(report))
    assert "\u2014" not in text and "\u2013" not in text
    assert not team_posts.BANNED_WORDS.search(text.replace(team_posts.DISCLAIMER, ""))


def test_banned_words_catch_the_obvious_cases():
    for phrase in ("a lock", "Best bets", "guaranteed", "my pick", "the odds", "parlay"):
        assert team_posts.BANNED_WORDS.search(phrase)
    assert not team_posts.BANNED_WORDS.search("better defense, unlocked potential")


@pytest.mark.parametrize("report", VARIANTS)
def test_every_post_carries_the_disclaimer(report):
    posts = posts_for(report)
    for text in (posts.video_script, posts.x_post, posts.linkedin, posts.followup_script):
        assert team_posts.DISCLAIMER in text
    assert team_posts.DISCLAIMER in posts.captions


@pytest.mark.parametrize("report", VARIANTS)
def test_video_script_opens_with_the_verdict(report):
    first = posts_for(report).video_script.split(". ")[0]
    assert team_posts.VERDICT_PHRASES[report.verdict] in first
    assert team_posts.chance_phrase(report.playoff_chance) in first


@pytest.mark.parametrize(
    ("chance", "phrase"),
    [(0.204, "about 1 in 5"), (0.118, "about 1 in 8"), (0.004, "less than 1 in 100"), (0.62, "about 62%")],
)
def test_chance_phrase(chance, phrase):
    assert team_posts.chance_phrase(chance) == phrase


@pytest.mark.parametrize(("n", "text"), [(1, "1st"), (2, "2nd"), (3, "3rd"), (11, "11th"), (21, "21st"), (32, "32nd")])
def test_ordinal(n, text):
    assert team_posts.ordinal(n) == text


def test_path_sentence_counts_the_wins_still_needed():
    sentence = team_posts.path_sentence(REPORT, BAR)
    assert "15 of 16 teams" in sentence
    assert "going 8-3 or better over the last 11 games" in sentence


def test_surprising_fact_order():
    assert "1-3 in games decided by one score" in team_posts.surprising_fact(REPORT)
    split = replace(REPORT, luck="about right")
    assert "offense ranks 8th" in team_posts.surprising_fact(split)
    even = replace(split, offense_epa_rank=15, defense_epa_rank=18)
    assert "3rd easiest schedule" in team_posts.surprising_fact(even)
    assert "16th hardest schedule" in team_posts.surprising_fact(replace(even, remaining_sos_rank=16))
    assert "16th easiest schedule" in team_posts.surprising_fact(replace(even, remaining_sos_rank=17))


def test_record_shows_ties_only_when_there_are_some():
    assert team_posts.record(REPORT) == "2-4"
    assert team_posts.record(replace(REPORT, ties=1)) == "2-4-1"


def test_markdown_has_every_section():
    text = team_posts.to_markdown(REPORT, posts_for(REPORT))
    for heading in ("## Main video", "## Chart post", "**LinkedIn:**", "## Follow-up clip"):
        assert heading in text


def test_playoff_bar_is_the_fewest_wins_with_at_least_half_making_it():
    table = pd.DataFrame({"teams": [18, 23, 16], "made": [2, 9, 15]}, index=[8, 9, 10])
    table["rate"] = table["made"] / table["teams"]
    assert playoff_bar(table) == PlayoffBar(10, 15, 16)
    with pytest.raises(ValueError):
        playoff_bar(table.iloc[:2])


@pytest.mark.parametrize(("chance", "value"), [(0.204, "1 in 5"), (0.004, "<1%"), (0.62, "62%"), (0.011, "1 in 91")])
def test_callout_value_fits_the_thumbnail(chance, value):
    assert team_posts.callout_value(chance) == value
    assert len(value) <= 8
