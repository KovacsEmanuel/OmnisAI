import { defineConfig } from 'oxlint';
export default defineConfig({
  jsPlugins: [{ name: 'anti-slop', specifier: './vendor/index.ts' }],
  rules: {
    'anti-slop/no-chained-type-assertions': 'error',
    'anti-slop/no-widen-then-assert': 'error',
    'anti-slop/require-safety-comment-for-type-assertion': 'error',
  },
});
