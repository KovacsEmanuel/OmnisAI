# Reviewer2 — rereview Settings focus, snapshot înghețat

## Verdict și dispoziție

- **QA-SETTINGS-FOCUS-01: remediere confirmată / APPROVED_FOCUS_SOURCE_SCOPED** pe `7a547046d54dbc5908a39ac3c85ad4984458d2ff`. Chromium real păstrează focusul Save prin PUT pending → GET autoritativ → Query refetch pending → final; focusul mutat de operator nu este furat; nu apare PUT suplimentar.
- **Cerința suplimentară „stale rămâne native disabled”: CHANGES_REQUESTED_SCOPED, LOW**, pentru suprapunerea stale + Reload pending descrisă mai jos. Nu este bypass de mutație și nu este reapariția pierderii de focus; părintele adjudecă findingul și integrarea.
- **Findingul installed QA-SETTINGS-FOCUS-01 nu este închis prin acest review SOURCE.** Aprobarea SOURCE anterioară UI-FOCUS-N01 nu îl închidea; nici prezenta verificare nu este noua QA instalată. Aceasta rămâne NOT_RUN pe bundle-ul focus nou.
- `make check-web` rămâne **FAIL_AUDIT / exit2**, separat de focus: handofful original păstrează 3 vulnerabilități în Vitest/@vitest/mocker/Vite, 2 moderate și 1 high, pe pinuri neschimbate. Nu am rerulat auditul, nu l-am exceptat și nu declar full-web PASS.

## Identitate, freeze și limite

Bază `c9eba4009291dede9cb034f259bd8b4f35bf6a98`; candidat `7a547046d54dbc5908a39ac3c85ad4984458d2ff`; tree `b6786ba2d6461e285c239b21dc4cae5f2a764c9c`; checkout `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/src`, curat înainte și după.

Manifest citit **înaintea execuției**: `t1-settings-focus-01/candidate-and-bundle.json`. Am verificat HEAD/tree, exact cele 4 căi ale diff-ului, blobs și SHA256 curente; la final am reverificat inclusiv blobs din bază. Diff SHA256 `34a071643b1dfff8cb3c51e07e89f233eb5ab7d0ef2d318112ae4d9269161fba` verificat direct din `git diff base candidate`.

| Fișier | Before blob → after blob | SHA256 curent |
|---|---|---|
| `web/src/app/ProviderKeySettings.test.tsx` | `5a5a08bfcf987f6132d8082fe70a4aaea2c46c72` → `7be2d9d8f0b1fbc0b53168ef9570d66831908b97` | `753226209390e47c93985c59da5b8bdb1e801c7a7d72ae041814e03c6504cb18` |
| `web/src/features/engagement/Engagement.module.css` | `d20450e7967ae4f8a035da24e20b37031ce022a4` → `d486723652bc25a49694beb0326044d7c9034432` | `d7f4b1058e0d6144d74ce0f188cf4967fa86c8cdc08210c991237ef8da9ef049` |
| `web/src/features/engagement/ProviderSettings.tsx` | `222bc359efe1cfc9961b7590cf4f77915fac0792` → `6cbab322e26b1635e87c9abe624966a89303d5b8` | `09ce8d93e3540e4581e5aaa7606b6cdcf78c5c9f951c66f722b75aaaead5f508` |
| `web/tests/e2e/provider-settings-focus.mjs` | absent → `5e1ee5312710f964597b2d915c987de3b153dbf9` | `09a42118d1b14b67c3edf31912e2005d80475e9dfc37882dc02b3cdf48d8cbbf` |

Bundle: `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1-settings-artifacts/bundle-web-focus-01`; `release.json` SHA256 `eccabd2a1fc3d7d42edad1ad602e83a30d9e1ad834e512b07a9266a39fc66f9d` verificat. `web/dist` existent are exact același set de fișiere și aceleași SHA256 ca webul acestui bundle; nu a fost necesar rebuild. Proveniența buildului este cea înregistrată de autor, nu un build nou făcut de reviewer. Cele 5 payloaduri non-web nu au fost reauditate; aprobările lor rămân numai la scope-ul neschimbat.

Checkoutul principal `/home/kali/OmnisAI` era `9d6a92a4ed4a4d08207ab12781f9aa5a49507d71`, cu HTML-ul untracked protejat; nu l-am citit/modificat. Am citit CURRENT și rândul T1 numai pentru orientare; nu modific statusul canonic.

## Finding concret nou

### R2-SETTINGS-NATIVE-01

- **Severity:** LOW; inconsecvență a cerinței explicite native-disabled, fără mutație neautorizată demonstrată.
- **File:line:** `web/src/features/engagement/ProviderSettings.tsx:39–40,43–44,110`.
- **Reproducer:** în fixture-ul browser existent, cu conexiune și selecție valide, răspunde la primul Save selection cu HTTP409 `REVISION_CONFLICT`. După mesajul „Settings changed”, Save are `button.disabled === true`. Apasă **Reload current settings**, ține GET-ul autoritativ pending peste două `requestAnimationFrame`: același buton are acum `disabled === false`, `aria-disabled="true"`. Click și `form.requestSubmit()` rămân respinse; PUT count rămâne exact1.
- **Rezultat real:** `{"phase":"stale reload GET pending","disabled":false,"ariaDisabled":"true","puts":1}`; aserțiunea pentru păstrarea native-disabled a eșuat cu exit1. În acel punct `stale` nu a fost încă șters: se șterge doar după GET reușit, la linia50.
- **Criterion:** cererea rereviewului cere ca stale să rămână **native disabled**. `(disabled && !selectionPending)` maschează și motivul stale când Reload setează sending, nu doar dezactivarea tranzitorie necesară fixului de focus.
- **Impact/limită:** controlul reintră în ordinea Tab în timp ce afișarea încă este stale; aria-disabled și guardurile rămân corecte. Nu susțin bypass CAS/busy, cheltuială provider ori pierdere de date. Starea stale stabilă este native disabled. Nu extrapolez acest reproducer la alte combinații auth/error.
- **Minimal remedy:** separă motivele hard-disabled, inclusiv stale, de pending-ul tranzitoriu care trebuie să păstreze focusul; nu elimina global toate motivele native-disabled când există sending/refetch. Adaugă un caz mic în testul existent pentru stale + reload GET întârziat; păstrează browserul pozitiv/negativ curent. Nu este necesar framework/harness nou.
- **Dovadă/replay:** `logs/reviewer2-focus-stale-reproducer.log`, `logs/reviewer2-focus-stale-command.json` conțin outputul și argv-ul complet executat. Am specializat **în memorie** fixture-ul browser existent (PUT409 și scenariul Reload); nicio rescriere a fișierului de test/produs și niciun harness persistent nou.

## Ce este confirmat în scope

| Cerință | Cod / dovadă | Dispoziție |
|---|---|---|
| Focus același operator la Save | `ProviderSettings.tsx:107–110`; browser `:67–117`, două frame-uri la fiecare fază | PASS_SOURCE_SCOPED |
| Operatorul a mutat focusul | niciun `focus()` de restaurare în produs; browser moved=true păstrează linkul Providers prin GET/refetch/final | PASS_SOURCE_SCOPED |
| Fără submit/admission suplimentar | `SelectionForm.submit:117–130` și `save:55–67` păstrează disabled + busy.current, command ID și revision; Enter repetat, click și requestSubmit la toate cele3 faze | exact1PUT per scenariu, command ID stabil în unit; expected_revision1 și draftul trimis păstrate |
| Reset autoritativ al draftului | numai SelectionForm keyed remount; Save rămâne în afara lui; modelul și Brain override revin din current GET | PASS_SOURCE_SCOPED |
| Unavailable/revoked | condiția separată `enabled && credential_present` rămâne native-disabled indiferent de pending; fieldseturile și butonul Revoke păstrează native disabled | citire directă + cele13 unit PASS; nu o nouă QA LOCKED instalată |
| Stale | steady state blocat; suprapunerea Reload pending nu păstrează atributul nativ | finding LOW de mai sus |
| Stil pending / focus ring | CSS local `Engagement.module.css:39–40`, global `global.css:8–15`; browser verifică cursor, color, hover și outline solid2px | PASS pentru aserțiunile DOM/CSS, nu aprobare estetică/WCAG |

Callerul efectiv rămâne `Settings.tsx:3,9–11`, aceeași rută Providers în App. API/CSRF/receipt parser, auth fencing și contractele nu sunt modificate de diff; nu am extins reviewul asupra lor. Testele unit existente acoperă Revoke/recovery/CAS, însă cazul CAS folosește conexiuni goale (`ProviderKeySettings.test.tsx:85–97`), deci nu detectează overlapul nou cu Save model populat.

## Browser regression și wiring

`web/tests/e2e/provider-settings-focus.mjs` este un runner **Node test**, nu un test care pretinde să fie descoperit de Playwright test runner. Comanda reală este documentată la linia17: `node --test tests/e2e/provider-settings-focus.mjs`, după build. `npm test` rulează Vitest, limitat la `src/**/*.test.{ts,tsx}`; `make check-web` nu include acest script; `make test-e2e` merge în familia pytest/API existentă. Nu deduc o integrare automată inexistentă și nu impun un nou framework sau target Make pentru o regresie focalizată explicit rulată.

Runnerul servește **App construit**, nu un componente-double: Vite `preview`, configFile=false, host127.0.0.1, port0, strictPort, cors=false. Interceptează HTTP-ul API cu date sintetice, blochează origin străin și rute API/health neașteptate; nu pornește API/PG și nu contactează providerul. Este SOURCE/synthetic, nu installed. Deadline30s și expect1500ms; am impus și timeout proces45s. Pozitivul și negativul țin separat PUT, current GET și refetch peste2frames și verifică același canal; unit/jsdom singur nu ar proba focusul nativ. Cleanupul eliberează promisiunile și închide context/browser/server în finally. Interceptarea nu este sandbox OS sau atestare universală de egress.

## Comenzi efectiv rulate, rezultate și limite

Prefix web: `PATH=/home/kali/.local/share/omnis-toolchains/bin:$PATH PLAYWRIGHT_BROWSERS_PATH=/home/kali/.cache/ms-playwright`; cwd `src/web`, dacă nu se spune altfel.

| Comandă / verificare | Exit și rezultat |
|---|---|
| Git status/diff/HEAD în checkout principal și candidat; verificare manifest înainte/final | 0; candidatul curat; 4fișiere, blobs/tree/SHA/diff exacte |
| `node --version`; `npm --version`; existența executabilului Chromium fixat | 0; v24.21.0 /11.19.0 / Playwright1.63.0 cached |
| `npm test -- src/app/ProviderKeySettings.test.tsx` | **0;13PASS**,3.383s; `logs/reviewer2-focus-unit.log` |
| `node --test tests/e2e/provider-settings-focus.mjs` | **0;2scenarii PASS**,3Node test records incluzând părintele; Chromium153.0.8010.12;2.588s; `logs/reviewer2-focus-browser.log` |
| `node --input-type=module -e <runner existent specializat în memorie>` | **1**, aserțiune native-disabled stale reload; argv complet în JSON,2records FAIL incluzând părintele, nu2defecte distincte |
| cwd `src`: `git diff --check c9eba4009291dede9cb034f259bd8b4f35bf6a98 HEAD`; `node --check web/tests/e2e/provider-settings-focus.mjs` | 0; fără modificări de produs |
| Cleanup /proc pentru procese browser/preview ale cwd-ului web | 0 final; niciun Chromium/preview/test Node rămas; tooling LSP exclus și neatins |

Am citit originalul installed `documents/verification/api-key-runtime-t1-evidence/qa-settings-installed-first.md:67–72` din checkoutul principal și logul RED al autorului: native disabled across paint → active BODY. Nu am regenerat RED-ul de produs și nu am modificat retrospectiv acea probă. Logul browser oficial rerulat independent pe candidat arată BUTTON/disabled=false/aria-disabled=true pending, focus=true după refetch/final, pentru ambele scenarii.

O verificare inițială de cleanup a clasificat prea larg toate procesele Node cu cwd web și a prins4procese ale language-serverului Hermes; aserțiunea internă a fost exit1, deși shell-ul compus a terminat0 după comenzile ulterioare. Am corectat numai clasificarea read-only și am confirmat exit0, zero browser/preview/test Node; nu am oprit procesele tooling. Două încercări read-only de discovery au folosit o cale de evidence absentă în worktree (apoi citită în main) și un `web/playwright.config.ts` inexistent; runnerul Node nu îl cere. Acestea nu sunt defecte de produs.

## Fișiere create și ce rămâne

Numai în `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/logs/`: acest raport original, `reviewer2-focus-unit.log`, `reviewer2-focus-browser.log`, `reviewer2-focus-stale-reproducer.log`, `reviewer2-focus-stale-command.json`. Niciun fișier product/test/canonical editat, nicio integrare sau commit; nu există schimbări Git de livrat de reviewer.

Părintele deține adjudecarea findingului LOW, auditul separat, integrarea și QA instalată pe bytes finali. T1/G04a nu este închis. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO.

Nu am rulat canonical/full-web, instalare nouă, PG/API/vault/CLI, provider/model/target, Q sau port48765, Docker, profile ori downloaduri; fără matrice universală și fără aprobare vizuală nouă. Riscuri rămase: auditul nerezolvat, native-disabled stale+pending și lipsa QA instalate pe artefactul focus nou.
