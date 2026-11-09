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

test('native document and inner scrollbars use theme tokens with rounded hover enhancement and forced-colors fallback', () => {
  const css = readFileSync(new URL('../src/shared/styles/global.css', import.meta.url), 'utf8');
  assert.match(css, /@media \(forced-colors: none\)/);
  assert.match(css, /@media \(forced-colors: active\)/);
  const themed = css.slice(css.indexOf('@media (forced-colors: none)'), css.indexOf('@media (forced-colors: active)'));
  const forced = css.slice(css.indexOf('@media (forced-colors: active)'));
  assert.match(themed, /html, html \*\s*\{[^}]*scrollbar-width: thin;[^}]*scrollbar-color: var\(--color-border\) transparent;/);
  assert.match(themed, /@supports selector\(::-webkit-scrollbar\)/);
  // Native standard properties must not override WebKit parts, including the existing catalog rule.
  const native = /html:root, html:root \*\s*\{[^}]*scrollbar-width: auto;[^}]*scrollbar-color: auto;/;
  assert.match(themed, native);
  assert.match(forced, native);
  assert.match(themed, /::-webkit-scrollbar\s*\{[^}]*width: 12px;[^}]*height: 12px;/);
  assert.match(themed, /::-webkit-scrollbar-track\s*\{[^}]*background: transparent;/);
  assert.match(themed, /::-webkit-scrollbar-thumb\s*\{[^}]*background: var\(--color-border\);[^}]*border: 4px solid transparent;[^}]*background-clip: padding-box;[^}]*border-radius: var\(--radius-pill\);/);
  assert.match(themed, /::-webkit-scrollbar-thumb:hover\s*\{[^}]*background-color: var\(--color-secondary\);/);
  assert.doesNotMatch(forced, /::-webkit-scrollbar/);
  assert.doesNotMatch(css, /scrollbar-width:\s*none|::-webkit-scrollbar\s*\{[^}]*display:\s*none|scroll-behavior:\s*smooth/);
});

test('S1 cream/ink/orange is exported without low-contrast orange body text', () => {
  const colors = JSON.parse(readFileSync(new URL('../../documents/Omnis_Design.tokens.json', import.meta.url))).color;
  for (const [role, hex] of Object.entries({ 'light-neutral': '#f3eee3', 'light-text': '#111111', 'light-accent': '#b87759', 'light-accentInk': '#111111' })) assert.equal(colors[role]?.$value.hex, hex);
  assert.notEqual(colors['light-primary'].$value.hex, colors['light-accent']?.$value.hex);
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
      ['accentInk', ['accent'], 4.5],
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
