# Glossary

Plain-language definitions of every stat used so far. Each notebook adds the
terms it introduces. Keep the short definition under 10 words, the way it would
read in a caption.

## Entry format

```markdown
### Term (abbreviation)

**In a caption:** under 10 words.

**Longer:** 2 to 3 sentences for me, with how it is computed.

**First used:** weekNN-notebook-name
```

## Terms

### Point differential (PD)

**In a caption:** Points scored minus points allowed.

**Longer:** The simplest measure of how well a team has played. Shown as a season total or per game. It ignores which games were won, which is the point: it is less bent by luck than the record.

**First used:** week01-save-the-season

### Pythagorean wins

**In a caption:** The record a team's points usually produce.

**Longer:** Points scored to the power 2.37, divided by that plus points allowed to the same power, times games played. Named after the Pythagorean theorem's squares; 2.37 is the exponent that fits NFL scoring.

**First used:** week01-save-the-season

### One-score game

**In a caption:** A game decided by 8 points or fewer.

**Longer:** Close enough that one touchdown and two-point try could have flipped it. A team's record in these games often swings on a bounce, a kick or a call.

**First used:** week01-save-the-season

### Turnover margin

**In a caption:** Takeaways minus giveaways.

**Longer:** Giveaways are interceptions thrown and fumbles lost; takeaways are the opponent's giveaways in the same game. In 2024-2025 the margin after six weeks only loosely tracked the rest of the season.

**First used:** week01-save-the-season

### EPA per play

**In a caption:** Average points each play adds to the expected score.

**Longer:** Expected points added: how much a play changes the points a team can expect from its drive, given down, distance and field position. Averaged over every run and pass.

**First used:** week01-save-the-season

### Success rate

**In a caption:** Share of plays that helped the expected score.

**Longer:** The share of plays with positive EPA. It counts how often an offense moves forward, while EPA per play also weighs how much.

**First used:** week01-save-the-season

### Regression to the mean

**In a caption:** Extreme early numbers drift back toward average.

**Longer:** Part of any hot or cold start is luck, which does not repeat. Since 2012, a little under half of a team's point differential per game after six weeks has carried into the rest of its season.

**First used:** week01-save-the-season

### Strength of schedule (SOS)

**In a caption:** How good a team's opponents are.

**Longer:** Here, the average rating of the opponents a team has left, ranked among the 32 teams. A team's rating is its point differential per game, shrunk toward zero.

**First used:** week01-save-the-season

### Simulation

**In a caption:** Playing the rest of the season thousands of times.

**Longer:** Each remaining game gets a win chance from the two teams' ratings and home field, and a computer flips a weighted coin for each one, 10,000 times. The share of runs that end a certain way is the estimate.

**First used:** week01-save-the-season

### Points record

**In a caption:** The record a team's points usually produce.

**Longer:** Pythagorean wins rounded to a whole win (halves round up), with the rest of the games as losses. A 6-0 team with 4.66 Pythagorean wins has a points record of 5-1. Ties are not shown.

**First used:** week01-real-or-lucky

### Median

**In a caption:** The middle game, so one blowout cannot skew it.

**Longer:** Sort the games and take the middle one (or halfway between the two middle ones). Used for what an opponent "usually" scores or allows: a team that scored 59, 24 and 21 usually scores 24, while its average says 34.7.

**First used:** week01-real-or-lucky

### Opponent adjustment

**In a caption:** Points allowed compared with what each opponent usually scores.

**Longer:** For each game, an opponent's median points in its other games minus what it scored against this team, averaged over the team's games. It credits a defense for holding good offenses, and the same idea works for an offense against defenses. A simple version of week 8's opponent-adjusted point differential.

**First used:** week01-real-or-lucky
