import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {data, theme} from './data';
import {preview, Result} from './previewData';
import {
  Hook,
  Outro,
  PointsSay,
  Playoffs,
  Pop,
  Ranks,
  Scene,
  Tag,
  Watermark,
  body,
  display,
  fontCss,
  mono,
} from './Video';

// ---------- Two teams heading opposite ways ----------
const ResultRow: React.FC<{name: string; results: Result[]; at: number; caption: string}> = ({
  name,
  results,
  at,
  caption,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <div style={{marginTop: 64}}>
      <Pop at={at} style={{...display, fontSize: 76}}>
        {name}
      </Pop>
      <div style={{display: 'flex', gap: 12, marginTop: 16}}>
        {results.map((r, i) => {
          const s = spring({frame: f - at - 6 - i * 5, fps, config: {damping: 14}});
          return (
            <div
              key={i}
              style={{
                width: 140,
                padding: '14px 0',
                borderRadius: 12,
                textAlign: 'center',
                background: r.won ? theme.grayLow : 'transparent',
                border: `3px solid ${r.won ? theme.gray : theme.accent}`,
                opacity: s,
                transform: `scale(${0.7 + 0.3 * s})`,
              }}
            >
              <div style={{...display, fontSize: 56, color: r.won ? theme.text : theme.accent}}>
                {r.won ? 'W' : 'L'}
              </div>
              <div style={{...mono, fontSize: 26, color: theme.text2}}>{r.score}</div>
            </div>
          );
        })}
      </div>
      <Pop at={at + 40} style={{...body, fontSize: 38, marginTop: 18}}>
        {caption}
      </Pop>
    </div>
  );
};

const Trend: React.FC = () => (
  <Scene dur={165}>
    <Pop>
      <Tag>Last 6 games</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
      Same record.
      <br />
      <span style={{color: theme.accent}}>Different stories.</span>
    </Pop>
    <ResultRow name="Philly" results={preview.results.PHI} at={24} caption="Started 2-0. Lost four straight." />
    <ResultRow
      name="Dallas"
      results={preview.results.DAL}
      at={70}
      caption="Losses by 8, 3, 8 and 10. Close, not collapsing."
    />
  </Scene>
);

// ---------- Injury news ----------
const Injuries: React.FC<{inj: (typeof preview.injuries)[number]}> = ({inj}) => (
  <Scene dur={150}>
    <Pop>
      <Tag>{inj.team} injuries · {inj.asOf}</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
      {inj.title[0]}
      <br />
      <span style={{color: theme.accent}}>{inj.title[1]}</span>
    </Pop>
    {inj.items.map((it, i) => (
      <Pop key={it.player} at={30 + i * 16} style={{marginTop: 46, display: 'flex', gap: 28, alignItems: 'flex-start'}}>
        <div
          style={{
            width: 22,
            height: 22,
            borderRadius: 11,
            marginTop: 22,
            flexShrink: 0,
            background: it.highlight ? theme.accent : theme.gray,
          }}
        />
        <div>
          <div style={{...display, fontSize: 64}}>
            {it.player} <span style={{color: theme.text2, fontSize: 44}}>{it.pos}</span>
          </div>
          <div style={{...body, fontSize: 40, color: it.highlight ? theme.accent : theme.text, fontWeight: 600}}>
            {it.status}
          </div>
          {it.note && <div style={{...body, fontSize: 32}}>{it.note}</div>}
        </div>
      </Pop>
    ))}
    <Pop at={90} style={{...body, fontSize: 30, marginTop: 50}}>
      Statuses can change before kickoff. {inj.source}
    </Pop>
  </Scene>
);

// ---------- The division shortcut ----------
const Division: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  return (
    <Scene dur={165}>
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
        return (
          <div key={r.team} style={{marginTop: 34}}>
            <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
              <span style={{...display, fontSize: 60, color: r.playing ? theme.accent : theme.text}}>
                {r.team}
              </span>
              <span style={{...mono, fontSize: 52, color: r.playing ? theme.accent : theme.text2}}>{r.record}</span>
            </div>
            <div style={{height: 40, width: 880, background: theme.grayLow, borderRadius: 6, marginTop: 8}}>
              <div
                style={{
                  height: 40,
                  width: 880 * r.pct * g,
                  background: r.playing ? theme.accent : theme.gray,
                  borderRadius: 6,
                }}
              />
            </div>
          </div>
        );
      })}
      <Pop at={90} style={{...body, fontSize: 40, marginTop: 46, lineHeight: 1.3}}>
        Division winners make the playoffs. Tonight's winner goes to 3-4, right back in the race.
      </Pop>
    </Scene>
  );
};

// ---------- Win tonight vs lose tonight (only when the notebook numbers are filled in) ----------
const Scenarios: React.FC = () => {
  const sc = preview.scenarios!;
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const rows: [string, {win: number; lose: number}][] = [
    ['Dallas', sc.DAL],
    ['Philly', sc.PHI],
  ];
  return (
    <Scene dur={165}>
      <Pop>
        <Tag>Playoff chance after tonight</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        Win or <span style={{color: theme.accent}}>go home?</span>
      </Pop>
      {rows.map(([name, v], i) => {
        const g1 = spring({frame: f - 30 - i * 30, fps, config: {damping: 18}});
        const g2 = spring({frame: f - 42 - i * 30, fps, config: {damping: 18}});
        const Bar = ({p, g, win}: {p: number; g: number; win: boolean}) => (
          <div style={{display: 'flex', alignItems: 'center', marginTop: 12}}>
            <div style={{...body, fontSize: 34, width: 140, flexShrink: 0}}>{win ? 'Win' : 'Lose'}</div>
            <div style={{height: 70, width: (p / 100) * 1400 * g, background: win ? theme.accent : theme.gray, borderRadius: 8}} />
            <div style={{...mono, fontSize: 52, marginLeft: 18, color: win ? theme.accent : theme.text2, opacity: g}}>
              {Math.round(p)}%
            </div>
          </div>
        );
        return (
          <div key={name} style={{marginTop: 60}}>
            <div style={{...display, fontSize: 76}}>{name}</div>
            <Bar p={v.win} g={g1} win />
            <Bar p={v.lose} g={g2} win={false} />
          </div>
        );
      })}
    </Scene>
  );
};

// ---------- Rematch + comment prompt ----------
const Question: React.FC = () => (
  <Scene dur={120}>
    <Pop>
      <Tag>Round 2: {preview.rematch}</Tag>
    </Pop>
    <Pop at={10} style={{...display, fontSize: 130, marginTop: 80}}>
      Which season
      <br />
      <span style={{color: theme.accent}}>ends tonight?</span>
    </Pop>
    <Pop at={40} style={{...body, fontSize: 48, marginTop: 60, color: theme.text}}>
      Tell me in the comments.
    </Pop>
  </Scene>
);

const buildScenes = (): [number, React.ReactNode][] => {
  const [dal, phi] = data.teams;
  const scenes: [number, React.ReactNode][] = [
    [90, <Hook />],
    [165, <Trend />],
    [
      150,
      <Ranks
        team={dal}
        title={<>Dallas: great offense…<br /><span style={{color: theme.accent}}>worst defense in football</span></>}
        note="A top-10 offense can't outscore the league's worst defense every week."
      />,
    ],
    [150, <Injuries inj={preview.injuries[0]} />],
    [
      135,
      <Ranks
        team={phi}
        title={<>Philly: struggling<br /><span style={{color: theme.accent}}>on both sides</span></>}
        note="Philly's offense ranks 30th of 32, and that was mostly with Hurts."
      />,
    ],
    [150, <Injuries inj={preview.injuries[1]} />],
    [135, <PointsSay />],
    [165, <Division />],
    [165, <Playoffs footnote="Rough estimate · data through week 6 · Philly's odds don't yet account for losing Hurts" />],
  ];
  if (preview.scenarios) scenes.push([165, <Scenarios />]);
  scenes.push([120, <Question />], [90, <Outro />]);
  return scenes;
};

export const previewFrames = () => buildScenes().reduce((a, [d]) => a + d, 0);

export const MnfPreview: React.FC = () => {
  const scenes = buildScenes();
  const f = useCurrentFrame();
  const outroStart = previewFrames() - 90;
  let from = 0;
  return (
    <AbsoluteFill style={{background: theme.bg}}>
      <style>{fontCss}</style>
      {scenes.map(([dur, el], i) => {
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
