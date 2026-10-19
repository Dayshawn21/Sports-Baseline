# WTA 125 event crosswalk (40a)

`tennis_wta125_events.csv` freezes verified Valuebetennis women's Challenger
tournament labels by match calendar year. This is an allowlist, not a rule that
accepts any name without an ITF prefix. It contains metadata only.

Source: the [official WTA calendar API](https://api.wtatennis.com/tennis/tournaments/?levels=WTA+125&page=0&pageSize=100),
retrieved on 2026-10-19 with the public `account: wta` header used by the
[WTA calendar](https://www.wtatennis.com/tournaments/wta-125).
Pages 0, 1 and 2 return 230 records in total, of which 228 have event years
2021-2026. Every referenced event's historical `level` is `WTA 125`. A group's
current level can differ; it is not used. Runtime requires no network access.

Each CSV row identifies a provider label and its official event year, WTA ID,
and official dates. The corresponding metadata is available at
`https://api.wtatennis.com/tennis/tournaments/<wta_id>/<wta_year>`;
the public overview is `https://www.wtatennis.com/tournaments/<wta_id>/<slug>/<wta_year>`.
Labels were compared using names, cities and dates, without match results.
The runtime filter matches `(season, tournament)` exactly. Official dates are
provenance, not additional match exclusions: provider dates include qualifying,
delays and timezone differences. Existing main-draw exclusions still apply.

`season` means the match date's calendar year, as in the existing loader.
The 2024 Canberra event has qualifying in December 2023; the 2025 Canberra
event starts in December 2024. Both therefore have entries in two seasons.
Charleston has two WTA 125 events under the same provider label in 2024;
both references are retained, with one allowlist key.

| Official event year | WTA 125 events listed | Represented in provider Challenger rows |
|---|---:|---:|
| 2021 | 15 | 15 |
| 2022 | 24 | 24 |
| 2023 | 31 | 31 |
| 2024 | 36 | 34 |
| 2025 | 53 | 53 |
| 2026 | 69 | 54 |

2024 gaps: Mumbai (1100) and Puerto Vallarta (1108).
2026 gaps with a start on or before 2026-10-19: Parma (2041), Paris (2057),
and Rio de Janeiro (1150, starts on the inspection date). Twelve additional
2026 events start after that date. Coverage refers only to women's Challenger
rows in these downloaded files; the population is not expanded to other
provider categories to fill gaps. This table does not claim that every match
of a represented event has a usable closing price or ELO.

Every unlisted women's Challenger label in the downloads has an explicit ITF
prefix (`W<number>` or `W<number>+H` followed by a space). Counts inspect every
label and stop on any other unlisted name, requiring metadata review before
a newer download can change the population. No fuzzy matching runs in the CLI.

Valuebetennis season CSVs remain local and gitignored. Source attribution:
[Valuebetennis open data](https://www.valuebetennis.com), CC BY 4.0.
