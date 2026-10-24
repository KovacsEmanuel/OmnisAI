# R1 — T1 SENT / crash / reconcile / no-resend

**Verdict: APPROVED_SCOPED — review independent al probei installed API component process-cut. Findings concrete: niciunul în scope-ul atribuit.** Nu este QA independentă, acceptare T1 integrală sau aprobare de integrare.

## Identitate și mandat

- Checkout: `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`, branch `impl/t1-sent-recovery`, curat la început și la readbackul final.
- HEAD exact: `be72942d82dfa6caf0c1c42c095306a5e33eaa81`; bază: `f26beb4e9f7611dbec0b0c1a15f03e1761fc8317`.
- Delta: numai `api/tests/installed_sent_probe.py` și adaosul de la linia 1002 în `api/tests/test_model_test_v2.py`; codul produsului este neschimbat.
- SHA256 helper: `e3050cf8d148d5a575eddf223afa6ed9f047ac6ae872cd4572ebd6556d55e093`; blob `cc23c4b1db12a0583966ca0bb9bdda75bf7626ec`.
- SHA256 test: `d2f5fbf7c4e293ab5831bdb0cd0e4393a2c62f5e2234b2d185c02b7c3c9fe92f`; blob `917267660f2f65e0fe2505955927892118cdb593`.
- Identitățile coincid cu `evidence/sent-freeze.json`. Contract: arhitectura actuală §5, în special idempotency/owner-loss, și §5.2 (SENT durabil înaintea trimiterii, UNKNOWN fără refund/replay SEND).
- Cerință → consumer → risc → decizie: producerul `ApiKeyModelTest` instalat, moarte reală la intrarea senderului și recuperare prin owner nou; detectarea unui SENT doar în memorie, producer fabricat, RELEASED/zero usage sau resend; aprobarea ori respingerea strictă a acestei probe.

## Verificarea producerului, ordinii și oracle-ului

| Criteriu | Urmărire în bytes și evaluare R1 |
|---|---|
| Componente instalate reale | Helperul construiește wheel normal, verifică modulele față de sursă și instalează offline (`installed_sent_probe.py:10–61`). Copiii folosesc Python-ul venv cu `-I -B`, verifică toate modulele și originile importurilor (`:89–104`; `test_model_test_v2.py:1040–1059`). Am comparat independent, read-only, cele două wheeluri și instalările păstrate cu sursa: **113 module identice** în fiecare. |
| Producer autentic, metadata explicit sintetică | Conexiunea/selecția trec prin `ProviderSettingsOwner.handle`, nu prin inserții de test. Start înainte de refresh trebuie să refuze `CAPABILITIES_REQUIRED`. Singurul răspuns substituit este `sender.metadata`; acesta execută guardul autentic, apoi `runtime.refresh` validează și persistă capability/result (`installed_sent_probe.py:158–199`; `model_test_runtime.py:301–345,475–595`). Nu se injectează direct READY, operation, dispatch ori SENT. |
| SENT comis înainte de crash | `runtime.handle` comite admiterea înainte de spawn (`model_test_runtime.py:436–441`). `run` salvează RUNNING și SENT în admission, iese din tranzacție și abia apoi intră în `sender.send` (`:708–748`; `instance/service.py:271–295,451–464`). Monitorizarea `PY_START` omoară procesul prin SIGKILL la intrarea metodei reale, înainte de corpul ei, fără patch pe send (`installed_sent_probe.py:114–128`). Testul cere exit `-SIGKILL` și citește DB prin conexiune separată după moarte: RUNNING/revision2, RESERVED/SENT, fără outcome/output (`test_model_test_v2.py:1109–1142`). Oracle-ul nu confundă logul `send_entry` cu dovada commitului. |
| Lease real, proces nou | Testul așteaptă expirarea lease-ului după ceasul DB, fără UPDATE/release artificial al ownerului mort (`test_model_test_v2.py:1143–1159`). Copilul nou cheamă `InstanceService.acquire`, care verifică lease-ul, închide admiterea și incrementează epoch-ul (`service.py:297–344`). Se verifică owner distinct, epoch incrementat și admitere închisă. |
| Reconcile / UNKNOWN / no-refund | `reconcile` drenează scope-ul moștenit înaintea settlementului, nu apelează `run` (`model_test_runtime.py:74–143`). `settle` distinge SENT de nesent și produce SETTLED, nu RELEASED (`:774–855`). Oracle-ul cere FINISHED/revision3, UNKNOWN/OWNER_LOST, usage UNKNOWN, cost/tokeni/observed/output neinventate; censusul păstrează rândurile anterioare și cere exact RESERVED/SENT/SETTLED (`installed_sent_probe.py:204–225`; `test_model_test_v2.py:1160–1177`). Aceasta este no-refund pentru permitul/accountingul V2, nu probă de rambursare financiară upstream. |
| No-resend și replay nou | Tripwire-ul metodei reale este calibrat prin controlul `deny_send` cu exit79, fără schimbări DB/relay. La recovery, orice intrare în send sau metadata ar termina copilul nenul. Relay-ul real acceptă numai FENCE/DRAIN înainte de DNS/connect, iar lista acțiunilor trebuie să fie exact acestea. Al doilea proces de recovery citește/rejoacă aceleași comenzi, refuză payload schimbat și nu creează taskuri. Censusul final permite numai schimbarea lease-ului (`test_model_test_v2.py:1090–1108,1178–1183`; `installed_sent_probe.py:204–226`). |
| Limita censusului | Sunt citite toate tabelele public existente, cu seturi explicite de tabele schimbate și păstrarea rândurilor append-only. Citirile sunt după terminarea copiilor, nu snapshoturi concurente cu producerul. Ledgerul/dispatchul și commandurile nu pot fi înlocuite sau multiplicate fără a contrazice aserțiile curente. |

## Verificări efectuate de R1

- `git status --short --branch`, `git rev-parse HEAD`, diff bază→HEAD, blobs și `sha256sum` pe ambele fișiere: identitate confirmată, exit0.
- `git diff --check f26beb4..HEAD` și `git diff --exit-code f26beb4..HEAD -- api/src cli/src`: exit0; produs neschimbat.
- Python `-B`, exclusiv citire/stdlib: compararea hashurilor source↔wheel↔instalare pentru artefactele păstrate; parsare AST helper/test/PROBE; exit0. Nu am executat codul produsului sau testele.
- Citire directă a stdout-urilor producer/recovery din freeze, verificarea SHA256 și a succesiunilor de evenimente: exit0. Readbackul păstrat arată READY → send_entry și recovery FINISHED/UNKNOWN/OWNER_LOST cu epoch-uri succesive, view identic la replay. Acestea sunt artefacte ale autorului, nu o nouă rulare R1.
- Rezultatul autorului **71 PASS / 116.74s / exit0** rămâne dovadă atribuită autorului; nu îl prezint ca QA executată independent. Nu am pornit PG, servicii, supervisor, provider sau alte procese de produs.

## Dispoziție și limite

Nu există finding care să blocheze această probă restrânsă. Aprobarea privește exact bytes de mai sus și oracle-ul lor, nu toate comportamentele runtime-ului neschimbat. Integrarea și acceptarea, inclusiv reviewul complementar și QA admisă separat, aparțin părintelui.

**NOT_RUN:** supervisor/launcher instalat complet, API HTTP/UI, provider real, TLS/SDK/inferență, connect/write și crash după bytes upstream. Metadata rămâne sintetică; relay-ul host este importat din sursă, nu instalare CLI completă. Bundle-ul release nu a fost reauditat; identitatea independent verificată aici este source↔wheelurile probei↔venv-urile păstrate. Nu certific exact-once upstream sau absența generală a defectelor.

Counter2 istorice PENDING/metadata și connect/write rămân deschise și neschimbate; această aprobare nu le închide și nu resetează ciclurile. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Singurul fișier creat: acest original în `evidence/sent-review-r1.md`, în afara repo-ului. Nicio implementare, modificare repo/skill/globală, cheie citită, instanță adoptată, QA/PG executată sau atingere a HTML-ului protejat.
