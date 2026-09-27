import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';

const tools = fileURLToPath(new URL('../../tools/development/anti-slop/', import.meta.url));
const owned = ['src', 'tests', 'scripts', 'vite.config.ts', 'vitest.config.ts'].map(path => fileURLToPath(new URL(`../${path}`, import.meta.url)));
const result = spawnSync(process.execPath, ['--import', 'tsx', 'node_modules/oxlint/bin/oxlint',
  '-c', 'oxlint.config.ts', '--deny-warnings', '--react-plugin', '--jsx-a11y-plugin',
  '--ignore-pattern', '**/generated.ts', ...owned], { cwd: tools, stdio: 'inherit', timeout: 90000 });
if (result.error) throw result.error;
process.exitCode = result.status ?? 1;
