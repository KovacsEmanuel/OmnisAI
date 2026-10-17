// One authentic records-v3 publication, through the existing owned PG/browser family.
// No response mocking, publication INSERTs, evaluator, provider or native runtime here.
import assert from 'node:assert/strict';
import { readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';

export async function runCatalog({ page, check, paired, output, origin, screenshot, secretChecks }) {
  const expected = JSON.parse(await readFile(join(output, 'catalog-fixture.json'), 'utf8'));
  const pin = expected.publication_ref;
  const apiPath = `/api/v1/settings/catalog/publications/${pin.id}/${pin.digest}`;
  const selection = `/settings/skills?publication=${pin.id}&digest=${pin.digest}`;
  const responses = [];
  const failures = [];
  const isCatalog = url => url.startsWith(`${origin}/api/v1/settings/catalog`);
  const onResponse = response => {
    if (isCatalog(response.url())) responses.push({ method: response.request().method(),
      path: new URL(response.url()).pathname, status: response.status() });
  };
  const onFailure = request => {
    if (isCatalog(request.url())) failures.push({ method: request.method(),
      path: new URL(request.url()).pathname, error: request.failure()?.errorText ?? 'UNKNOWN' });
  };
  page.on('response', onResponse);
  page.on('requestfailed', onFailure);
  try {
    await paired();
    await page.getByRole('navigation', { name: 'Settings navigation' }).getByRole('link', { name: 'Skills', exact: true }).click();
    await check(page.getByRole('heading', { name: 'Published catalog', exact: true })).toBeVisible();
    const inspect = page.getByRole('button', { name: `Inspect ${expected.profile_key}`, exact: true });
    await check(inspect).toBeVisible();
    await check(page.getByRole('button', { name: /^Inspect / })).toHaveCount(1);
    const detail = page.getByRole('region', { name: 'Exact publication', exact: true });
    const reload = page.getByRole('button', { name: 'Reload read-only catalog', exact: true });

    async function exactView() {
      await check(detail).toBeVisible();
      await check(detail).toContainText(`${pin.id} · ${pin.digest}`);
      await check(detail).toContainText('Review: RECORDED_STATIC_PASS · STATIC: RECORDED_STATIC_PASS · PURE: RECORDED_PURE_PASS');
      await check(detail).toContainText('Dependency metadata: NO_EXTERNAL_DEPENDENCIES · Material: NOT_VERIFIED · Runtime: NOT_AVAILABLE');
      await check(detail).toContainText('BENCHMARK: NOT_VERIFIED · FIXTURE: NOT_VERIFIED · SECURITY: NOT_VERIFIED');
      await check(detail).toContainText('Resolution: NO_MODEL · Assessment selectable: no');
      await check(detail).toContainText('Effective model: not available.');
      for (const field of ['snapshot_ref', 'technical_review_ref', 'static_evaluation_ref', 'pure_evaluation_ref', 'confirmation_ref', 'profile_ref']) {
        const ref = expected[field];
        await check(detail).toContainText(`${ref.kind} · ${ref.id} · revision ${ref.revision} · ${ref.digest}`);
      }
      for (const field of ['material_digest', 'resolved_index_digest', 'dependency_closure_digest', 'compiler_revision', 'evaluator_revision']) {
        await check(detail).toContainText(expected[field]);
      }
      const packages = detail.getByRole('region', { name: 'Named packages and index identities' });
      await check(packages.getByRole('heading', { name: 'records-mapping-contract', exact: true })).toBeVisible();
      for (const binding of expected.catalog_bindings.filter(item => item.package_key === 'records-mapping-contract')) {
        const ref = binding.ref;
        await check(packages).toContainText(`${ref.kind} · ${ref.id} · revision ${ref.revision} · ${ref.digest}`);
        if (binding.entity_kind !== 'package') await check(packages).toContainText(`${binding.entity_kind}: ${binding.key}`);
      }
    }

    // Keyboard activation through the real rendered controls, with a visible focus ring.
    await reload.focus();
    await page.keyboard.press('Shift+Tab');
    await check(inspect).toBeFocused();
    assert.equal(await inspect.evaluate(element => getComputedStyle(element).outlineWidth), '2px');
    const selectedResponse = page.waitForResponse(`${origin}${apiPath}`);
    await page.keyboard.press('Enter');
    const selected = await selectedResponse;
    assert.equal(selected.status(), 200);
    assert.deepEqual(await selected.json(), expected);
    await exactView();
    assert.equal(new URL(page.url()).searchParams.get('publication'), pin.id);
    assert.equal(new URL(page.url()).searchParams.get('digest'), pin.digest);

    const reloadedResponse = page.waitForResponse(`${origin}${apiPath}`);
    await page.reload();
    const reloaded = await reloadedResponse;
    assert.equal(reloaded.status(), 200);
    assert.deepEqual(await reloaded.json(), expected);
    await exactView();

    const refreshedResponse = page.waitForResponse(`${origin}${apiPath}`);
    await reload.click();
    const refreshed = await refreshedResponse;
    assert.equal(refreshed.status(), 200);
    assert.deepEqual(await refreshed.json(), expected);
    await exactView();

    // A well-formed wrong digest reaches the SAME browser/API, not a mocked error.
    const wrong = `${pin.digest[0] === '0' ? '1' : '0'}${pin.digest.slice(1)}`;
    const badPath = `/api/v1/settings/catalog/publications/${pin.id}/${wrong}`;
    const deniedResponse = page.waitForResponse(`${origin}${badPath}`);
    await page.goto(`${origin}/settings/skills?publication=${pin.id}&digest=${wrong}`);
    const denied = await deniedResponse;
    assert.equal(denied.status(), 503);
    const refusal = await denied.json();
    assert.deepEqual(Object.keys(refusal), ['error']);
    assert.deepEqual(Object.keys(refusal.error).sort(), ['code', 'correlation_id', 'field_errors']);
    assert.equal(refusal.error.code, 'CONTROL_UNAVAILABLE');
    assert.match(refusal.error.correlation_id, /^[0-9a-f]{8}(-[0-9a-f]{4}){3}-[0-9a-f]{12}$/);
    assert.deepEqual(refusal.error.field_errors, []);
    await check(detail.getByRole('alert')).toHaveText('Exact publication unavailable or unsupported. No readiness is confirmed.');
    await check(detail).not.toContainText('RECORDED_STATIC_PASS');
    await check(detail).not.toContainText('RECORDED_PURE_PASS');
    await check(detail).not.toContainText(pin.digest);
    await check(detail.getByRole('region', { name: 'Named packages and index identities' })).toHaveCount(0);
    await screenshot('catalog-wrong-digest');

    // Explicit recovery by Inspect, rather than accepting a stale successful result.
    const recoveredResponse = page.waitForResponse(`${origin}${apiPath}`);
    await inspect.click();
    const recovered = await recoveredResponse;
    assert.equal(recovered.status(), 200);
    assert.deepEqual(await recovered.json(), expected);
    await exactView();
    assert.equal(new URL(page.url()).pathname + new URL(page.url()).search, selection);

    for (const viewport of [{ width: 1440, height: 1000 }, { width: 390, height: 844 }]) {
      await page.setViewportSize(viewport);
      // Enter keyboard modality after pointer recovery before checking :focus-visible.
      await inspect.focus();
      await page.keyboard.press('Tab');
      await check(reload).toBeFocused();
      const focus = await reload.evaluate(element => {
        const rect = element.getBoundingClientRect();
        return { outline: getComputedStyle(element).outlineWidth, top: rect.top, bottom: rect.bottom,
          width: rect.width, height: rect.height, viewport: innerHeight };
      });
      assert.equal(focus.outline, '2px');
      assert.ok(focus.width >= 44 && focus.height >= 44 && focus.top >= 0 && focus.bottom <= focus.viewport, 'Catalog keyboard focus is clipped or undersized');
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), 'Catalog horizontal overflow');
      await page.screenshot({ path: join(output, `catalog-${viewport.width}-viewport.png`), fullPage: false });
      await screenshot(`catalog-${viewport.width}-full`);
    }
    await secretChecks();
    assert.deepEqual(failures, [], 'Catalog request failed (retained in catalog-network.json)');
    const expectedHttpNegatives = responses.filter(item => item.path === badPath && item.status === 503).length;
    assert.equal(expectedHttpNegatives, 1, 'Expected exactly one deliberate digest refusal');
    assert.ok(responses.filter(item => item.path === apiPath && item.status === 200).length >= 3);
    assert.ok(responses.every(item => item.method === 'GET'), 'Catalog consumer performed a mutation');
    assert.ok(responses.every(item => item.status === 200 || (item.path === badPath && item.status === 503)), 'Unexpected catalog response');
    return { publication_ref: pin, package_key: 'records-mapping-contract', wrongDigestRefused: true,
      recoveredSameIdentity: true, reloadSameIdentity: true, keyboardFocus: true,
      screenshots: ['catalog-1440-viewport.png', 'catalog-1440-full.png', 'catalog-390-viewport.png', 'catalog-390-full.png'],
      expectedHttpNegatives, requestFailures: failures.length };
  } finally {
    page.off('response', onResponse);
    page.off('requestfailed', onFailure);
    await writeFile(join(output, 'catalog-network.json'), JSON.stringify({ responses, failures }, null, 2) + '\n');
  }
}
