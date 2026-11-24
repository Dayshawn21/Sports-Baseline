// Real or Lucky? in the clean Lineform look, built around the animated record-vs-points chart, with a broadcast
// score bug and source strip on top. Every number comes from the props, which are the JSON the
// week01-real-or-lucky notebook writes (render with --props=<that file>); nothing here is typed by hand.
import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from './data';
import {Outro, Pop, RankBar, Scene, Tag, Watermark, body, display, fontCss, mono} from './Video';

type GameRow = {
  week: number;
  opponent: string;
  home: boolean;
  scored: number;
  allowed: number;
  margin: number;
  oneScore: boolean;
};

type LeagueDot = {team: string; nickname: string; actualWins: number; pythagoreanWins: number};

// Every past team that won as many games to start a season as this team has, from the notebook's history read.
type History = {
  firstSeason: number;
  lastSeason: number;
  games: number;
  starts: number;
  pointsBelowPerfect: number;
  morePoints: number;
  restWinPct: number;
  pythagoreanWins: number[];
  fewerPoints: number;
  fewerAllowed: number;
};

// Points allowed against each opponent's median in its other games, with the biggest hold.
type OpponentAdjustment = {allowedBelow: number; bestOpponent: string; bestAllowed: number; bestUsual: number};

// Present only when the kicker scored at least half of the team's points in its last few games.
type Kicker = {kickPoints: number; points: number; games: number; allGames: boolean};

export type RealOrLuckyProps = {
  team: string;
  nickname: string;
  teamName: string;
  season: number;
  throughWeek: number;
  record: string;
  pointsRecord: string;
  actualWins: number;
  pythagoreanWins: number;
  games: GameRow[];
  oneScoreWins: number;
  oneScoreLosses: number;
  turnoverMargin: number;
  turnoverMarginRank: number;
  turnoverCarryover: number;
  offenseEpaRank: number;
  defenseEpaRank: number;
  verdict: string;
  verdictSentence: string;
  source: string;
  chartTitle: string;
  league: LeagueDot[];
  lastUnbeaten: boolean;
  history: History | null;
  opponentAdjustment: OpponentAdjustment | null;
  kicker: Kicker | null;
};

// Made-up numbers so the composition opens in Studio; real renders always pass --props.
export const exampleRealOrLucky: RealOrLuckyProps = {
  team: 'EX',
  nickname: 'Examples',
  teamName: 'Example Team',
  season: 2026,
  throughWeek: 4,
  record: '4-0',
  pointsRecord: '3-1',
  actualWins: 4,
  pythagoreanWins: 2.9,
  games: [
    {week: 1, opponent: 'Sample A', home: true, scored: 24, allowed: 20, margin: 4, oneScore: true},
    {week: 2, opponent: 'Sample B', home: false, scored: 17, allowed: 14, margin: 3, oneScore: true},
    {week: 3, opponent: 'Sample C', home: true, scored: 31, allowed: 10, margin: 21, oneScore: false},
    {week: 4, opponent: 'Sample D', home: false, scored: 20, allowed: 13, margin: 7, oneScore: true},
  ],
  oneScoreWins: 3,
  oneScoreLosses: 0,
  turnoverMargin: 3,
  turnoverMarginRank: 5,
  turnoverCarryover: 0.31,
  offenseEpaRank: 12,
  defenseEpaRank: 6,
  verdict: 'Mostly real, some luck',
  verdictSentence: 'EXAMPLE DATA: made-up numbers for the Studio preview.',
  source: 'EXAMPLE DATA, not real',
  chartTitle: 'The Examples are 4-0, but their points say 3-1',
  league: [
    {team: 'EX', nickname: 'Examples', actualWins: 4, pythagoreanWins: 2.9},
    {team: 'S1', nickname: 'Sample 1', actualWins: 3, pythagoreanWins: 3.1},
    {team: 'S2', nickname: 'Sample 2', actualWins: 2, pythagoreanWins: 1.6},
    {team: 'S3', nickname: 'Sample 3', actualWins: 1, pythagoreanWins: 1.4},
    {team: 'S4', nickname: 'Sample 4', actualWins: 0, pythagoreanWins: 0.7},
  ],
  lastUnbeaten: true,
  history: {
    firstSeason: 2012,
    lastSeason: 2025,
    games: 4,
    starts: 6,
    pointsBelowPerfect: 5,
    morePoints: 2,
    restWinPct: 60,
    pythagoreanWins: [2.6, 2.8, 2.9, 3.1, 3.3, 3.6],
    fewerPoints: 0,
    fewerAllowed: 1,
  },
  opponentAdjustment: {allowedBelow: 8.4, bestOpponent: 'Sample B', bestAllowed: 14, bestUsual: 27.5},
  kicker: {kickPoints: 40, points: 70, games: 5, allGames: false},
};

const ordinal = (n: number) => {
  const tens = n % 100;
  const suffix = tens >= 10 && tens <= 20 ? 'th' : ({1: 'st', 2: 'nd', 3: 'rd'} as Record<number, string>)[n % 10] ?? 'th';
  return `${n}${suffix}`;
};

const signed = (n: number) => (n > 0 ? `+${n}` : `${n}`);

const pointTotals = (p: RealOrLuckyProps) => ({
  scored: p.games.reduce((a, g) => a + g.scored, 0),
  allowed: p.games.reduce((a, g) => a + g.allowed, 0),
});

const carryoverWords = (p: RealOrLuckyProps) =>
  `Turnover margin this early ${p.turnoverCarryover < 0.5 ? 'only loosely' : 'fairly well'} predicts the rest of a season.`;

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

// Scene lengths in frames, read by both each scene's fade and the timeline. They fit the generated voiceover script
// (about 150 words, 52 to 55 seconds spoken); the chart and the verdict get the most time because they carry the answer.
const DUR = {hook: 105, chart: 390, history: 270, close: 240, perPlay: 195, turnovers: 180, verdict: 270, question: 105};

// An unbeaten team's history scene takes over part of the chart's job, so the chart and turnovers give back time to
// it. The video may run past a minute (owner, 2026-10-27); lengthen scenes if the script grows past about 160 words.
const durations = (p: RealOrLuckyProps) => {
  const perPlay = DUR.perPlay + (p.opponentAdjustment ? 30 : 0) + (p.kicker ? 60 : 0);
  return p.history
    ? {...DUR, chart: DUR.chart - 60, history: DUR.history + 30, close: DUR.close - 30, perPlay, turnovers: DUR.turnovers - 30}
    : {...DUR, perPlay};
};

// Scene content stops at x = 930 so the platforms' like/comment/share buttons (the right ~150px) never cover it.
const SAFE_RIGHT = 150;
const CONTENT_W = 1080 - SAFE_RIGHT - 80;

// Barlow Condensed caps run about 0.45em a character, so long nicknames shrink to one line instead of wrapping.
const fitDisplay = (text: string, max: number) => Math.min(max, Math.floor(CONTENT_W / (text.length * 0.45)));

// The feed chart, animated: grid, then the "record matches points" line, then every other team drops in, then the
// team's dot starts on the line where its points put it and rises to its actual record.
const LeagueChart: React.FC<{p: RealOrLuckyProps; at?: number; size?: number}> = ({p, at = 0, size = 880}) => {
  const f = useCurrentFrame() - at;
  const {fps} = useVideoConfig();
  const pad = {l: 90, r: 30, t: 110, b: 100};
  const plot = size - pad.l - pad.r;
  const plotH = size - pad.t - pad.b;
  const top = Math.max(1, Math.ceil(Math.max(...p.league.map((d) => Math.max(d.actualWins, d.pythagoreanWins)))));
  const x = (v: number) => pad.l + (v / top) * plot;
  const y = (v: number) => pad.t + (1 - v / top) * plotH;
  const ticks = Array.from({length: top + 1}, (_, i) => i);
  const others = p.league.filter((d) => d.team !== p.team);
  const draw = interpolate(f, [15, 45], [0, 1], clamp);
  const rise = spring({frame: f - 120, fps, config: {damping: 14}});
  const appear = spring({frame: f - 105, fps, config: {damping: 12}});
  const label = spring({frame: f - 150, fps, config: {damping: 14}});
  const teamY = y(p.pythagoreanWins + (p.actualWins - p.pythagoreanWins) * rise);
  // The label sits above the plot, over the dot, with a straight leader down to it, so it never covers a team and
  // the leader only crosses one that shares the dot's x.
  const labelX = Math.min(Math.max(x(p.pythagoreanWins), pad.l + 160), size - pad.r - 160);
  return (
    <svg width={size} height={size} style={{overflow: 'visible'}}>
      <g opacity={interpolate(f, [0, 15], [0, 1], clamp)}>
        {ticks.map((t) => (
          <g key={t}>
            <line x1={x(0)} x2={x(top)} y1={y(t)} y2={y(t)} stroke={theme.grayLow} strokeWidth={2} />
            <text x={pad.l - 20} y={y(t) + 10} textAnchor="end" fill={theme.text2} style={{...mono, fontSize: 28}}>
              {t}
            </text>
            <text x={x(t)} y={size - pad.b + 44} textAnchor="middle" fill={theme.text2} style={{...mono, fontSize: 28}}>
              {t}
            </text>
          </g>
        ))}
        <text x={pad.l + plot / 2} y={size - 8} textAnchor="middle" fill={theme.text2} style={{...body, fontSize: 30}}>
          Wins their points usually produce
        </text>
        <text transform={`translate(22 ${pad.t + plotH / 2}) rotate(-90)`} textAnchor="middle" fill={theme.text2} style={{...body, fontSize: 30}}>
          Actual wins
        </text>
      </g>
      <line x1={x(0)} y1={y(0)} x2={x(top * draw)} y2={y(top * draw)} stroke={theme.text2} strokeWidth={3} strokeDasharray="12 10" />
      {others.map((d, i) => {
        const s = spring({frame: f - 45 - (i * 60) / Math.max(others.length, 1), fps, config: {damping: 15}});
        return <circle key={d.team} cx={x(d.pythagoreanWins)} cy={y(d.actualWins) - (1 - s) * 120} r={15} fill={theme.gray} opacity={s} />;
      })}
      <line x1={x(p.pythagoreanWins)} x2={x(p.pythagoreanWins)} y1={y(p.pythagoreanWins)} y2={teamY} stroke={theme.accent} strokeWidth={4} strokeDasharray="6 8" opacity={appear} />
      <circle cx={x(p.pythagoreanWins)} cy={teamY} r={24 * appear} fill={theme.accent} />
      <g opacity={label}>
        <line x1={x(p.pythagoreanWins)} y1={pad.t - 10} x2={x(p.pythagoreanWins)} y2={y(p.actualWins) - 28} stroke={theme.accent} strokeWidth={2} />
        <text x={labelX} y={pad.t - 58} textAnchor="middle" fill={theme.accent} style={{...display, fontSize: 52}}>
          {p.nickname}: {p.record}
        </text>
        <text x={labelX} y={pad.t - 20} textAnchor="middle" fill={theme.text} style={{...body, fontSize: 30}}>
          points say {p.pointsRecord}
        </text>
      </g>
    </svg>
  );
};

const MarginChart: React.FC<{p: RealOrLuckyProps; at?: number}> = ({p, at = 0}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const W = CONTENT_W;
  const H = 480;
  // Sized to the margins played, but always tall enough to show the whole one-score band.
  const top = Math.max(8, ...p.games.map((g) => g.margin));
  const bottom = Math.max(8, ...p.games.map((g) => -g.margin));
  const unit = (H - 100) / (top + bottom);
  const mid = 50 + top * unit;
  const slot = W / p.games.length;
  const barW = Math.min(90, slot * 0.6);
  return (
    <svg width={W} height={H} style={{overflow: 'visible'}}>
      <rect x={0} y={mid - 8 * unit} width={W} height={16 * unit} fill={theme.grayLow} />
      <line x1={0} x2={W} y1={mid} y2={mid} stroke={theme.text2} strokeWidth={2} />
      {p.games.map((g, i) => {
        const grow = spring({frame: f - at - i * 6, fps, config: {damping: 18}});
        const h = Math.abs(g.margin) * unit * grow;
        const cx = slot * i + slot / 2;
        const color = g.oneScore ? theme.accent : theme.gray;
        const up = g.margin >= 0;
        return (
          <g key={g.week}>
            <rect x={cx - barW / 2} y={up ? mid - h : mid} width={barW} height={Math.max(h, 2)} fill={color} rx={6} />
            <text x={cx} y={up ? mid - h - 14 : mid + h + 40} textAnchor="middle" fill={color} opacity={grow} style={{...mono, fontSize: 32}}>
              {signed(g.margin)}
            </text>
            <text x={cx} y={H + 40} textAnchor="middle" fill={theme.text2} style={{...mono, fontSize: 26}}>
              W{g.week}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

const Hook: React.FC<{p: RealOrLuckyProps}> = ({p}) => (
  <Scene dur={DUR.hook}>
    <Pop>
      <Tag>Real or lucky? · Week {p.throughWeek}</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: fitDisplay(`The ${p.nickname}`, 190), marginTop: 60}}>
      The {p.nickname}
      <br />
      are <span style={{color: theme.accent}}>{p.record}.</span>
    </Pop>
    {p.lastUnbeaten && (
      <Pop at={24} style={{...display, fontSize: fitDisplay("The NFL's last unbeaten team", 80), color: theme.accent, marginTop: 30}}>
        The NFL's last unbeaten team
      </Pop>
    )}
    <Pop at={40} style={{...display, fontSize: fitDisplay('Are they for real?', 120), marginTop: p.lastUnbeaten ? 60 : 80}}>
      Are they for real?
    </Pop>
  </Scene>
);

// Past perfect starts as gray dots by the wins their points said, stacked where they share a value, with the team
// in blue on top of its column.
const HistoryStrip: React.FC<{p: RealOrLuckyProps; h: History; at?: number}> = ({p, h, at = 0}) => {
  const f = useCurrentFrame() - at;
  const {fps} = useVideoConfig();
  const W = CONTENT_W;
  const base = 230;
  const lo = Math.floor(Math.min(...h.pythagoreanWins, p.pythagoreanWins));
  const x = (v: number) => 30 + ((v - lo) / (h.games - lo)) * (W - 60);
  const ticks = Array.from({length: h.games - lo + 1}, (_, i) => lo + i);
  const stack = new Map<number, number>();
  const level = (v: number) => {
    const key = Math.round(v * 10);
    const n = stack.get(key) ?? 0;
    stack.set(key, n + 1);
    return n;
  };
  const dots = h.pythagoreanWins.map((v) => ({v, row: level(v)}));
  const teamRow = level(p.pythagoreanWins);
  const team = spring({frame: f - 20 - dots.length * 4, fps, config: {damping: 12}});
  const teamY = base - 26 - teamRow * 36;
  // The label clears the tallest stack, with a leader down to the dot, so it never covers a past team.
  const labelY = base - 26 - Math.max(teamRow, ...dots.map((d) => d.row)) * 36 - 64;
  return (
    <svg width={W} height={320} style={{overflow: 'visible'}}>
      <line x1={x(lo)} x2={x(h.games)} y1={base} y2={base} stroke={theme.text2} strokeWidth={2} />
      {ticks.map((v) => (
        <text key={v} x={x(v)} y={base + 44} textAnchor="middle" fill={theme.text2} style={{...mono, fontSize: 28}}>
          {v}
        </text>
      ))}
      <text x={W / 2} y={base + 88} textAnchor="middle" fill={theme.text2} style={{...body, fontSize: 28}}>
        Wins their points said after {h.games} games
      </text>
      {dots.map(({v, row}, i) => {
        const s = spring({frame: f - 10 - i * 4, fps, config: {damping: 15}});
        return <circle key={i} cx={x(v)} cy={base - 26 - row * 36} r={15} fill={theme.gray} opacity={s} transform={`translate(0 ${(1 - s) * -60})`} />;
      })}
      <circle cx={x(p.pythagoreanWins)} cy={teamY} r={22 * team} fill={theme.accent} />
      <g opacity={team}>
        <line x1={x(p.pythagoreanWins)} x2={x(p.pythagoreanWins)} y1={labelY + 10} y2={teamY - 24} stroke={theme.accent} strokeWidth={2} />
        <text x={x(p.pythagoreanWins)} y={labelY} textAnchor="middle" fill={theme.accent} style={{...display, fontSize: 44}}>
          {p.nickname}
        </text>
      </g>
    </svg>
  );
};

const HistoryScene: React.FC<{p: RealOrLuckyProps; h: History}> = ({p, h}) => (
  <Scene dur={durations(p).history}>
    <Pop>
      <Tag>
        Every {h.games}-0 start since {h.firstSeason}
      </Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 150, color: theme.accent, marginTop: 30}}>
      {h.pointsBelowPerfect} of {h.starts}
    </Pop>
    <Pop at={16} style={{...body, fontSize: 40, lineHeight: 1.3, color: theme.text}}>
      had points saying they should have lost at least once.
    </Pop>
    <div style={{marginTop: 30}}>
      <HistoryStrip p={p} h={h} at={40} />
    </div>
    <Pop at={150} style={{...body, fontSize: 38, lineHeight: 1.3, color: theme.text, marginTop: 30}}>
      {h.morePoints === 0 ? 'None' : `Only ${h.morePoints}`} had better points than the {p.nickname}. Together they won{' '}
      {h.restWinPct}% of their remaining games.
    </Pop>
    {h.fewerPoints === 0 && (
      <Pop at={215} style={{...display, fontSize: 56, color: theme.accent, marginTop: 30, lineHeight: 1.1}}>
        Fewest points by a {h.games}-0 team since {h.firstSeason}: {pointTotals(p).scored}
      </Pop>
    )}
  </Scene>
);

const ChartScene: React.FC<{p: RealOrLuckyProps}> = ({p}) => {
  const {scored, allowed} = pointTotals(p);
  return (
    <Scene dur={durations(p).chart}>
      <Pop>
        <Tag>Record vs points</Tag>
      </Pop>
      <Pop at={4} style={{...display, fontSize: 76, marginTop: 30}}>
        {p.chartTitle}
      </Pop>
      <Pop at={10} style={{...body, fontSize: 32, marginTop: 14}}>
        Above the line = record better than points.
      </Pop>
      <div style={{marginTop: 30}}>
        <LeagueChart p={p} at={20} size={700} />
      </div>
      <Pop at={200} style={{...body, fontSize: 36, marginTop: 20, lineHeight: 1.3, color: theme.text}}>
        {scored} scored and {allowed} allowed usually add up to {p.pointsRecord}, not {p.record}.
      </Pop>
    </Scene>
  );
};

const CloseGames: React.FC<{p: RealOrLuckyProps}> = ({p}) => (
  <Scene dur={durations(p).close}>
    <Pop>
      <Tag>Close games</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
      {p.oneScoreWins}-{p.oneScoreLosses} in
      <br />
      <span style={{color: theme.accent}}>one-score games</span>
    </Pop>
    <Pop at={14} style={{...body, fontSize: 32, marginTop: 30, display: 'flex', alignItems: 'center', gap: 16}}>
      <span style={{width: 40, height: 28, background: theme.grayLow, display: 'inline-block'}} />
      Shaded: won or lost by 8 points or fewer
    </Pop>
    <div style={{marginTop: 10}}>
      <MarginChart p={p} at={24} />
    </div>
    <Pop at={90} style={{...body, fontSize: 40, marginTop: 70, lineHeight: 1.3, color: theme.text}}>
      A one-score game can turn on a single bounce, kick or call.
    </Pop>
  </Scene>
);

const PerPlay: React.FC<{p: RealOrLuckyProps}> = ({p}) => (
  <Scene dur={durations(p).perPlay}>
    <Pop>
      <Tag>Per play</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 100, marginTop: p.opponentAdjustment ? 20 : 40}}>
      Offense {ordinal(p.offenseEpaRank)}
      <br />
      <span style={{color: theme.accent}}>Defense {ordinal(p.defenseEpaRank)}</span>
    </Pop>
    <RankBar label="Offense" rank={p.offenseEpaRank} at={30} highlight={p.offenseEpaRank < p.defenseEpaRank} full={CONTENT_W} />
    <RankBar label="Defense" rank={p.defenseEpaRank} at={48} highlight={p.defenseEpaRank <= p.offenseEpaRank} full={CONTENT_W} />
    <Pop at={90} style={{...body, fontSize: 36, marginTop: p.opponentAdjustment ? 20 : 60, lineHeight: 1.3}}>
      {/* With the kicker line in, the rank labels already say "/ 32", so the second sentence gives way. */}
      EPA per play: how much each play helps the score.{p.kicker ? '' : ' Rank 1 is the best of 32.'}
    </Pop>
    {p.kicker && (
      <Pop at={120} style={{...body, fontSize: 36, marginTop: 24, lineHeight: 1.3, color: theme.text}}>
        Their kicker scored <span style={{color: theme.accent}}>{p.kicker.kickPoints}</span> of their{' '}
        {p.kicker.allGames ? '' : 'last '}
        {p.kicker.points} points.
      </Pop>
    )}
    {p.opponentAdjustment && (
      <Pop at={p.kicker ? 190 : 130} style={{...body, fontSize: 36, marginTop: 24, lineHeight: 1.3, color: theme.text}}>
        Opponents score {p.opponentAdjustment.allowedBelow.toFixed(1)} fewer points against them than usual. The{' '}
        {p.opponentAdjustment.bestOpponent} usually score {p.opponentAdjustment.bestUsual} and scored{' '}
        <span style={{color: theme.accent}}>{p.opponentAdjustment.bestAllowed}</span>.
      </Pop>
    )}
  </Scene>
);

const Turnovers: React.FC<{p: RealOrLuckyProps}> = ({p}) => (
  <Scene dur={durations(p).turnovers}>
    <Pop>
      <Tag>Turnovers</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
      Turnover margin
    </Pop>
    <Pop at={24} style={{...mono, fontSize: 220, color: theme.accent, marginTop: 30}}>
      {signed(p.turnoverMargin)}
    </Pop>
    <Pop at={36} style={{...display, fontSize: 70}}>
      {ordinal(p.turnoverMarginRank)} <span style={{color: theme.text2, fontSize: 50}}>in the league</span>
    </Pop>
    <Pop at={70} style={{...body, fontSize: 40, marginTop: 60, lineHeight: 1.3, color: theme.text}}>
      {carryoverWords(p)}
    </Pop>
  </Scene>
);

const Verdict: React.FC<{p: RealOrLuckyProps}> = ({p}) => (
  <Scene dur={DUR.verdict}>
    <Pop>
      <Tag>The verdict</Tag>
    </Pop>
    <Pop at={10} style={{...display, fontSize: 130, color: theme.accent, marginTop: 50}}>
      {p.verdict}
    </Pop>
    <Pop at={40} style={{...body, fontSize: 42, marginTop: 50, lineHeight: 1.3, color: theme.text}}>
      {p.verdictSentence}
    </Pop>
  </Scene>
);

const Question: React.FC = () => (
  <Scene dur={DUR.question}>
    <Pop style={{...display, fontSize: 150, marginTop: 120}}>
      Real
      <br />
      or <span style={{color: theme.accent}}>lucky?</span>
    </Pop>
    <Pop at={20} style={{...body, fontSize: 48, marginTop: 50, color: theme.text}}>
      Tell me below.
    </Pop>
  </Scene>
);

// Broadcast pieces on top of the clean scenes: the score bug sits between the handle and the scene content, and
// the source strip sits just above the area vertical
// platforms cover with captions.
const ScoreBug: React.FC<{p: RealOrLuckyProps}> = ({p}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 16}});
  const cell: React.CSSProperties = {display: 'flex', alignItems: 'center', padding: '0 22px', height: '100%'};
  return (
    <div style={{position: 'absolute', top: 180, left: 80, height: 80, display: 'flex', border: `4px solid ${theme.text}`, transform: `translateY(${(1 - s) * -160}px)`}}>
      <div style={{...cell, gap: 14, background: theme.accent}}>
        <span style={{...display, fontSize: 50, color: '#000'}}>{p.team}</span>
        <span style={{...display, fontSize: 44, color: '#000'}}>{p.record}</span>
      </div>
      <div style={{...cell, ...display, fontSize: 34, color: theme.text, background: '#1a1a20'}}>Week {p.throughWeek}</div>
      <div style={{...cell, ...display, fontSize: 34, color: theme.accent, background: '#000'}}>Real or lucky?</div>
    </div>
  );
};

const SourceStrip: React.FC<{p: RealOrLuckyProps}> = ({p}) => (
  <div style={{position: 'absolute', left: 0, top: 1490, width: 1080, height: 70, background: '#0d0d12', borderTop: `4px solid ${theme.accent}`, display: 'flex', alignItems: 'center'}}>
    <div style={{...display, fontSize: 32, background: theme.accent, color: '#000', padding: '0 22px', height: '100%', display: 'flex', alignItems: 'center'}}>
      Source
    </div>
    <div style={{...body, fontSize: 27, color: theme.text, paddingLeft: 22}}>
      {p.source.replace(/^Source:\s*/, '')}
    </div>
  </div>
);

type SceneList = [number, React.ReactNode][];

const scenes = (p: RealOrLuckyProps): SceneList => {
  const d = durations(p);
  const history: SceneList = p.history ? [[d.history, <HistoryScene p={p} h={p.history} />]] : [];
  return [
    [d.hook, <Hook p={p} />],
    [d.chart, <ChartScene p={p} />],
    ...history,
    [d.close, <CloseGames p={p} />],
    [d.perPlay, <PerPlay p={p} />],
    [d.turnovers, <Turnovers p={p} />],
    [d.verdict, <Verdict p={p} />],
    [d.question, <Question />],
    [90, <Outro />],
  ];
};

const sceneFrames = (list: SceneList) => list.reduce((a, [d]) => a + d, 0);

const Timeline: React.FC<{list: SceneList}> = ({list}) => {
  let from = 0;
  return (
    <>
      {list.map(([dur, el], i) => {
        const seq = (
          <Sequence key={i} from={from} durationInFrames={dur}>
            {el}
          </Sequence>
        );
        from += dur;
        return seq;
      })}
    </>
  );
};

export const realOrLuckyFrames = (p: RealOrLuckyProps = exampleRealOrLucky) => sceneFrames(scenes(p));

export const RealOrLucky: React.FC<RealOrLuckyProps> = (p) => {
  const live = useCurrentFrame() < realOrLuckyFrames(p) - 90;
  return (
    <AbsoluteFill style={{background: theme.bg}}>
      <style>{fontCss}</style>
      <AbsoluteFill style={{width: 1080 - (SAFE_RIGHT - 80)}}>
        <Timeline list={scenes(p)} />
      </AbsoluteFill>
      {live && <Watermark />}
      {live && <ScoreBug p={p} />}
      {live && <SourceStrip p={p} />}
    </AbsoluteFill>
  );
};
