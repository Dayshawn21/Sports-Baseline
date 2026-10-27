// Reusable comic / manga building blocks, all drawn with CSS + SVG (no artwork needed).
import React from 'react';
import {interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {theme} from '../data';

export const INK = '#000000';
export const PAPER = '#f5f5f7';
export const YELLOW = '#ffd23f'; // narration boxes only

// Halftone dot pattern as a CSS background.
export const halftone = (color: string, size = 18, dot = 4): React.CSSProperties => ({
  backgroundImage: `radial-gradient(${color} ${dot}px, transparent ${dot + 0.5}px)`,
  backgroundSize: `${size}px ${size}px`,
});

// A panel that "slams" onto the page: scales down from big, with a tiny shake.
export const Panel: React.FC<{
  at: number;
  x: number;
  y: number;
  w: number;
  h: number;
  tilt?: number;
  bg?: string;
  style?: React.CSSProperties;
  children?: React.ReactNode;
}> = ({at, x, y, w, h, tilt = 0, bg = '#0b0b0e', style, children}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 11, stiffness: 180}});
  const shake = f - at > 0 && f - at < 8 ? (random(`s${f}`) - 0.5) * 10 : 0;
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        height: h,
        background: bg,
        border: `8px solid ${PAPER}`,
        boxShadow: `10px 10px 0 ${theme.accent}`,
        transform: `rotate(${tilt}deg) scale(${interpolate(s, [0, 1], [1.25, 1])}) translate(${shake}px, ${-shake}px)`,
        opacity: s,
        overflow: 'hidden',
        ...style,
      }}
    >
      {children}
    </div>
  );
};

// Manga speed lines radiating from a point.
export const SpeedLines: React.FC<{cx: number; cy: number; w: number; h: number; color?: string; count?: number}> = ({
  cx,
  cy,
  w,
  h,
  color = PAPER,
  count = 70,
}) => {
  const f = useCurrentFrame();
  const R = Math.hypot(w, h);
  return (
    <svg width={w} height={h} style={{position: 'absolute', left: 0, top: 0}}>
      {Array.from({length: count}).map((_, i) => {
        const a = (i / count) * Math.PI * 2 + random(`a${i}`) * 0.05;
        const inner = 230 + random(`r${i}-${Math.floor(f / 3)}`) * 140;
        const spread = 0.006 + random(`w${i}`) * 0.012;
        const p = (ang: number, r: number) => `${cx + Math.cos(ang) * r},${cy + Math.sin(ang) * r}`;
        return (
          <polygon
            key={i}
            points={`${p(a, inner)} ${p(a - spread, R)} ${p(a + spread, R)}`}
            fill={color}
            opacity={0.55}
          />
        );
      })}
    </svg>
  );
};

// Jagged starburst behind a shout.
export const Burst: React.FC<{size: number; color: string; points?: number; at?: number; style?: React.CSSProperties; children?: React.ReactNode}> = ({
  size,
  color,
  points = 14,
  at = 0,
  style,
  children,
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 9, stiffness: 200}});
  const r1 = size / 2;
  const r2 = size / 2.8;
  const pts = Array.from({length: points * 2})
    .map((_, i) => {
      const r = i % 2 ? r2 : r1 * (0.88 + random(`b${i}`) * 0.12);
      const a = (i / (points * 2)) * Math.PI * 2;
      return `${r1 + Math.cos(a) * r},${r1 + Math.sin(a) * r}`;
    })
    .join(' ');
  return (
    <div style={{position: 'absolute', width: size, height: size, transform: `scale(${s}) rotate(${(1 - s) * -30}deg)`, ...style}}>
      <svg width={size} height={size} style={{position: 'absolute'}}>
        <polygon points={pts} fill={color} stroke={INK} strokeWidth={8} strokeLinejoin="round" />
      </svg>
      <div style={{position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', textAlign: 'center'}}>
        {children}
      </div>
    </div>
  );
};

// Comic lettering: bold, outlined, slightly skewed.
export const Sfx: React.FC<{size: number; color?: string; stroke?: string; skew?: number; style?: React.CSSProperties; children: React.ReactNode}> = ({
  size,
  color = theme.accent,
  stroke = INK,
  skew = -8,
  style,
  children,
}) => (
  <div
    style={{
      fontFamily: 'Barlow Condensed',
      fontWeight: 800,
      fontSize: size,
      lineHeight: 0.9,
      textTransform: 'uppercase',
      color,
      WebkitTextStroke: `${Math.max(4, size / 18)}px ${stroke}`,
      paintOrder: 'stroke fill',
      transform: `skew(${skew}deg)`,
      textShadow: `6px 6px 0 ${INK}`,
      ...style,
    }}
  >
    {children}
  </div>
);

// Speech bubble with a tail. Text types on over time.
export const Bubble: React.FC<{
  at: number;
  x: number;
  y: number;
  w: number;
  text: string;
  tail?: 'left' | 'right' | 'down';
  size?: number;
}> = ({at, x, y, w, text, tail = 'down', size = 46}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 12}});
  const chars = Math.floor(interpolate(f - at, [4, 4 + text.length * 0.9], [0, text.length], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'}));
  const tailPos: Record<string, React.CSSProperties> = {
    down: {left: w * 0.3, bottom: -44, borderWidth: '46px 26px 0 26px', borderColor: `${INK} transparent transparent transparent`},
    left: {left: -40, top: 40, borderWidth: '22px 46px 22px 0', borderColor: `transparent ${INK} transparent transparent`},
    right: {right: -40, top: 40, borderWidth: '22px 0 22px 46px', borderColor: `transparent transparent transparent ${INK}`},
  };
  const tailInner: Record<string, React.CSSProperties> = {
    down: {left: w * 0.3 + 8, bottom: -30, borderWidth: '36px 18px 0 18px', borderColor: `${PAPER} transparent transparent transparent`},
    left: {left: -28, top: 48, borderWidth: '14px 34px 14px 0', borderColor: `transparent ${PAPER} transparent transparent`},
    right: {right: -28, top: 48, borderWidth: '14px 0 14px 34px', borderColor: `transparent transparent transparent ${PAPER}`},
  };
  return (
    <div style={{position: 'absolute', left: x, top: y, width: w, transform: `scale(${s})`, transformOrigin: '30% 100%'}}>
      <div
        style={{
          position: 'relative',
          background: PAPER,
          border: `7px solid ${INK}`,
          borderRadius: 48,
          padding: '28px 36px',
          fontFamily: 'DM Sans',
          fontWeight: 600,
          fontSize: size,
          lineHeight: 1.2,
          color: INK,
        }}
      >
        {text.slice(0, chars)}
        <span style={{opacity: 0}}>{text.slice(chars)}</span>
        <div style={{position: 'absolute', width: 0, height: 0, borderStyle: 'solid', ...tailPos[tail]}} />
        <div style={{position: 'absolute', width: 0, height: 0, borderStyle: 'solid', ...tailInner[tail]}} />
      </div>
    </div>
  );
};

// Yellow narration box, classic comic caption.
export const Caption: React.FC<{at: number; x: number; y: number; w: number; children: React.ReactNode}> = ({at, x, y, w, children}) => {
  const f = useCurrentFrame();
  const o = interpolate(f - at, [0, 6], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        width: w,
        opacity: o,
        background: YELLOW,
        border: `6px solid ${INK}`,
        padding: '14px 24px',
        fontFamily: 'Barlow Condensed',
        fontWeight: 800,
        fontSize: 44,
        textTransform: 'uppercase',
        color: INK,
        boxShadow: `6px 6px 0 ${INK}`,
      }}
    >
      {children}
    </div>
  );
};

// Original mascot: the logo tile with a face. Blinks and bounces.
export const Mascot: React.FC<{at: number; x: number; y: number; size: number; mood?: 'shock' | 'smart'}> = ({
  at,
  x,
  y,
  size,
  mood = 'smart',
}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 10}});
  const bob = Math.sin((f - at) / 6) * 6;
  const blink = (f - at) % 70 > 64;
  const S = size;
  return (
    <svg
      width={S}
      height={S * 1.15}
      style={{position: 'absolute', left: x, top: y + bob, transform: `scale(${s})`, overflow: 'visible'}}
      viewBox="0 0 200 230"
    >
      {/* head */}
      <rect x="10" y="40" width="180" height="170" rx="40" fill="#0b1830" stroke={PAPER} strokeWidth="8" />
      {/* bar "hair" from the logo */}
      <rect x="40" y="18" width="24" height="40" rx="4" fill={PAPER} stroke={INK} strokeWidth="5" />
      <rect x="72" y="8" width="24" height="50" rx="4" fill={PAPER} stroke={INK} strokeWidth="5" />
      <rect x="104" y="-2" width="24" height="60" rx="4" fill={PAPER} stroke={INK} strokeWidth="5" />
      <rect x="136" y="-20" width="26" height="78" rx="4" fill={theme.accent} stroke={INK} strokeWidth="5" />
      {/* glasses */}
      <circle cx="70" cy="115" r="30" fill={PAPER} stroke={INK} strokeWidth="7" />
      <circle cx="130" cy="115" r="30" fill={PAPER} stroke={INK} strokeWidth="7" />
      <line x1="100" y1="115" x2="100" y2="115" stroke={INK} strokeWidth="7" />
      {blink ? (
        <>
          <line x1="56" y1="117" x2="84" y2="117" stroke={INK} strokeWidth="7" strokeLinecap="round" />
          <line x1="116" y1="117" x2="144" y2="117" stroke={INK} strokeWidth="7" strokeLinecap="round" />
        </>
      ) : (
        <>
          <circle cx={mood === 'shock' ? 70 : 74} cy="118" r={mood === 'shock' ? 8 : 11} fill={INK} />
          <circle cx={mood === 'shock' ? 130 : 134} cy="118" r={mood === 'shock' ? 8 : 11} fill={INK} />
        </>
      )}
      {/* mouth */}
      {mood === 'shock' ? (
        <ellipse cx="100" cy="172" rx="18" ry="22" fill={INK} />
      ) : (
        <path d="M70 165 Q100 192 130 165" fill="none" stroke={PAPER} strokeWidth="8" strokeLinecap="round" />
      )}
    </svg>
  );
};
