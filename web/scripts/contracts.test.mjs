import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync, mkdirSync, copyFileSync, symlinkSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { test } from 'node:test';

const root = new URL('../../', import.meta.url);

test('canonical check and CI include the web contract gate', () => {
  const refused = spawnSync('make', ['-n', 'check'], { cwd: root, encoding: 'utf8', timeout: 15000 });
  assert.notEqual(refused.status, 0, 'a dry run must not pass as canonical verification');
  assert.match(refused.stderr, /Unsafe Make flags for verification/);
  const makefile = readFileSync(new URL('Makefile', root), 'utf8');
  assert.match(makefile, /^check:\n\t\$\(API_PY\) -I ops\/run_test_db_gate\.py --check/m);
  assert.match(makefile, /^check-components:.*\bcheck-web\b/m);
  const dryRun = spawnSync('make', ['-n', 'check-web'], { cwd: root, encoding: 'utf8', timeout: 15000 });
  assert.equal(dryRun.status, 0);
  assert.match(dryRun.stdout, /npm --prefix web run check:contracts/);
  const ci = readFileSync(new URL('.github/workflows/ci.yml', root), 'utf8');
  assert.match(ci, /make check/);
  assert.match(ci, /--directory cli/);
  assert.match(ci, /npm --prefix web ci --include=dev --ignore-scripts/);
});

test('web pins match the baseline, without opportunistic dependencies', () => {
  const pins = JSON.parse(readFileSync(new URL('documents/Omnis_Stack_Baseline.versions.json', root)));
  const pkg = JSON.parse(readFileSync(new URL('web/package.json', root)));
  const allowed = { ...pins.frontend_runtime, ...pins.frontend_build, ...pins.frontend_tests };
  for (const [name, version] of Object.entries({ ...pkg.dependencies, ...pkg.devDependencies })) {
    assert.equal(version, allowed[name], name);
  }
  assert.equal(pkg.engines.node, pins.runtimes.node.selected);
  assert.equal(pkg.packageManager, `npm@${pins.runtimes.node.bundled_npm}`);
});

test('TypeScript generation detects drift without rewriting it', () => {
  const directory = mkdtempSync(join(process.env.TMPDIR, 'omnis-ts-'));
  try {
    const output = join(directory, 'generated.ts');
    const command = [fileURLToPath(new URL('generate-contracts.mjs', import.meta.url)), '--output', output];
    const run = (...args) => spawnSync(process.execPath, [...command, ...args], { timeout: 15000, encoding: 'utf8' });
    assert.equal(run().status, 0, 'TypeScript generator must run');
    assert.match(readFileSync(output, 'utf8'), /SessionView/);
    assert.equal(run('--check').status, 0);
    writeFileSync(output, '// deliberate synthetic drift\n');
    const drift = run('--check');
    assert.equal(drift.status, 1);
    assert.match(drift.stderr, /TypeScript contract drift/);
    assert.equal(readFileSync(output, 'utf8'), '// deliberate synthetic drift\n');
  } finally {
    rmSync(directory, { recursive: true, force: true });
  }
});

test('contract generation works inside an actual path with spaces', () => {
  const directory = mkdtempSync(join(process.env.TMPDIR, 'omnis spaced checkout '));
  try {
    mkdirSync(join(directory, 'web/scripts'), { recursive: true });
    mkdirSync(join(directory, 'contracts'));
    copyFileSync(new URL('generate-contracts.mjs', import.meta.url), join(directory, 'web/scripts/generate-contracts.mjs'));
    copyFileSync(new URL('contracts/omnis.openapi.json', root), join(directory, 'contracts/omnis.openapi.json'));
    symlinkSync(fileURLToPath(new URL('../node_modules', import.meta.url)), join(directory, 'web/node_modules'));
    const result = spawnSync(process.execPath, [join(directory, 'web/scripts/generate-contracts.mjs')], { timeout: 15000 });
    assert.equal(result.status, 0);
    assert.ok(existsSync(join(directory, 'web/src/shared/api/generated.ts')), 'generated file must be inside the spaced checkout');
  } finally {
    rmSync(directory, { recursive: true, force: true });
    // The pre-fix generator incorrectly uses the percent-encoded filesystem name.
    rmSync(directory.replaceAll(' ', '%20'), { recursive: true, force: true });
  }
});
