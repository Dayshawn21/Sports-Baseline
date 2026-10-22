// Run from the repo root with PLAYWRIGHT_MODULE pointing to an existing install.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')

const out = __dirname
const base = 'http://localhost:3001'
const report = { real: {}, controlled: {}, errors: [], existingResourceErrors: [] }

async function captureSection(page, locator, filename) {
  await page.evaluate(() => window.scrollTo(0, 0))
  const box = await locator.boundingBox()
  assert.ok(box && box.width > 0 && box.height > 0)
  await page.screenshot({ path: path.join(out, filename), fullPage: true, clip: box })
}

async function main() {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, timeout: 10000 })
  try {
    const cache = new Map()
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' })
    const page = await context.newPage()
    const requests = []
    page.on('pageerror', error => report.errors.push(error.message))
    page.on('console', msg => {
      if (msg.type() !== 'error') return
      const entry = { message: msg.text(), location: msg.location().url }
      if (entry.location === `${base}/favicon.ico`) report.existingResourceErrors.push(entry)
      else report.errors.push(entry)
    })
    page.on('request', request => { if (request.url().includes('/api/')) requests.push(request.url()) })
    page.on('response', async response => {
      if (response.url().includes('/api/') && response.ok()) {
        const body = await response.body().catch(() => null)
        if (body) cache.set(response.url(), { status: response.status(), contentType: response.headers()['content-type'], body })
      }
    })
    await page.goto(`${base}/#/nfl/game/94`)
    await page.locator('.nfl-context-usage > summary').waitFor()
    await page.getByRole('heading', { name: 'Team stats', exact: true }).waitFor()
    const response = await page.request.get(`${base}/api/nfl/games/94/context`)
    assert.equal(response.status(), 200)
    const data = await response.json()
    const section = page.locator('.nfl-context')
    const allowed = section.getByRole('region', { name: 'Position production allowed', exact: true })
    const keys = ['rbCarries', 'rbRushYards', 'rbReceptions', 'rbRecYards', 'wrReceptions', 'wrRecYards', 'teReceptions', 'teRecYards']
    for (let i = 0; i < keys.length; i++) {
      for (const [j, team] of [data.matchupContext.away, data.matchupContext.home].entries()) {
        const text = await allowed.locator('tbody tr').nth(i).locator('td').nth(j).innerText()
        const metric = team.allowed[keys[i]]
        assert.ok(text.startsWith(metric.value === null ? '-' : metric.value.toFixed(1)))
        if (metric.rank !== null) assert.ok(text.includes(`Rank ${metric.rank} / ${metric.rankedTeams}`))
        if (metric.eligibleGames > 0) assert.ok(text.includes(`${metric.observedGames} / ${metric.eligibleGames} games`))
      }
    }
    assert.equal(requests.filter(url => /\/games\/94\/context$/.test(url)).length, 1)
    await page.screenshot({ path: path.join(out, 'step-3-desktop.png'), fullPage: true })
    await captureSection(page, section, 'step-3-desktop-context.png')
    const summary = page.locator('.nfl-context-usage > summary')
    await summary.focus()
    await page.keyboard.press('Enter')
    assert.equal(await page.locator('.nfl-context-usage').getAttribute('open'), '')
    const players = await page.locator('.nfl-context-usage tbody th a').evaluateAll(links => links.map(link => ({ name: link.textContent, href: link.getAttribute('href') })))
    assert.deepEqual(players.map(player => player.name), data.players.map(player => player.name))
    for (let i = 0; i < players.length; i++) assert.ok(players[i].href.endsWith(`/nfl/player/${data.players[i].playerId}`))
    await summary.evaluate(el => el.scrollIntoView({ block: 'start' }))
    await page.evaluate(() => window.scrollBy(0, -80))
    await page.screenshot({ path: path.join(out, 'step-3-desktop-usage.png') })
    report.real = { gameId: data.gameId, season: data.season, week: data.week, players: players.length, allowedValuesMatch: 16, gameContextRequests: 1, keyboardDisclosure: true, allPlayerLinksMatch: true }
    await summary.press('Enter')
    await page.setViewportSize({ width: 390, height: 844 })
    await page.evaluate(() => window.scrollTo(0, 0))
    await page.screenshot({ path: path.join(out, 'step-3-mobile.png'), fullPage: true })
    await captureSection(page, section, 'step-3-mobile-context.png')
    await summary.click()
    await summary.evaluate(el => el.scrollIntoView({ block: 'start' }))
    await page.evaluate(() => window.scrollBy(0, -80))
    await page.screenshot({ path: path.join(out, 'step-3-mobile-usage.png') })
    const geometry = await section.evaluate(el => ({
      viewport: window.innerWidth, document: document.documentElement.scrollWidth,
      minFont: Math.min(...[...el.querySelectorAll('th, td, span, small, p, summary')].map(node => parseFloat(getComputedStyle(node).fontSize))),
      numberColors: [...new Set([...el.querySelectorAll('.nfl-context-metric__value')].map(node => getComputedStyle(node).color))],
    }))
    assert.ok(geometry.document <= geometry.viewport)
    assert.ok(geometry.minFont >= 11)
    assert.deepEqual(geometry.numberColors, ['rgb(245, 245, 247)'])
    report.real.mobile = geometry
    await context.close()

    async function fixturePage(payload, options = {}) {
      const ctx = await browser.newContext({ viewport: { width: 390, height: 844 } })
      const p = await ctx.newPage()
      await p.route('**/api/**', async route => {
        const cached = cache.get(route.request().url())
        if (cached) await route.fulfill(cached)
        else await route.continue()
      })
      let attempts = 0
      let release
      const wait = new Promise(resolve => { release = resolve })
      await p.route('**/api/nfl/games/94/context', async route => {
        attempts++
        if (options.loading) await wait
        if (options.error && attempts === 1) return route.fulfill({ status: 503, json: { detail: 'Controlled context failure' } })
        await route.fulfill({ json: payload })
      })
      await p.goto(`${base}/#/nfl/game/94`)
      return { p, ctx, release, attempts: () => attempts }
    }

    const loading = await fixturePage(data, { loading: true })
    await loading.p.getByText('Loading matchup and usage context...', { exact: true }).waitFor()
    await captureSection(loading.p, loading.p.locator('.nfl-context'), 'step-3-loading.png')
    loading.release()
    await loading.p.locator('.nfl-context-usage > summary').waitFor()
    report.controlled.loading = true
    await loading.ctx.close()

    const failed = await fixturePage(data, { error: true })
    await failed.p.locator('.nfl-context').getByRole('button', { name: 'Retry', exact: true }).waitFor()
    assert.equal(failed.attempts(), 1)
    await captureSection(failed.p, failed.p.locator('.nfl-context'), 'step-3-error.png')
    await failed.p.locator('.nfl-context').getByRole('button', { name: 'Retry', exact: true }).focus()
    await failed.p.keyboard.press('Enter')
    await failed.p.locator('.nfl-context-usage > summary').waitFor()
    assert.equal(failed.attempts(), 2)
    assert.equal(await failed.p.locator('.nfl-context').getByRole('button', { name: 'Retry', exact: true }).count(), 0)
    report.controlled.manualRetry = true
    await failed.ctx.close()

    const emptyMetric = { value: null, observedGames: 0, eligibleGames: 0, windowStart: null, windowEnd: null, reason: 'no_history', rank: null, rankedTeams: 0 }
    const empty = structuredClone(data)
    empty.players = []
    for (const side of ['away', 'home']) for (const key of keys) empty.matchupContext[side].allowed[key] = emptyMetric
    const missing = await fixturePage(empty)
    await missing.p.getByText(/No unambiguous QB, RB, WR or TE roster memberships/).waitFor()
    assert.equal(await missing.p.locator('.nfl-context').getByText('No pre-week games', { exact: true }).count(), 16)
    await captureSection(missing.p, missing.p.locator('.nfl-context'), 'step-3-unavailable-empty.png')
    report.controlled.emptyRosterAndNoHistory = true
    await missing.ctx.close()

    const zero = structuredClone(data)
    const player = structuredClone(data.players.find(player => player.position === 'WR'))
    player.seasonUsage.targetShare = { ...emptyMetric, value: 0, observedGames: 1, eligibleGames: 2, windowStart: '2026-10-18', windowEnd: '2026-10-18', reason: null }
    player.seasonUsage.carryShare = { ...emptyMetric, eligibleGames: 2, reason: 'zero_denominator' }
    zero.players = [player]
    const zeros = await fixturePage(zero)
    await zeros.p.locator('.nfl-context-usage > summary').click()
    const usage = zeros.p.locator('.nfl-context-usage')
    await usage.getByText('0.0%', { exact: true }).waitFor()
    await usage.getByText('Team total is zero', { exact: true }).waitFor()
    await usage.getByText('1 / 2 games (50%)', { exact: true }).waitFor()
    await captureSection(zeros.p, usage, 'step-3-zero-partial.png')
    report.controlled.zeroAndPartialCoverage = true
    await zeros.ctx.close()
    assert.deepEqual(report.errors, [])
    fs.writeFileSync(path.join(out, 'step-3-browser.json'), JSON.stringify(report, null, 2) + '\n')
    console.log(JSON.stringify(report))
  } finally { await browser.close() }
}

main().catch(error => { console.error(error.stack); process.exitCode = 1 })
