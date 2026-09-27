import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const root = new URL('../../', import.meta.url);
const output = new URL('../src/shared/styles/', import.meta.url);
const tokens = JSON.parse(await readFile(new URL('documents/Omnis_Design.tokens.json', root)));
const provenance = await readFile(new URL('documents/assets/fonts-provenance.json', root));
const source = JSON.parse(provenance);
const fonts = await readFile(new URL('documents/assets/prototype-fonts.css', root));
const license = await readFile(new URL('documents/assets/fonts-OFL.txt', root));
const digest = bytes => createHash('sha256').update(bytes).digest('hex');
if (digest(fonts) !== source.generated_css_sha256 || digest(license) !== source.license_sha256) {
  throw new Error('Local font provenance mismatch');
}
let css = '/* Generated from DESIGN.md via Omnis_Design.tokens.json. Do not edit. */\n:root {\n';
for (const [name, token] of Object.entries(tokens.color)) {
  if (!name.startsWith('$')) css += `  --color-${name}: ${token.$value.hex};\n`;
}
for (const [group, prefix] of [['spacing', 'space'], ['rounded', 'radius']]) {
  for (const [name, token] of Object.entries(tokens[group])) {
    if (!name.startsWith('$')) css += `  --${prefix}-${name}: ${token.$value.value}${token.$value.unit};\n`;
  }
}
css += `  --font-sans: ${tokens.typography['body-md'].$value.fontFamily};\n`;
css += `  --font-mono: ${tokens.typography.code.$value.fontFamily};\n}\n`;
// Verify the original bytes above; normalize trailing whitespace only in the distributed notice.
const notice = Buffer.from(license.toString('utf8').replace(/[\t ]+$/gm, ''));
const files = { 'tokens.css': Buffer.from(css), 'fonts.css': fonts, 'fonts-OFL.txt': notice, 'fonts-provenance.json': provenance };
if (!process.argv.includes('--check')) await mkdir(output, { recursive: true });
for (const [name, bytes] of Object.entries(files)) {
  const path = new URL(name, output);
  if (process.argv.includes('--check')) {
    let actual;
    try { actual = await readFile(path); } catch (error) { if (error.code !== 'ENOENT') throw error; }
    if (!actual?.equals(bytes)) { console.error(`Design asset drift: ${name}`); process.exitCode = 1; }
  } else {
    await writeFile(path, bytes);
  }
}
