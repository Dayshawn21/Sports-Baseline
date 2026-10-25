"""Save the Season numbers for one NFL team: pure calculations on query DataFrames."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

FINAL_STATUSES = frozenset({"completed", "postponed", "canceled"})
PYTHAGOREAN_EXPONENT = 2.37
ONE_SCORE_MARGIN = 8
LUCK_THRESHOLD = 0.75
SAVABLE_CHANCE = 0.35
LONG_SHOT_CHANCE = 0.10
SIMULATIONS = 10_000
SEED = 2026
PLAYOFF_GAME_TYPES = frozenset({"WC", "DIV"})  # top seeds skip the Wild Card round and first play in DIV

Luck = Literal["unlucky", "about right", "lucky"]
Verdict = Literal["savable", "long shot", "very unlikely"]

TEAM_NAMES: dict[str, tuple[str, str]] = {
    "ARI": ("Arizona", "Cardinals"), "ATL": ("Atlanta", "Falcons"), "BAL": ("Baltimore", "Ravens"),
    "BUF": ("Buffalo", "Bills"), "CAR": ("Carolina", "Panthers"), "CHI": ("Chicago", "Bears"),
    "CIN": ("Cincinnati", "Bengals"), "CLE": ("Cleveland", "Browns"), "DAL": ("Dallas", "Cowboys"),
    "DEN": ("Denver", "Broncos"), "DET": ("Detroit", "Lions"), "GB": ("Green Bay", "Packers"),
    "HOU": ("Houston", "Texans"), "IND": ("Indianapolis", "Colts"), "JAX": ("Jacksonville", "Jaguars"),
    "KC": ("Kansas City", "Chiefs"), "LA": ("Los Angeles", "Rams"), "LAC": ("Los Angeles", "Chargers"),
    "LV": ("Las Vegas", "Raiders"), "MIA": ("Miami", "Dolphins"), "MIN": ("Minnesota", "Vikings"),
    "NE": ("New England", "Patriots"), "NO": ("New Orleans", "Saints"), "NYG": ("New York", "Giants"),
    "NYJ": ("New York", "Jets"), "PHI": ("Philadelphia", "Eagles"), "PIT": ("Pittsburgh", "Steelers"),
    "SEA": ("Seattle", "Seahawks"), "SF": ("San Francisco", "49ers"), "TB": ("Tampa Bay", "Buccaneers"),
    "TEN": ("Tennessee", "Titans"), "WAS": ("Washington", "Commanders"),
}


def team_name(code: str) -> str:
    city, nickname = TEAM_NAMES[code]
    return f"{city} {nickname}"


def nickname(code: str) -> str:
    return TEAM_NAMES[code][1]


def last_final_week(games: pd.DataFrame, season: int) -> int:
    """The last week such that it and every earlier week has all its games final; 0 if none."""
    season_games = games[games["season"] == season]
    final = season_games.groupby("week")["status"].agg(lambda s: s.isin(FINAL_STATUSES).all())
    week = 0
    for number, done in final.sort_index().items():
        if not done:
            break
        week = int(number)
    return week


def _sides(frame: pd.DataFrame) -> pd.DataFrame:
    """Each game twice, once from each team's side."""
    sides = []
    for side, other in (("home", "away"), ("away", "home")):
        sides.append(pd.DataFrame({
            "game_id": frame["game_id"],
            "season": frame["season"],
            "week": frame["week"],
            "team": frame[side],
            "opponent": frame[other],
            "is_home": side == "home",
            "points_for": frame[f"{side}_score"],
            "points_against": frame[f"{other}_score"],
        }))
    return pd.concat(sides, ignore_index=True)


def team_games(games: pd.DataFrame) -> pd.DataFrame:
    """One row per team per completed game, from that team's side."""
    rows = _sides(games[games["status"] == "completed"])
    rows["margin"] = rows["points_for"] - rows["points_against"]
    return rows


def played_between(games: pd.DataFrame, season: int, first_week: int, last_week: int) -> pd.DataFrame:
    rows = team_games(games)
    keep = (rows["season"] == season) & rows["week"].between(first_week, last_week)
    return rows[keep].reset_index(drop=True)


def pythagorean_wins(points_for, points_against, games):
    """Wins a team 'should' have from its points; works on numbers or Series."""
    pf = np.asarray(points_for, dtype=float) ** PYTHAGOREAN_EXPONENT
    pa = np.asarray(points_against, dtype=float) ** PYTHAGOREAN_EXPONENT
    return pf / (pf + pa) * np.asarray(games, dtype=float)


def luck_label(pythagorean: float, wins: int, ties: int) -> Luck:
    gap = pythagorean - (wins + ties / 2)
    if gap >= LUCK_THRESHOLD:
        return "unlucky"
    if gap <= -LUCK_THRESHOLD:
        return "lucky"
    return "about right"


def standings(games: pd.DataFrame, season: int, through_week: int) -> pd.DataFrame:
    rows = played_between(games, season, 1, through_week)
    close = rows["margin"].abs() <= ONE_SCORE_MARGIN
    rows = rows.assign(
        win=rows["margin"] > 0,
        loss=rows["margin"] < 0,
        tie=rows["margin"] == 0,
        one_score_win=close & (rows["margin"] > 0),
        one_score_loss=close & (rows["margin"] < 0),
    )
    table = rows.groupby("team").agg(
        games=("game_id", "size"),
        wins=("win", "sum"),
        losses=("loss", "sum"),
        ties=("tie", "sum"),
        points_for=("points_for", "sum"),
        points_against=("points_against", "sum"),
        one_score_wins=("one_score_win", "sum"),
        one_score_losses=("one_score_loss", "sum"),
    )
    table["point_diff"] = table["points_for"] - table["points_against"]
    table["pythagorean_wins"] = pythagorean_wins(table["points_for"], table["points_against"], table["games"])
    return table


def rank(values: pd.Series, *, best: Literal["high", "low"]) -> pd.Series:
    """1 = best; tied values share the better rank."""
    return values.rank(ascending=best == "low", method="min").astype(int)


def _join_per_game(rows: pd.DataFrame, per_game: pd.DataFrame, side: str, columns: list[str]) -> pd.DataFrame:
    """Attach a team-game stat from the team's side or the opponent's; missing rows are an error."""
    renamed = per_game.rename(columns={"team": side, **{c: f"{side}_{c}" for c in columns}})
    joined = rows.merge(renamed, on=["game_id", side], how="left")
    missing = joined[[f"{side}_{c}" for c in columns]].isna().any(axis=1)
    if missing.any():
        raise ValueError(f"{int(missing.sum())} team-games have no {', '.join(columns)} row (not loaded)")
    return joined


def turnover_margins(giveaways: pd.DataFrame, games: pd.DataFrame, season: int,
                     first_week: int, last_week: int) -> pd.DataFrame:
    """Takeaways are the opponent's giveaways in the same game."""
    rows = played_between(games, season, first_week, last_week)
    rows = _join_per_game(rows, giveaways, "team", ["giveaways"])
    rows = _join_per_game(rows, giveaways, "opponent", ["giveaways"])
    table = rows.groupby("team").agg(
        games=("game_id", "size"),
        giveaways=("team_giveaways", "sum"),
        takeaways=("opponent_giveaways", "sum"),
    ).astype(int)
    table["margin"] = table["takeaways"] - table["giveaways"]
    table["margin_rank"] = rank(table["margin"], best="high")
    return table


def efficiency_ranks(efficiency: pd.DataFrame, games: pd.DataFrame, season: int, through_week: int) -> pd.DataFrame:
    """EPA per play and success rate, on offense and allowed on defense; rank 1 = best of the league."""
    stats = ["plays", "epa", "successes"]
    rows = played_between(games, season, 1, through_week)
    rows = _join_per_game(rows, efficiency, "team", stats)
    rows = _join_per_game(rows, efficiency, "opponent", stats)
    sums = rows.groupby("team")[[f"{side}_{s}" for side in ("team", "opponent") for s in stats]].sum()
    table = pd.DataFrame({
        "offense_epa": sums["team_epa"] / sums["team_plays"],
        "offense_success": sums["team_successes"] / sums["team_plays"],
        "defense_epa": sums["opponent_epa"] / sums["opponent_plays"],
        "defense_success": sums["opponent_successes"] / sums["opponent_plays"],
    })
    for column in ("offense_epa", "offense_success"):
        table[f"{column}_rank"] = rank(table[column], best="high")
    for column in ("defense_epa", "defense_success"):
        table[f"{column}_rank"] = rank(table[column], best="low")
    return table


@dataclass(frozen=True)
class Carryover:
    correlation: float
    team_seasons: int


def turnover_carryover(giveaways: pd.DataFrame, games: pd.DataFrame, seasons: list[int],
                       through_week: int) -> Carryover:
    """How well turnover margin per game through a week tracks the rest of the season."""
    pairs = []
    for season in seasons:
        early = turnover_margins(giveaways, games, season, 1, through_week)
        late = turnover_margins(giveaways, games, season, through_week + 1, 99)
        both = (early["margin"] / early["games"]).to_frame("early").join(
            (late["margin"] / late["games"]).to_frame("late"), how="inner")
        pairs.append(both)
    combined = pd.concat(pairs)
    return Carryover(float(combined["early"].corr(combined["late"])), len(combined))



def final_wins(schedules: pd.DataFrame) -> pd.DataFrame:
    """Each team-season's regular-season wins, ties as half, rounded down; unscored games are skipped."""
    reg = schedules[(schedules["game_type"] == "REG") & schedules["home_score"].notna()]
    sides = []
    for side, other in (("home", "away"), ("away", "home")):
        margin = reg[f"{side}_score"] - reg[f"{other}_score"]
        sides.append(pd.DataFrame({"season": reg["season"], "team": reg[f"{side}_team"],
                                   "points": (margin > 0) + (margin == 0) * 0.5}))
    totals = pd.concat(sides).groupby(["season", "team"])["points"].sum()
    return np.floor(totals).astype(int).to_frame("wins").reset_index()


def playoff_entrants(schedules: pd.DataFrame) -> pd.DataFrame:
    """One row per team-season that played a playoff game."""
    games = schedules[schedules["game_type"].isin(PLAYOFF_GAME_TYPES)]
    teams = pd.concat([games[["season", side]].set_axis(["season", "team"], axis=1)
                       for side in ("home_team", "away_team")])
    return teams.drop_duplicates().reset_index(drop=True)


def playoff_rate_by_wins(schedules: pd.DataFrame) -> pd.DataFrame:
    """For each final win total: team-seasons, how many reached the playoffs, and the share."""
    teams = final_wins(schedules).merge(playoff_entrants(schedules).assign(made=1),
                                        on=["season", "team"], how="left")
    teams["made"] = teams["made"].fillna(0).astype(int)
    table = teams.groupby("wins").agg(teams=("team", "size"), made=("made", "sum"))
    table["rate"] = table["made"] / table["teams"]
    return table


@dataclass(frozen=True)
class PlayoffBar:
    wins: int    # the fewest final wins at which at least half of teams made the playoffs
    made: int
    teams: int


def playoff_bar(table: pd.DataFrame) -> PlayoffBar:
    above = table[table["rate"] >= 0.5]
    if above.empty:
        raise ValueError("no win total reached the playoffs at least half the time")
    wins = int(above.index.min())
    return PlayoffBar(wins, int(table.loc[wins, "made"]), int(table.loc[wins, "teams"]))


def playoff_rate(table: pd.DataFrame, wins: int) -> float:
    """Below the lowest observed total 0, above the highest 1; an unseen total in between is interpolated."""
    if wins < table.index.min():
        return 0.0
    if wins > table.index.max():
        return 1.0
    if wins in table.index:
        return float(table.loc[wins, "rate"])
    full = table["rate"].reindex(range(table.index.min(), table.index.max() + 1)).interpolate()
    return float(full.loc[wins])



@dataclass(frozen=True)
class LeagueFit:
    slope: float           # how much of a team's point differential per game carries into the rest of the season
    slope_team_seasons: int
    home_edge: float       # mean home margin, points
    sigma: float           # spread of game margins, points


def shrink_slope(games: pd.DataFrame, seasons: list[int], through_week: int) -> tuple[float, int]:
    """Least squares through the origin: rest-of-season PD per game on PD per game through the week."""
    pairs = []
    for season in seasons:
        early = played_between(games, season, 1, through_week).groupby("team")["margin"].mean()
        late = played_between(games, season, through_week + 1, 99).groupby("team")["margin"].mean()
        pairs.append(pd.concat([early.rename("early"), late.rename("late")], axis=1, join="inner"))
    both = pd.concat(pairs)
    slope = float((both["early"] * both["late"]).sum() / (both["early"] ** 2).sum())
    return slope, len(both)


def home_edge_and_sigma(games: pd.DataFrame, seasons: list[int]) -> tuple[float, float]:
    played = games[(games["status"] == "completed") & games["season"].isin(seasons)]
    margins = played["home_score"] - played["away_score"]
    return float(margins.mean()), float(margins.std())


def fit_league(games: pd.DataFrame, *, slope_seasons: list[int], margin_seasons: list[int],
               through_week: int) -> LeagueFit:
    slope, team_seasons = shrink_slope(games, slope_seasons, through_week)
    home_edge, sigma = home_edge_and_sigma(games, margin_seasons)
    return LeagueFit(slope, team_seasons, home_edge, sigma)


def ratings(table: pd.DataFrame, fit: LeagueFit) -> pd.Series:
    """Expected point differential per game from here on: this season's, shrunk toward zero."""
    return table["point_diff"] / table["games"] * fit.slope


def win_chance(rating: float, opponent_rating: float, is_home: bool, fit: LeagueFit) -> float:
    edge = rating - opponent_rating + (fit.home_edge if is_home else -fit.home_edge)
    return 0.5 * (1 + math.erf(edge / (fit.sigma * math.sqrt(2))))


def remaining_games(games: pd.DataFrame, season: int, through_week: int) -> pd.DataFrame:
    """Every game after the cutoff week, from each team's side; canceled games are dropped."""
    later = games[(games["season"] == season) & (games["week"] > through_week) & (games["status"] != "canceled")]
    return _sides(later)[["game_id", "week", "team", "opponent", "is_home"]]


def remaining_sos(remaining: pd.DataFrame, team_ratings: pd.Series) -> pd.DataFrame:
    """Average remaining opponent rating; rank 1 = hardest schedule left."""
    rows = remaining.assign(opponent_rating=remaining["opponent"].map(team_ratings))
    table = rows.groupby("team").agg(games=("game_id", "size"), opponent_rating=("opponent_rating", "mean"))
    table["rank"] = rank(table["opponent_rating"], best="high")
    return table


def simulate_wins(chances: list[float], *, simulations: int = SIMULATIONS, seed: int = SEED) -> np.ndarray:
    """Wins in each simulated rest of season; simulated games never tie."""
    rng = np.random.default_rng(seed)
    return (rng.random((simulations, len(chances))) < np.asarray(chances)).sum(axis=1)


def final_win_distribution(current_wins: float, simulated: np.ndarray) -> dict[int, float]:
    totals = np.floor(current_wins + simulated).astype(int)
    values, counts = np.unique(totals, return_counts=True)
    return {int(v): float(c) / len(simulated) for v, c in zip(values, counts)}


def playoff_chance(distribution: dict[int, float], table: pd.DataFrame) -> float:
    return sum(share * playoff_rate(table, wins) for wins, share in distribution.items())


def verdict(chance: float) -> Verdict:
    if chance >= SAVABLE_CHANCE:
        return "savable"
    if chance >= LONG_SHOT_CHANCE:
        return "long shot"
    return "very unlikely"


@dataclass(frozen=True)
class TeamReport:
    team: str
    season: int
    through_week: int
    wins: int
    losses: int
    ties: int
    points_for: int
    points_against: int
    pythagorean_wins: float
    one_score_wins: int
    one_score_losses: int
    turnover_margin: int
    turnover_margin_rank: int
    offense_epa_rank: int
    defense_epa_rank: int
    offense_success_rank: int
    defense_success_rank: int
    rating: float
    remaining_games: int
    remaining_sos_rank: int
    expected_final_wins: float
    final_win_distribution: dict[int, float]
    playoff_chance: float
    luck: Luck
    verdict: Verdict


def team_report(team: str, season: int, through_week: int, *, games: pd.DataFrame, efficiency: pd.DataFrame,
                giveaways: pd.DataFrame, playoff_table: pd.DataFrame, fit: LeagueFit) -> TeamReport:
    table = standings(games, season, through_week)
    if team not in table.index:
        raise ValueError(f"{team} has no completed games in {season} through week {through_week}")
    row = table.loc[team]
    turnovers = turnover_margins(giveaways, games, season, 1, through_week).loc[team]
    eff = efficiency_ranks(efficiency, games, season, through_week).loc[team]
    team_ratings = ratings(table, fit)
    remaining = remaining_games(games, season, through_week)
    schedule = remaining[remaining["team"] == team]
    chances = [win_chance(team_ratings[team], team_ratings[opp], home, fit)
               for opp, home in zip(schedule["opponent"], schedule["is_home"])]
    current = int(row["wins"]) + int(row["ties"]) / 2
    distribution = final_win_distribution(current, simulate_wins(chances))
    chance = playoff_chance(distribution, playoff_table)
    return TeamReport(
        team=team, season=season, through_week=through_week,
        wins=int(row["wins"]), losses=int(row["losses"]), ties=int(row["ties"]),
        points_for=int(row["points_for"]), points_against=int(row["points_against"]),
        pythagorean_wins=float(row["pythagorean_wins"]),
        one_score_wins=int(row["one_score_wins"]), one_score_losses=int(row["one_score_losses"]),
        turnover_margin=int(turnovers["margin"]), turnover_margin_rank=int(turnovers["margin_rank"]),
        offense_epa_rank=int(eff["offense_epa_rank"]), defense_epa_rank=int(eff["defense_epa_rank"]),
        offense_success_rank=int(eff["offense_success_rank"]), defense_success_rank=int(eff["defense_success_rank"]),
        rating=float(team_ratings[team]),
        remaining_games=len(schedule),
        remaining_sos_rank=int(remaining_sos(remaining, team_ratings).loc[team, "rank"]),
        expected_final_wins=current + sum(chances),
        final_win_distribution=distribution,
        playoff_chance=chance,
        luck=luck_label(float(row["pythagorean_wins"]), int(row["wins"]), int(row["ties"])),
        verdict=verdict(chance),
    )
