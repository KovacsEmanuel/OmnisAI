import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { dirname } from 'node:path';
import { parseArgs } from 'node:util';
import openapiTS, { astToString } from 'openapi-typescript';

const { values } = parseArgs({ options: { check: { type: 'boolean' }, output: { type: 'string' } } });
const output = values.output ?? new URL('../src/shared/api/generated.ts', import.meta.url).pathname;
// Only this trusted repository contract is input; never target specs or remote $refs.
const source = new URL('../../contracts/omnis.openapi.json', import.meta.url);
const content = '// Generated from contracts/omnis.openapi.json. Do not edit.\n' + astToString(await openapiTS(source));
if (values.check) {
  let existing;
  try {
    existing = await readFile(output, 'utf8');
  } catch (error) {
    if (error.code !== 'ENOENT') throw error;
  }
  if (existing !== content) {
    console.error('TypeScript contract drift: run make generate-contracts');
    process.exitCode = 1;
  }
} else {
  await mkdir(dirname(output), { recursive: true });
  await writeFile(output, content);
}
