# S01 composition adaptation notice

Source: usestrix/strix, commit `ff5c8cc8e46d8e60c2bc2439f7bcb07c05ca3db2`, `strix/agents/prompt.py`.
Source file SHA-256: `2b30f1ecee988f9effed96c54af2baecd3a6506b6bcfdc5bd9a0f325cf540a33`.
Reviewed fragments: lines 20–71 (`a060f5d4664a56b1376e03143c3667dcf8972c330bd23ab52051e3fd8c3fe08d`) and 74–126 (`0d7b37c93b37e73f3e8e84b93b6b1fc835c93a5a3669530b8c572ecb81ce2f4f`).

Copyright 2025 OmniSecure Inc.
Licensed under Apache-2.0. The complete pinned LICENSE is retained as `composition-LICENSE` (SHA-256 `7db9697134251e314bd8d39257fe170c98b3e2ad9b2ed67e97acaf9613e7b9e3`). A finite request for the pinned repository-root `NOTICE` returned HTTP 404; no upstream NOTICE content is invented. This is Omnis's adaptation notice.

## Changed by OmnisAI

The relevant algorithm is explicit ordered role/mode/selected-skill composition. `omnis_hermes/prompt_bundle.py` adapts this into base → role → exact brief → bound method → selected skills. Unlike the source renderer, it rejects duplicate/shadowed material rather than silently deduplicating, rejects missing material rather than returning an empty prompt, and has no implicit skill injection, Jinja/template execution, filesystem catalog search, external runtime, warm constructor options, or model invocation. Canonical JSON segmentation, immutable envelope/ref checking, complete mandatory material, conservative byte/token accounting and fail-closed budgets are first-party Omnis code. The runtime hashes the installed composer source; no self-hash constant is embedded.

Native validates transmitted package manifests, content membership/digests/sizes and mandatory SKILL.md plus method presence. Exact selected `technique.method_ref` ownership is checked by the API against the retained catalog/preparation; the wire transmits no technique envelope with a path mapping. Native does not fabricate that mapping or claim positive child read/method execution.

The original source is retained only as non-executable review data in `composition-source/strix-prompt.py.txt`, not imported or installed as a foreign runtime.
