import React from 'react';
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from 'remotion';
import {data, theme} from './data';

export const fontCss = `
@font-face { font-family: 'Barlow Condensed'; src: url('${staticFile('BarlowCondensed-ExtraBold.ttf')}'); font-weight: 800; }
@font-face { font-family: 'DM Sans'; src: url('${staticFile('DMSans-Regular.ttf')}'); font-weight: 400; }
@font-face { font-family: 'DM Sans'; src: url('${staticFile('DMSans-SemiBold.ttf')}'); font-weight: 600; }
@font-face { font-family: 'JetBrains Mono'; src: url('${staticFile('JetBrainsMono-Medium.ttf')}'); font-weight: 500; }
`;

export const display: React.CSSProperties = {
  fontFamily: 'Barlow Condensed',
  fontWeight: 800,
  textTransform: 'uppercase',
  lineHeight: 0.95,
  color: theme.text,
};
export const body: React.CSSProperties = {fontFamily: 'DM Sans', color: theme.text2};
export const mono: React.CSSProperties = {fontFamily: 'JetBrains Mono', fontWeight: 500};

// Fade a whole scene in and out so cuts feel smooth.
export const Scene: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
  const f = useCurrentFrame();
  const opacity = interpolate(f, [0, 8, dur - 8, dur], [0, 1, 1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  return (
    <AbsoluteFill style={{opacity, padding: '330px 80px 0 80px', flexDirection: 'column'}}>
      {children}
    </AbsoluteFill>
  );
};

// Text that springs up into place starting at `at` frames.
export const Pop: React.FC<{at?: number; style?: React.CSSProperties; children: React.ReactNode}> = ({
  at = 0,
  style,
  children,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 14}});
  return (
    <div style={{transform: `translateY(${(1 - s) * 40}px)`, opacity: s, ...style}}>{children}</div>
  );
};

export const Tag: React.FC<{children: React.ReactNode}> = ({children}) => (
  <div
    style={{
      ...display,
      fontSize: 40,
      color: theme.accent,
      border: `3px solid ${theme.accent}`,
      borderRadius: 40,
      padding: '6px 22px',
      display: 'inline-block',
      letterSpacing: 2,
    }}
  >
    {children}
  </div>
);

// ---------- Scene 1: hook ----------
export const Hook: React.FC = () => (
  <Scene dur={90}>
    <Pop>
      <Tag>{data.game.label}</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 190, marginTop: 50}}>
      {data.game.away}
      <br />
      <span style={{color: theme.text2, fontSize: 110}}>VS</span>
      <br />
      {data.game.home}
    </Pop>
    <Pop at={30} style={{...display, fontSize: 140, color: theme.accent, marginTop: 70}}>
      BOTH 2-4.
    </Pop>
    <Pop at={48} style={{...display, fontSize: 96, marginTop: 20}}>
      ONE SEASON IS ON THE LINE.
    </Pop>
  </Scene>
);

// ---------- Rank bars (longer = better, out of 32 teams) ----------
export const RankBar: React.FC<{label: string; rank: number; at: number; highlight: boolean; full?: number}> = ({
  label,
  rank,
  at,
  highlight,
  full = 880,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const grow = spring({frame: f - at, fps, config: {damping: 18}});
  const width = Math.max(14, ((33 - rank) / 32) * full) * grow;
  const shownRank = Math.round(interpolate(grow, [0, 1], [32, rank]));
  const color = highlight ? theme.accent : theme.text;
  return (
    <div style={{marginTop: 70}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
        <div style={{...display, fontSize: 76, color: highlight ? theme.accent : theme.text}}>{label}</div>
        <div style={{...mono, fontSize: 76, color}}>
          {shownRank}
          <span style={{fontSize: 34, color: theme.text2}}> / 32</span>
        </div>
      </div>
      <div style={{height: 96, background: theme.grayLow, borderRadius: 8, marginTop: 14, width: full}}>
        <div style={{height: 96, width, background: highlight ? theme.accent : theme.gray, borderRadius: 8}} />
      </div>
    </div>
  );
};

export const Ranks: React.FC<{team: (typeof data.teams)[number]; title: React.ReactNode; note: string; footnote?: boolean}> = ({
  team,
  title,
  note,
  footnote = true,
}) => {
  const worst = team.defenseRank >= team.offenseRank ? 'def' : 'off';
  return (
    <Scene dur={165}>
      <Pop>
        <Tag>{team.name} · {team.record}</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        {title}
      </Pop>
      <RankBar label="Offense" rank={team.offenseRank} at={30} highlight={worst === 'off'} />
      <RankBar label="Defense" rank={team.defenseRank} at={55} highlight={worst === 'def'} />
      <Pop at={95} style={{...body, fontSize: 42, marginTop: 50, lineHeight: 1.3}}>
        {note}
      </Pop>
      {footnote && (
        <Pop at={110} style={{...body, fontSize: 30, marginTop: 24}}>
          Rank by points added per play · longer bar = better
        </Pop>
      )}
    </Scene>
  );
};

// ---------- Scene 4: record vs what the points say ----------
export const WinsBars: React.FC<{team: (typeof data.teams)[number]; at: number}> = ({team, at}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const g1 = spring({frame: f - at, fps, config: {damping: 18}});
  const g2 = spring({frame: f - at - 18, fps, config: {damping: 18}});
  const scale = 220; // px per win
  const Bar = ({v, g, color, label}: {v: number; g: number; color: string; label: string}) => (
    <div style={{display: 'flex', alignItems: 'center', marginTop: 14}}>
      <div style={{...body, fontSize: 32, width: 230, flexShrink: 0}}>{label}</div>
      <div style={{height: 84, width: v * scale * g, background: color, borderRadius: 8}} />
      <div style={{...mono, fontSize: 46, color, marginLeft: 18, opacity: g}}>{v.toFixed(1)}</div>
    </div>
  );
  return (
    <div style={{marginTop: 70}}>
      <div style={{...display, fontSize: 76}}>{team.name}</div>
      <Bar v={team.actualWins} g={g1} color={theme.gray} label="Actual wins" />
      <Bar v={team.pointsSayWins} g={g2} color={theme.accent} label="Points say" />
    </div>
  );
};

export const PointsSay: React.FC = () => {
  const [dal, phi] = data.teams;
  return (
    <Scene dur={150}>
      <Pop>
        <Tag>Real or lucky?</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
        What their points say
      </Pop>
      <WinsBars team={dal} at={28} />
      <WinsBars team={phi} at={58} />
      <Pop at={100} style={{...body, fontSize: 42, marginTop: 50, lineHeight: 1.3}}>
        Dallas has played closer to a 3-win team. Philly's record is about what it has earned.
      </Pop>
    </Scene>
  );
};

// ---------- Scene 5: playoff chance as a dot grid ----------
export const DotGrid: React.FC<{oneIn: number; at: number}> = ({oneIn, at}) => {
  const f = useCurrentFrame();
  const total = 40;
  const lit = Math.round(total / oneIn);
  return (
    <div style={{display: 'grid', gridTemplateColumns: 'repeat(10, 66px)', gap: 16, marginTop: 18}}>
      {Array.from({length: total}).map((_, i) => {
        const on = i < lit;
        const appear = interpolate(f - at - i * 0.8, [0, 6], [0, 1], {
          extrapolateLeft: 'clamp',
          extrapolateRight: 'clamp',
        });
        return (
          <div
            key={i}
            style={{
              width: 66,
              height: 66,
              borderRadius: 33,
              background: on ? theme.accent : theme.grayLow,
              opacity: appear,
              transform: `scale(${0.6 + 0.4 * appear})`,
            }}
          />
        );
      })}
    </div>
  );
};

export const Playoffs: React.FC<{footnote?: string}> = ({footnote}) => (
  <Scene dur={165}>
    <Pop>
      <Tag>10,000 simulated seasons</Tag>
    </Pop>
    <Pop at={6} style={{...display, fontSize: 100, marginTop: 40}}>
      Chance to make the playoffs
    </Pop>
    {data.teams.map((t, idx) => (
      <div key={t.key} style={{marginTop: 64}}>
        <Pop at={26 + idx * 40} style={{display: 'flex', alignItems: 'baseline', gap: 24}}>
          <span style={{...display, fontSize: 64}}>{t.name}</span>
          <span style={{...mono, fontSize: 64, color: theme.accent}}>1 in {t.playoffOneIn}</span>
        </Pop>
        <DotGrid oneIn={t.playoffOneIn} at={30 + idx * 40} />
      </div>
    ))}
    <Pop at={120} style={{...body, fontSize: 32, marginTop: 40}}>
      {footnote ?? `Rough estimate · data through week ${data.week} · no tiebreakers`}
    </Pop>
  </Scene>
);

// ---------- Scene 6: outro ----------
export const Outro: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 12}});
  return (
    <Scene dur={90}>
      <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', marginTop: 240}}>
        <Img src={staticFile('logo.png')} style={{width: 320, borderRadius: 60, transform: `scale(${s})`}} />
        <Pop at={12} style={{...display, fontSize: 96, textAlign: 'center', marginTop: 50}}>
          Numbers behind
          <br />
          the game
        </Pop>
        <Pop at={26} style={{...body, fontSize: 44, marginTop: 30, color: theme.accent}}>
          Follow @numbersbehindthegame
        </Pop>
      </div>
    </Scene>
  );
};

// Small handle in the top corner on every scene except the outro.
export const Watermark: React.FC = () => (
  <div style={{position: 'absolute', top: 90, left: 80, display: 'flex', alignItems: 'center', gap: 16}}>
    <Img src={staticFile('logo.png')} style={{width: 64, borderRadius: 14}} />
    <span style={{...body, fontSize: 30}}>@numbersbehindthegame</span>
  </div>
);

export const SaveTheSeason: React.FC = () => {
  const [dal, phi] = data.teams;
  const scenes: [number, React.ReactNode][] = [
    [90, <Hook />],
    [
      165,
      <Ranks
        team={dal}
        title={<>Dallas: great offense…<br /><span style={{color: theme.accent}}>worst defense in football</span></>}
        note="A top-10 offense can't outscore the league's worst defense every week."
      />,
    ],
    [
      165,
      <Ranks
        team={phi}
        title={<>Philly: struggling<br /><span style={{color: theme.accent}}>on both sides</span></>}
        note="Philly's problem starts with the offense: 30th of 32."
      />,
    ],
    [150, <PointsSay />],
    [165, <Playoffs />],
    [90, <Outro />],
  ];
  let from = 0;
  const outroStart = scenes.slice(0, -1).reduce((a, [d]) => a + d, 0);
  const f = useCurrentFrame();
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

export const TOTAL_FRAMES = 90 + 165 + 165 + 150 + 165 + 90;
