# Numbers Behind the Game: example Remotion video

Save the Season preview (Cowboys vs Eagles), 1080x1920, 30 fps, ~27 seconds, no audio.

## Run it
npm install
npx remotion studio src/index.ts        # live preview in the browser
npx remotion render src/index.ts SaveTheSeason out/video.mp4

## Change it
- Numbers: src/data.ts (copy fresh values from the notebook before each video)
- Scenes, timing, text: src/Video.tsx (each scene is a component; durations are in frames, 30 = 1 second)
- Fonts and logo: public/

## Monday Night Football preview (MnfPreview)
npx remotion render src/index.ts MnfPreview out/mnf-preview.mp4

Before rendering on Monday, update src/previewData.ts:
- division: Giants and Commanders records after Sunday's games
- injuries: final statuses
- scenarios: win/lose playoff % from the notebook (the scene appears automatically once filled in)

## Dallas-only preview (DallasPreview)
npx remotion render src/index.ts DallasPreview out/dallas-preview.mp4
Uses the same src/previewData.ts, so the Monday-morning updates apply to it too.

## Comic style sample (ComicSample)
npx remotion render src/index.ts ComicSample out/comic-sample.mp4
Reusable comic pieces live in src/comic/Comic.tsx: Panel, SpeedLines, Burst, Sfx, Bubble, Caption, Mascot, halftone().

## Hybrid style (HybridDallas) — the chosen look
npx remotion render src/index.ts HybridDallas out/dallas-hybrid.mp4
Clean charts inside a comic panel frame; the mascot, speech bubbles, one burst and speed lines only at key moments.

## Style samples (StyleSamples)
Broadcast, trading card and game-ratings looks in src/styles/StyleSamples.tsx.

## Segment samples (FeatureSamples)
Prediction receipts (EXAMPLE data until real graded calls exist) and Guess the number, in src/styles/FeatureSamples.tsx.

## Real or Lucky? (RealOrLucky), data-driven
npx remotion render src/index.ts RealOrLucky out/real-or-lucky-min.mp4 --props=../output/week01-real-or-lucky-min-video.json
Reads the JSON that week01-real-or-lucky.ipynb writes, so nothing is typed by hand; rerun the notebook for a new team or week.
Clean Lineform look (no comic pieces): animated record-vs-points chart, score bug and source strip.
An unbeaten team gets an extra scene comparing it with every past team that started with the same record.
Without --props it shows a labelled made-up example.
