# Settings C polish — QA independentă PASS_SCOPED

**Verdict:** PASS_SCOPED pentru consumerul built-browser → API → private PostgreSQL/TLS sintetic, pe `7795b66f1dd62f93043d430543d2450d6899b871`. O singură tentativă, fără retry, editări de cod/harness, commit sau rollout. Nu închide gate-ul global; adjudecarea aparține părintelui.

## Snapshot / execuție

- Repo `/home/kali/OmnisAI`, tracked/staged clean înainte și după; cele două căi untracked protejate nu au fost citite sau atinse.
- Cele opt SHA256 din `/home/kali/.hermes/cache/scratch/settings-polish-freeze-yLnpHE/freeze.json` coincid înainte/după; diff față de `0b882cbd7d90d247f130718ac877168267788963`: `8adc2be2ab2a3de357c23618e3ea4d46e03e69ae152fe254265fd339bd452957`.
- Cele patru assets built coincid cu freeze după rebuild-ul targetului. SHA256 `web/dist/omnis-web.json`: `fd18f2f2376cef459ae006ff293fb2d9d083d1525621b95a089e3ea05197c13d`.
- R1/R2 APPROVED_SOURCE_SCOPED și admiterea părintelui precedă această QA. Preflight-ul propriu suplimentar: hashes/acces, scratch liber 6181240832 bytes, MemAvailable 4349656 kB. Prerechizitele/collect-only deja verificate de părinte nu au fost rerulate.

Comanda efectivă, cu root nou creat prin `mktemp -d /home/kali/.hermes/cache/scratch/spq-XXXXXX`:

```sh
env -i HOME=/home/kali PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch/spq-rNtk86 PYTHONDONTWRITEBYTECODE=1 api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target test-settings-models-ui-pg --timeout-seconds 600 --uv /home/kali/.local/share/omnis-toolchains/uv-0.12.19
```

Output redirectat în `runner.log`; proces original `proc_547000e81697`, încheiat **exit 0**. `--check` este efectful, nu dry-run. Targetul existent a făcut build-web și cazul `test_api_pg_sdk_protocol_and_replay[settings_ui]`: **1 passed in 97.52s (0:01:37)**. Marker original `SETTINGS_UI_REAL_API_PG_TLS_API_RESTART_PASS`. Receipt original `gate.log.result.json`: `{"schema_version":1,"code":0,"family_drained":true}`. Shellul toolului a emis două avertismente `can't change option: zle` înaintea runnerului; nu au afectat comanda sau rezultatul.

## Dovezi originale / criterii

Root dovezi `R=/home/kali/.hermes/cache/scratch/spq-rNtk86`; DB `D=R/db-080d1bbc20794374`; browser `B=R/pytest-of-kali/pytest-0/test_api_pg_sdk_protocol_and_r0`.

- `B/settings-browser.log` conține două `E2E PASS settings-models`, înainte și după restart API, Chromium **153.0.8010.12**; browser/context izolate, fără atașare la operator.
- `B/browser-result.json` păstrează rezultatul **after**: passed=true, entries=32, apiRestartReadback=true, historyReadback=true, disabled=true, selectionRevision=3, exactTestOperation=`a0f05d4d-33c9-4b4f-b84b-90ebfcbad30c`; requestCount=27, externalRequests=0, pageErrors=0, secretChecks=true. Aceste contoare sunt ale etapei after, nu totalul ambelor etape.
- Limita producerului existent: etapa after citește/validează receipt-ul before, apoi îl suprascrie la aceeași cale. Nu există un al doilea JSON before păstrat; nu reconstruiesc contoarele sale. Cele două PASS-uri originale și aserțiile executate rămân dovezile înainte/după.
- Fluxul executat verifică Add models / Connection → Models → Review, saved ≠ tested, salvarea unui model fără default implicit, confirmarea separată Save assignments, cheia deja salvată fără resalvare, search/paginare și Back cu selecția păstrată.
- Consent direct: provider/model exact `OpenRouter · fixture/00`, checkbox inițial unchecked, Send disabled; după acord, **Cancel fără Send**, zero model-test writes până la acest punct. Wizard-ul trimite numai după acord explicit pentru `fixture/02 via OpenRouter`.
- Testul original nemodificat a trecut aserțiile pentru **4 GET catalog + exact 1 POST inference** la peerul TLS sintetic și exact **1 SENT** în ledger; nu sunt contoare inventate din browser. `fixture/02` produce `OMNIS_MODEL_TEST_OK`; cap cerut64, observed model `fixture/observed`, usage9/7/reasoning UNKNOWN și cost UNKNOWN apar în captura detaliilor. Nu provider extern/spending.
- Competing writer autentic: CAS vechi →409 `REVISION_CONFLICT`, selecția avansată rămâne intactă, Reload fără resubmit. Save & test nu schimbă defaultul `fixture/00`, override-ul explicit sau capurile. Salvarea explicită ulterioară persistă Brain=`fixture/01`, cap37, default cap64, selection revision3; investigator/validator rămân null/Use default.
- Conexiune dezactivată rev2: refresh stale și nou test refuzate409 `CONNECTION_UNAVAILABLE`, fără inference suplimentară; Continue/Test/Save assignments disabled conform aserțiilor. Reload/cancel/restart nu retrimit operația; istoricul exact este citit după restart.
- Census **13 tabele**, egalitate exactă before/after restart în testul original: provider_connection_revision, provider_settings_command, provider_selection_revision, provider_model_entry, provider_model_entry_revision, provider_model_registry_revision, provider_model_command, model_record_v2, model_command_v2, system_operation, system_operation_event, model_dispatch_v2, model_dispatch_event_v2. Producerul compară rândurile în memorie; nu pretind un export de rânduri/counters care nu există.
- Disclosure-uri native: închise inițial, Enter expand/collapse, focus păstrat și outline2px non-none la1440/390; fără overflow la1440/1280/390/320. Testul a verificat reduced motion și200% CSS zoom. UUID-ul operației este citit numai după deschiderea Operation details; Cancel terminal confirmat nu mai apare.

## Inspecție vizuală independentă

Inventar calculat: **45 PNG**, **47 artefacte browser** (PNG + browser-result.json + settings-browser.log), **51 artefacte originale selectate** incluzând runner.log, fixture.json, gate.log și gate.log.result.json; nu număr vault/credentiale/PGDATA ca evidence publică. Inspectate prin vision **16 capturi noi**, plus2 referințe și2 capturi UI4 istorice.

Capturi noi inspectate: pentru fiecare prefix de mai jos, ambele sufixe `-1440x1000.png` și `-390x1000.png`, sub B:

- settings-models-saved-many-assignments
- settings-models-saved-many-assignments-details-expanded
- settings-models-review-many
- settings-models-review-many-details-expanded
- settings-models-direct-test-consent-details-expanded
- settings-models-test-completed-details-expanded
- settings-models-stale-wizard-denied
- settings-models-api-restart-disabled

Referințe: `/home/kali/.hermes/cache/scratch/settings-polish-reference-xcPfhm/reference-{desktop,mobile}.png`. Before UI4: `documents/verification/settings-c-evidence/ui-screenshots/ui4/settings-models-saved-many-assignments-1440x1000.png` și `settings-models-review-many-390x1000.png`.

Compoziția C rămâne recognoscibilă: modele grupate/provider și Add models, apoi assignments separat; wizard inline, nu dialog. Detaliile secundare nu mai domină starea implicită. Consentul și warningurile sunt vizibile în afara disclosure-urilor; salvare/test/asignare distincte. Capturile expandate arată focusul și capurile/identitățile integrale. Mesajele unknown/stale și recovery rămân vizibile. Nu am identificat un blocker nou demonstrat de aceste capturi.

Limite vizuale: lista sintetică32modele produce pagini foarte lungi. Capturile fullPage arată artefacte Skip to content inclusiv în before UI4; fără pereche viewport/hit-test la același scroll nu le promovez la defect live și nu pretind occlusion-free universal. Pe mobil, suffix-ul lung Unavailable din select nativ este tăiat vizual, dar identitatea/statusul complet sunt repetate vizibil în afara lui; nu este pierdere de identitate demonstrată. Aceasta nu este o aprobare estetică nouă.

## Cleanup — ownerul original și readback independent

- Project exact: `omnis-p01-cb3dc481cd2c4dd8b382aefd7bbe104f`.
- CID exact: `9c676b331663705934199c829e3387a4ed406d474fb4ac74fd34d2d9a7e64327`.
- Docker endpoint `unix:///run/docker.sock`, daemon `94260307-c33f-46ac-af7c-8a5ac1a7ffdc`, imagine `sha256:8d76d8de17e883d3995f76252e260bc6b7761e9c23edbf3356b0676d37c49ddb`; PG18.6, network_none=true, system_id7701323727429173278 în runner.log.
- Runnerul a raportat `absent=True networks_absent=True socket_absent=True uncertain=False`; nu am executat cleanup suplimentar/global.
- Readback independent cu `docker --host unix:///run/docker.sock info --format '{{.ID}}'`: exit0, același daemon.
- `docker --host unix:///run/docker.sock inspect <CID-exact-de-mai-sus> --format '{{.Id}}'`: exit1, `No such object` pentru CID-ul exact; `ps -a --no-trunc --filter id=<CID-exact-de-mai-sus> --format '{{.ID}}'`: exit0, gol.
- `docker --host unix:///run/docker.sock ps -a --no-trunc --filter label=com.docker.compose.project=omnis-p01-cb3dc481cd2c4dd8b382aefd7bbe104f --format '{{.ID}}'` și `network ls --no-trunc` cu același filter: exit0, goale. Nu există network ID propriu de inventat: fixture-ul folosește network none.
- `D/socket/.s.PGSQL.5432` absent; `D/data` păstrat UID1000/mode0700, `D/data/18/docker/PG_VERSION` există și conține18. Receiptul familiei este drained=true; readbackul Docker nu este certificat separat pentru fiecare proces istoric. Datele și logurile private sunt păstrate, nu restore-tested. Nicio resursă/operator root/config/browser8780 accesată.

## Hashuri și limite finale

SHA256 originale:

| Artefact | SHA256 |
|---|---|
| R/runner.log | 806f515f766c5898d5449624c69360b9240ac4ef77426b15181ff07a21b59294 |
| D/gate.log | a48fd3df16e3d9ec3d526f103a47244e076484612535ba2f1db3bb23c1ea0578 |
| D/gate.log.result.json | dba7684cc05e7e66698376a87dabb6f8fac91e71f52684f54bb97887558487d6 |
| D/fixture.json | 4bbd068c085a8107ac3a1282f4c212b8886b827c1a28c93535eefbb917fad1cd |
| B/browser-result.json | bb113c899a404906a6c48a2bbf870ea3b81618a6dd0978133c26ef1b178876e6 |
| B/settings-browser.log | bf0efdf01540950d20975010bee321546d13eac861689aa6f93c997f7633a1d8 |

Inventar45PNG digest `f625eb27c0f45565cb9bfd4e305cb46eb566a1758d88d617f88ddc3cf60f2eae`: SHA256 peste JSON UTF-8 cu lista sortată după path, obiecte `{name,sha256}`, `sort_keys=True,separators=(',',':')`, fără newline.

Guards nemodificate before/after: `api/tests/test_model_test_v2.py` SHA256 `41d21df9a86edc64447ed824f9670ba05dbf98754e012d947d02d0d130247487`; `api/tests/test_web_e2e.py` `ab36bbddbfec3645bdc9cfab6025241ae4fd8f3c1e5a22061861294ba0594075`; `ops/run_test_db_gate.py` `e5279ca0d9079b98f2ee8436eb1fd2e45634e0c66319be4b8194b35d61c782c2`.

Singura scriere manuală este acest raport scratch; runnerul existent a produs artefactele/fixture-ul și a reconstruit assets identice. Fără repository/docs/skills/global writes, instalări sau upgrade. Nu am rerulat check-web/controale neafectate; PASS212/20 workers2 al părintelui rămâne separat. Reticle NOT_INTEGRATED/NOT_RUN în această probă, Chisel BLOCKED_NO_GO.

Neexecutat: suite canonical, screen readers/toate browserele, test live provider sau operator, rollout/restore, viewport-pair pentru artefactele fullPage. Rămân canonical BLOCKED_BUDGET/NOT_CLOSED, default check-web FAIL/cauză UNKNOWN, UI1/2/3 FAIL istorice și rollout BLOCKED_NO_SUPPORTED_IN_PLACE_UPGRADE; această QA nu le resetează și nu închide integrarea.
