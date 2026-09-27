import { readFile, readdir, writeFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const root = new URL('../dist/', import.meta.url);
const files = {};
for (const name of ['index.html', ...(await readdir(new URL('assets/', root))).map(name => `assets/${name}`)].sort()) {
  if (!/^(index\.html|assets\/[A-Za-z0-9_-]+\.(js|css|woff2|txt))$/.test(name)) throw new Error('Unexpected build output');
  const content = await readFile(new URL(name, root));
  files[name] = createHash('sha256').update(content).digest('hex');
}
await writeFile(new URL('omnis-web.json', root), JSON.stringify({ version: 1, files }, null, 2) + '\n');
console.log(`Trusted web manifest: ${Object.keys(files).length} files`);
