# anti-slop — development only

Reviewed subset of [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop), immutable revision and file digests in `upstream.json`. The original three rule implementations are unchanged and keep `vendor/LICENSE` (MIT). `vendor/index.ts`, configuration, fixtures and smoke runner are Omnis integration code, not an upstream full installation.

## Install / exercise

From the Omnis root, through Hermes `terminal`:

```sh
npm --prefix tools/development/anti-slop ci --include=dev --ignore-scripts --no-fund
npm --prefix tools/development/anti-slop test
npm --prefix tools/development/anti-slop audit --include=dev
```

Lint an explicit source file/directory with an **absolute path**:

```sh
npm --prefix tools/development/anti-slop run lint -- /absolute/path/to/source.ts
```

Do not lint `fixtures/*-fail.ts` as production files: they intentionally exercise each error rule. The smoke must accept the boundary-validation fixture and reject each of the three separate bad fixtures with the expected diagnostic, not merely exit nonzero.

## Deliberate policy

Enabled as errors: `no-chained-type-assertions`, `no-widen-then-assert`, `require-safety-comment-for-type-assertion`. Oxlint's default correctness rules also remain enabled; `lint --deny-warnings` makes their warnings fail the explicit lint command too. The comment documents an independently checked invariant; it is not proof that a cast is sound.

The smoke checks exact structured diagnostic code, severity and fixture identity. An independent review reproduced a false green when matching a rule-name substring inside a plugin exception stack; a RED regression control now rejects that case (and wrong-severity/wrong-fixture cases). The vendor/license digests are checked before CLI execution. These checks detect drift relative to the committed manifest, not malicious changes to both manifest and source.

We do **not** adopt upstream bans on `unknown`, `typeof`, symbol names, all mocks or dictionary types; Omnis needs honest untrusted-input validation and tests at explicit boundaries. No Effect group, Tailwind change, universal refactor or blanket autofix. More rules require review and a demonstrated useful control.

Oxlint and `@oxlint/plugins` are pinned together to upstream's `1.78.0`, not arbitrary latest. This is an isolated tool package, not an application dependency or claim that P0 is complete. Its three rules do not replace TypeScript, React/a11y linting, Python linting, integration tests or security review.

## Reproduced environment pitfalls

- This host inherits `NODE_ENV=production`; plain `npm ci` omitted every dev dependency. Use `--include=dev` explicitly.
- Host Node `22.22.0` is compiled without TypeScript support (`process.features.typescript=false`, `ERR_NO_TYPESCRIPT`). Version alone was insufficient. Use the pinned `tsx` loader in the commands even if another Node build supports native stripping.
- One cold lint invocation exceeded 30 seconds. Separate retries returned the expected real diagnostic in approximately 25 seconds; smoke uses a bounded 90-second process timeout, not a performance assertion. A timeout still fails the test.

## Update / rollback

Review the upstream diff at a selected SHA; never overwrite customized files through the upstream install skill. Compare unchanged files to `upstream.json`, advance matching Oxlint/plugin pins together, regenerate the lock and repeat all positive/negative controls. Keep this directory in its own coherent commit. Reverting that commit removes the integration; an ignored `node_modules` directory is only a disposable install and contains no product data.
