import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdtempSync, readFileSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

const root = new URL('../../', import.meta.url);

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
    const command = [new URL('generate-contracts.mjs', import.meta.url).pathname, '--output', output];
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
