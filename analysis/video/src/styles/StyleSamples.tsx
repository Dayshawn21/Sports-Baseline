// Three alternative looks, ~7 seconds each, using the Dallas numbers:
// 1) Broadcast / scoreboard  2) Trading card  3) Video-game ratings.
// All generic designs: no network, card-company or game branding; no logos or player images.
import React from 'react';
import {AbsoluteFill, Img, Sequence, interpolate, spring, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import {data, theme} from '../data';
import {preview} from '../previewData';
import {body, display, fontCss, mono} from '../Video';

const dal = data.teams[0];
const SCENE = 225; // 7.5 s each
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;

const Label: React.FC<{n: number; name: string}> = ({n, name}) => (
  <div style={{position: 'absolute', top: 90, right: 80, ...body, fontSize: 28, color: theme.text2}}>
    Style {n}: {name}
  </div>
);
const Handle: React.FC = () => (
  <div style={{position: 'absolute', top: 80, left: 80, display: 'flex', alignItems: 'center', gap: 14}}>
    <Img src={staticFile('logo.png')} style={{width: 56, borderRadius: 12}} />
    <span style={{...body, fontSize: 28}}>@numbersbehindthegame</span>
  </div>
);

// ============ 1. BROADCAST ============
const ScoreBug: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f, fps, config: {damping: 16}});
  const Team = ({abbr, rec, hi}: {abbr: string; rec: string; hi?: boolean}) => (
    <div style={{display: 'flex', alignItems: 'center', gap: 16, padding: '0 26px', height: '100%', background: hi ? theme.accent : '#1a1a20'}}>
      <span style={{...display, fontSize: 56, color: hi ? '#000' : theme.text}}>{abbr}</span>
      <span style={{...mono, fontSize: 36, color: hi ? '#000' : theme.text2}}>{rec}</span>
    </div>
  );
  return (
    <div style={{position: 'absolute', top: 190, left: 80, height: 90, display: 'flex', border: `4px solid ${theme.text}`, transform: `translateY(${(1 - s) * -160}px)`}}>
      <Team abbr="DAL" rec="2-4" hi />
      <div style={{...display, fontSize: 40, color: theme.text2, alignSelf: 'center', padding: '0 14px', background: '#000', height: '100%', display: 'flex', alignItems: 'center'}}>@</div>
      <Team abbr="PHI" rec="2-4" />
      <div style={{background: '#000', color: theme.text, ...display, fontSize: 36, display: 'flex', alignItems: 'center', padding: '0 22px'}}>
        MON · 7:15 CT
      </div>
    </div>
  );
};

const LowerThird: React.FC<{at: number; y: number; kicker: string; title: string; value: string; hi?: boolean}> = ({at, y, kicker, title, value, hi}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const s = spring({frame: f - at, fps, config: {damping: 18}});
  const wipe = interpolate(f - at, [6, 20], [0, 100], clamp);
  return (
    <div style={{position: 'absolute', left: 80, top: y, width: 920, transform: `translateX(${(1 - s) * -1100}px)`}}>
      <div style={{...display, fontSize: 34, color: '#000', background: theme.accent, display: 'inline-block', padding: '6px 18px', letterSpacing: 2}}>{kicker}</div>
      <div style={{display: 'flex', alignItems: 'stretch', background: '#14141a', borderLeft: `14px solid ${hi ? theme.accent : theme.text}`, clipPath: `inset(0 ${100 - wipe}% 0 0)`}}>
        <div style={{...display, fontSize: 72, color: theme.text, padding: '18px 30px', flex: 1}}>{title}</div>
        <div style={{...mono, fontSize: 80, color: hi ? '#000' : theme.text, background: hi ? theme.accent : '#24242c', padding: '14px 34px', display: 'flex', alignItems: 'center'}}>{value}</div>
      </div>
    </div>
  );
};

const Ticker: React.FC = () => {
  const f = useCurrentFrame();
  const text = `NFC EAST: NYG 3-2-1 · DAL 2-4 · PHI 2-4 · WAS 1-4-1   ●   DAL 1-3 IN ONE-SCORE GAMES   ●   PHI QB JALEN HURTS OUT FOR SEASON   ●   DAL PLAYOFF CHANCE ABOUT 1 IN ${dal.playoffOneIn}   ●   `;
  const x = -((f * 7) % 2600);
  return (
    <div style={{position: 'absolute', left: 0, top: 1490, width: 1080, height: 76, background: '#0d0d12', borderTop: `4px solid ${theme.accent}`, overflow: 'hidden', display: 'flex', alignItems: 'center'}}>
      <div style={{...display, fontSize: 36, background: theme.accent, color: '#000', padding: '0 22px', height: '100%', display: 'flex', alignItems: 'center', zIndex: 2}}>PREGAME</div>
      <div style={{whiteSpace: 'nowrap', transform: `translateX(${x}px)`, ...display, fontSize: 40, color: theme.text, paddingLeft: 30}}>
        {text}
        {text}
      </div>
    </div>
  );
};

const Broadcast: React.FC = () => (
  <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 35%, #12233f 0%, #000 70%)'}}>
    <ScoreBug />
    <div style={{position: 'absolute', top: 360, left: 80, ...display, fontSize: 120, lineHeight: 0.95}}>
      Can Dallas
      <br />
      <span style={{color: theme.accent}}>save it?</span>
    </div>
    <LowerThird at={20} y={650} kicker="Defense" title="League rank" value={`${dal.defenseRank}/32`} hi />
    <LowerThird at={55} y={860} kicker="Offense" title="League rank" value={`${dal.offenseRank}/32`} />
    <LowerThird at={90} y={1070} kicker="Real or lucky" title="Points say" value={`${dal.pointsSayWins} W`} hi />
    <LowerThird at={125} y={1280} kicker="Close games" title="One-score record" value="1-3" />
    <Ticker />
  </AbsoluteFill>
);

// ============ 2. TRADING CARD ============
const Card: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const flip = spring({frame: f - 20, fps, config: {damping: 14, mass: 1.2}});
  const angle = interpolate(flip, [0, 1], [180, 0]);
  const showFront = angle < 90;
  const enter = spring({frame: f, fps, config: {damping: 14}});
  const shine = interpolate((f - 60) % 90, [0, 40], [-120, 220], clamp);
  const float = Math.sin(f / 18) * 8;
  const W = 760;
  const H = 1060;
  const Row = ({k, v, hi, at}: {k: string; v: string; hi?: boolean; at: number}) => (
    <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', borderBottom: `2px solid #2a2a33`, padding: '11px 0', opacity: interpolate(f - at, [0, 8], [0, 1], clamp)}}>
      <span style={{...display, fontSize: 46, color: theme.text2}}>{k}</span>
      <span style={{...mono, fontSize: 52, color: hi ? theme.accent : theme.text}}>{v}</span>
    </div>
  );
  return (
    <AbsoluteFill style={{background: 'radial-gradient(circle at 50% 50%, #0f1a2e 0%, #000 75%)', perspective: 2200}}>
      <div
        style={{
          position: 'absolute',
          left: (1080 - W) / 2,
          top: 330 + float,
          width: W,
          height: H,
          transformStyle: 'preserve-3d',
          transform: `scale(${enter}) rotateY(${angle}deg) rotateZ(${(1 - flip) * -6}deg)`,
        }}
      >
        {showFront ? (
          <div style={{position: 'absolute', inset: 0, borderRadius: 36, padding: 22, background: `linear-gradient(135deg, ${theme.accent}, #6fe0ff 40%, #0a6fa0)`}}>
            <div style={{position: 'absolute', inset: 22, borderRadius: 24, background: '#0b0b10', padding: '40px 44px', overflow: 'hidden'}}>
              <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
                <span style={{...display, fontSize: 40, color: theme.accent, letterSpacing: 3}}>NBTG · 2026 · WK 6</span>
                <span style={{...display, fontSize: 34, color: '#000', background: theme.accent, padding: '4px 14px', borderRadius: 8}}>RARE</span>
              </div>
              <div style={{...display, fontSize: 130, marginTop: 24, lineHeight: 0.9}}>Dallas</div>
              <div style={{...mono, fontSize: 92, color: theme.accent, marginTop: 4}}>2-4</div>
              <div style={{marginTop: 18}}>
                <Row k="OFFENSE RANK" v={`#${dal.offenseRank}`} at={50} />
                <Row k="DEFENSE RANK" v={`#${dal.defenseRank}`} hi at={60} />
                <Row k="POINTS SAY" v={`${dal.pointsSayWins} wins`} hi at={70} />
                <Row k="ONE-SCORE GAMES" v="1-3" at={80} />
                <Row k="PLAYOFF CHANCE" v={`1 in ${dal.playoffOneIn}`} at={90} />
              </div>
              <div style={{marginTop: 26, ...body, fontSize: 30, color: theme.text2, opacity: interpolate(f - 110, [0, 10], [0, 1], clamp)}}>
                Special ability: plays close games… loses most of them.
              </div>
              {/* foil shine */}
              <div style={{position: 'absolute', top: -200, bottom: -200, width: 160, left: `${shine}%`, transform: 'rotate(20deg)', background: 'linear-gradient(90deg, transparent, rgba(255,255,255,0.22), transparent)'}} />
            </div>
          </div>
        ) : (
          <div style={{position: 'absolute', inset: 0, borderRadius: 36, transform: 'rotateY(180deg)', background: `repeating-linear-gradient(45deg, #0b1830 0 30px, #0e2040 30px 60px)`, border: `22px solid ${theme.accent}`, display: 'flex', alignItems: 'center', justifyContent: 'center'}}>
            <Img src={staticFile('logo.png')} style={{width: 320, borderRadius: 50}} />
          </div>
        )}
      </div>
      <div style={{position: 'absolute', top: 1440, width: 1080, textAlign: 'center', ...display, fontSize: 64, opacity: interpolate(f - 120, [0, 10], [0, 1], clamp)}}>
        Keep or trade? <span style={{color: theme.accent}}>Comment below.</span>
      </div>
    </AbsoluteFill>
  );
};

// ============ 3. VIDEO-GAME RATINGS ============
// Illustrative 59-99 scale from league rank: rank 1 = 99, rank 32 = 59.
const rating = (rank: number) => Math.round(99 - ((rank - 1) * 40) / 31);

const RatingRow: React.FC<{at: number; label: string; value: number; sub: string; hi?: boolean}> = ({at, label, value, sub, hi}) => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const g = spring({frame: f - at, fps, config: {damping: 20}});
  const shown = Math.round(interpolate(g, [0, 1], [40, value]));
  const pct = ((shown - 40) / 59) * 100;
  return (
    <div style={{marginTop: 60, opacity: interpolate(f - at, [0, 6], [0, 1], clamp)}}>
      <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'baseline'}}>
        <span style={{...display, fontSize: 60}}>{label}</span>
        <span style={{...mono, fontSize: 80, color: hi ? theme.accent : theme.text}}>{shown}</span>
      </div>
      <div style={{height: 34, background: '#1d1d24', marginTop: 8, clipPath: 'polygon(0 0, 100% 0, 98% 100%, 0 100%)'}}>
        <div style={{height: '100%', width: `${pct}%`, background: hi ? theme.accent : theme.text, clipPath: 'polygon(0 0, 100% 0, 97% 100%, 0 100%)'}} />
      </div>
      <div style={{...body, fontSize: 30, marginTop: 8}}>{sub}</div>
    </div>
  );
};

const Ratings: React.FC = () => {
  const f = useCurrentFrame();
  const {fps} = useVideoConfig();
  const off = rating(dal.offenseRank);
  const def = rating(dal.defenseRank);
  const ovr = Math.round((off + def) / 2);
  const ring = spring({frame: f - 10, fps, config: {damping: 20}});
  const ovrShown = Math.round(interpolate(ring, [0, 1], [40, ovr]));
  const R = 120;
  const C = 2 * Math.PI * R;
  const upg = spring({frame: f - 150, fps, config: {damping: 12}});
  const inj = preview.injuries[0].items[0];
  return (
    <AbsoluteFill style={{background: 'linear-gradient(160deg, #0d1424 0%, #000 60%)', padding: '290px 80px 0'}}>
      <div style={{display: 'flex', alignItems: 'center', gap: 40}}>
        <svg width={300} height={300}>
          <circle cx={150} cy={150} r={R} stroke="#1d1d24" strokeWidth={26} fill="none" />
          <circle cx={150} cy={150} r={R} stroke={theme.accent} strokeWidth={26} fill="none" strokeDasharray={C} strokeDashoffset={C * (1 - ((ovrShown - 40) / 59) * ring)} transform="rotate(-90 150 150)" strokeLinecap="round" />
          <text x={150} y={168} textAnchor="middle" fill={theme.text} style={{...mono, fontSize: 96}}>{ovrShown}</text>
          <text x={150} y={218} textAnchor="middle" fill={theme.text2} style={{...display, fontSize: 34}}>OVR</text>
        </svg>
        <div>
          <div style={{...display, fontSize: 40, color: theme.accent, letterSpacing: 3}}>TEAM RATINGS</div>
          <div style={{...display, fontSize: 130, lineHeight: 0.9}}>Dallas</div>
          <div style={{...mono, fontSize: 44, color: theme.text2}}>2-4 · week 6</div>
        </div>
      </div>
      <RatingRow at={40} label="Offense" value={off} sub={`#${dal.offenseRank} of 32 in points added per play`} />
      <RatingRow at={70} label="Defense" value={def} sub={`#${dal.defenseRank} of 32: dead last`} hi />
      <div
        style={{
          marginTop: 60,
          border: `4px solid ${theme.accent}`,
          padding: '22px 28px',
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          transform: `scale(${upg})`,
          transformOrigin: 'left center',
          background: 'rgba(9,189,254,0.08)',
        }}
      >
        <span style={{...display, fontSize: 70, color: theme.accent}}>▲</span>
        <div>
          <div style={{...display, fontSize: 44, color: theme.accent}}>Upgrade incoming</div>
          <div style={{...body, fontSize: 34, color: theme.text}}>
            {inj.player} ({inj.pos}) returns tonight
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', top: 1500, left: 80, ...body, fontSize: 26, opacity: interpolate(f - 60, [0, 10], [0, 1], clamp)}}>
        Ratings are NBTG's 59-99 scale from league rank, for fun, not a model.
      </div>
    </AbsoluteFill>
  );
};

const Fade: React.FC<{children: React.ReactNode}> = ({children}) => {
  const f = useCurrentFrame();
  const o = interpolate(f, [0, 6, SCENE - 8, SCENE], [0, 1, 1, 0], clamp);
  return <AbsoluteFill style={{opacity: o}}>{children}</AbsoluteFill>;
};

export const STYLE_FRAMES = SCENE * 3;

export const StyleSamples: React.FC = () => (
  <AbsoluteFill style={{background: '#000'}}>
    <style>{fontCss}</style>
    <Sequence from={0} durationInFrames={SCENE}>
      <Fade>
        <Broadcast />
        <Label n={1} name="Broadcast" />
      </Fade>
    </Sequence>
    <Sequence from={SCENE} durationInFrames={SCENE}>
      <Fade>
        <Card />
        <Label n={2} name="Trading card" />
      </Fade>
    </Sequence>
    <Sequence from={SCENE * 2} durationInFrames={SCENE}>
      <Fade>
        <Ratings />
        <Label n={3} name="Game ratings" />
      </Fade>
    </Sequence>
    <Handle />
  </AbsoluteFill>
);
