// Local read-only browser verification; use an already installed Playwright module.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const out = __dirname
const base = 'http://localhost:3001'
const report = { real: {}, controlled: {}, errors: [], resourceErrors: [] }

async function settled(page) {
  await page.locator('.ant-drawer-content-wrapper:visible').last().evaluate(async el => {
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))
    await Promise.all(el.getAnimations().map(animation => animation.finished.catch(() => {})))
  })
  await page.waitForFunction(() => {
    const el = [...document.querySelectorAll('.ant-drawer-content-wrapper')].find(el => el.getBoundingClientRect().width > 0)
    return el && !/motion-(enter|appear)/.test(el.className) && Math.abs(el.getBoundingClientRect().right - innerWidth) < 1
  })
}

async function capture(page, name) {
  const section = page.locator('.ant-drawer-body .nfl-evidence-context')
  await section.evaluate(el => {
    const body = el.closest('.ant-drawer-body')
    body.scrollTop += el.getBoundingClientRect().top - body.getBoundingClientRect().top - 8
  })
  await page.screenshot({ path: path.join(out, `step-4-${name}-usage.png`) })
  const opponent = section.locator('.nfl-evidence-context__opponent')
  if (await opponent.count()) {
    await opponent.evaluate(el => el.scrollIntoView({ block: 'end' }))
    await page.screenshot({ path: path.join(out, `step-4-${name}-opponent.png`) })
  }
}

async function closeAndRestore(page, trigger) {
  await page.keyboard.press('Escape')
  await page.locator('.ant-drawer-body .nfl-prop-detail').waitFor({ state: 'hidden' })
  await page.waitForFunction(el => el === document.activeElement, await trigger.elementHandle(), { timeout: 1500 }).catch(async () => {
    throw new Error('Focus was not restored: ' + JSON.stringify(await trigger.evaluate(el => ({ connected: el.isConnected, active: document.activeElement.outerHTML.slice(0, 250) }))))
  })
}

async function main() {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, timeout: 10000 })
  try {
    const cache = new Map()
    const ctx = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
    const page = await ctx.newPage()
    const contextRequests = []
    page.on('pageerror', error => report.errors.push(error.message))
    page.on('console', msg => { if (msg.type() === 'error') report.resourceErrors.push({ message: msg.text(), url: msg.location().url }) })
    page.on('request', request => { if (/\/games\/\d+\/context$/.test(request.url())) contextRequests.push(request.url()) })
    page.on('response', async response => {
      if (response.url().includes('/api/') && response.ok()) {
        const body = await response.body().catch(() => null)
        if (body) cache.set(response.url(), { status: response.status(), contentType: response.headers()['content-type'], body })
      }
    })
    await page.goto(`${base}/#/nfl/game/94`)
    const gameButton = page.locator('section[aria-label="Receiving yards lines"] button.prop-table__open').first()
    await gameButton.waitFor()
    const playerName = await gameButton.innerText()
    await page.locator('.nfl-context-usage > summary').waitFor()
    const data = await (await page.request.get(`${base}/api/nfl/games/94/context`)).json()
    const player = data.players.find(player => player.name === playerName)
    assert.ok(player)
    await gameButton.focus()
    await page.keyboard.press('Enter')
    await settled(page)
    const section = page.locator('.ant-drawer-body .nfl-evidence-context')
    await section.getByRole('table').first().waitFor()
    const usageKeys = ['targets', 'targetShare', 'carries', 'carryShare', 'avgGameSnapShare']
    for (const [i, key] of usageKeys.entries()) {
      for (const [j, window] of [player.recentUsage, player.seasonUsage].entries()) {
        const metric = window[key]
        const expected = metric.value === null ? '-' : key === 'targets' || key === 'carries' ? metric.value.toFixed(1) : `${(metric.value * 100).toFixed(1)}%`
        const cell = await section.getByRole('table').first().locator('tbody tr').nth(i).locator('td').nth(j).innerText()
        assert.ok(cell.startsWith(expected))
        if (metric.eligibleGames > 0) assert.ok(cell.includes(`${metric.observedGames} / ${metric.eligibleGames} games`))
      }
    }
    const opponent = player.team === data.matchupContext.away.team ? data.matchupContext.home : data.matchupContext.away
    const allowedKeys = [`${player.position.toLowerCase()}Receptions`, `${player.position.toLowerCase()}RecYards`]
    for (let i = 0; i < 2; i++) {
      const metric = opponent.allowed[allowedKeys[i]]
      const text = await section.locator('.nfl-evidence-context__opponent tbody tr').nth(i).locator('td').innerText()
      assert.ok(text.startsWith(metric.value === null ? '-' : metric.value.toFixed(1)))
      if (metric.rank !== null) assert.ok(text.includes(`Rank ${metric.rank} / ${metric.rankedTeams}`))
    }
    const gameText = await section.innerText()
    assert.equal(contextRequests.length, 1)
    await capture(page, 'desktop')
    await closeAndRestore(page, gameButton)
    await page.locator('a[href="#/nfl/board"]:visible').first().click()
    await page.getByRole('navigation', { name: 'Prop categories' }).getByRole('button', { name: /^Receiving yards/ }).click()
    const boardButton = page.getByRole('button', { name: playerName, exact: true }).first()
    console.log('Shared player:', playerName, 'board line:', await boardButton.getAttribute('data-line-id'))
    await boardButton.click()
    await settled(page)
    await section.getByRole('table').first().waitFor()
    assert.equal(await section.innerText(), gameText)
    assert.equal(contextRequests.length, 1)
    await closeAndRestore(page, boardButton)
    const sameGameNames = data.players.filter(player => player.name !== playerName).map(player => player.name)
    const visibleNames = await page.locator('button.prop-table__open').allTextContents()
    const otherName = visibleNames.find(name => sameGameNames.includes(name))
    assert.ok(otherName)
    const otherButton = page.getByRole('button', { name: otherName, exact: true }).first()
    await otherButton.click()
    await settled(page)
    await page.locator(`aside[aria-label="Evidence for ${otherName}"]`).waitFor()
    await section.getByRole('table').first().waitFor()
    assert.equal(contextRequests.length, 1)
    await closeAndRestore(page, otherButton)
    await page.setViewportSize({ width: 390, height: 844 })
    const mobileButton = page.getByRole('button', { name: playerName, exact: true }).first()
    await mobileButton.click()
    await settled(page)
    await section.getByRole('table').first().waitFor()
    assert.equal(await section.innerText(), gameText)
    await capture(page, 'mobile')
    const geometry = await section.evaluate(el => ({
      width: el.clientWidth, scrollWidth: el.scrollWidth,
      minFont: Math.min(...[...el.querySelectorAll('th, td, span, small, p')].map(node => parseFloat(getComputedStyle(node).fontSize))),
      colors: [...new Set([...el.querySelectorAll('.nfl-context-metric__value')].map(node => getComputedStyle(node).color))],
    }))
    assert.ok(geometry.scrollWidth <= geometry.width)
    assert.ok(geometry.minFont >= 11)
    assert.deepEqual(geometry.colors, ['rgb(245, 245, 247)'])
    await closeAndRestore(page, mobileButton)
    report.real = { playerName, gameBoardParity: true, rawUsageCellsMatch: 10, rawOpponentMeasuresMatch: 2,
      oneSharedGameRequestAcrossPlayersAndPages: true, keyboardCloseAndFocusRestoration: true, mobile: geometry,
      storedSlateHasRecTargets: await page.getByRole('navigation', { name: 'Prop categories' }).getByRole('button', { name: /^Rec targets/i }).count() > 0 }
    await page.getByRole('navigation', { name: 'Prop categories' }).getByRole('button', { name: /^Rushing yards/ }).click()
    const rbButton = page.getByRole('button', { name: "D'Andre Swift", exact: true }).first()
    await rbButton.click()
    await settled(page)
    await section.locator('.nfl-evidence-context__opponent').waitFor()
    assert.deepEqual(await section.locator('.nfl-evidence-context__opponent tbody th').allTextContents(), ['RB carries', 'RB rush yards'])
    await closeAndRestore(page, rbButton)
    report.real.rbRushingMeasures = true
    await page.getByRole('navigation', { name: 'Prop categories' }).getByRole('button', { name: /^Passing yards/ }).click()
    const qbButton = page.locator('button.prop-table__open').first()
    await qbButton.click()
    await settled(page)
    await section.getByRole('table').first().waitFor()
    assert.equal(await section.getByRole('rowheader', { name: 'Targets / game', exact: true }).count(), 0)
    assert.equal(await section.locator('.nfl-evidence-context__opponent').count(), 0)
    await closeAndRestore(page, qbButton)
    report.real.unsupportedQbReceivingMeasuresOmitted = true
    await page.evaluate(() => { location.hash = '/nfl/game/94' })
    await page.getByRole('heading', { name: 'NE @ CHI', exact: true }).waitFor()
    await page.getByRole('button', { name: 'Drake Maye', exact: true }).first().click()
    await settled(page)
    await section.getByRole('table').first().waitFor()
    await page.evaluate(() => { location.hash = '/nfl/game/95' })
    await page.getByRole('heading', { name: / @ /, level: 1 }).waitFor()
    await page.locator('.ant-drawer-body .nfl-prop-detail').waitFor({ state: 'hidden' })
    report.real.gameNavigationClosesOldSelection = true
    await ctx.close()

    async function fixture(options = {}) {
      const context = await browser.newContext({ viewport: { width: 390, height: 844 }, reducedMotion: 'reduce' })
      const p = await context.newPage()
      p.on('pageerror', error => report.errors.push(error.message))
      await p.route('**/api/**', async route => {
        const url = route.request().url()
        if (options.weekReset && /\/nfl\/(slate|line-only-props)\?/.test(url) && url.includes('week=8')) {
          const template = cache.get(url.replace('week=8', 'week=7'))
          const emptyWeek = template ? JSON.parse(template.body.toString()) : {}
          return route.fulfill({ json: { ...emptyWeek, season: 2026, week: 8, count: 0, games: [] } })
        }
        const item = cache.get(url)
        if (item && options.targets && route.request().url().includes('/nfl/slate?')) {
          const slate = JSON.parse(item.body.toString())
          const game = slate.games.find(game => game.gameId === 94)
          const source = game.lines.find(row => row.playerName === playerName && row.market === 'receiving_yards')
          game.lines.push({ ...source, lineId: 999991, market: 'receiving_targets', line: 6.5, projection: 7,
            edge: 0.5, oddsType: 'standard', qualityFlags: [], projectionModelVersion: 'nfl-targets-v1',
            pOver: null, pUnder: null, overProbabilityVersion: null })
          await route.fulfill({ ...item, body: JSON.stringify(slate) })
        } else if (item) await route.fulfill(item)
        else await route.continue()
      })
      let attempts = 0
      let release
      const pending = new Promise(resolve => { release = resolve })
      await p.route('**/api/nfl/games/94/context', async route => {
        attempts++
        if (options.loading) await pending
        if (options.error && attempts === 1) return route.fulfill({ status: 503, json: { detail: 'Controlled context failure' } })
        return route.fulfill({ json: options.missing ? { ...data, players: [] } : data })
      })
      await p.goto(`${base}/#/nfl/board`)
      await p.getByRole('navigation', { name: 'Prop categories' }).getByRole('button', { name: options.targets ? /^Rec targets/i : /^Receiving yards/ }).click()
      const trigger = p.getByRole('button', { name: playerName, exact: true }).first()
      await trigger.waitFor()
      assert.equal(attempts, 0)
      await trigger.click()
      await settled(p)
      return { p, context, release, attempts: () => attempts }
    }
    const loading = await fixture({ loading: true })
    const loadingSection = loading.p.locator('.nfl-evidence-context')
    await loadingSection.getByText('Loading historical context...', { exact: true }).waitFor()
    assert.equal(await loading.p.locator('.nfl-prop-detail__projection strong').count(), 1)
    assert.equal(await loadingSection.locator('tbody tr').count(), 0)
    await capture(loading.p, 'loading')
    loading.release()
    await loadingSection.getByRole('table').first().waitFor()
    await loading.context.close()
    const error = await fixture({ error: true })
    const errorSection = error.p.locator('.nfl-evidence-context')
    await errorSection.getByRole('button', { name: 'Retry', exact: true }).waitFor()
    assert.equal(error.attempts(), 1)
    assert.equal(await error.p.locator('.nfl-prop-detail__projection strong').count(), 1)
    await capture(error.p, 'error')
    await errorSection.getByRole('button', { name: 'Retry', exact: true }).click()
    await errorSection.getByRole('table').first().waitFor()
    assert.equal(error.attempts(), 2)
    await error.context.close()
    const missing = await fixture({ missing: true })
    await missing.p.getByText(`No unambiguous current-week roster context is stored for ${playerName} in this game.`, { exact: true }).waitFor()
    assert.equal(await missing.p.locator('.nfl-evidence-context tbody tr').count(), 0)
    await capture(missing.p, 'missing-roster')
    await missing.context.close()
    const targets = await fixture({ targets: true })
    const targetsSection = targets.p.locator('.nfl-evidence-context')
    await targetsSection.getByText('Rec Targets uses receiving context:', { exact: false }).waitFor()
    assert.equal(await targetsSection.locator('.nfl-evidence-context__opponent tbody tr').count(), 2)
    assert.equal(await targets.p.locator('.nfl-prop-detail__projection > span').innerText(), 'Rec targets reference')
    await capture(targets.p, 'targets-fixture')
    await targets.context.close()
    const weekReset = await fixture({ weekReset: true })
    await weekReset.p.locator('.nfl-evidence-context table').first().waitFor()
    const original = weekReset.p.getByRole('button', { name: playerName, exact: true }).first()
    await closeAndRestore(weekReset.p, original)
    await weekReset.p.evaluate(() => window.scrollTo(0, 0))
    await weekReset.p.getByRole('combobox', { name: 'Week', exact: true }).focus()
    await weekReset.p.getByRole('combobox', { name: 'Week', exact: true }).press('ArrowDown')
    await weekReset.p.locator('.ant-select-dropdown:visible [title="Week 8"]').click()
    await weekReset.p.getByText('2026 · Week 8', { exact: true }).waitFor()
    assert.equal(await weekReset.p.locator('.nfl-evidence-context').count(), 0)
    await weekReset.p.getByRole('combobox', { name: 'Week', exact: true }).focus()
    await weekReset.p.getByRole('combobox', { name: 'Week', exact: true }).press('ArrowDown')
    await weekReset.p.locator('.ant-select-dropdown:visible [title="Week 7"]').click()
    await weekReset.p.getByRole('navigation', { name: 'Prop categories' }).getByRole('button', { name: /^Receiving yards/ }).click()
    await original.waitFor()
    assert.equal(await weekReset.p.locator('.ant-drawer-open').count(), 0)
    assert.equal(weekReset.attempts(), 1)
    await weekReset.context.close()
    report.controlled = { noContextFetchUntilDrawerSelected: true, loadingContainsNoStaleMetrics: true, errorIsolatedFromProjection: true, manualRetry: true, missingRosterContainsNoInventedZero: true, recTargetsUsesReceivingContextOnly: true, weekAndMarketChangesDoNotResurrectSelection: true }
    assert.deepEqual(report.errors, [])
    assert.ok(report.resourceErrors.every(error => error.url === `${base}/favicon.ico`))
    fs.writeFileSync(path.join(out, 'step-4-browser.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify(report))
  } finally { await browser.close() }
}

main().catch(error => { console.error(error.stack); process.exitCode = 1 })
