import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';
import { readFileSync } from 'node:fs';

test('design export produces local tokens/fonts with provenance and detects drift', () => {
  const script = new URL('sync-design.mjs', import.meta.url);
  const run = spawnSync(process.execPath, [fileURLToPath(script), '--check'], { encoding: 'utf8', timeout: 10000 });
  assert.equal(run.status, 0, 'Design assets must be generated from the accepted local baseline');
});

test('both palettes export the same roles and keep text, states and focus readable', () => {
  const colors = JSON.parse(readFileSync(new URL('../../documents/Omnis_Design.tokens.json', import.meta.url))).color;
  const css = readFileSync(new URL('../src/shared/styles/tokens.css', import.meta.url), 'utf8');
  const [dark, light] = css.split(':root[data-theme="light"]');
  const roles = Object.keys(colors).filter(name => !name.startsWith('$') && !name.startsWith('light-'));
  assert.deepEqual(Object.keys(colors).filter(name => name.startsWith('light-')).map(name => name.slice(6)), roles);
  function luminance(hex) {
    const channels = hex.slice(1).match(/../g).map(value => parseInt(value, 16) / 255)
      .map(value => value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
    return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
  }
  for (const [prefix, block] of [['', dark], ['light-', light]]) {
    for (const role of roles) assert.ok(block.includes(`--color-${role}: ${colors[prefix + role].$value.hex};`), `${prefix}${role} must reach CSS`);
    for (const [foreground, backgrounds, minimum] of [
      ['text', ['neutral', 'surface', 'elevated', 'selected'], 4.5],
      ['secondary', ['neutral', 'surface', 'elevated', 'selected'], 4.5],
      ['primary', ['neutral', 'surface', 'selected'], 4.5],
      ['danger', ['neutral', 'surface', 'dangerBg'], 4.5],
      ['warning', ['warningBg'], 4.5], ['success', ['successBg'], 4.5], ['info', ['infoBg'], 4.5],
      ['focus', ['neutral', 'surface', 'selected'], 3], ['border', ['neutral', 'surface'], 3],
    ]) {
      for (const background of backgrounds) {
        const a = luminance(colors[prefix + foreground].$value.hex), b = luminance(colors[prefix + background].$value.hex);
        const ratio = (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
        assert.ok(ratio >= minimum, `${prefix}${foreground}/${background}: ${ratio.toFixed(2)} < ${minimum}`);
      }
    }
  }
});
