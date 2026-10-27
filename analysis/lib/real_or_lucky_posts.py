"""Draft posts for one Real or Lucky? team, written from its season snapshot under the README's language rules."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from lib.nfl_team_report import (FieldGoalRank, OpponentAdjustment, ScoringRun, SeasonSnapshot, UnbeatenHistory,
                                 nickname, points_record, real_verdict, team_name)
from lib.team_posts import Posts, ordinal

# A lucky verdict says the record ran ahead of the points, never that the team will start losing. The sentences
# state the answer outright; only the spoken script asks the question first.
VERDICT_SENTENCES = {
    "Real": "The points back the record up. It matches how well they have played.",
    "Better than their record": "They have played better than their wins and losses show.",
    "Mostly real, some luck": "They are a good team, and their record has run ahead of their points. "
                      "That does not mean they will start losing.",
    "Lucky": "They have not outscored their opponents, and their record has run ahead of that.",
}


def spoken_question(verdict: str) -> str:
    return "So are they better than their record?" if verdict == "Better than their record" else \
        "So are they for real?"


def record(snapshot: SeasonSnapshot) -> str:
    base = f"{snapshot.wins}-{snapshot.losses}"
    return f"{base}-{snapshot.ties}" if snapshot.ties else base


def chart_title(snapshot: SeasonSnapshot) -> str:
    nick, actual = nickname(snapshot.team), record(snapshot)
    points = points_record(snapshot.pythagorean_wins, snapshot.games)
    if actual == points:
        return f"The {nick} are {actual}, and their points agree"
    if snapshot.luck == "about right":
        return f"The {nick} are {actual}, close to the {points} their points say"
    return f"The {nick} are {actual}, but their points say {points}"


def opening_sentence(snapshot: SeasonSnapshot, *, last_unbeaten: bool = False) -> str:
    points = points_record(snapshot.pythagorean_wins, snapshot.games)
    joiner = "and" if snapshot.luck == "about right" else "but"
    alone = " the NFL's last unbeaten team," if last_unbeaten else ""
    return (f"The {team_name(snapshot.team)} are {record(snapshot)} through week {snapshot.through_week},{alone} "
            f"{joiner} the record their points usually produce is {points}.")


def history_sentences(snapshot: SeasonSnapshot, history: UnbeatenHistory | None) -> list[str]:
    """How past teams with the same perfect start looked by their points, and how they finished."""
    if history is None or history.starts == 0:
        return []
    perfect = f"{history.games}-0"
    better = "None" if history.more_points == 0 else f"Only {history.more_points}"
    return [
        f"Since {history.first_season}, {history.points_below_perfect} of the {history.starts} teams that started "
        f"{perfect} had points that said they should have lost at least once.",
        f"{better} of them had better points than the {nickname(snapshot.team)}.",
        f"Together, they won {round(history.rest_win_rate * 100)}% of their remaining games.",
    ]


def fewest_points_sentence(snapshot: SeasonSnapshot, history: UnbeatenHistory | None) -> str | None:
    """Only when no past perfect start scored fewer: the record is built on defense, not scoring."""
    if history is None or history.starts == 0 or history.fewer_points > 0:
        return None
    allowed = "none" if history.fewer_allowed == 0 else f"only {history.fewer_allowed}"
    return (f"No team that started {history.games}-0 since {history.first_season} scored fewer than their "
            f"{snapshot.points_for} points, and {allowed} allowed fewer than their {snapshot.points_against}.")


@dataclass(frozen=True)
class Research:
    """Stats that take digging to find; any of them can be missing."""
    adjustment: OpponentAdjustment | None = None
    opponents_record: tuple[int, int, int] | None = None
    field_goals: FieldGoalRank | None = None


def adjustment_sentence(adjustment: OpponentAdjustment) -> str:
    return (f"Their opponents scored {adjustment.allowed_below:.1f} fewer points against them than in a typical "
            f"game. The {nickname(adjustment.best_opponent)} usually score {adjustment.best_usual:g} and scored "
            f"{adjustment.best_allowed}.")


def schedule_sentence(opponents: tuple[int, int, int]) -> str:
    wins, losses, ties = opponents
    combined = f"{wins}-{losses}-{ties}" if ties else f"{wins}-{losses}"
    lean = "on the easy side" if wins < losses else "on the hard side" if wins > losses else "about average"
    return f"Their opponents are a combined {combined} in their other games, so the schedule has been {lean}."


def kicker_extra(scoring_vs_usual: float | None, field_goals: FieldGoalRank | None) -> str | None:
    parts = []
    if field_goals is not None:
        where = "the most" if field_goals.rank == 1 else f"the {ordinal(field_goals.rank)} most"
        parts.append(f"They have made {field_goals.field_goals} field goals, {where} in the league")
    if scoring_vs_usual is not None and scoring_vs_usual < 0:
        parts.append(f"they score {abs(scoring_vs_usual):.1f} fewer points a game than these defenses usually allow")
    return f"{', and '.join(parts)}." if parts else None


def points_sentence(snapshot: SeasonSnapshot) -> str:
    diff = snapshot.points_for - snapshot.points_against
    return (f"They have scored {snapshot.points_for} points and allowed {snapshot.points_against}, "
            f"a point differential of {diff:+d}. Teams with those points usually win about "
            f"{snapshot.pythagorean_wins:.1f} of {snapshot.games} games.")


def close_games_sentence(snapshot: SeasonSnapshot) -> str:
    return (f"They are {snapshot.one_score_wins}-{snapshot.one_score_losses} in games decided by one score, "
            "and a one-score game can turn on a single bounce, kick or call.")


def turnover_sentence(snapshot: SeasonSnapshot, turnover_carryover: float) -> str:
    how = "only loosely" if turnover_carryover < 0.5 else "fairly well"
    return (f"Their turnover margin is {snapshot.turnover_margin:+d}, {ordinal(snapshot.turnover_margin_rank)} "
            f"in the league, and turnover margin this early {how} predicts the rest of a season.")


def per_play_sentence(snapshot: SeasonSnapshot) -> str:
    return (f"Per play, their offense ranks {ordinal(snapshot.offense_epa_rank)} in the league "
            f"and their defense {ordinal(snapshot.defense_epa_rank)}.")


def kicker_carries(scoring: ScoringRun | None) -> bool:
    return scoring is not None and scoring.points > 0 and 2 * scoring.kick_points >= scoring.points


def kicker_line(snapshot: SeasonSnapshot, run: ScoringRun) -> str:
    """The main video's one kicker sentence; the follow-up clip keeps the fuller version."""
    last = "" if run.games == snapshot.games else "last "
    return f"Their kicker scored {run.kick_points} of their {last}{run.points} points."


def kicker_sentence(snapshot: SeasonSnapshot, run: ScoringRun) -> str:
    stretch = f"their {run.games} games" if run.games == snapshot.games else f"their last {run.games} games"
    tds = "1 touchdown" if run.touchdowns == 1 else f"{run.touchdowns} touchdowns"
    return (f"The {nickname(snapshot.team)} have scored {tds} in {stretch}. Their kicker scored {run.kick_points} "
            f"of their {run.points} points in that stretch.")


def surprising_fact(snapshot: SeasonSnapshot, scoring: ScoringRun | None = None,
                    research: Research = Research()) -> str:
    """The one fact for the follow-up clip, picked by a fixed order of rules.

    A kicker carrying the scoring comes first, then a lopsided team: a winning record with a bottom-ten offense is
    more surprising than close wins, which the main video already covers.
    """
    if kicker_carries(scoring):
        usual = research.adjustment.scored_vs_usual if research.adjustment else None
        extra = kicker_extra(usual, research.field_goals)
        return " ".join(filter(None, [kicker_sentence(snapshot, scoring), extra]))
    nick = nickname(snapshot.team)
    close = f"{snapshot.one_score_wins}-{snapshot.one_score_losses}"
    gap = snapshot.defense_epa_rank - snapshot.offense_epa_rank
    if abs(gap) >= 15:
        better, worse = ("offense", "defense") if gap > 0 else ("defense", "offense")
        better_rank, worse_rank = sorted((snapshot.offense_epa_rank, snapshot.defense_epa_rank))
        return (f"The {nick} are {record(snapshot)}. Per play, their {better} ranks {ordinal(better_rank)} in the "
                f"league and their {worse} ranks {ordinal(worse_rank)}, so one side of the ball is carrying "
                "the other.")
    if snapshot.luck == "lucky" and snapshot.one_score_wins >= 2:
        return (f"The {nick} are {close} in games decided by one score. Close wins count the same as blowouts "
                "in the standings, but they say less about how good a team is.")
    if snapshot.luck == "unlucky" and snapshot.one_score_losses >= 2:
        return (f"The {nick} are {close} in games decided by one score. A one-score game can turn on a single "
                "bounce, kick or call.")
    return (f"The {nick} turnover margin is {snapshot.turnover_margin:+d}, "
            f"{ordinal(snapshot.turnover_margin_rank)} in the league.")


def league_luck_sentence(snapshot: SeasonSnapshot, luck_gaps: Mapping[str, float]) -> str | None:
    """Where the team's record-minus-points gap sits in the league, so a lucky team is not framed as the luckiest.

    Gaps are compared at one decimal, so a team only counts as further away by a visible margin.
    """
    if snapshot.luck == "about right":
        return None
    own = round(luck_gaps[snapshot.team], 1)
    others = [round(gap, 1) for team, gap in luck_gaps.items() if team != snapshot.team]
    ahead = snapshot.luck == "lucky"
    further = sum(gap > own for gap in others) if ahead else sum(gap < own for gap in others)
    direction = "ahead of" if ahead else "behind"
    if further == 0:
        return f"No team's record has run further {direction} its points."
    teams = "team's record is" if further == 1 else "teams' records are"
    return f"Their record is {direction} their points, but {further} {teams} further {direction} theirs."


def build_posts(snapshot: SeasonSnapshot, *, turnover_carryover: float,
                luck_gaps: Mapping[str, float] | None = None, history: UnbeatenHistory | None = None,
                last_unbeaten: bool = False, scoring: ScoringRun | None = None,
                research: Research = Research()) -> Posts:
    nick = nickname(snapshot.team)
    verdict = real_verdict(snapshot)
    opening = opening_sentence(snapshot, last_unbeaten=last_unbeaten)
    past = history_sentences(snapshot, history)
    fewest = fewest_points_sentence(snapshot, history)
    held = adjustment_sentence(research.adjustment) if research.adjustment else None
    schedule = schedule_sentence(research.opponents_record) if research.opponents_record else None
    points = points_sentence(snapshot)
    close = close_games_sentence(snapshot)
    turnovers = turnover_sentence(snapshot, turnover_carryover)
    per_play = per_play_sentence(snapshot)
    kicker = kicker_line(snapshot, scoring) if kicker_carries(scoring) else None
    caveat = f"This is {snapshot.games} games, a small sample."

    concept = "A record tells you who won. Points scored and allowed tell you how well a team has played."
    if past:
        # The history carries the script, so the evidence lines get shorter to keep it within 180 words.
        video = " ".join(filter(None, [
            opening, concept, "That is normal for an unbeaten team.", *past,
            fewest or f"They have scored {snapshot.points_for} points and allowed {snapshot.points_against}.",
            f"They are {snapshot.one_score_wins}-{snapshot.one_score_losses} in one-score games.",
            per_play, kicker, spoken_question(verdict), VERDICT_SENTENCES[verdict], caveat,
        ]))
    else:
        video = " ".join(filter(None, [
            opening, concept, points, close, turnovers, per_play, kicker, spoken_question(verdict),
            VERDICT_SENTENCES[verdict], caveat,
        ]))
    captions = [
        f"{nick}: {record(snapshot)} through week {snapshot.through_week}",
        f"Points say {points_record(snapshot.pythagorean_wins, snapshot.games)}",
        f"One-score games: {snapshot.one_score_wins}-{snapshot.one_score_losses}",
        f"Verdict: {verdict}",
    ]
    x_post = f"{opening} {past[0]}" if past else f"{opening} {VERDICT_SENTENCES[verdict]}"
    linkedin = "\n\n".join(filter(None, [
        f"{opening} This week I asked whether the {nick} are as good as their record.",
        "I started with a simple idea. A record shows who won, but points scored and allowed show how well "
        "a team has actually played, and over a season they track wins closely.",
        " ".join(filter(None, [*past, fewest])) if past else None,
        " ".join(filter(None, [points, close,
                               None if past or not luck_gaps else league_luck_sentence(snapshot, luck_gaps)])),
        # With the history and research in, the turnover line moves to the video only to keep LinkedIn readable.
        " ".join(filter(None, [None if past else turnovers, per_play, held])),
        " ".join(filter(None, [f'My verdict is "{verdict}."', VERDICT_SENTENCES[verdict], caveat, schedule])),
        "The lesson I took from it is that a perfect record almost always runs ahead of a team's points, so the "
        "useful question is how far." if past else
        "The lesson I took from it is that close games are where a record and a team's quality drift apart.",
    ]))
    followup = surprising_fact(snapshot, scoring, research)
    return Posts(video, captions, x_post, linkedin, followup)


def to_markdown(snapshot: SeasonSnapshot, posts: Posts) -> str:
    lines = [
        f"# Week 1 draft posts: Are the {nickname(snapshot.team)} for real?",
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
