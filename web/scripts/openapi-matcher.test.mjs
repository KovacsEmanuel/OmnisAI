import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { test } from 'node:test';
import openapiTS, { astToString } from 'openapi-typescript';

const require = createRequire(import.meta.url);
const generatorRequire = createRequire(require.resolve('openapi-typescript'));
const corePath = generatorRequire.resolve('@redocly/openapi-core');
const coreRequire = createRequire(corePath);
const { readFileFromUrl, createConfig } = generatorRequire('@redocly/openapi-core');

test('the actual generator resolves the declared backport, with no minimatch branch', () => {
  const pkg = coreRequire('../package.json');
  assert.equal(pkg.version, '1.34.20+omnis.picomatch.1');
  assert.equal(pkg.dependencies.picomatch, '4.0.7');
  assert.equal(pkg.dependencies.minimatch, undefined);
  assert.equal(corePath, require.resolve('@redocly/openapi-core'));
  assert.throws(() => coreRequire.resolve('minimatch'), { code: 'MODULE_NOT_FOUND' });
  const lock = JSON.parse(readFileSync(new URL('../package-lock.json', import.meta.url)));
  assert.deepEqual(Object.keys(lock.packages).filter(path => path.endsWith('/@redocly/openapi-core')), ['node_modules/@redocly/openapi-core']);
  assert.deepEqual(Object.keys(lock.packages).filter(path => path.endsWith('/minimatch')), []);
});

test('real Redocly URL reader selects only matching synthetic headers without HTTP', async () => {
  const headers = [
    { matches: 'schemas.invalid/**', name: 'X-Synthetic', value: 'fixture' },
    { matches: 'https://schemas.invalid/*.json', name: 'X-HTTPS', value: 'fixture' },
    { matches: 'other.invalid/**', name: 'X-Wrong-Host', value: 'never' },
  ];
  const cases = [
    ['https://schemas.invalid/api.json', { 'X-Synthetic': 'fixture', 'X-HTTPS': 'fixture' }],
    ['http://schemas.invalid/api.json', { 'X-Synthetic': 'fixture' }],
    ['https://schemas.invalid/nested/api.json', { 'X-Synthetic': 'fixture' }],
    ['https://schemas.invalid.evil.invalid/api.json', {}],
    ['https://unrelated.invalid/api.json', {}],
  ];
  for (const [url, expected] of cases) {
    let calls = 0;
    const result = await readFileFromUrl(url, {
      headers,
      customFetch: async (actualUrl, options) => {
        calls++;
        assert.equal(actualUrl, url);
        assert.deepEqual(options.headers, expected);
        return new Response('{}', { headers: { 'content-type': 'application/json' } });
      },
    });
    assert.equal(calls, 1);
    assert.deepEqual(result, { body: '{}', mimeType: 'application/json' });
  }
  await assert.rejects(readFileFromUrl('https://schemas.invalid/api.json', {
    headers,
    customFetch: async () => new Response(null, { status: 403, statusText: 'Forbidden' }),
  }), /Failed to load .*: 403 Forbidden/);
});

test('public generator retains local-ref bundling, lint and unsupported-schema rejection', async () => {
  const schema = {
    openapi: '3.0.3', info: { title: 'Synthetic fixture', version: '1' },
    paths: { '/fixture': { get: { operationId: 'fixture', responses: {
      200: { description: 'ok', content: { 'application/json': { schema: { $ref: '#/components/schemas/Fixture' } } } },
    } } } },
    components: { schemas: { Fixture: { type: 'object', properties: { marker: { type: 'string' } }, required: ['marker'] } } },
  };
  const redocly = await createConfig({ rules: { 'operation-operationId': 'error' } });
  const output = astToString(await openapiTS(schema, { redocly }));
  assert.match(output, /marker: string/);
  assert.match(output, /components\["schemas"\]\["Fixture"\]/);
  const missingRef = structuredClone(schema);
  missingRef.paths['/fixture'].get.responses[200].content['application/json'].schema.$ref = '#/components/schemas/Missing';
  await assert.rejects(openapiTS(missingRef, { redocly }), /resolve.*ref|does not exist/i);
  const missingOperation = structuredClone(schema);
  delete missingOperation.paths['/fixture'].get.operationId;
  await assert.rejects(openapiTS(missingOperation, { redocly }), /operationId/);
  await assert.rejects(openapiTS({ swagger: '2.0', paths: {} }), /Unsupported Swagger version/);
});
