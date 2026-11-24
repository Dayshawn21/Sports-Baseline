import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {data, theme} from './data';
import {preview} from './previewData';
import {DotGrid, Outro, Pop, Ranks, Scene, Tag, Watermark, body, display, fontCss, mono} from './Video';

export const dal = data.teams[0];
const dalResults = preview.results.DAL;
const scored = [20, 37, 31, 34, 16, 13];
const allowed = [28, 20, 34, 30, 24, 23];

// ---------- 1. Hook ----------
const Hook: React.FC = () => (
  <Scene dur={105}>
    <Pop>
      <Tag>Monday Night Football · at Philly</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 210, marginTop: 60}}>
      Dallas
      <br />
      is <span style={{color: theme.accent}}>2-4.</span>
    </Pop>
    <Pop at={36} style={{...display, fontSize: 110, marginTop: 60}}>
      Tonight might decide its season.
    </Pop>
  </Scene>
);

// ---------- 2. Scoring trend line chart ----------
export const Trend: React.FC = () => {
  const f = useCurrentFrame();
  const W = 900;
  const H = 520;
  const pad = {l: 70, r: 30, t: 30, b: 70};
  const max = 40;
  const x = (i: number) => pad.l + 50 + (i * (W - pad.l - pad.r - 80)) / (scored.length - 1);
  const y = (v: number) => pad.t + (1 - v / max) * (H - pad.t - pad.b);
  const path = (vals: number[]) => vals.map((v, i) => `${i ? 'L' : 'M'}${x(i)},${y(v)}`).join(' ');
  const draw = interpolate(f, [25, 85], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const len = 2000;
  return (
    <Scene dur={195}>
      <Pop>
        <Tag>Points per game</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        The offense
        <br />
        <span style={{color: theme.accent}}>went cold</span>
      </Pop>
      <svg width={W} height={H} style={{marginTop: 40, overflow: 'visible'}}>
        {[0, 10, 20, 30, 40].map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={W - pad.r} y1={y(v)} y2={y(v)} stroke={theme.grayLow} strokeWidth={2} />
            <text x={pad.l - 16} y={y(v) + 10} textAnchor="end" fill={theme.text2} style={{...mono, fontSize: 28}}>
              {v}
            </text>
          </g>
        ))}
        {scored.map((_, i) => (
          <text key={i} x={x(i)} y={H - 20} textAnchor="middle" fill={theme.text2} style={{...mono, fontSize: 28}}>
            G{i + 1}
          </text>
        ))}
        <path d={path(allowed)} fill="none" stroke={theme.gray} strokeWidth={6} strokeDasharray={len} strokeDashoffset={len * (1 - draw)} />
        <path d={path(scored)} fill="none" stroke={theme.accent} strokeWidth={9} strokeDasharray={len} strokeDashoffset={len * (1 - draw)} strokeLinejoin="round" />
        {scored.map((v, i) => {
          const show = interpolate(draw, [i / scored.length, (i + 1) / scored.length], [0, 1], {
            extrapolateLeft: 'clamp',
            extrapolateRight: 'clamp',
          });
          return (
            <g key={i} opacity={show}>
              <circle cx={x(i)} cy={y(v)} r={14} fill={theme.accent} />
              <text x={x(i)} y={y(v) - 26} textAnchor="middle" fill={theme.text} style={{...mono, fontSize: 32}}>
                {v}
              </text>
            </g>
          );
        })}
      </svg>
      <Pop at={30} style={{display: 'flex', gap: 40, marginTop: 10}}>
        <span style={{...body, fontSize: 32, color: theme.accent, fontWeight: 600}}>● Dallas scored</span>
        <span style={{...body, fontSize: 32, color: theme.text2}}>● Allowed</span>
      </Pop>
      <Pop at={100} style={{...body, fontSize: 42, marginTop: 40, lineHeight: 1.3, color: theme.text}}>
        30+ points in 3 of the first 4 games. Then 16 and 13, both losses.
      </Pop>
    </Scene>
  );
};

// ---------- 4. Injuries: Dallas help + Philly without its QB ----------
const items = [
  {group: 'Dallas', player: 'DeMarvion Overshown', pos: 'LB', status: 'Returning (limited snaps)', hi: true},
  {group: 'Dallas', player: 'Cobie Durant', pos: 'CB', status: 'Trending toward return', hi: true},
  {group: 'Dallas', player: 'Dee Winters', pos: 'LB', status: 'Out', hi: false},
  {group: 'Philly', player: 'Jalen Hurts', pos: 'QB', status: 'Out for the season (blood clots)', hi: true},
  {group: 'Philly', player: 'Tanner McKee', pos: 'QB', status: 'Started last week, a 25-14 loss', hi: false},
];
export const Injuries: React.FC = () => (
  <Scene dur={195}>
    <Pop>
      <Tag>Injuries · as of Sat, Oct 24</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 96, marginTop: 40}}>
      Help on defense.
      <br />
      <span style={{color: theme.accent}}>And Philly has no Hurts.</span>
    </Pop>
    {items.map((it, i) => (
      <Pop key={it.player} at={30 + i * 14} style={{marginTop: i === 3 ? 56 : 30}}>
        {(i === 0 || i === 3) && (
          <div style={{...body, fontSize: 30, color: theme.text2, marginBottom: 8, letterSpacing: 2}}>
            {it.group.toUpperCase()}
          </div>
        )}
        <div style={{display: 'flex', gap: 24, alignItems: 'baseline'}}>
          <div style={{width: 20, height: 20, borderRadius: 10, background: it.hi ? theme.accent : theme.gray, flexShrink: 0}} />
          <div>
            <span style={{...display, fontSize: 56}}>{it.player} </span>
            <span style={{...display, fontSize: 38, color: theme.text2}}>{it.pos}</span>
            <div style={{...body, fontSize: 36, color: it.hi ? theme.accent : theme.text, fontWeight: 600}}>{it.status}</div>
          </div>
        </div>
      </Pop>
    ))}
    <Pop at={110} style={{...body, fontSize: 28, marginTop: 40}}>
      Statuses can change before kickoff. Sources: Dallas Cowboys, AP
    </Pop>
  </Scene>
);

// ---------- 5. Real or lucky ----------
export const RealOrLucky: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const g1 = spring({frame: f - 28, fps, config: {damping: 18}});
  const g2 = spring({frame: f - 46, fps, config: {damping: 18}});
  const scale = 260;
  const Bar = ({v, g, color, label}: {v: number; g: number; color: string; label: string}) => (
    <div style={{display: 'flex', alignItems: 'center', marginTop: 20}}>
      <div style={{...body, fontSize: 36, width: 240, flexShrink: 0}}>{label}</div>
      <div style={{height: 96, width: v * scale * g, background: color, borderRadius: 8}} />
      <div style={{...mono, fontSize: 60, color, marginLeft: 20, opacity: g}}>{v.toFixed(1)}</div>
    </div>
  );
  const oneScore = dalResults.filter((r) => {
    const [a, b] = r.score.split('-').map(Number);
    return Math.abs(a - b) <= 8;
  });
  const osW = oneScore.filter((r) => r.won).length;
  return (
    <Scene dur={165}>
      <Pop>
        <Tag>Real or lucky?</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        Better than
        <br />
        <span style={{color: theme.accent}}>their record</span>
      </Pop>
      <div style={{marginTop: 50}}>
        <Bar v={dal.actualWins} g={g1} color={theme.gray} label="Actual wins" />
        <Bar v={dal.pointsSayWins} g={g2} color={theme.accent} label="Points say" />
      </div>
      <Pop at={80} style={{...display, fontSize: 70, marginTop: 70}}>
        {osW}-{oneScore.length - osW} <span style={{color: theme.text2, fontSize: 50}}>in one-score games</span>
      </Pop>
      <Pop at={100} style={{...body, fontSize: 40, marginTop: 24, lineHeight: 1.3, color: theme.text}}>
        Close games are close to coin flips. Dallas keeps landing on the wrong side.
      </Pop>
    </Scene>
  );
};

// ---------- 6. Division ----------
export const Division: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene dur={180}>
      <Pop>
        <Tag>
          {preview.division.name} · {preview.division.asOf}
        </Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        The shortcut:
        <br />
        <span style={{color: theme.accent}}>win the division</span>
      </Pop>
      {preview.division.rows.map((r, i) => {
        const g = spring({frame: f - 30 - i * 8, fps, config: {damping: 18}});
        const isDal = r.team === 'Cowboys';
        return (
          <div key={r.team} style={{marginTop: 34}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
              <span style={{...display, fontSize: 60, color: isDal ? theme.accent : theme.text}}>{r.team}</span>
              <span style={{...mono, fontSize: 52, color: isDal ? theme.accent : theme.text2}}>{r.record}</span>
            </div>
            <div style={{height: 40, width: 880, background: theme.grayLow, borderRadius: 6, marginTop: 8}}>
              <div style={{height: 40, width: 880 * r.pct * g, background: isDal ? theme.accent : theme.gray, borderRadius: 6}} />
            </div>
          </div>
        );
      })}
      <Pop at={90} style={{...body, fontSize: 40, marginTop: 46, lineHeight: 1.3, color: theme.text}}>
        Division winners make the playoffs. A win tonight puts Dallas at 3-4, right back in the race.
      </Pop>
    </Scene>
  );
};

// ---------- 7. Playoff chance (+ win/lose if the notebook numbers are filled in) ----------
export const Playoffs: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const sc = preview.scenarios?.DAL;
  return (
    <Scene dur={180}>
      <Pop>
        <Tag>10,000 simulated seasons</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        Dallas makes the playoffs
        <br />
        <span style={{color: theme.accent}}>about 1 in {dal.playoffOneIn}</span>
      </Pop>
      <div style={{marginTop: 30}}>
        <DotGrid oneIn={dal.playoffOneIn} at={30} />
      </div>
      {sc &&
        (['win', 'lose'] as const).map((k, i) => {
          const g = spring({frame: f - 90 - i * 14, fps, config: {damping: 18}});
          const win = k === 'win';
          return (
            <div key={k} style={{display: 'flex', alignItems: 'center', marginTop: i ? 14 : 50}}>
              <div style={{...body, fontSize: 36, width: 260, flexShrink: 0}}>{win ? 'Win tonight' : 'Lose tonight'}</div>
              <div style={{height: 70, width: (sc[k] / 100) * 1300 * g, background: win ? theme.accent : theme.gray, borderRadius: 8}} />
              <div style={{...mono, fontSize: 52, marginLeft: 18, color: win ? theme.accent : theme.text2, opacity: g}}>
                {Math.round(sc[k])}%
              </div>
            </div>
          );
        })}
      <Pop at={sc ? 130 : 90} style={{...body, fontSize: 30, marginTop: 40}}>
        Rough estimate · data through week {data.week} · no tiebreakers
      </Pop>
    </Scene>
  );
};

// ---------- 8. Question ----------
export const Question: React.FC = () => (
  <Scene dur={120}>
    <Pop>
      <Tag>Round 2: {preview.rematch}</Tag>
    </Pop>
    <Pop at={10} style={{...display, fontSize: 140, marginTop: 80}}>
      Can Dallas
      <br />
      <span style={{color: theme.accent}}>save it?</span>
    </Pop>
    <Pop at={40} style={{...body, fontSize: 48, marginTop: 60, color: theme.text}}>
      Tell me in the comments.
    </Pop>
  </Scene>
);

const scenes = (): [number, React.ReactNode][] => [
  [105, <Hook />],
  [195, <Trend />],
  [
    165,
    <Ranks
      team={dal}
      title={<>Still a good offense…<br /><span style={{color: theme.accent}}>worst defense in football</span></>}
      note="Even a top-10 offense can't outscore the league's worst defense every week."
    />,
  ],
  [195, <Injuries />],
  [165, <RealOrLucky />],
  [180, <Division />],
  [180, <Playoffs />],
  [120, <Question />],
  [90, <Outro />],
];

export const dallasFrames = () => scenes().reduce((a, [d]) => a + d, 0);

export const DallasPreview: React.FC = () => {
  const f = useCurrentFrame();
  const list = scenes();
  const outroStart = dallasFrames() - 90;
  let from = 0;
  return (
    <AbsoluteFill style={{background: theme.bg}}>
      <style>{fontCss}</style>
      {list.map(([dur, el], i) => {
        const seq = (
          <Sequence key={i} from={from} durationInFrames={dur}>
            {el}
          </Sequence>
        );
        from += dur;
        return seq;
      })}
      {f < outroStart && <Watermark />}
    </AbsoluteFill>
  );
};
