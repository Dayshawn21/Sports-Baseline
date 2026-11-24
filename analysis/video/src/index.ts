import React from 'react';
import {Composition, registerRoot} from 'remotion';
import {SaveTheSeason, TOTAL_FRAMES} from './Video';
import {MnfPreview, previewFrames} from './Preview';
import {DallasPreview, dallasFrames} from './DallasPreview';
import {ComicSample, COMIC_FRAMES} from './comic/ComicSample';
import {HybridDallas, hybridFrames} from './HybridDallas';
import {StyleSamples, STYLE_FRAMES} from './styles/StyleSamples';
import {FeatureSamples, FEATURE_FRAMES} from './styles/FeatureSamples';
import {RealOrLucky, RealOrLuckyProps, exampleRealOrLucky, realOrLuckyFrames} from './RealOrLucky';
const Root: React.FC = () =>
  React.createElement(
    React.Fragment,
    null,
    React.createElement(Composition, {
      id: 'SaveTheSeason',
      component: SaveTheSeason,
      durationInFrames: TOTAL_FRAMES,
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'MnfPreview',
      component: MnfPreview,
      durationInFrames: previewFrames(),
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'DallasPreview',
      component: DallasPreview,
      durationInFrames: dallasFrames(),
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'ComicSample',
      component: ComicSample,
      durationInFrames: COMIC_FRAMES,
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'HybridDallas',
      component: HybridDallas,
      durationInFrames: hybridFrames(),
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'StyleSamples',
      component: StyleSamples,
      durationInFrames: STYLE_FRAMES,
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'FeatureSamples',
      component: FeatureSamples,
      durationInFrames: FEATURE_FRAMES,
      fps: 30,
      width: 1080,
      height: 1920,
    }),
    React.createElement(Composition, {
      id: 'RealOrLucky',
      component: RealOrLucky,
      durationInFrames: realOrLuckyFrames(),
      // The history scene appears only for an unbeaten team, so the length follows the props passed in.
      calculateMetadata: ({props}: {props: RealOrLuckyProps}) => ({durationInFrames: realOrLuckyFrames(props)}),
      fps: 30,
      width: 1080,
      height: 1920,
      defaultProps: exampleRealOrLucky,
    }),
  );

registerRoot(Root);
