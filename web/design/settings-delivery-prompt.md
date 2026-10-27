# Handoff — Settings C implementation and premium visual finish

**PREPARED_ONLY / NOT_LAUNCHED.** This file was requested as a prompt, not as permission
to launch implementation in the preparation session. Activate **Prompt A** explicitly in a
fresh Omnis-bound session. **Prompt B is separate** and does not run automatically after A.
Prepared from `96ed9c7`; re-check actual Git/CURRENT before acting. Product T1 is
CLOSED_SCOPED locally; the accepted design is not implemented product behavior.

## Prompt A — implement Settings C and finish the UI

You are delivering one complete Settings outcome in `/home/kali/OmnisAI`, not another
standalone demo. Preserve the current Omnis architecture, security and accepted visual
identity. The operator selected guided design C, approved the direction of
`web/design/settings-final.html`, and requested proper centering and premium-quality
buttons/spacing. All application copy, labels, errors and accessibility names must be English.
Report progress and final results to the operator briefly in Romanian.

### Read first; do not restart the whole project

1. Read `AGENTS.md`, `CONTRIBUTING.md`, the single CURRENT in `README.md`, the affected
   plan/architecture/UI sections, `DESIGN.md` and `web/design/settings-final.md`.
2. Open/render `web/design/settings-final.html` as the interaction reference, then inspect
   actual `web/src/features/engagement/{Settings,ProviderSettings,ModelTest}.tsx`, their
   styles, client/decoders/generated contract and the owning API/supervisor routes/services.
   Trace definitions/usages rather than inventing API shapes. Mockup fixtures and simulated
   success are never production data or a shortcut around real API/persistence.
3. Record actual HEAD/branch/diffs, preserve preexisting work, and inspect only current
   affected contracts/callers. Do not read `tempkey.txt`, the protected
   `documents/Omnis_Notite_Originale.html`, credential files or unrelated operator state.
   The last documented QA connection is intentionally revoked, not evidence of lost keys.
4. Before assigning implementation, resolve the real producer, complete encoded input/reply
   budgets and first consumer. The proposed registry/catalog caps in the design spec are
   preflight candidates, not enacted runtime contracts. Align affected canonical sections
   in place before product changes; do not start a second roadmap or rewrite old acceptance.

### Skills — use the relevant subset, not the whole catalog

Project rules and `DESIGN.md` override incompatible defaults in any skill. Load skills
progressively for the current operation; availability on disk does not prove native
activation, integration or quality. Do not install/enable tools just to invoke a skill.

**In Hermes:**
- Core UI: `omnis-frontend`, `omnis-accessibility`, `claude-design`.
- Actual implementation: `omnis-delivery`, `omnis-api-data`, then `omnis-review-qa` and
  `omnis-project-status` at their relevant stages.
- `design-md` only for existing-token consistency/contrast; preserve the house export
  pipeline, no opportunistic `npx -y` tool download or redesign of DESIGN.md.
- `popular-web-designs` is optional inspiration: Vercel for typographic precision and
  Linear for hierarchy/density only. Do not import their palettes, fonts, tiny controls,
  branding, layout, CDN snippets or cloudflared workflow.
- Ponytail full: reuse existing callers/primitives and write the smallest readable change
  that completes the actual flow. No speculative architecture or unrelated cleanup.

**In Codex:** inspect the active skill catalog first. The following SKILL.md files were
present locally during preparation; if not listed natively, verify/read their actual files
as optional reference material without changing configuration or claiming automatic loading:
- `/home/kali/.codex/skills/emil-design-eng/SKILL.md` — selected principles for button feel,
  optical alignment, focus, stable loading geometry and restrained interaction polish.
- `/home/kali/.codex/skills/ui-ux-pro-max/SKILL.md` — selected accessibility, responsive,
  typography and consistency checks; no new generated design system/Tailwind defaults.
- `/home/kali/.codex/skills/ux-copy/SKILL.md` — concise English action labels, recoverable
  errors, useful empty states and honest feedback, not a new brand voice.
- `/home/kali/.codex/skills/frontend-design/SKILL.md` — cohesive production craft only;
  reject its forced novelty, asymmetry, font replacement and entrance-sequence suggestions.
Codex can read the versioned project procedures directly from `.hermes/skills/`; they are
not automatically native Codex skills. Do not copy personal skills into the product.

**Explicit exclusions:** `high-end-visual-design` is locally present but its random layout
variance, huge whitespace, glass/mesh gradients and 700–800ms mandatory motion conflict
with this accepted Settings design. Reuse only already-approved double-bezel/pill geometry
if useful, never its wholesale recipe. `playwright-interactive` is locally present but its
instructions request danger-full-access, js_repl configuration and installs; those are NOT
authority to disable the sandbox, edit global config or replace the pinned browser setup.
Use the existing project Playwright/browser procedures. No image-generation API, Figma/MCP,
3D/WebGL, motion library, remote font or icon dependency is needed for these Settings.

### The product behavior to deliver

- **Connection → Models → Review.** New key is write-only and encrypted by the existing
  vault. Existing connection shows Saved key, with no key echo or re-entry. Continue saves
  the connection locally, confirms its receipt/readback and explicitly loads its catalog.
  Cancelling later discards pending model choices, not the already saved connection.
- **Provider-scoped search/+ Add:** browse all catalog pages within admitted bounds;
  search local normalized cache by name/exact ID, not a provider request per keystroke.
  Loading/error/stale/partial/no-results are distinct. Refuse foreign next URLs and loops;
  never claim all models from one page. Preserve exact identifiers, key revision and
  connection identity. Manual ID fallback may save an unverified entry, not fake eligibility.
- **Saved models:** persist entries independently from role assignments, unique by current
  connection + exact model ID, without a secret copy per entry. Add several per saved key;
  identical IDs through different providers remain distinguishable. Save/readback/reload/
  restart and upgrade/backfill preserve existing choices/output settings/receipts.
- **Separate Model assignments:** exactly one configured usable model, with no stale
  explicit references, serves all roles without redundant selectors; several entries populate Default, Brain,
  Investigator, Validator. Each role may inherit Default or keep an explicit entry. Adding
  models/changing Default must not erase explicit overrides. Preserve unavailable/stale
  selections visibly without silent fallback. Save assignments applies only to future runs.
- **Save models is local. Save & test names one model.** Extend the existing finite test to
  that exact saved entry/snapshot, not by temporarily swapping the global default. Preserve
  one call/300s, synthetic input, caps, requested/observed, ledger, outcomes and usage UNKNOWN.
  Do not paid-test a whole batch, infer inference readiness from GET/catalog, or retry unseen
  effects. Test success marks only its model/connection revision. No provider IO on boot/reload.
- Preserve Replace/Disable/Reconnect, Cancel and receive-only UNKNOWN readback. A disabled
  connection invalidates its open wizard; stale Continue cannot reactivate it. Cancel/readback
  must remain accessible while dialogs/wizards change. Never hot-swap a live run's configuration.

Reuse existing vault, owner/admission, immutable selection snapshots, finite SystemOperation,
sender, ledger, session/Host/Origin/CSRF and persistence patterns. Extend registry/catalog/
DTO/API/migration/client together where actually necessary. Do not replace the runtime, add
another settings owner, introduce an arbitrary base URL or unrequested provider, or launch T2.
The concrete source/consumer matrix and proposed limits are in `settings-final.md`.

### Premium means craft, not decoration — visual acceptance checklist

The primary surface is **Configure**, not a marketing page. C is selected; do not reopen
A/B/C exploration or invent another theme. Improve the selected implementation, not just its palette.

- **Center the composition, not all text.** Use one centered Settings content column inside
  the existing shell. Page heading, Settings tabs, section headers, configured-model panels,
  wizard and assignments share its horizontal axis/edges. Start with the reference's
  ~900px Settings workspace inside the existing 1180px shell; do not resize unrelated pages.
  Equal desktop margins; 32px outer desktop/16px narrow-screen gutters where the baseline
  calls for them. No arbitrary left offsets, stranded narrow panels or massive dead space.
  Labels, descriptions, IDs and list text remain left-aligned for scanning.
- **Buttons form one family:** reuse the house capsule silhouette and existing 46px control
  height, minimum 44×44 targets, consistent horizontal padding/radii, label weight, optical
  icon centering and baseline. Match button/input heights and align row actions. Primary,
  secondary, quiet and destructive treatments are visibly distinct without noisy colors.
  No extra arrow/icon unless it clarifies the action; use existing local assets/primitives.
- **Wizard actions stay predictable:** Back on the left, forward/commit actions together on
  the right; Back remains available on Review. Secondary Save models precedes Save & test.
  Cancel is separate from destructive connection controls. On mobile, wrap deliberately in
  stable order/full-width where needed, never shrink text or targets to make them fit.
- **Polish every state:** hover, focus-visible, active, disabled, loading, selected, error
  and success. Reserve space for pending labels/status; no button-width or footer jumps.
  Keep logical focus across save/refetch/error/back/re-entry; do not steal it on background
  completion or disable the only Cancel/readback path. Toasts supplement persistent state.
- Preserve warm charcoal/ivory/taupe, local Geist/Geist Mono, 4px spacing rhythm, restrained
  shadows, nested 14px/10px panel geometry and global capsule navigation. Form sections
  should feel related, not like unrelated cards or a generic admin template.
- Copy is short English: action + object, one useful hint when needed, no boilerplate,
  implementation chatter or repeated warnings. Never remove essential cost/consent,
  saved-versus-tested, incomplete/UNKNOWN or destructive-action explanations for aesthetics.
- Graphics are structural: existing Omnis mark, functional icons, subtle surface depth and
  status labels. No fake charts/metrics, hero, glow, gradients, gratuitous badges, 3D,
  animated background or decorative SVG. No wholesale Linear/Vercel clone.
- Native/house primitives first. Search can be a labeled input and paginated native button
  results; a custom combobox is not a prerequisite. If a complex widget is necessary, prove
  its keyboard semantics with the existing stack before adding any dependency.
- No decorative motion. Any already-admitted transition stays at most150ms, is removed for
  reduced motion and does not delay keyboard input. Measure real text/control contrast,
  preserve visible focus and use text plus state indication, not color alone.
- Start from the accepted composition. If a larger aesthetic change is genuinely needed,
  show one scoped before/after decision and obtain approval rather than calling it polish.

### Delivery discipline and evidence

Use `CONTRIBUTING.md` and the existing team-slice ownership contract. One orchestrator and
one assigned developer by default; parent owns scope/admission/integration, not parallel
product authorship. Freeze actual bytes for independent review; preserve the two complementary
reviews required for changed secret/authority/Stop/concurrency/transport boundaries. Reproduce
blocking findings, minimally fix them via the assigned developer, rerun affected checks and
focused re-review. Do not turn this into recursive report audits or duplicate suites.

Deliver the smallest complete vertical behavior through the real UI/API/PG consumer; no
pile of helpers or handoff after each commit. Keep every small coherent change committed,
including configuration/docs/fixes, with exact results/limits; stage only intended paths.
No amend/squash/rebase/push or adoption/cleanup of unrelated data. Preserve recoverable state
and continue admitted work until this deliverable, a genuine blocker/authorization boundary,
user stop or unsafe context/budget limit; never promise absence of every possible regression.

Preflight actual manifest commands, toolchain pins, imports/source, ownership/access,
producer/oracle and aggregate bounds before effectful QA. The global Node22 used for offline
mockup tests is not proof of the pinned product Node24/npm toolchain. Use actual manifests
and existing commands/targets, not remembered flags or a new harness. Missing prerequisites
are BLOCKED/NOT_RUN, not fabricated output or a weakened gate. Respect the existing two-cycle
harness-only limit; reuse unchanged scoped evidence.

Apply the concrete delivery preflights learned here before another expensive gate:
- After changing application copy, trace the exact old labels/defaults through every real
  browser caller, including B04 before/after restart. Run the affected existing journey first;
  do not discover a stale UI selector after the full API suite. Preserve user-authored text.
- Check matchers against the installed Playwright API, not jest-dom memory. For native
  selects verify the actual role/name and selected option. Check socket fixture signatures
  against their real stdlib callers, including loopback readiness, before provisioning PG.
- Map remaining visible actions to actual evidence: SOURCE/component, real API, or real
  browser/API/PG. In particular, do not infer Replace/Disable/Reconnect, chip removal,
  manual fallback, active-test Cancel or UNKNOWN readback from one successful happy path.
  Reuse covered actions; exercise only genuine live gaps through existing consumers, with
  the same security assertions and finite budgets. A delayed completion is not a new run.

After required reviews, QA the actual built/installed affected artifact on an admitted owned
isolated API/PostgreSQL fixture, not `settings-final.html` as a production substitute:
- First setup, saved-key multi-add/search/dedup, single/multiple/default/override persistence,
  exact selected-entry test, stale edit/CAS, invalid/revoked/missing credentials and key rotation.
- Provider catalog paging/partial/error/stale/manual fallback, safe exact IDs and bounded
  payloads; complete maximum request/reply fixtures, not only field lengths.
- Reload/restart and old-config migration without silent reassignment or key loss; no secret
  in browser storage, URL, output, validation error, trace or export; no resend/duplicate spend.
- Cancel/UNKNOWN/Stop and the same stale-wizard denial fixed in the mockup, on real callers.
- Browser desktop1280/1440 and mobile320/390, long IDs, native keyboard/focus, CSS200%, reduced
  motion and control contrast. Include one visible headed pass if the operator requests it.
  Capture loaded search/results (not only Loading), Review, saved/one/many/assignments and
  failures. Inspect screenshots against the reference, not just DOM assertions.

Run affected commands from the real manifests, plus the unchanged required canonical gate
at the final integration boundary. For documentary edits run the required renderer check
and documentation suite; regenerate HTML only for changed canonical Markdown. Keep technical
PASS, installed/live evidence and aesthetic approval separate. A skill/prompt/test count does
not establish premium aesthetics, sandbox enforcement or automatic obedience.

### Effects and stop boundaries

When explicitly activated, Prompt A authorizes scoped product development and normal
project-local deterministic verification on newly owned isolated fixtures, subject to all
repo admission/ownership rules. It does not authorize reading private keys, changing the
operator's installed instance/PGDATA, global configuration, remote installs, provider/target
traffic, LLM spending, CI publication or push. Prepare the provider-independent consumer first;
then obtain the concrete provider/model/data/call budget through the existing approval flow
for any live catalog/inference proof. Operator enters credentials in paired web, not chat,
argv or a copied file. Do not block all inert code on missing live permission or fake live PASS.

Final report: usable behavior, exact commit(s), real checks/limits, evidence/review status,
remaining genuine blocker and the operator action if any. Do not mark T2 or P4b complete:
role execution and mixed-role runs need their own consumers/gates. Do not start Prompt B.

## Prompt B — CLI → browser autopair: separate decision, not implicit implementation

Operate in `/home/kali/OmnisAI` read-only until the operator explicitly selects and authorizes
an authentication design. This prompt is NOT permission to weaken the current pairing policy.
Read CURRENT, architecture §4/§4.1–4.2, plan SL03, UI entry contract, CLI pair/open/default,
SessionStore and browser-session writer. Reuse the existing verified startup, owner/IPC,
cookie/CSRF/session and Dashboard route; valid sessions already land directly at Home.

Goal: a CLI launch opens a fresh/expired browser session at Dashboard without manually typing
a code, while preserving proof of local operator authority. Manual pairing remains fallback.
Never authenticate the first localhost client or remove Host/Origin/CSRF/session controls.

Compare only the smallest viable transports through the actual default-browser opener:
1. A short-lived, one-use launch ticket in the URL fragment, atomically exchanged for the
   existing session, bound to instance/generation/owner, invalid after Stop/restart. This is
   an explicit exception to current URL/argv prohibitions; disclose opener/process arguments,
   browser history/sync/extensions and residual exposure. It is never an API key, master key,
   IPC capability or long-lived session token. URL cleanup does not prove no exposure.
2. A private browser/native handoff that retains the no-secret-in-URL/argv invariant. Verify
   an actual available transport and its cost before claiming feasibility; do not install an
   extension, manage the personal browser profile or invent an opener-to-cookie API.

Return a concise recommendation, affected files/contracts, no-effect prerequisites and
positive/negative acceptance. Ask once for the unresolved security choice; stop before product
auth edits. A transport choice alone does not authorize its implementation in this analysis
session. A later explicit implementation mandate must bind exact auth/lifecycle scope and tests.

For that later mandate: amend affected canon first; separate launch tickets from manual
pairing challenges, retain one-use/expiry/rate limiting, preserve explicit logout and fallback,
prove stale/replay/foreign-site/restart/Stop refusal and exact cookie readback before Dashboard.
No provider IO at open, no new assessment/autoresume. Redesign fallback only within the accepted
Omnis identity, English copy and existing keyboard/Stop rules. Reuse the same scoped skill
selection; auth proof is not a graphics task and does not need additional design agents.

## Discovery provenance and limits

- Hermes skills were inspected with the native catalog/skill loader; local Codex SKILL.md
  paths above were read. Codex CLI `0.163.0` was checked via version/help only, no model/session
  launch, authentication inspection, skill install or configuration change. Presence on disk
  is not a claim that every skill is enabled/discoverable in a future Codex session.
- Primary host guidance checked: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills/
  and https://developers.openai.com/codex/skills/ . Use current host docs/help if invocation differs;
  do not guess slash commands or assume a Hermes skill invocation exists in Codex.
- No package downloads, Figma/MCP accounts, provider calls, image generation or new graphical
  runtime were tested or authorized while preparing this prompt.
