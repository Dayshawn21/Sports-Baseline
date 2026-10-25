"""Draft posts for one Save the Season team, written from its numbers under the README's language rules."""
from __future__ import annotations

import re
from dataclasses import dataclass

from lib.nfl_team_report import PlayoffBar, TeamReport, nickname, team_name

DISCLAIMER = "Not betting advice."
# Checked with the disclaimer removed, so it is the only place betting language can appear.
BANNED_WORDS = re.compile(r"\b(bets?|betting|locks?|guaranteed|picks?|odds|parlays?)\b", re.IGNORECASE)
VERDICT_PHRASES = {"savable": "is still savable", "long shot": "is a long shot", "very unlikely": "is very unlikely"}


@dataclass(frozen=True)
class Posts:
    video_script: str
    captions: list[str]
    x_post: str
    linkedin: str
    followup_script: str


def ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def chance_phrase(chance: float) -> str:
    """A plain-words chance: 'about 1 in 5' below a half, a rounded percentage above."""
    if chance < 0.01:
        return "less than 1 in 100"
    if chance < 0.5:
        return f"about 1 in {round(1 / chance)}"
    return f"about {round(chance * 100)}%"


def callout_value(chance: float) -> str:
    """The chance in 8 characters or fewer, for a thumbnail callout."""
    if chance < 0.01:
        return "<1%"
    if chance < 0.5:
        return f"1 in {round(1 / chance)}"
    return f"{round(chance * 100)}%"


def record(report: TeamReport) -> str:
    base = f"{report.wins}-{report.losses}"
    return f"{base}-{report.ties}" if report.ties else base


def season_sentence(report: TeamReport) -> str:
    return (f"saving their season {VERDICT_PHRASES[report.verdict]}: "
            f"they make the playoffs in {chance_phrase(report.playoff_chance)} simulated seasons")


def luck_sentence(report: TeamReport) -> str:
    points = f"{report.points_for} points scored and {report.points_against} allowed"
    expected = f"about {report.pythagorean_wins:.1f} wins"
    if report.luck == "unlucky":
        return f"Their {points} usually add up to {expected}, so the record looks worse than the team has played."
    if report.luck == "lucky":
        return f"Their {points} usually add up to {expected}, so the record flatters them."
    return f"Their {points} usually add up to {expected}, so the record is about what they have earned."


def path_sentence(report: TeamReport, bar: PlayoffBar) -> str:
    needed = min(max(bar.wins - report.wins, 0), report.remaining_games)
    left = report.remaining_games
    return (f"Since 2021, {bar.made} of {bar.teams} teams that finished with {bar.wins} wins made the playoffs. "
            f"Getting there means going {needed}-{left - needed} or better over the last {left} games.")


def surprising_fact(report: TeamReport) -> str:
    """The one fact for the follow-up clip, picked by a fixed order of rules."""
    if report.luck == "unlucky" and report.one_score_losses >= 2:
        return (f"The {nickname(report.team)} are {report.one_score_wins}-{report.one_score_losses} in games "
                f"decided by one score. A one-score game can turn on a single bounce, kick or call.")
    gap = report.defense_epa_rank - report.offense_epa_rank
    if abs(gap) >= 15:
        better, worse = ("offense", "defense") if gap > 0 else ("defense", "offense")
        better_rank, worse_rank = sorted((report.offense_epa_rank, report.defense_epa_rank))
        return (f"The {nickname(report.team)} {better} ranks {ordinal(better_rank)} in the league per play, "
                f"but the {worse} ranks {ordinal(worse_rank)}. One side of the ball is carrying the other.")
    rank, teams = report.remaining_sos_rank, 32
    which = f"{ordinal(rank)} hardest" if rank <= teams // 2 else f"{ordinal(teams + 1 - rank)} easiest"
    return (f"The {nickname(report.team)} have the {which} schedule left in the league, "
            f"by how well their opponents have played so far.")


def turnover_sentence(report: TeamReport, turnover_carryover: float) -> str:
    margin = f"{report.turnover_margin:+d}"
    how = "only loosely" if turnover_carryover < 0.5 else "fairly well"
    return (f"Their turnover margin is {margin}, {ordinal(report.turnover_margin_rank)} in the league, "
            f"and turnover margin this early {how} predicts the rest of the season.")


def build_posts(report: TeamReport, *, bar: PlayoffBar, turnover_carryover: float) -> Posts:
    name, nick = team_name(report.team), nickname(report.team)
    opening = f"The {name} are {record(report)}, and {season_sentence(report)}."
    luck = luck_sentence(report)
    path = path_sentence(report, bar)
    turnovers = turnover_sentence(report, turnover_carryover)
    caveat = (f"This is a rough estimate from {report.through_week} weeks of games, "
              "with no tiebreakers or division races.")

    video = " ".join([
        opening,
        "A record tells you what happened. Points tell you how well a team has played.",
        luck,
        f"Per play, their offense ranks {ordinal(report.offense_epa_rank)} and their defense "
        f"{ordinal(report.defense_epa_rank)}.",
        path,
        f"Play the rest of the season 10,000 times and they finish with about "
        f"{report.expected_final_wins:.1f} wins on average.",
        f"{caveat} {DISCLAIMER}",
    ])
    captions = [
        f"{nick}: {record(report)} through week {report.through_week}",
        f"Points say about {report.pythagorean_wins:.1f} wins",
        f"Need about {bar.wins} wins",
        f"Playoffs in {chance_phrase(report.playoff_chance)} simulated seasons",
        DISCLAIMER,
    ]
    x_post = (f"Can the {nick} save their season? At {record(report)}, they make the playoffs in "
              f"{chance_phrase(report.playoff_chance)} simulated seasons. {luck} {DISCLAIMER}")
    linkedin = " ".join([
        f"This week I asked whether the {name} can still save their season.",
        f"They are {record(report)} through week {report.through_week}.",
        "I started with a simple idea: a record shows what happened, but points scored and allowed show how well "
        "a team has actually played.",
        luck,
        turnovers,
        "Then I gave every team a rating from its point differential, pulled toward average because "
        f"{report.through_week} weeks is a small sample, and played out the remaining schedule 10,000 times.",
        path,
        f"The answer: the {nick} reach the playoffs in {chance_phrase(report.playoff_chance)} simulated seasons, "
        f"so it {VERDICT_PHRASES[report.verdict]}.",
        caveat,
        "What I learned: a few close games can bend a record a long way, and the honest answer to "
        "\"are they done?\" is usually a range, not a yes or no.",
        DISCLAIMER,
    ])
    followup = f"{surprising_fact(report)} {DISCLAIMER}"
    return Posts(video, captions, x_post, linkedin, followup)


def all_text(posts: Posts) -> str:
    return "\n".join([posts.video_script, *posts.captions, posts.x_post, posts.linkedin, posts.followup_script])


def to_markdown(report: TeamReport, posts: Posts) -> str:
    lines = [
        f"# Week 1 draft posts: {team_name(report.team)}",
        "",
        "Drafts generated from the notebook's numbers. Edit before posting.",
        "",
        "## Main video (45 to 60 seconds)",
        "",
        posts.video_script,
        "",
        "**On-screen captions:**",
        "",
        *[f"- {caption}" for caption in posts.captions],
        "",
        "## Chart post",
        "",
        "**X / Threads:**",
        "",
        posts.x_post,
        "",
        "**LinkedIn:**",
        "",
        posts.linkedin,
        "",
        "## Follow-up clip (15 to 20 seconds)",
        "",
        posts.followup_script,
        "",
    ]
    return "\n".join(lines)
