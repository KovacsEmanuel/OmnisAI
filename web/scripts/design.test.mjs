import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { test } from 'node:test';
import { fileURLToPath } from 'node:url';

test('design export produces local tokens/fonts with provenance and detects drift', () => {
  const script = new URL('sync-design.mjs', import.meta.url);
  const run = spawnSync(process.execPath, [fileURLToPath(script), '--check'], { encoding: 'utf8', timeout: 10000 });
  assert.equal(run.status, 0, 'Design assets must be generated from the accepted local baseline');
});
