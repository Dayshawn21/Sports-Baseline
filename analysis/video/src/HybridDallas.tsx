// Hybrid style: clean, readable charts inside a comic panel frame, with comic
// accents (mascot + speech bubbles, one burst, speed lines) only at key moments.
import React from 'react';
import {AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from './data';
import {Outro, Pop, Ranks, Scene, Tag, Watermark, display, fontCss} from './Video';
import {Division, Injuries, Playoffs, Question, RealOrLucky, Trend, dal} from './DallasPreview';
import {Bubble, Burst, INK, Mascot, PAPER, Sfx, SpeedLines} from './comic/Comic';

// Comic panel frame around every scene (clean inside).
const Frame: React.FC = () => (
  <div
    style={{
      position: 'absolute',
      left: 40,
      top: 180,
      width: 1000,
      height: 1450,
      border: `6px solid ${PAPER}`,
      boxShadow: `12px 12px 0 ${theme.accent}`,
      pointerEvents: 'none',
    }}
  />
);

// Mascot popping out of the bottom of the frame, with an optional bubble.
const Host: React.FC<{at: number; mood?: 'smart' | 'shock'; say?: string}> = ({at, mood = 'smart', say}) => (
  <>
    <Mascot at={at} x={70} y={1480} size={230} mood={mood} />
    {say && <Bubble at={at + 8} x={330} y={1510} w={560} tail="left" text={say} size={40} />}
  </>
);

// ---------- Hook: clean text + subtle speed lines + one burst ----------
const Hook: React.FC = () => {
  const f = useCurrentFrame();
  const lines = interpolate(f, [0, 10], [0, 0.35], {extrapolateRight: 'clamp'});
  return (
    <Scene dur={105}>
      <div style={{position: 'absolute', left: 46, top: 186, width: 988, height: 1438, overflow: 'hidden', opacity: lines}}>
        <SpeedLines cx={680} cy={700} w={988} h={1438} count={60} />
      </div>
      <Pop>
        <Tag>Monday Night Football · at Philly</Tag>
      </Pop>
      <Pop at={6} style={{...display, fontSize: 200, marginTop: 50}}>
        Dallas
        <br />
        is
      </Pop>
      <Burst size={560} color={theme.accent} at={16} style={{left: 470, top: 600}}>
        <Sfx size={170} color={PAPER} skew={-8}>
          2-4
        </Sfx>
      </Burst>
      <Pop at={40} style={{...display, fontSize: 100, marginTop: 420}}>
        Tonight might decide
        <br />
        <span style={{color: theme.accent}}>its season.</span>
      </Pop>
    </Scene>
  );
};

// Small comic stamp, e.g. "COLD!" on the trend chart.
const Stamp: React.FC<{at: number; x: number; y: number; text: string; rot?: number}> = ({at, x, y, text, rot = -8}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 9, stiffness: 220}});
  return (
    <div style={{position: 'absolute', left: x, top: y, transform: `scale(${interpolate(s, [0, 1], [2.2, 1])}) rotate(${rot}deg)`, opacity: s}}>
      <Sfx size={96} color={theme.accent} stroke={INK}>
        {text}
      </Sfx>
    </div>
  );
};

// Layer accents on top of an existing clean scene.
const With: React.FC<{base: React.ReactNode; dur: number; children: React.ReactNode}> = ({base, dur, children}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 8, dur - 8, dur], [0, 1, 1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <AbsoluteFill>
      {base}
      <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

const scenes = (): [number, React.ReactNode][] => [
  [105, <Hook />],
  [195, <With base={<Trend />} dur={195}><Stamp at={95} x={610} y={430} text="Ice cold!" rot={-6} /></With>],
  [
    165,
    <With
      base={
        <Ranks
          team={dal}
          title={<>Still a good offense…<br /><span style={{color: theme.accent}}>worst defense in football</span></>}
          note="Even a top-10 offense can't outscore the league's worst defense every week."
          footnote={false}
        />
      }
      dur={165}
    >
      <Host at={80} mood="shock" say="Dead last. 32 out of 32!" />
    </With>,
  ],
  [195, <Injuries />],
  [
    165,
    <With base={<RealOrLucky />} dur={165}>
      <Host at={110} say="Some of 2-4 is bad luck, not bad football." />
    </With>,
  ],
  [180, <Division />],
  [
    180,
    <With base={<Playoffs />} dur={180}>
      <Host at={100} say="Not dead yet… but tonight matters." />
    </With>,
  ],
  [
    120,
    <With base={<Question />} dur={120}>
      <Host at={30} />
    </With>,
  ],
  [90, <Outro />],
];

export const hybridFrames = () => scenes().reduce((a, [d]) => a + d, 0);

export const HybridDallas: React.FC = () => {
  const f = useCurrentFrame();
  const outroStart = hybridFrames() - 90;
  let from = 0;
  return (
    <AbsoluteFill style={{background: theme.bg}}>
      <style>{fontCss}</style>
      {f < outroStart && <Frame />}
      {scenes().map(([dur, el], i) => {
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
