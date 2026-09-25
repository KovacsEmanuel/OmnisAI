// Integration contract: the real vendored rules must reject type-evidence loss.
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';

const here = path.dirname(fileURLToPath(import.meta.url));
const cli = path.join(here, 'node_modules', 'oxlint', 'bin', 'oxlint');
const config = path.join(here, 'oxlint.config.ts');
const provenance = JSON.parse(readFileSync(path.join(here, 'upstream.json'), 'utf8'));
for (const file of provenance.files) {
  const location = path.resolve(here, file.vendored_path);
  assert.ok(location.startsWith(path.join(here, 'vendor') + path.sep), 'Manifest path outside vendor');
  const digest = createHash('sha256').update(readFileSync(location)).digest('hex');
  assert.equal(digest, file.sha256, `Vendored content drift: ${file.vendored_path}`);
}

function isRuleDiagnostic(diagnostic, rule, filename) {
  return diagnostic.code === `anti-slop(${rule})`
    && diagnostic.severity === 'error'
    && typeof diagnostic.filename === 'string'
    && path.resolve(here, diagnostic.filename) === path.join(here, 'fixtures', filename);
}

// Regression control: an exception stack may contain the rule's filename.
assert.equal(isRuleDiagnostic({
  message: 'Error running JS plugin: vendor/rules/no-chained-type-assertions.ts:69:15',
  severity: 'error', filename: 'fixtures/chain-fail.ts',
}, 'no-chained-type-assertions', 'chain-fail.ts'), false, 'A crashed plugin is not a rule verdict');
assert.equal(isRuleDiagnostic({ code: 'anti-slop(no-chained-type-assertions)', severity: 'warning', filename: 'fixtures/chain-fail.ts' }, 'no-chained-type-assertions', 'chain-fail.ts'), false);
assert.equal(isRuleDiagnostic({ code: 'anti-slop(no-chained-type-assertions)', severity: 'error', filename: 'fixtures/other.ts' }, 'no-chained-type-assertions', 'chain-fail.ts'), false);
console.log('PASS verifier controls: plugin failure, wrong severity and wrong fixture are rejected');

const cases = [
  ['boundary-pass.ts', 0, []],
  ['chain-fail.ts', 1, ['no-chained-type-assertions']],
  ['widen-fail.ts', 1, ['no-widen-then-assert']],
  ['comment-fail.ts', 1, ['require-safety-comment-for-type-assertion']],
];
for (const [name, exitCode, rules] of cases) {
  const run = spawnSync(process.execPath, ["--import", "tsx", cli, '-c', config, '--format', 'json', path.join(here, 'fixtures', name)], {
    cwd: here, encoding: 'utf8', timeout: 90000,
  });
  assert.equal(run.error, undefined, `${name}: ${run.error}`);
  assert.equal(run.status, exitCode, `${name}: ${run.stderr}\n${run.stdout}`);
  const result = JSON.parse(run.stdout);
  const diagnostics = result.diagnostics;
  assert.ok(Array.isArray(diagnostics), `${name}: missing structured diagnostics`);
  assert.equal(diagnostics.length, rules.length, `${name}: unexpected diagnostic (possibly a plugin failure)`);
  for (const rule of rules) assert.ok(diagnostics.some(d => isRuleDiagnostic(d, rule, name)), `${name}: missing ${rule}`);
  if (exitCode === 0) assert.equal(diagnostics.length, 0, run.stdout);
  console.log(`PASS ${name}: actual exit ${run.status}; ${diagnostics.length} diagnostic(s)`);
}
console.log(`PASS ${cases.length} real Oxlint integration cases; no network or application execution`);
