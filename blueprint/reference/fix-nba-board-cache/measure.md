# NBA board cache: measurements

Local API (Windows selector-loop launcher, port 8017) against the shared Neon
database, measured 2026-10-23 (Eastern today 2026-10-23). Each run starts a
fresh API process, waits for `/health`, then requests `/nba/props?date=2026-10-21`
once ("first", a cold process, warm database) and five more times, then
2026-10-22 to 2026-10-25, 2026-11-15 (outside the cache window) and the
default date. Memory is the process working set (Windows), read before the
first board request and after the last.

These are development observations, not hosted Render figures.

## Step 1 - baseline (no cache)

| Run | First (s) | Repeat 2026-10-21 (s) | Default (s) | Working set before / after (MB) | Peak (MB) |
|---:|---:|---|---:|---|---:|
| 1 | 7.64 | 1.94, 1.74, 2.15, 1.76, 1.79 | 1.05 | 216.1 / 265.6 | 306.0 |
| 2 | 3.00 | 1.74, 1.70, 1.75, 1.74, 1.66 | 1.16 | 216.0 / 262.8 | 306.6 |
| 3 | 2.42 | 1.72, 1.76, 1.74, 1.72, 1.65 | 1.05 | 215.4 / 261.0 | 305.5 |
| 4 | 2.59 | 1.75, 1.68, 1.78, 1.71, 1.73 | 1.05 | 215.4 / 260.5 | 305.9 |
| 5 | 2.44 | 1.68, 1.78, 1.78, 1.67, 1.65 | 0.98 | 215.5 / 262.0 | 305.5 |

Other dates, every run within about 0.1 s of: 2026-10-22 0.79 s,
2026-10-23 1.05 s, 2026-10-24 0.72 s, 2026-10-25 0.49 s, 2026-11-15 0.48 s.

- **Body:** 6,455,505 bytes for 2026-10-21, sha256
  `ba2c59c2ae2f8c4204b267b1dc5dce41a5e3f8ebc82085043eb9c0e5e1b9a8bf`,
  identical across all five runs (more lines than the 4.9 MB recorded in 42b).
- **Every request rebuilds:** repeats stay at about 1.7 s.
- **A single build peaks about 90 MB above the idle process** (216 MB to
  306 MB), and the process keeps about 45 MB afterwards. On a 512 MB host,
  concurrent uncached builds are the memory risk, more than the stored bytes.

## Step 3 - with the cache

Same script, same dates, five fresh processes. The six other requests fill
six keys against a limit of five, so the 2026-10-21 entry is evicted.

| Run | First (s) | Repeat 2026-10-21 (s) | Default (s) | Working set before / after (MB) | Peak (MB) |
|---:|---:|---|---:|---|---:|
| 1 | 2.56 | 0.010, 0.010, 0.010, 0.010, 0.010 | 1.05 | 215.2 / 258.9 | 287.3 |
| 2 | 3.31 | 0.010, 0.011, 0.010, 0.013, 0.009 | 0.96 | 215.6 / 261.2 | 287.6 |
| 3 | 2.46 | 0.022, 0.010, 0.010, 0.011, 0.011 | 1.04 | 215.4 / 258.3 | 287.6 |
| 4 | 3.32 | 0.011, 0.009, 0.010, 0.010, 0.010 | 1.00 | 215.6 / 259.2 | 287.5 |
| 5 | 2.38 | 0.010, 0.009, 0.009, 0.010, 0.011 | 0.99 | 216.0 / 259.6 | 288.0 |

- **Body:** 6,455,505 bytes, the same sha256 as the baseline in every run.
- **A cached repeat takes about 0.01 s,** against about 1.7 s before. A
  first request per date still builds (about 0.5 to 1.1 s for these dates,
  2.4 to 3.3 s for 2026-10-21 in a fresh process).
- **Memory with five boards cached:** 258 to 261 MB after, against 260 to
  266 MB in the baseline, which kept nothing. The stored bodies (at most five,
  about 32 MB at 6.5 MB each) are within the noise of what the allocator
  already retained after one build.
- **Peak:** 287 to 288 MB, against 305 to 307 MB in the baseline, because
  repeats no longer rebuild.
- **Not measured:** a burst of visitors on different dates. The serial build
  lock means only one board builds at a time, so the peak should stay near
  a single build's; hosted Render memory and latency are unverified.
