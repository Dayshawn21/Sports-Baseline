import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import PageHead from '~/components/shared/PageHead'
import { SPORTS } from '~/utils/sportNav'
import { SPORT_STATUS } from './howItWorksContent'
import './nfl-model.css'
import './how-it-works.css'

function Section({ title, children }: { title: string, children: ReactNode }) {
  return <section aria-label={title}>
    <h2 className="nfl-model-heading">{title}</h2>
    {children}
  </section>
}

const STATUS_ROWS = [
  ['Model today', 'model'],
  ['Shown as a pick', 'picks'],
  ['Reference only', 'reference'],
  ['Status', 'status'],
] as const

function SportCards() {
  return <div className="hiw-sports">
    {SPORTS.map(sport => {
      const status = SPORT_STATUS[sport.code]
      return <article key={sport.code} className="nfl-model-card hiw-sport" aria-label={sport.label}>
        <h3 className="hiw-sport__name">{sport.label}</h3>
        <dl className="hiw-sport__rows">
          {STATUS_ROWS.map(([label, field]) => <div key={field}>
            <dt>{label}</dt>
            <dd>{status[field]}</dd>
          </div>)}
        </dl>
        <nav className="hiw-sport__links" aria-label={`${sport.label} pages`}>
          <Link to={sport.views.slate}>Slate</Link>
          <Link to={sport.views.model}>Track record</Link>
        </nav>
      </article>
    })}
  </div>
}

const LEGEND = [
  {
    tone: 'is-positive',
    name: 'Green',
    meaning: 'On a slate, the positive expected value of a tennis pick. On a track record page, a result more than 2 standard errors better than its baseline.',
  },
  {
    tone: 'is-negative',
    name: 'Red',
    meaning: 'On a track record page, a result more than 2 standard errors worse than its baseline.',
  },
  {
    tone: 'is-neutral',
    name: 'Gray',
    meaning: 'Everything else. Gray means reference, not a recommendation. NFL and NBA numbers are always gray until a check passes.',
  },
] as const

function ColorLegend() {
  return <dl className="hiw-legend" aria-label="Color legend">
    {LEGEND.map(entry => <div key={entry.name} className="hiw-legend__row">
      <dt><span className={`hiw-legend__swatch ${entry.tone}`} aria-hidden="true" />{entry.name}</dt>
      <dd>{entry.meaning}</dd>
    </div>)}
  </dl>
}

export default function HowItWorksPage() {
  return <div className="page-shell"><div className="page-container is-wide">
    <PageHead title="How it works" />

    <Section title="What it is">
      <div className="nfl-model-card hiw-card">
        <p>
          A sports betting research tool built for one person. It gathers schedules, stats, odds and
          PrizePicks prop lines on a schedule, runs models, compares them with the market, and shows
          where they disagree.
        </p>
        <p>It does not place bets and has no user accounts.</p>
      </div>
    </Section>

    <Section title="How data flows">
      <div className="nfl-model-card hiw-card">
        <ol className="hiw-flow">
          <li>Scheduled jobs (GitHub Actions) collect schedules, box scores, sportsbook odds and prop lines for tennis, the NFL and the NBA.</li>
          <li>Each provider's names are matched to the same players, teams and games.</li>
          <li>Models produce win probabilities and stat projections. Sportsbook odds are de-vigged (the book's margin removed) into a fair market probability.</li>
          <li>Predictions are stored before each event starts, then graded against the result once it ends.</li>
          <li>The web app shows the slate, each game or match, and each model's track record.</li>
        </ol>
      </div>
    </Section>

    <Section title="What each sport shows">
      <SportCards />
    </Section>

    <Section title="How a model earns a pick">
      <div className="nfl-model-card hiw-card">
        <ul className="hiw-rules">
          <li>Every new signal is tested on games it was not fitted on, against a rule written down before the test ran. Most signals tried so far failed and were left out.</li>
          <li>Forward checks grade predictions frozen before each event, so a result can never leak into its own grade.</li>
          <li>The market is hard to beat. Where the evidence says it wins, the app says so and turns the pick off.</li>
        </ul>
        <h3 className="hiw-legend__title">Color legend</h3>
        <ColorLegend />
      </div>
    </Section>
  </div></div>
}
