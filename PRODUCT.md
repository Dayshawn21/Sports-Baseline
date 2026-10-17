# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Primary: the owner**, one person researching bets daily. Uses desktop and
  phone equally: research at a desk, a last check on the phone before placing
  a bet. Bets are placed and tracked elsewhere (sportsbooks, PrizePicks,
  Pikkit); this app never places one.
- **Secondary: anonymous visitors to the public read-only demo**, mostly
  employers reviewing the project. They browse the same pages with no account
  and need to follow what they see without a guide.

## Product Purpose

Betting intelligence for tennis, NFL and NBA. It ingests schedules, stats,
odds and PrizePicks prop lines on a schedule, runs models, compares them with
the de-vigged market, and shows where they disagree. Predictions are frozen
before each event and graded afterward, so any edge is measured rather than
assumed. Success: the owner scans a slate and sees the few actionable plays
without reading everything, and a visitor understands what is a pick and what
is only reference.

## Positioning

Honest about the edge. Most models here have been tested against the market
and lost, and the app says so: a number is a pick only after a pre-registered
check passes, and everything else is shown as gray reference. The model pages
publish the graded record, including the failures.

## Operating Context

- **First jobs on opening the app:** find today's plays on a slate, and open
  one game or match to read its market, props, injuries and line movement.
- Line shopping (best price beside a fair price) and checking the model track
  record pages are secondary jobs.
- Cadence: tennis daily, NFL weekly (Thursday to Monday), NBA daily from
  October to June.
- Each sport has three views: Slate, Props (tennis and NFL) and Model, plus
  game or match, and player detail pages.

## Capabilities and Constraints

- React SPA (Vite, Ant Design, Tailwind v4, TanStack Query) over a FastAPI
  API; hosted on Render, read-only for visitors; one owner-only admin page.
- **Signal color is a rule, not a style:** green only for a validated positive
  signal, red only for a result more than 2 SE below its baseline, everything
  else gray. NFL and NBA edges stay gray until their ranking checks adopt a
  slice; tennis moneyline picks are off.
- No UI text below 11px.
- Display changes never change a probability, edge, rank, sort or pick.
- Times are shown in Central time, labeled `CT`.

## Brand Commitments

- Name: Lineform. Dark, dense, data-first; the palette, fonts (Barlow
  Condensed display, DM Sans body, JetBrains Mono numerics) and signal colors
  in `web/src/index.css` are kept (structural redesign decided 2026-10-16).

## Evidence on Hand

- Live demo: `https://sportapp-web-7v3r.onrender.com`; public code:
  `github.com/Dayshawn21/Sports-Baseline`.
- Real data for every page (slates, props, graded model records). No
  testimonials, users or performance claims exist, and none may be invented;
  the app makes no claim to win money.

## Product Principles

1. The actionable few first: a slate leads with what is worth acting on, and
   reference detail is one step away.
2. Pick versus reference is always unmistakable.
3. One app, not three: every sport uses the same page shapes, so learning one
   sport teaches the others.
4. Evidence on demand: every number can be traced to its inputs on the detail
   page.

## Accessibility & Inclusion

No product-specific standard set. Baseline: readable at 11px and up, keyboard
reachable controls, meaning never carried by color alone (picks also carry a
label).
