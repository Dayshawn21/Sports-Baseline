// Fixed HTTP fixtures exercise the real game page without a shared database.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core')
const path = require('node:path')

const keys = ['points', 'rebounds', 'assists', 'threes_made', 'blocks']
function team(code, state) {
  const completedGames = state === 'empty' ? 0 : 10
  const stats = Object.fromEntries(keys.map((key, index) => {
    const empty = state === 'empty' || (state === 'partial' && key === 'blocks')
    const games = empty ? 0 : state === 'partial' && key === 'assists' ? 2 : 10
    const rate = allowed => ({ perGame: empty ? null : [112.4, 43.2, 25.4, 12.6, 0][index] + (allowed ? 1 : 0),
      rank: empty ? null : 8, games, rankedTeams: empty && state === 'empty' ? 0 : 30 })
    return [key, { for: rate(false), allowed: rate(true) }]
  }))
  return { team: code, completedGames, stats }
}
function detail(state) {
  return {
    gameId: 900001, season: 2026, week: 3, gameType: 'REG', gameDate: '2026-11-01',
    startUtc: '2026-11-01T23:00:00Z', status: 'scheduled', awayTeam: 'NY', homeTeam: 'BOS',
    awayTeamName: 'New York Knicks', homeTeamName: 'Boston Celtics', awayScore: null, homeScore: null,
    awayRecord: { wins: 6, losses: 4 }, homeRecord: { wins: 7, losses: 3 }, propLineCount: 0,
    moneyline: null, spread: null, total: null, lineMovement: [], lineHistory: [],
    injuryReport: { source: 'ESPN', fetchedAt: null, freshness: 'unavailable', injuries: [] },
    teamStats: state === 'missing' ? null : {
      season: 2026, beforeDate: '2026-11-01', basis: 'stored_player_box_scores',
      away: team('NY', state), home: team('BOS', state),
    },
  }
}

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const observations = []
  try {
    for (const width of [1440, 390]) {
      for (const state of ['loaded', 'empty', 'partial', 'missing']) {
        const context = await browser.newContext({ viewport: { width, height: 1000 } })
        const page = await context.newPage()
        const errors = []
        page.on('pageerror', error => errors.push(error.message))
        await context.route('**/*', async route => {
          const url = new URL(route.request().url())
          if (!url.pathname.includes('/nba/games/900001')) return route.continue()
          const payload = url.pathname.endsWith('/props') || url.pathname.endsWith('/line-only-props')
            ? { gameId: 900001, modelVersion: 'nba-reference-v1', lines: [],
              injuryReport: detail(state).injuryReport, teamStats: detail(state).teamStats }
            : detail(state)
          return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
        })
        await page.goto('http://127.0.0.1:3001/#/nba/game/900001')
        const section = page.getByRole('region', { name: 'Team stats', exact: true })
        await section.waitFor()
        await page.evaluate(() => document.fonts.ready)
        if (state !== 'missing' && await section.getByRole('table').count() !== 2) throw new Error('Missing team tables')
        if (state === 'empty' && await section.getByText('No earlier regular-season games this season.').count() !== 2) throw new Error('Missing no-history state')
        if (state === 'partial') {
          await section.getByText('Small sample', { exact: true }).first().waitFor()
          await section.getByText('Partial coverage', { exact: true }).first().waitFor()
        }
        if (state === 'loaded') await section.getByText('0.0', { exact: true }).first().waitFor()
        if (state === 'missing') await section.getByText('Team stats unavailable.', { exact: true }).waitFor()
        await page.evaluate(() => window.scrollTo(0, 0))
        await page.screenshot({ path: path.join(__dirname, `step4-${state}-${width}.png`), fullPage: true })
        const metrics = await section.evaluate(element => ({
          pageOverflow: document.documentElement.scrollWidth > innerWidth,
          tableOverflow: [...element.querySelectorAll('table')].some(table => table.scrollWidth > table.clientWidth),
          minFont: Math.min(...[...element.querySelectorAll('th, td span, p')].map(node => parseFloat(getComputedStyle(node).fontSize))),
        }))
        if (errors.length || metrics.pageOverflow || metrics.tableOverflow || metrics.minFont < 11) {
          throw new Error(JSON.stringify({ state, width, errors, ...metrics }))
        }
        observations.push({ state, width, ...metrics, errors })
        await context.close()
      }
    }
    console.log(JSON.stringify(observations, null, 2))
  } finally {
    await browser.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
