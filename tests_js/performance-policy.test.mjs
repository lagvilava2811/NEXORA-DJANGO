import test from 'node:test';
import assert from 'node:assert/strict';

import { experiencePolicy } from '../static/performance-policy.mjs';


test('reduced motion always selects the static experience', () => {
  assert.deepEqual(experiencePolicy({ reducedMotion: true }), {
    tier: 'static',
    webgl: false,
    ambientVideo: false,
  });
});

test('save-data and slow connections select the lightweight experience', () => {
  assert.equal(experiencePolicy({ saveData: true }).tier, 'lite');
  assert.equal(experiencePolicy({ effectiveType: '2g' }).tier, 'lite');
  assert.equal(experiencePolicy({ effectiveType: 'slow-2g' }).tier, 'lite');
});

test('low-memory and low-core devices avoid WebGL and ambient video', () => {
  assert.deepEqual(experiencePolicy({ deviceMemory: 4, hardwareConcurrency: 4 }), {
    tier: 'lite',
    webgl: false,
    ambientVideo: false,
  });
});

test('small viewports use the lightweight experience even on powerful devices', () => {
  assert.deepEqual(
    experiencePolicy({
      viewportWidth: 375,
      deviceMemory: 8,
      hardwareConcurrency: 8,
    }),
    { tier: 'lite', webgl: false, ambientVideo: false },
  );
});

test('capable devices retain the full premium experience', () => {
  assert.deepEqual(
    experiencePolicy({
      reducedMotion: false,
      saveData: false,
      effectiveType: '4g',
      viewportWidth: 1440,
      deviceMemory: 8,
      hardwareConcurrency: 8,
    }),
    { tier: 'full', webgl: true, ambientVideo: true },
  );
});
