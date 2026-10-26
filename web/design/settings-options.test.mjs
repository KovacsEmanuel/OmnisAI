// Offline design check only; never starts Omnis, a DB, or a provider.
import assert from 'node:assert/strict';
import { mkdir, readFile } from 'node:fs/promises';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { chromium, expect } from '../node_modules/@playwright/test/index.mjs';

const source = new URL('./settings-options.html', import.meta.url);
const html = await readFile(source, 'utf8');
assert.match(html, /MOCKUP/);
assert.doesNotMatch(html, /\b(?:fetch|XMLHttpRequest|WebSocket|localStorage|sessionStorage)\b/);
const output = process.env.OMNIS_DESIGN_OUTPUT;
if (output) {
  const scratch = resolve(process.env.TMPDIR || '/home/kali/.hermes/cache/scratch');
  assert.ok(resolve(output).startsWith(scratch + '/'), 'Screenshots belong under the configured scratch root');
  await mkdir(output, { recursive: true });
}
const browser = await chromium.launch();
const errors = [];
const external = [];
const root = fileURLToPath(new URL('../../', import.meta.url));
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
await context.route('**/*', async route => {
  const url = route.request().url();
  if (url.startsWith('file:') && fileURLToPath(url).startsWith(root)) await route.continue();
  else { external.push(url); await route.abort(); }
});
const page = await context.newPage();
page.on('pageerror', error => errors.push(error.message));
page.on('console', message => { if (message.type() === 'error') errors.push(message.text()); });
async function screenshot(name) {
  if (output) await page.screenshot({ path: join(output, name + '.png'), fullPage: true });
}
async function fits() {
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'No page-wide horizontal overflow');
}
try {
  await page.goto(source.href);
  await page.evaluate(() => document.fonts.ready);
  const variants = ['a', 'b', 'c'];
  assert.equal(await page.locator('[data-variant-button]').count(), variants.length);
  for (const variant of variants) {
    await page.locator(`[data-variant-button="${variant}"]`).click();
    await page.locator('#demo-state').selectOption('empty');
    await expect(page.locator('#workspace')).toHaveAttribute('data-variant', variant);
    await expect(page.locator('#api-key')).toHaveAttribute('readonly', '');
    await screenshot(variant + '-desktop-empty');
    if (variant === 'c') {
      await page.getByRole('button', { name: 'Continuă', exact: true }).click();
      await page.getByRole('button', { name: 'Continuă', exact: true }).click();
      await expect(page.locator('#review-model')).toHaveText('openai/gpt-4.1-mini');
    }
    await page.getByRole('button', { name: 'Salvează și verifică', exact: true }).click();
    await expect(page.locator('#status-title')).toHaveText('Se verifică modelul…');
    await expect(page.getByRole('button', { name: 'Modifică', exact: true })).toBeDisabled();
    await page.locator('#edit').evaluate(element => element.click());
    await expect(page.getByRole('button', { name: 'Anulează testul', exact: true })).toBeVisible();
    await expect(page.locator('#status-title')).toHaveText('Model conectat');
    await expect(page.locator('#saved-summary')).toBeVisible();
    await expect(page.locator('#toast')).toContainText('Model conectat');
    await expect(page.locator('#api-key')).toHaveValue('');
    await screenshot(variant + '-desktop-connected');
    await page.getByRole('button', { name: 'Modifică', exact: true }).click();
    await expect(page.getByLabel('Model exact')).toBeVisible();
    await expect(page.getByLabel('Model exact')).toBeFocused();
    await page.getByLabel('Model exact').fill('demo/' + variant + '-edited');
    await expect(page.locator('#status-title')).toHaveText('Modificări neverificate');
    if (variant === 'c') {
      await page.getByRole('button', { name: 'Continuă', exact: true }).click();
      await expect(page.locator('#review-model')).toHaveText('demo/c-edited');
      await page.getByRole('button', { name: 'Înapoi', exact: true }).click();
      await expect(page.getByLabel('Model exact')).toBeVisible();
      await page.getByRole('button', { name: 'Continuă', exact: true }).click();
    }
    await page.locator('#advanced > summary').click();
    await expect(page.getByLabel('Model Brain')).toBeVisible();
    await expect(page.getByLabel('Model Investigator')).toBeVisible();
    await expect(page.getByLabel('Model Validator')).toBeVisible();
    for (const state of ['error', 'unknown', 'locked', 'revoked']) {
      await page.locator('#demo-state').selectOption(state);
      await expect(page.locator('#status')).toBeVisible();
      await expect(page.locator('#status-title')).not.toHaveText('Model conectat');
      if (state === 'unknown') {
        await expect(page.getByRole('button', { name: 'Modifică', exact: true })).toBeDisabled();
        await page.locator('#edit').evaluate(element => element.click());
        await expect(page.getByRole('button', { name: 'Citește starea', exact: true })).toBeVisible();
      }
      if (state === 'locked') await expect(page.getByRole('button', { name: 'Verifică modelul', exact: true })).toBeDisabled();
    }
    for (const width of [320, 390, 1280, 1440]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.locator('#demo-state').selectOption('empty');
      await fits();
      if (width === 390) await screenshot(variant + '-mobile-empty');
    }
  }
  await page.locator('[data-variant-button="a"]').click();
  await page.locator('#demo-state').selectOption('empty');
  await page.getByRole('button', { name: 'Salvează', exact: true }).click();
  await expect(page.locator('#status-title')).toHaveText('Configurație salvată');
  await expect(page.locator('#status-copy')).toContainText('nu a fost testat');
  await page.locator('#demo-outcome').selectOption('error');
  await page.getByRole('button', { name: 'Verifică modelul', exact: true }).click();
  await expect(page.locator('#status-title')).toHaveText('Verificare nereușită');
  await expect(page.locator('#saved-summary')).toBeVisible();
  await screenshot('a-desktop-error');
  await page.locator('#demo-outcome').selectOption('unknown');
  await page.getByRole('button', { name: 'Verifică modelul', exact: true }).click();
  await expect(page.locator('#status-title')).toHaveText('Rezultat neconfirmat');
  await expect(page.locator('#status-copy')).toContainText('nu repetă');
  await page.locator('#demo-state').selectOption('saved');
  await page.getByRole('button', { name: 'Modifică', exact: true }).click();
  const model = page.getByLabel('Model exact');
  await model.fill('<img src=x onerror=alert(1)>');
  await page.getByRole('button', { name: 'Salvează', exact: true }).click();
  await expect(page.locator('#saved-model')).not.toHaveText('<img src=x onerror=alert(1)>');
  await model.fill('demo/<b>literal</b>');
  await page.getByRole('button', { name: 'Salvează', exact: true }).click();
  await expect(page.locator('#saved-model')).toHaveText('demo/<b>literal</b>');
  assert.equal(await page.locator('#saved-model b').count(), 0, 'Model IDs render as inert text');
  await page.locator('#demo-state').selectOption('empty');
  await page.keyboard.press('Control+Home');
  await page.locator('.skip').focus();
  await page.keyboard.press('Enter');
  await expect(page.locator('#prototype')).toBeFocused();
  await model.focus();
  assert.notEqual(await model.evaluate(element => getComputedStyle(element).outlineStyle), 'none');
  await page.evaluate(() => { document.documentElement.style.zoom = '2'; });
  await fits();
  await expect(page.getByRole('button', { name: 'Salvează și verifică', exact: true })).toBeVisible();
  await page.evaluate(() => { document.documentElement.style.zoom = ''; });
  await page.locator('#demo-state').selectOption('empty');
  await page.getByRole('button', { name: 'Salvează și verifică', exact: true }).click();
  await page.getByRole('button', { name: 'Anulează testul', exact: true }).click();
  await expect(page.locator('#status-title')).toHaveText('Test anulat local');
  await page.waitForTimeout(900);
  await expect(page.locator('#status-title')).toHaveText('Test anulat local');
  await page.locator('#demo-state').selectOption('empty');
  await page.getByRole('button', { name: 'Salvează și verifică', exact: true }).click();
  await page.locator('[data-variant-button="b"]').click();
  await page.waitForTimeout(900);
  await expect(page.locator('#status-title')).toHaveText('Nicio conexiune configurată');
  await page.reload();
  await expect(page.locator('#status-title')).toHaveText('Nicio conexiune configurată');
  assert.deepEqual(errors, [], 'No browser or CSP errors');
  assert.deepEqual(external, [], 'No external requests');
  console.log(JSON.stringify({ result: 'PASS', artifact: fileURLToPath(source), variants, widths: [320, 390, 1280, 1440], browser: browser.version(), external_requests: external.length, console_errors: errors.length, screenshots: output || 'not requested', boundary: 'Offline mockup only; no real persistence, provider, CLI, pairing or product regression proof' }, null, 2));
} finally {
  await context.close();
  await browser.close();
}
