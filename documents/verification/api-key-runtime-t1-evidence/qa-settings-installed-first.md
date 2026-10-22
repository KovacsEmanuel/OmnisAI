# QA independentă Settings INSTALLED + Chromium — PARTIAL / CHANGES_REQUESTED

## Verdict și identitate

Prima probă reală pe aplicația **build-uită și instalată**, nu Vite/source ASGI, a exercitat Save → API/owner → PostgreSQL/seif → current GET/UI, selecție, recovery receive-only, CAS și Revoke. **Nu este acceptare completă**: focusul Save eșuează în Chromium; primul Start explicit după Stop a refuzat `PORT_CONFLICT`. La această frontieră am oprit fără retry. Autounlock/restart și negativul LOCKED sunt NOT_RUN. T1/G04a și celelalte gates rămân deschise.

- Repo: `/home/kali/OmnisAI`; sursă admisă `af8c3ba5c64c5d6122a5fde6deaeba09e2ff4873`.
- În timpul QA părintele a avansat HEAD la `506c1e409ea209f6bcb8ee61261a3fc1d39a98cf` numai pe documente/evidence. `git diff --exit-code af8c3ba5..HEAD -- api/src cli/src web/src ops api/pyproject.toml api/uv.lock cli/pyproject.toml web/package.json web/package-lock.json`: exit0. Nu am modificat/commit-uit produsul. HTML-ul untracked protejat nu a fost citit/atins/copiat.
- Bundle autoritativ: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1-settings-artifacts/bundle-web-fixed`; release `0.1.0`, format3, profile `t1-provider-settings`, schema `0014_provider_settings`.
- `release.json` SHA256: `9ef854c6d2cca95a81bae032b9e7667e5c067517a40ed73f2b40da5173b63616`. Toate cele10 payload hashes reverificate înainte și după execuție.
- API wheel SHA256: `ca2096d466c0b8ec4a31ccb26cf31b43458c77ee08f626384824a4fda271dcae`; CLI wheel: `3cf775e962b85716542207af48f05be38396ef7e4aba078ffa339d2e2f7e0f9e`.
- Root nou, absent înainte: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q` (Q). CLI instalat: `Q/venv/bin/omnis`; release instalat: `Q/d/omnis/releases/0.1.0`.
- Image construită prin `install-image`: `sha256:59df70b899383f776cb71412135fead2942f3a6250afc0e0f05fc4063569e25e`, etichetată/profile+manifest conform `Q/d/omnis/image.json`. Imaginea rămâne păstrată.
- Instance: `647f4297-2eb1-4f1a-9093-0a974b44c622`; proiect `omnis-local-24d5844fce7947e8bd9afab001d3a981`; origine `http://127.0.0.1:48765`; system_identifier PG `7699608422299463723`.
- Browser pinned Playwright din `src/web/node_modules`; `PLAYWRIGHT_BROWSERS_PATH=/home/kali/.cache/ms-playwright`; Chromium **153.0.8010.12**. Niciun browser download sau Chromium de sistem substituit.

## Comenzi și ieșiri originale

Prefixul CLI de mai jos este `Q/venv/bin/omnis`. HOME/XDG_CONFIG_HOME/XDG_DATA_HOME/XDG_STATE_HOME/XDG_RUNTIME_DIR/TMPDIR sunt exclusiv Q/h,c,d,s,r,Q; override-urile ambient OMNIS au fost eliminate explicit, fără citirea configurației operatorului. Niciun serviciu alternativ/owner nou.

| Comandă | Exit / rezultat |
|---|---|
| canonical uv0.12.19 `venv --no-config --no-python-downloads --python .../src/cli/.venv/bin/python Q/venv` | 0 |
| uv `pip install --no-config --python Q/venv/bin/python --no-deps B/cli/omnis_cli-0.1.0-py3-none-any.whl` | 0 |
| `install --bundle B` | 0 |
| `install-image` | 0; OCI privat construit |
| `start --no-open --port 48765 --json --startup-timeout 120 --cleanup-timeout 90` | 0 / READY,12.912s |
| `status --json` | 0 / READY |
| `python -I -B Q/run_browser.py initial` | 1; Save real reușit, apoi selector QA exact-label incompatibil cu label-ul selectului |
| `python -I -B Q/run_browser.py continue` | 0; restul journey finit executat, **o aserțiune soft de produs FAIL** |
| `stop --json --shutdown-timeout 120` | 0 / STOPPED,9.097s |
| `status --json` | 0 / STOPPED |
| **același Start explicit cu aceleași limite** | **2 / REFUSED, reason PORT_CONFLICT**,0.667s |
| `status --json` final | 0 / STOPPED, generation2, admission_open=false |

Originalele sunt `Q/evidence/install-{0..3}.{stdout,stderr}`, `install-commands.json`, `first-start.*`, `first-status.*`, `journey-{initial,continue}.*`, `first-stop.*`, `first-stopped-status.*`, `restart-start.*`, `final-status.*`. `*.command.json` păstrează argv/exit/timp, fără coduri pairing.

Pairing real prin helperul existent `cli/integration/installed_pair_open.py::tty_pair`, CLI instalat și PTY; codul a rămas numai în memoria Python și stdin-ul browserului. Nicio rută debugging pentru emitere, nici log/cookie/CSRF/pairing secret în raport. Primul helper/browser a fost închis și joined înainte de continuare. Nicio mutație repetată pentru a reconstitui stdout.

## Matrice observabilă

| Criteriu | Rezultat și limită |
|---|---|
| Root/port fresh, pinuri și help real | PASS; root absent,48765 fără listener; digesturile reale Python/PG atestate. Două greșeli de discovery fără efecte sunt păstrate în preflight.json: aliasul `postgres:18.6` nu exista, iar `python -m omnis_cli` nu are __main__. S-au consultat constructorul și console-script-ul real, nu s-au schimbat pinuri. |
| Instanță nouă / schema0014 / profil | PASS; READY și query PG READ ONLY autentice, toate3 tabele Settings goale înainte de Save. |
| Topologie fără Hermes/provider relay | PASS_STRUCTURAL_TOPOLOGY: exact api/db/supervisor, network internal, fără porturi Docker publicate; vault și vault-key montate numai la supervisor. Nici runtime/catalog/native/provider-relay service. Nu este packet/syscall proof universal. |
| Nicio master key înainte de Save | PASS; metadata/existență înainte de browser Save=false. Niciodată citite/printate/hash-uite bytes master.key. |
| Save formular → current GET/UI → PG/seif | PASS; cheia sintetică NEFUNCȚIONALĂ intră numai prin input; exact1 Save inițial, HTTP200/current configured+present/UNLOCKED; istoric PG real. |
| Secret write-only | PASS_SCOPED pentru input gol, DOM, localStorage/sessionStorage, cache privat React Query observat real și răspunsuri publice Settings; logurile celor3 containere și forwarder nu conțin canary. Nu am certificat toate mecanismele browser storage: cookies/IndexedDB scan NOT_RUN. |
| Model default + Brain override/clear | PASS; exact `Exact/Default:Case`,output137 și `Exact/Brain:Case`,output211; surse persisted override/default; clear Brain=null; Investigator/Validator moștenesc default. |
| Reload și reopen fără PUT | PASS; ambele navigări reale, count PUT neschimbat. |
| Lost browser reply | PASS; interceptor finit **forwardează PUT real**, primește HTTP200/receipt real, apoi abort browser response. Reload menține command UUID; Recover citește exact `/commands/{UUID}` apoi current GET. Exact1PUT și zero resend automat pentru acea comandă. Nu este provider double sau fault în DB/owner. |
| Două taburi CAS | PASS; ambele citesc rev2; primul rotate→rev3, al doilea stale PUT→409/REVISION_CONFLICT; mesaj persistent, niciun fals Saved, input gol și Save blocat până la Reload explicit. |
| Revoke și ciphertext păstrat | PASS; rev4 enabled=false, credential_present=true, readback/UI reale; model Save disabled; ulterior reactivare explicită rev5. |
| Focus Chromium Save model selection | **FAIL**, vezi findingul de mai jos. Tasta Tab ajunge la Save și focus-visible/ring există înainte; după Enter și răspuns activeElement=BODY. |
| Labels/keyboard/error/reflow | PASS_SCOPED: labels legate pe controalele active; key invalid whitespace nu permite submit; Tab→Save→Enter real; eroare409 vizibilă;1440/390/320 fără overflow document și capturi tehnic inspectate fără clipping/overlap. Nu screen-reader/all-controls/all-browsers/WCAG complet. |
| Contrast numeric / 200% / forced colors | NOT_RUN; culorile DOM planificate pentru următorul boot nu au fost colectate după refuzul Start. Nu declar WCAG/estetică aprobate din capturi. |
| Reachability / inference / Test model | UI corect NOT_VERIFIED, fără buton Test model. **SystemOperation/sender/model consumer încă lipsesc**, nu PASS. Nicio cheie reală/provider/target IO executată. |
| Stop și retenție | PASS; Stop ACK/STOPPED și readback exact CIDs/network/forwarder/listener/IPC absente; PGDATA/vault/master/pending/receipts păstrate. |
| Start aceeași instanță/autounlock | **BLOCKED/NOT_RUN după primul refuz PORT_CONFLICT**; nu retry, nu deadline extins, nu root/port înlocuit. |
| LOCKED cu master absent și local Revoke | NOT_RUN dependent de Start refuzat. **Master key nu a fost mutată deloc**; nu există cleanup de rename de făcut și nu se revendică restore/bootstrap feature. |

Numere brute ale celor două fișiere browser:85 aserțiuni PASS și1FAIL; acestea includ verificări repetate de răspuns și **nu sunt85 scenarii unice**. Capturile5 sunt separat, nu teste PASS. `browser-initial.json` păstrează TimeoutError-ul original de driver după Save; `browser-continue.json` păstrează journey-ul finit și FAIL-ul de focus.

## Findings și tentative nereușite

### QA-SETTINGS-FOCUS-01 — MEDIUM, CHANGES_REQUESTED pentru acceptance keyboard/focus

- Locație: `web/src/features/engagement/ProviderSettings.tsx:39,56,66–73,109` (sursa testată identică bundle-ului).
- Reproducer real: configurează default+Brain; focus prin Tab pe **Save model selection**; Enter; așteaptă Saved/current. Înainte: buton focus-visible cu outline solid2px. După HTTP200/current și re-enable: **document.activeElement este BODY**, nu butonul. `browser-continue.json` păstrează exact observația; nu a fost transformată într-un exit0=PASS.
- Guardul `disabled={disabled || ...}` dezactivează controlul focalizat în timpul requestului. Păstrarea nodului montat rezolvă identitatea React, dar nu dovedește focusul nativ Chromium în disabled→enabled.
- Remediu minim propus developerului, nu executat de QA: păstrează efectiv focusul pe aceeași acțiune în Chromium fără a slăbi busy/admission/CAS și fără a-l fura dacă operatorul a mutat focusul; regression browser real pentru ambele cazuri. Testul SOURCE anterior pentru UI-FOCUS-N01 nu închide acest rezultat INSTALLED.

### Restart frontier — PORT_CONFLICT, nu retry

- Original: `restart-start.stdout` conține `REFUSED / PORT_CONFLICT`, exit2; stderr gol.
- `cli/src/omnis_cli/start.py:193–200` face bind fără SO_REUSEADDR și normalizează orice OSError la PORT_CONFLICT.
- Imediat după refuz: `ss -tanp '( sport = :48765 or dport = :48765 )'` a arătat TIME-WAIT inclusiv local48765, fără listener; query exact făcut ulterior și păstrat în `restart-refusal-ss.stdout` nu mai avea intrări. TIME_WAIT este compatibil cu guardul existent; errno original nu este retenționat, deci nu atribui o cauză exclusivă.
- Este blocker concret pentru acest Stop→Start imediat; politica guardului este deliberată, deci **nu adjudec automat defect de siguranță** și nu recomand SO_REUSEADDR orb. Părintele decide un preflight de rebind și o nouă tentativă admisă ori o remediere scoped care păstrează refuzul portului străin. În acest mandat: stop frontier, autounlock/LOCKED NOT_RUN.

### Driver, păstrat separat de produs

Primul browser a salvat real apoi `getByLabel('Default connection',{exact:true})` a expirat30s. Label-ul real include textul opțiunilor (`Default connectionChoose connectionopenrouter · revision 1`), deci selectorul exact era greșit. Am restrâns driverul la selectul existent `name=default-connection`/`brain-connection`, cu control DOM pozitiv și absent-name negativ, și am continuat de la configurația deja salvată. **Nu am resalvat comanda inițială și nu am adăugat un nou lifecycle owner/general harness.** Originalul eșuat rămâne. Nicio a treia expansiune harness-only.

## Erori browser / logs

- pageErrors:0 în ambele execuții.
- Console initial:401 înainte de pairing. Continue:401 înainte de pairing, ERR_FAILED al reply drop intenționat,409 al stale negativ.
- requestFailures continue: un `/api/v1/settings/providers` ERR_FAILED intenționat și4 `/health/ready` ERR_ABORTED la navigare/închidere. Aceste anulări sunt păstrate, **nu declar zero erori de rețea**; asocierea exactă fiecărui health abort cu un request ID/phase nu a fost instrumentată.
- Logurile originale private au fost salvate înainte de îndepărtarea containerelor: `configured-live-{api,db,supervisor}-logs.{stdout,stderr}` plus forwarder.log retenționat. `canary_log_hits=[]` pentru acest scope.
- Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. Nicio instrumentare de producție adăugată.

## Cleanup și date păstrate — confirmat fizic, nu dedus din exit

STOPPED final cu aceeași instanță/generation2/admission_open=false. Exact:

- api CID `9fd87650c864939a5c9c37d9f8a0eb1b9f61773cf38a0e21aa1e0b0e38179892`: absent;
- db CID `b500b1e3f6128e766156b72b631a1bec718e689bb4bda5b36579ab69203e5eca`: absent;
- supervisor CID `0bb6f93d3f244cdf5dfb675f60871c2d011b3f6eb4703479b38a9913d024ba38`: absent;
- network ID `608c79b73ba87ea4895a39c3d16b17aecd61c285ccd7ba18158ae1b966f01c86`: exact inspect absent, project-list empty;
- forwarder PID690680/start_ticks14318289: `/proc/690680` absent; loopback48765 connection refused; control.sock/api.sock absente prin lstat/lexists și zero socket entries în directoarele owned;
- journal `teardown_completed`: forwarder/api/supervisor/db/network/ipc, și Stop receipt/finalize readback păstrate;
- PG bind-root inode9056352 și PGDATA `/postgres/18/docker` inode9060550 păstrate. Datele interne PG sunt owned UID999, nu au fost deschise/chmod-uite de QA;
- vault/vault.json inode9085192, vault.pending și master.key inode9085320 (0600,32bytes) păstrate, metadata identică din configured-live până la final și ciphertext hash identic. **Nu am citit/hash-uit master key**;
- `Q/s/omnis/stop-*.json`, jurnal, logs, PGDATA, vault/key, instalare/bundle/image rămân pe loc. Niciun prune/down-v/pkill/kill străin/remove de date.

Ultima configurație legitimă înainte de Stop: openrouter connection `210104f3-031e-4d30-a658-e263db3e3502` rev5 enabled=true/present=true, selection rev3 default `Exact/Default:Case` output137, connection_revision5, toate override-urile null. Persistența PG a fost citită înainte de Stop; **nu este revendicat autounlock după reboot**.

## Locatoare originale pentru părinte

- Acest raport original: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q/independent-settings-report.md`.
- Matrice/evidență JSON: `Q/evidence/acceptance-summary.json` și `browser-{initial,continue}.json`.
- Topologie și boot: `Q/evidence/first-topology.json`, `first-containers.original.json`, `first-networks.original.json`, `fresh-pg.stdout`.
- Persistență live/loguri: `Q/evidence/configured-live-readback.json`, `configured-live-pg.stdout`.
- Cleanup exact final: `Q/evidence/final-stopped-readback.json`, `final-status.stdout`; originalele Docker inspect/absence adiacente.
- Capturi reale, input secret gol înainte de fiecare:
  - `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q/screens/continue-stale-desktop.png`
  - `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q/screens/continue-revoked-desktop.png`
  - `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q/screens/continue-width-1440.png`
  - `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q/screens/continue-width-390.png`
  - `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q/screens/continue-width-320.png`

Singurele fișiere create/modificate de QA sunt în Q: venv/install/data/evidence/screens și micile drivere scratch `qa_local.py`, `run_browser.py`, `journey.mjs`, `observe.py`, raportul și sumarul. Niciun commit, schimbare globală, profil existent, cheie personală sau provider/target real. Părintele adjudecă focusul și re-admiterea restartului; nu închid T1/gates.
