// Owned lab browser for the installed CLI-issued code, never the personal profile.
import assert from 'node:assert/strict';
import { chromium, expect } from '../../web/node_modules/@playwright/test/index.mjs';

const origin = process.env.OMNIS_BROWSER_ORIGIN;
const instance = process.env.OMNIS_BROWSER_INSTANCE;
assert.match(origin ?? '', /^http:\/\/127\.0\.0\.1:[0-9]+$/);
assert.match(instance ?? '', /^[0-9a-f-]{36}$/);
let code = '';
for await (const chunk of process.stdin) {
  code += chunk.toString();
  assert.ok(code.length <= 128, 'Oversized private input');
}
assert.match(code, /^[A-Za-z0-9_-]{16,128}$/);
const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const external = [];
  const requestUrls = [];
  const pageErrors = [];
  await context.route('**/*', async route => {
    const url = route.request().url();
    if (!url.startsWith(`${origin}/`)) { external.push('off-origin'); await route.abort(); }
    else await route.continue();
  });
  const page = await context.newPage();
  page.on('request', request => requestUrls.push(request.url()));
  page.on('pageerror', error => pageErrors.push(error.message));
  await page.goto(`${origin}/`);
  await expect(page.getByLabel('Pairing code')).toBeVisible();
  await page.getByLabel('Pairing code').fill(code);
  await page.getByRole('button', { name: 'Pair browser' }).click();
  await expect(page.getByText(instance, { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Start assessment' })).toBeDisabled();
  const cookie = (await context.cookies()).find(item => item.name === 'omnis_session');
  assert.ok(cookie?.httpOnly && cookie.sameSite === 'Strict');
  assert.equal((await context.request.get(`${origin}/api/session`)).status(), 200);
  await page.reload();
  await expect(page.getByText(instance, { exact: true })).toBeVisible();
  await page.getByRole('button', { name: 'Log out' }).click();
  await expect(page.getByText('Logged out. The server session was revoked.')).toBeVisible();
  assert.equal((await context.request.get(`${origin}/api/session`)).status(), 401);
  assert.ok(requestUrls.every(url => !url.includes(code)), 'Code appeared in a browser URL');
  assert.deepEqual(external, [], 'Off-origin browser request');
  assert.ok(pageErrors.every(message => !message.includes(code)), 'Code in browser exception');
  assert.deepEqual(pageErrors, [], 'Browser JavaScript failure');
  console.log('INSTALLED_BROWSER_SESSION_OK');
} finally {
  await browser.close();
  console.log('INSTALLED_BROWSER_CLOSED');
}
