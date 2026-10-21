// Manual browser evidence using fixed HTTP responses; no shared database access.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core')
const path = require('node:path')
const labels = { points: 'Points', rebounds: 'Rebounds', assists: 'Assists', threes_made: '3-pointers made',
  blocks: 'Blocks', points_rebounds_assists: 'Pts + reb + ast', double_double: 'Double-double' }
const keys = ['points', 'rebounds', 'assists', 'threes_made', 'blocks']
const report = { source: 'ESPN', fetchedAt: null, freshness: 'unavailable', injuries: [] }
function team(code, state) {
  return { team: code, completedGames: state === 'empty' ? 0 : 10,
    stats: Object.fromEntries(keys.map((key, index) => {
      const empty = state === 'empty' || (state === 'partial' && key === 'blocks')
      const games = empty ? 0 : state === 'partial' ? 2 : 10
      return [key, { for: { perGame: empty ? null : 99, rank: empty ? null : 1, games, rankedTeams: 30 },
        allowed: { perGame: empty ? null : key === 'blocks' ? 0 : 20 + index + (code === 'NY' ? 10 : 0),
          rank: empty ? null : 8, games, rankedTeams: empty && state === 'empty' ? 0 : 30 } }]
    })) }
}
function context(state) {
  return state === 'missing' ? null : { season: 2026, beforeDate: '2026-11-01', basis: 'stored_player_box_scores',
    away: team('NY', state), home: team('BOS', state) }
}
function lines(state) {
  return Object.keys(labels).map((market, index) => ({
    playerId: index + 1, playerName: `Example ${market}`, position: 'G', team: state === 'unknown' ? null : 'NY',
    market, oddsType: 'standard', line: market === 'double_double' ? 0.5 : 4.5,
    fetchedAt: '2026-11-01T18:00:00Z', recent: [], injury: null,
    ...(market === 'double_double' ? {} : { projection: 5, gamesInSample: 20, priorMinutes: 32, gap: 0.5,
      pOver: market === 'assists' ? 0.55 : null, pUnder: market === 'assists' ? 0.45 : null,
      overProbabilityVersion: market === 'assists' ? 'nba-pover-v1' : null,
      flags: market === 'assists' ? [] : ['no_over_probability'] }),
  }))
}
function game(state) {
  return { gameId: 900001, season: 2026, week: 3, gameType: 'REG', gameDate: '2026-11-01',
    startUtc: '2026-11-01T23:00:00Z', status: 'scheduled', awayTeam: 'NY', homeTeam: 'BOS',
    awayTeamName: 'New York Knicks', homeTeamName: 'Boston Celtics', awayScore: null, homeScore: null,
    awayRecord: { wins: 6, losses: 4 }, homeRecord: { wins: 7, losses: 3 }, propLineCount: 7,
    moneyline: null, spread: null, total: null, lineMovement: [], lineHistory: [], injuryReport: report,
    teamStats: context(state), lines: lines(state).filter(line => line.market !== 'double_double'),
    lineOnlyLines: lines(state).filter(line => line.market === 'double_double') }
}

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const results = []
  const parity = new Map()
  const cases = [...Object.keys(labels).map(market => ({ market, state: 'loaded' })),
    ...['unknown', 'missing', 'empty', 'partial'].map(state => ({ market: 'assists', state })),
    { market: 'blocks', state: 'partial' }]
  try {
    for (const width of [1440, 390]) for (const entry of ['board', 'game']) {
      const browserContext = await browser.newContext({ viewport: { width, height: 1000 } })
      const page = await browserContext.newPage()
      const errors = [], requests = []
      let state = 'loaded'
      page.on('pageerror', error => errors.push(error.message))
      await browserContext.route('**/*', async route => {
        const url = new URL(route.request().url())
        if (!url.pathname.includes('/nba/games/900001') && !url.pathname.endsWith('/nba/props')) return route.continue()
        requests.push(url.pathname)
        const data = game(state)
        const payload = url.pathname.endsWith('/nba/props')
          ? { date: '2026-11-01', previousDate: null, nextDate: null, modelVersion: 'nba-reference-v1', games: [data] }
          : url.pathname.endsWith('/props') || url.pathname.endsWith('/line-only-props')
            ? { gameId: data.gameId, modelVersion: 'nba-reference-v1', injuryReport: report, teamStats: data.teamStats,
              lines: url.pathname.endsWith('/line-only-props') ? data.lineOnlyLines : data.lines } : data
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
      })
      for (const item of cases) {
        console.log('Checking', width, entry, item.market, item.state)
        state = item.state
        const target = entry === 'board' ? `/nba/board?date=2026-11-01&market=${item.market}` : '/nba/game/900001'
        await page.goto(`http://127.0.0.1:3001/?fixture=${item.market}-${state}#${target}`)
        const table = page.getByRole('table', { name: `${labels[item.market]} ${item.market === 'double_double' ? 'other lines' : 'props'}`, exact: true })
        const opener = table.getByRole('button', { name: `Example ${item.market}`, exact: true })
        await opener.waitFor()
        const order = await page.locator('.prop-table__open').allTextContents()
        const requestCount = requests.length
        await opener.focus()
        await page.keyboard.press('Enter')
        const evidence = page.getByRole('region', { name: 'Opponent team context', exact: true })
        await evidence.waitFor()
        const text = await evidence.innerText()
        if (!keys.includes(item.market) && !text.includes('not available for this market')) throw new Error(text)
        if (state === 'unknown' && !text.includes('line team')) throw new Error(text)
        if (state === 'missing' && !text.includes('Team stats unavailable')) throw new Error(text)
        if (state === 'empty' && !text.includes('No earlier regular-season games')) throw new Error(text)
        if (state === 'partial' && !text.includes('Partial coverage')) throw new Error(text)
        if (keys.includes(item.market) && state === 'loaded' && !text.includes('BOS allows')) throw new Error(text)
        if (item.market === 'blocks' && state === 'loaded' && !text.includes('0.0 blocks/game')) throw new Error(text)
        const parityKey = `${width}:${item.market}:${state}`
        if (entry === 'board') parity.set(parityKey, text)
        else if (parity.get(parityKey) !== text) throw new Error('Board/game opponent context mismatch')
        if (!await page.getByRole('region', { name: 'Injury report', exact: true }).isVisible()) throw new Error('Injury evidence missing')
        const overflow = await evidence.evaluate(element => element.scrollWidth > element.clientWidth)
        if (overflow || errors.length) throw new Error(JSON.stringify({ overflow, errors }))
        if ((item.market === 'assists' && ['loaded', 'unknown', 'partial'].includes(state)) || item.market === 'double_double') {
          await page.locator('.ant-drawer-content').screenshot({ path: path.join(__dirname, `step5-${entry}-${item.market}-${state}-${width}.png`) })
        }
        await page.keyboard.press('Escape')
        await evidence.waitFor({ state: 'hidden' })
        await page.waitForFunction(name => document.activeElement?.textContent === name, `Example ${item.market}`)
        if (requests.length !== requestCount) throw new Error('Drawer fetched new context')
        if (JSON.stringify(order) !== JSON.stringify(await page.locator('.prop-table__open').allTextContents())) throw new Error('Row order changed')
        results.push({ width, entry, ...item, parity: true, focusRestored: true, newDrawerRequests: 0 })
      }
      await browserContext.close()
    }
    console.log(JSON.stringify({ passed: results.length, runtimeErrors: 0, observations: results }))
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
