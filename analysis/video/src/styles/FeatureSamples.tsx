// Two segment formats:
//  A) Prediction receipts: a thermal receipt prints, calls get stamped.
//     Uses EXAMPLE data (clearly labeled) until real graded calls exist.
//  B) Guess the number: question, choices, countdown, reveal.
//     Uses a real stat from the week-1 notebook: 59 of 60 teams with 10+ wins
//     made the playoffs in the 17-game seasons 2021-2025.
import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../data';
import {body, display, fontCss, mono} from '../Video';
import {Bubble, INK, Mascot, PAPER, Sfx} from '../comic/Comic';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const A = 330;
const B = 360;

const Handle: React.FC = () => (
  <div style={{position: 'absolute', top: 80, left: 80, display: 'flex', alignItems: 'center', gap: 14}}>
    <Img src={staticFile('logo.png')} style={{width: 56, borderRadius: 12}} />
    <span style={{...body, fontSize: 28}}>@numbersbehindthegame</span>
  </div>
);

// ================= A) PREDICTION RECEIPTS =================
type Line = {call: string; said: string; result: string; ok: boolean; note: string};
const EXAMPLE_LINES: Line[] = [
  {call: 'MIN to beat DET', said: '40%', result: 'Lost', ok: true, note: 'a 40% call should miss 6 in 10'},
  {call: 'DAL playoff chance', said: '1 in 5', result: 'Pending', ok: true, note: 'graded in January'},
  {call: 'PHI to beat DAL', said: '65%', result: 'Lost', ok: false, note: 'missed'},
  {call: 'KC to stay unbeaten', said: '30%', result: 'Lost', ok: true, note: 'as expected'},
];

const Stamp: React.FC<{at: number; ok: boolean; pending?: boolean}> = ({at, ok, pending}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 9, stiffness: 240}});
  const color = pending ? '#9a9aa3' : ok ? theme.accent : '#ff5a5a';
  const text = pending ? 'PENDING' : ok ? 'ON TARGET' : 'MISSED';
  return (
    <div
      style={{
        position: 'absolute',
        right: 150,
        top: -4,
        ...display,
        border: `5px solid ${color}`,
        color,
        borderRadius: 10,
        padding: '2px 14px',
        fontSize: 34,
        transform: `rotate(-10deg) scale(${interpolate(s, [0, 1], [2.4, 1])})`,
        opacity: s * 0.95,
        background: 'rgba(255,255,255,0.6)',
      }}
    >
      {text}
    </div>
  );
};

const Receipts: React.FC = () => {
  const f = useCurrentFrame();
  const W = 820;
  const fullH = 1020;
  const printed = interpolate(f, [10, 110], [180, fullH], clamp);
  const lineAt = (i: number) => 30 + i * 22;
  const totalAt = 150;
  const receiptMono: React.CSSProperties = {fontFamily: 'JetBrains Mono', color: '#1a1a1a'};
  const zig = Array.from({length: 41})
    .map((_, i) => `${100 - (i / 40) * 100}% ${i % 2 ? 98.5 : 100}%`)
    .join(', ');
  return (
    <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 30%, #13233f 0%, #000 70%)'}}>
      {/* printer slot */}
      <div style={{position: 'absolute', left: 100, top: 220, width: 880, height: 40, background: '#1d1d24', borderRadius: 20, border: `4px solid #2e2e38`}} />
      <div style={{position: 'absolute', left: (1080 - W) / 2, top: 240, width: W, height: printed, overflow: 'hidden'}}>
        <div
          style={{
            position: 'absolute',
            bottom: 0,
            width: W,
            height: fullH,
            background: '#f3f1ea',
            clipPath: `polygon(0 0, 100% 0, ${zig})`,
            padding: '50px 50px',
            boxSizing: 'border-box',
          }}
        >
          <div style={{...receiptMono, fontSize: 30, textAlign: 'center', letterSpacing: 2}}>NUMBERS BEHIND THE GAME</div>
          <div style={{...receiptMono, fontSize: 52, textAlign: 'center', fontWeight: 500, marginTop: 6}}>RECEIPTS · WEEK 7</div>
          <div style={{...receiptMono, fontSize: 24, textAlign: 'center', color: '#666'}}>every call, graded. wins and misses.</div>
          <div style={{borderTop: '4px dashed #999', margin: '26px 0'}} />
          {EXAMPLE_LINES.map((l, i) => (
            <div key={i} style={{position: 'relative', marginBottom: 26, opacity: interpolate(f - lineAt(i), [0, 6], [0, 1], clamp)}}>
              <div style={{...receiptMono, fontSize: 34}}>{l.call}</div>
              <div style={{display: 'flex', justifyContent: 'space-between', ...receiptMono, fontSize: 28, color: '#444'}}>
                <span>said {l.said}</span>
                <span>→ {l.result}</span>
              </div>
              <div style={{...receiptMono, fontSize: 22, color: '#777'}}>{l.note}</div>
              <Stamp at={lineAt(i) + 16} ok={l.ok} pending={l.result === 'Pending'} />
            </div>
          ))}
          <div style={{borderTop: '4px dashed #999', margin: '8px 0 20px'}} />
          <div style={{display: 'flex', justifyContent: 'space-between', ...receiptMono, fontSize: 36, opacity: interpolate(f - totalAt, [0, 8], [0, 1], clamp)}}>
            <span>SEASON CALLS</span>
            <span>31-12</span>
          </div>
          <div style={{display: 'flex', justifyContent: 'space-between', ...receiptMono, fontSize: 28, color: '#444', opacity: interpolate(f - totalAt - 8, [0, 8], [0, 1], clamp)}}>
            <span>70%+ calls hit</span>
            <span>8 of 10 ✓</span>
          </div>
        </div>
      </div>
      {/* EXAMPLE banner */}
      <div style={{position: 'absolute', top: 1410, left: 80, right: 80, textAlign: 'center', background: '#ff5a5a', color: '#000', ...display, fontSize: 40, padding: '8px 0', transform: 'rotate(-2deg)'}}>
        EXAMPLE · not real results yet
      </div>
      <Mascot at={190} x={70} y={1490} size={210} />
      <Bubble at={198} x={310} y={1510} w={620} tail="left" text="A 40% call that misses isn't wrong. It should miss 6 in 10!" size={36} />
    </AbsoluteFill>
  );
};

// ================= B) GUESS THE NUMBER =================
const CHOICES = ['1', '6', '15', '25'];
const ANSWER = 0;

const Guess: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const q = spring({frame: f, fps, config: {damping: 14}});
  const countStart = 70;
  const reveal = 175;
  const secLeft = Math.max(0, 3 - Math.floor((f - countStart) / 30));
  const inCount = f >= countStart && f < reveal;
  const ringP = interpolate(f, [countStart, countStart + 90], [1, 0], clamp);
  const R = 70;
  const C = 2 * Math.PI * R;
  const revealed = f >= reveal;
  const total = 60;
  const made = 59;
  return (
    <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 30%, #13233f 0%, #000 70%)', padding: '230px 80px 0'}}>
      <div style={{...display, fontSize: 40, color: theme.accent, letterSpacing: 3, opacity: q}}>GUESS THE NUMBER</div>
      <div style={{...display, fontSize: 88, lineHeight: 0.98, marginTop: 14, transform: `translateY(${(1 - q) * 40}px)`, opacity: q}}>
        Since 2021, 60 NFL teams won 10+ games.
        <br />
        <span style={{color: theme.accent}}>How many missed the playoffs?</span>
      </div>
      <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24, marginTop: 50}}>
        {CHOICES.map((c, i) => {
          const s = spring({frame: f - 20 - i * 6, fps, config: {damping: 14}});
          const right = revealed && i === ANSWER;
          const wrong = revealed && i !== ANSWER;
          return (
            <div
              key={c}
              style={{
                height: 150,
                border: `5px solid ${right ? theme.accent : '#3a3a42'}`,
                background: right ? theme.accent : '#111116',
                borderRadius: 18,
                display: 'flex',
                alignItems: 'center',
                gap: 26,
                padding: '0 30px',
                transform: `scale(${s * (right ? 1.04 : 1)})`,
                opacity: wrong ? 0.3 : s,
              }}
            >
              <span style={{...display, fontSize: 50, color: right ? '#000' : theme.text2}}>{'ABCD'[i]}</span>
              <span style={{...mono, fontSize: 80, color: right ? '#000' : theme.text}}>{c}</span>
            </div>
          );
        })}
      </div>
      {inCount && (
        <div style={{position: 'absolute', left: 80, right: 80, top: 1170, display: 'flex', alignItems: 'center', gap: 40}}>
          <svg width={180} height={180}>
            <circle cx={90} cy={90} r={R} stroke="#1d1d24" strokeWidth={16} fill="none" />
            <circle cx={90} cy={90} r={R} stroke={theme.accent} strokeWidth={16} fill="none" strokeDasharray={C} strokeDashoffset={C * (1 - ringP)} transform="rotate(-90 90 90)" strokeLinecap="round" />
            <text x={90} y={118} textAnchor="middle" fill={theme.text} style={{...mono, fontSize: 84}}>{secLeft || 1}</text>
          </svg>
          <Sfx size={96} color={PAPER} stroke={INK}>
            Pause & guess!
          </Sfx>
        </div>
      )}
      {revealed && (
        <div style={{position: 'absolute', left: 80, right: 80, top: 1080}}>
          <div style={{display: 'grid', gridTemplateColumns: 'repeat(15, 48px)', gap: 12}}>
            {Array.from({length: total}).map((_, i) => {
              const miss = i === total - 1;
              const a = interpolate(f - reveal - i * 0.6, [0, 6], [0, 1], clamp);
              return (
                <div
                  key={i}
                  style={{
                    width: 48,
                    height: 48,
                    borderRadius: 24,
                    background: miss ? '#ff5a5a' : theme.accent,
                    opacity: a,
                    transform: `scale(${miss ? 1 + 0.25 * Math.max(0, Math.sin((f - reveal) / 5)) : 1})`,
                  }}
                />
              );
            })}
          </div>
          <div style={{...display, fontSize: 64, marginTop: 30, opacity: interpolate(f - reveal - 40, [0, 8], [0, 1], clamp)}}>
            Just <span style={{color: theme.accent}}>1</span>. {made} of {total} got in.
          </div>
          <div style={{...body, fontSize: 28, marginTop: 10, opacity: interpolate(f - reveal - 50, [0, 8], [0, 1], clamp)}}>
            Source: nflverse via Lineform · 17-game seasons, 2021-2025
          </div>
        </div>
      )}
      {revealed && (
        <>
          <Mascot at={reveal + 70} x={70} y={1500} size={200} />
          <Bubble at={reveal + 78} x={300} y={1520} w={640} tail="left" text="Win 10 and you're almost always in. Dallas needs 8 more." size={36} />
        </>
      )}
    </AbsoluteFill>
  );
};

const Fade: React.FC<{dur: number; children: React.ReactNode}> = ({dur, children}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 6, dur - 8, dur], [0, 1, 1, 0], clamp);
  return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

export const FEATURE_FRAMES = A + B;

export const FeatureSamples: React.FC = () => (
  <AbsoluteFill style={{background: '#000'}}>
    <style>{fontCss}</style>
    <Sequence from={0} durationInFrames={A}>
      <Fade dur={A}>
        <Receipts />
      </Fade>
    </Sequence>
    <Sequence from={A} durationInFrames={B}>
      <Fade dur={B}>
        <Guess />
      </Fade>
    </Sequence>
    <Handle />
  </AbsoluteFill>
);
