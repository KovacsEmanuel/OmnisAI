# Managed cold admission overlay

`omnis-managed.patch` applies **after** the unchanged `omnis-inert.patch` to
Hermes `ee5ee84a345204a3b1d6ef6ba1ab747e602867b9` (0.21.5). The six source
outputs and their before/after SHA256 values are in
`managed-patch-manifest.json`; new files have `original_sha256: null`.
`ops/prepare_hermes_runtime.py` verifies every original and output before copying.
The base version/archive, dependency inputs and inert/preparation patch are unchanged.

- `AIAgent(cold_admission=ColdAdmission())` creates a real native root without
  calling `init_agent`; child agents are constructed by the existing
  `SubagentLifecycleService.stage` extension. NO_MODEL is fixed, not model text.
- Cold state is complete and cannot become warm. Warm surfaces are deny-by-default;
  only native identity/state inspection and idempotent `close` are admitted.
- `stage` creates native registry records without executor submission. The indexed
  binding is required by `release`; native records become terminal `BLOCKED` with
  `error_classification=NO_MODEL`, no started turn and no success state.
- Private inert RPC methods: `omnis.managed.stage`, `.release`, `.status`.
  They are not tools. The RuntimeHost existing owner transports the exact wire
  payload and returns it under the outer `managed` key. All three operations
  require `deadline_ns`; current authority is checked before grant renewal.
- Native ticket lifetime is 4.5 seconds. Each RPC is bounded by
  `min(3.2 seconds, remaining grant)`. Existing grant limits are unchanged.
- Same manifest replays existing identities/results; conflicting payloads,
  binding substitution, expired stages and closed roots refuse. Unknown lineage,
  stock cold launch, wake, conversation, tools and session/domain reads refuse.
- Provider plugin discovery is suppressed under the existing inert flag, including
  home providers. A source audit demonstrated that bundled discovery otherwise
  attempted `secret_scope.load_env_file` during ordinary `run_agent` import.
  Hooks are not authority and cannot override the explicit binding barrier.

`tests/managed_source_probe.py` runs full source with a source overlay and independent
sink auditing; it is **not installed-runtime proof**. `tests/managed_native_probe.py`
is the finite installed Python3.13.15 probe for the parent's isolated fixture.
The RuntimeHost fence verifies runtime boot/generation/epoch. The supervisor remains
responsible for authenticating owner/instance and committing the binding before release.

Remaining acceptance: installed artifact/owner transport/PG integration and independent
review, owned by the parent. No provider inference, target effects, methodology success,
Brain continuation, durable native reconnect, or global B06b/G02 acceptance is claimed.
