import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {data, theme} from '../data';
import {fontCss} from '../Video';
import {Bubble, Burst, Caption, INK, Mascot, PAPER, Panel, Sfx, SpeedLines, YELLOW, halftone} from './Comic';

const dal = data.teams[0];
const W = 1080;

const Fade: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 5, dur - 6, dur], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

// ---------- Scene 1: the hook, full-bleed manga splash ----------
const Splash: React.FC = () => (
  <Fade dur={140}>
    <Panel at={0} x={50} y={260} w={980} h={1180} tilt={-1.5}>
      <div style={{position: 'absolute', inset: 0, ...halftone('#1c2a44', 22, 5)}} />
      <SpeedLines cx={490} cy={560} w={980} h={1180} />
      <Burst size={760} color={theme.accent} at={8} style={{left: 110, top: 190}}>
        <Sfx size={190} color={PAPER} skew={-10}>
          2-4
        </Sfx>
      </Burst>
      <Sfx size={150} color={PAPER} style={{position: 'absolute', left: 60, top: 40}}>
        Dallas
      </Sfx>
    </Panel>
    <Caption at={20} x={80} y={200} w={640}>
      Monday Night · Dallas at Philly
    </Caption>
    <Panel at={34} x={150} y={1400} w={860} h={230} tilt={2} bg={YELLOW} style={{boxShadow: `10px 10px 0 ${INK}`, border: `8px solid ${INK}`}}>
      <div style={{padding: '30px 40px'}}>
        <Sfx size={96} color={INK} stroke={YELLOW} skew={-4} style={{textShadow: 'none'}}>
          Tonight decides
          <br />
          its season!
        </Sfx>
      </div>
    </Panel>
  </Fade>
);

// ---------- Scene 2: worst defense, two stacked panels ----------
const RankPanelBar: React.FC<{label: string; rank: number; at: number; hi: boolean}> = ({label, rank, at, hi}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const g = spring({frame: f - at, fps, config: {damping: 16}});
  const full = 760;
  const w = Math.max(30, ((33 - rank) / 32) * full) * g;
  return (
    <div style={{marginTop: 34}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
        <Sfx size={64} color={hi ? theme.accent : PAPER} skew={-6} style={{textShadow: 'none'}}>
          {label}
        </Sfx>
        <Sfx size={64} color={hi ? theme.accent : PAPER} skew={-6} style={{textShadow: 'none'}}>
          #{Math.round(interpolate(g, [0, 1], [32, rank]))}
        </Sfx>
      </div>
      <div style={{height: 84, width: full, border: `6px solid ${PAPER}`, marginTop: 10, background: '#16161c'}}>
        <div style={{height: '100%', width: w, background: hi ? theme.accent : PAPER, ...(!hi ? halftone('#9a9aa3', 12, 3) : {})}} />
      </div>
    </div>
  );
};

const WorstDefense: React.FC = () => (
  <Fade dur={170}>
    <Caption at={0} x={80} y={210} w={560}>
      Meanwhile, on defense…
    </Caption>
    <Panel at={4} x={50} y={300} w={980} h={620} tilt={1}>
      <div style={{padding: '40px 60px'}}>
        <Sfx size={72} color={PAPER} style={{textShadow: 'none'}}>
          League rank, out of 32
        </Sfx>
        <RankPanelBar label="Offense" rank={dal.offenseRank} at={16} hi={false} />
        <RankPanelBar label="Defense" rank={dal.defenseRank} at={34} hi />
      </div>
    </Panel>
    <Panel at={62} x={50} y={960} w={980} h={640} tilt={-1.2} bg="#0b1830">
      <div style={{position: 'absolute', inset: 0, ...halftone('#14284a', 20, 5)}} />
      <SpeedLines cx={300} cy={330} w={980} h={640} count={50} />
      <Mascot at={66} x={90} y={170} size={340} mood="shock" />
      <Burst size={420} color={YELLOW} at={74} style={{left: 520, top: 40}}>
        <Sfx size={120} color={INK} stroke={YELLOW} style={{textShadow: 'none'}}>
          Dead
          <br />
          last!
        </Sfx>
      </Burst>
    </Panel>
    <Bubble at={92} x={430} y={1460} w={560} tail="left" text="Worst defense in football?!" size={48} />
  </Fade>
);

// ---------- Scene 3: real or lucky, mascot explains ----------
const RealOrLucky: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const g1 = spring({frame: f - 22, fps, config: {damping: 16}});
  const g2 = spring({frame: f - 40, fps, config: {damping: 16}});
  const H = 520; // bar max height for 3 wins
  const Bar = ({v, g, label, hi}: {v: number; g: number; label: string; hi: boolean}) => (
    <div style={{display: 'flex', flexDirection: 'column', alignItems: 'center', width: 260}}>
      <Sfx size={84} color={hi ? theme.accent : PAPER} style={{textShadow: 'none', opacity: g}}>
        {v.toFixed(1)}
      </Sfx>
      <div
        style={{
          width: 200,
          height: (v / 3) * H * g,
          marginTop: 12,
          border: `7px solid ${PAPER}`,
          background: hi ? theme.accent : PAPER,
          ...(hi ? {} : halftone('#9a9aa3', 12, 3)),
        }}
      />
      <Sfx size={50} color={PAPER} skew={-4} style={{marginTop: 16, textShadow: 'none'}}>
        {label}
      </Sfx>
    </div>
  );
  return (
    <Fade dur={170}>
      <Caption at={0} x={80} y={210} w={420}>
        Real or lucky?
      </Caption>
      <Panel at={4} x={50} y={300} w={980} h={900} tilt={-0.8}>
        <div style={{display: 'flex', justifyContent: 'center', gap: 120, alignItems: 'flex-end', height: 820}}>
          <Bar v={dal.actualWins} g={g1} label="Actual wins" hi={false} />
          <Bar v={dal.pointsSayWins} g={g2} label="Points say" hi />
        </div>
      </Panel>
      <Mascot at={70} x={60} y={1260} size={300} mood="smart" />
      <Bubble at={78} x={400} y={1240} w={600} tail="left" text="Their points say they've played like an almost-3-win team!" size={42} />
    </Fade>
  );
};

const Mark: React.FC = () => (
  <div style={{position: 'absolute', top: 90, left: 80, display: 'flex', alignItems: 'center', gap: 16}}>
    <Img src={staticFile('logo.png')} style={{width: 64, borderRadius: 14, border: `4px solid ${PAPER}`}} />
    <span style={{fontFamily: 'DM Sans', fontSize: 30, color: PAPER}}>@numbersbehindthegame</span>
  </div>
);

export const COMIC_FRAMES = 140 + 170 + 170;

export const ComicSample: React.FC = () => (
  <AbsoluteFill style={{background: '#000', ...halftone('#101018', 26, 3)}}>
    <style>{fontCss}</style>
    <Sequence from={0} durationInFrames={140}>
      <Splash />
    </Sequence>
    <Sequence from={140} durationInFrames={170}>
      <WorstDefense />
    </Sequence>
    <Sequence from={310} durationInFrames={170}>
      <RealOrLucky />
    </Sequence>
    <Mark />
  </AbsoluteFill>
);

void W;
