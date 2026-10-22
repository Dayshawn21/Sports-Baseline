const {chromium}=require(process.env.PLAYWRIGHT_MODULE)
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict')
async function main(){
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true})
 const report={real:[],controlled:[],errors:[]}
 try{
  const ctx=await browser.newContext({reducedMotion:'reduce'}),page=await ctx.newPage()
  page.on('pageerror',e=>report.errors.push(e.message))
  const data=await(await page.request.get('http://localhost:3001/api/nfl/players/40440')).json()
  assert.equal(data.gameLog[0].fgMade,2);assert.equal(data.gameLog[0].patMade,2);assert.equal(data.gameLog[0].kickingPoints,8)
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000})
   await page.goto('http://localhost:3001/#/nfl/game/94')
   const details=page.locator('details[aria-label="Other markets"]')
   await details.locator('summary').click()
   const link=details.getByRole('table',{name:'Kicking points lines',exact:true}).getByRole('link',{name:'Andy Borregales'})
   await link.click()
   const log=page.getByRole('region',{name:'Game log',exact:true})
   await log.getByRole('columnheader',{name:'Kicking pts',exact:true}).waitFor()
   assert.deepEqual(await log.locator('thead th').allTextContents(),['Week','Opp','Result','FG','PAT','Kicking pts'])
   assert.equal(await log.locator('.is-selected-market').textContent(),'Kicking pts')
   assert.equal(await page.getByRole('region',{name:'Usage by week'}).count(),0)
   assert.equal(await page.getByText('Snap share',{exact:true}).count(),0)
   assert.deepEqual((await log.locator('tbody tr').first().locator('td').allTextContents()).slice(-3),['2','2','8'])
   assert.ok(page.url().includes('market=kicking_points'))
   await page.evaluate(()=>scrollTo(0,0))
   await page.screenshot({path:path.join(__dirname,`specialist-${width}-kicker.png`),fullPage:true})
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
   report.real.push({width,kickerCounts:true,offensiveSectionsHidden:true,marketLink:true,noOverflow:true})
  }
  const punter={...data,playerId:999999,name:'Punter fixture',position:'P',gameLog:data.gameLog.slice(0,2).map((g,i)=>({...g,punts:i===0?4:null}))}
  await page.route('**/api/nfl/players/999999',r=>r.fulfill({json:punter}))
  for(const width of [1440,390]){
   await page.setViewportSize({width,height:1000})
   await page.goto('http://localhost:3001/#/nfl/player/999999?market=punts#game-log')
   const log=page.getByRole('region',{name:'Game log',exact:true})
   await log.getByRole('columnheader',{name:'Punts',exact:true}).waitFor()
   assert.deepEqual(await log.locator('thead th').allTextContents(),['Week','Opp','Result','Punts'])
   assert.equal(await log.locator('.is-selected-market').textContent(),'Punts')
   assert.deepEqual(await log.locator('tbody tr td:last-child').allTextContents(),['4','--'])
   assert.equal(await page.getByRole('region',{name:'Usage by week'}).count(),0)
   await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(__dirname,`specialist-${width}-punter.png`),fullPage:true})
   assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth))
   report.controlled.push({width,punterColumns:true,missingIsUnavailable:true,noOverflow:true})
  }
  await page.goto('http://localhost:3001/#/nfl/player/5283')
  await page.getByRole('region',{name:'Usage by week'}).waitFor()
  await page.getByRole('columnheader',{name:'PP fantasy',exact:true}).waitFor()
  report.offenseRetained=true
  assert.deepEqual(report.errors,[])
 }finally{await browser.close();fs.writeFileSync(path.join(__dirname,'specialist-browser.json'),JSON.stringify(report,null,2))}
 console.log(JSON.stringify(report))
}
main().catch(e=>{console.error(e);process.exitCode=1})
