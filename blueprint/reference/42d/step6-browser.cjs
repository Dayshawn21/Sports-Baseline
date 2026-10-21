const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright-core')
const fs = require('node:fs')
const path = require('node:path')
const data = JSON.parse(fs.readFileSync(path.join(__dirname, 'step6-stored-fixtures.json'), 'utf8'))

async function main() {
  const browser = await chromium.launch({ channel: 'msedge', headless: true })
  const results = []
  try {
    for (const width of [1440, 390]) {
      const context = await browser.newContext({ viewport: { width, height: 1600 } })
      const page = await context.newPage()
      const runtimeErrors = []
      let mode = 'normal', release
      page.on('pageerror', error => runtimeErrors.push(error.message))
      await context.route('**/*', async route => {
        const url = new URL(route.request().url())
        if (!url.pathname.includes('/nba/games/') && !url.pathname.endsWith('/nba/props')) return route.continue()
        if (mode === 'loading') await new Promise(resolve => { release = resolve })
        if (mode === 'error') return route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"Controlled verification failure"}' })
        const historical = url.pathname.includes(`/games/${data.historical.gameId}`)
        const game = historical ? data.historical : data.game
        let payload = game
        if (url.pathname.endsWith('/nba/props')) payload = {
          date: game.gameDate, previousDate: null, nextDate: null, modelVersion: data.props.modelVersion,
          games: [{ ...game, lines: data.props.lines, lineOnlyLines: data.plain.lines }],
        }
        else if (url.pathname.endsWith('/line-only-props')) payload = historical
          ? { gameId: game.gameId, lines: [], injuryReport: game.injuryReport, teamStats: game.teamStats } : data.plain
        else if (url.pathname.endsWith('/props')) payload = historical
          ? { gameId: game.gameId, modelVersion: data.props.modelVersion, lines: [], injuryReport: game.injuryReport, teamStats: game.teamStats } : data.props
        return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(payload) })
      })
      for (const name of ['historical', 'game']) {
        await page.goto(`http://127.0.0.1:3001/?stored=${name}#/nba/game/${data[name].gameId}`)
        const section = page.getByRole('region', { name: 'Team stats', exact: true })
        await section.waitFor()
        if (name === 'historical') {
          const rate = data.historical.teamStats.home.stats.points.for
          if (!await section.getByText(rate.perGame.toFixed(1), { exact: true }).count()) throw new Error('Stored rate mismatch')
        } else if (await section.getByText('No earlier regular-season games this season.').count() !== 2) {
          throw new Error('Opening-day prior-season fallback')
        }
        await section.scrollIntoViewIfNeeded()
        await section.screenshot({ path: path.join(__dirname, `step6-stored-${name}-${width}.png`) })
        results.push({ width, check: name, pass: true })
      }
      const sample = data.props.lines.find(line => line.market === 'assists')
      let boardText
      for (const entry of ['board', 'game']) {
        const target = entry === 'board'
          ? `/nba/board?date=${data.game.gameDate}&market=assists` : `/nba/game/${data.game.gameId}`
        await page.goto(`http://127.0.0.1:3001/?stored=${entry}#${target}`)
        await page.getByRole('table', { name: 'Assists props', exact: true }).getByRole('button', { name: sample.playerName, exact: true }).click()
        const section = page.getByRole('region', { name: 'Opponent team context', exact: true })
        await section.waitFor()
        const text = await section.innerText()
        if (entry === 'board') boardText = text
        else if (text !== boardText) throw new Error('Stored-data drawer parity')
        await page.locator('.ant-drawer-content').screenshot({ path: path.join(__dirname, `step6-stored-${entry}-drawer-${width}.png`) })
        await page.keyboard.press('Escape')
        results.push({ width, check: `${entry} stored drawer`, pass: true })
      }
      mode = 'loading'
      await page.goto(`http://127.0.0.1:3001/?state=loading#/nba/game/${data.game.gameId}`)
      await page.getByText('Loading game...', { exact: true }).waitFor()
      mode = 'normal'
      release()
      await page.getByRole('region', { name: 'Team stats', exact: true }).waitFor()
      results.push({ width, check: 'loading then success', pass: true })
      mode = 'error'
      await page.goto(`http://127.0.0.1:3001/?state=error#/nba/game/${data.game.gameId}`)
      await page.getByText('Failed to load data', { exact: true }).waitFor()
      await page.screenshot({ path: path.join(__dirname, `step6-error-${width}.png`), fullPage: true })
      mode = 'normal'
      await page.getByRole('button', { name: 'Retry', exact: true }).click()
      await page.getByRole('region', { name: 'Team stats', exact: true }).waitFor()
      results.push({ width, check: '503 then manual retry success', pass: true })
      if (runtimeErrors.length) throw new Error(JSON.stringify(runtimeErrors))
      await context.close()
    }
    console.log(JSON.stringify(results, null, 2))
  } finally { await browser.close() }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
