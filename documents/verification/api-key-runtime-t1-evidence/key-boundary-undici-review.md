# Review independent — undici dev-transitiv / paritate web

## Verdict

**APPROVED_SCOPED — exact delta `92e36082d64b8ae49437df1976876b0d66ba089f` → `4eb0bfc149c099380af653740329726a5a9bf38f`.** Fără findings blocante sau remedieri solicitate în această deltă. Nu este acceptare T1, PASS canonical ori aprobare nouă de runtime/distribuție instalată.

Review read-only în `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`; singura scriere proprie este acest original. HEAD, părintele direct și checkoutul curat au fost verificate; snapshotul a rămas același la încheiere.

## Scope și identitate

Cerință → consumer → risc → decizie: eliminarea celor trei advisories din dependența dev `jsdom`/Vitest, fără schimbarea manifestului sau produsului → instalarea/testele web și buildul existent → rezoluție incompatibilă, integritate incorectă ori drift de artefact → aprobarea/refuzul exclusiv al lock delta și parității web.

- Singurul fișier modificat: `web/package-lock.json:2298–2300`; numai `version`, `resolved`, `integrity` pentru `node_modules/undici`, **8.11.2 → 8.12.2**. Compararea JSON integrală confirmă că toate celelalte câmpuri/intrări sunt identice, inclusiv `dev: true`, MIT și engine.
- Blob: `e05c2c10484957a4e90bb67a4d78baf338ad8cf0`.
- SHA-256 lock: `6e0e4fcabad117056b8a1c13fcd2af0b28fd0a28e3133c6fc782bce19036b3c7`.
- SHA-256 diff: `ec91847f388bda23467ad8d7bfc8ff2dafef6a8cec088bc0a30a68001f3ab67d`.
- Identitățile corespund `freeze.json`. `git diff --check 92e36082 4eb0bfc149c099380af653740329726a5a9bf38f`: exit 0.
- Fără schimbări la pini direcți, `package.json`, fixtures, teste, exports, config, gate, skip, API/CLI ori surse runtime. Nu sunt necesare schimbări de callers: `web/package.json:36` păstrează jsdom 30.1.1, `web/package-lock.json:1425` păstrează `undici: ^8.10.2`, iar `web/vitest.config.ts:7` folosește jsdom.

## Compatibilitate și surse primare

Verificare independentă cu Node-ul fixat și `semver` din npm existent, exit 0: pachetele instalate sunt jsdom **30.1.1** și undici **8.12.2**; versiunea undici satisface `^8.10.2`. Node **v24.21.0** satisface atât engine-ul jsdom `^22.22.2 || ^24.15.0 || >=26.0.0`, cât și undici `>=22.19.0`.

Am citit direct, fără autentificare, registry-ul oficial:

- <https://registry.npmjs.org/undici/8.12.2>
- <https://registry.npmjs.org/jsdom/30.1.1>

Versiunile, engines, licențele, dependencies, `dist.tarball` și `dist.integrity` coincid cu lockul; undici nu adaugă dependencies runtime. Tarballul oficial `https://registry.npmjs.org/undici/-/undici-8.12.2.tgz`, descărcat numai în memorie, are SHA-512 calculat identic cu lockul:

`sha512-XtuDWVdqTLr3NAxm2ly9/hU6kUsJOgGh1RASzMBbsw6aWCOaQzHdW+QQDfdERjfJ2V5vL5pRPa4RetO9UfivDg==`

Cele trei advisories publicate de proiectul upstream au fost citite direct. Toate declară pentru seria 8 intervalul afectat `>=8.0.0, <8.12.2` și versiunea remediată **8.12.2**:

| Advisory upstream | Efect declarat | Severitate upstream |
|---|---|---|
| [GHSA-4qv8-2p9j-2685](https://github.com/nodejs/undici/security/advisories/GHSA-4qv8-2p9j-2685) | memorie nebounded în parserul EventSource | Moderate |
| [GHSA-f72v-6w45-q472](https://github.com/nodejs/undici/security/advisories/GHSA-f72v-6w45-q472) | bypass SRI pentru tokenuri cu majuscule | Moderate |
| [GHSA-xjj6-f33q-929c](https://github.com/nodejs/undici/security/advisories/GHSA-xjj6-f33q-929c) | eroare netratată la content-encodings excesive | High |

Acestea sunt vulnerabilitățile remediate ale bazei, nu findings rămase asupra candidatului. Nu am executat exploituri și nu extrapolez către TLS/provider, undici încorporat în Node sau securitatea globală.

## Dovezi existente, citite — fără QA nou

Am verificat hashes/dimensiuni pentru toate cele **19** fișiere enumerate în `freeze.json` și am citit rezultatele relevante. Codurile de ieșire de mai jos sunt cele consemnate în freeze/commit, susținute de logurile păstrate, nu execuții noi ale reviewerului:

| Comandă existentă | Rezultat păstrat |
|---|---|
| `npm --prefix web audit --include=dev --json`, baza | exit 1; un pachet HIGH, cele trei advisories |
| `npm --prefix web ci --include=dev --ignore-scripts --no-fund` | exit 0; 149 pachete instalate |
| aceeași comandă audit, fix | exit 0; zero vulnerabilități raportate |
| `npm --prefix web ls --all` / `ls undici jsdom` | exit 0; jsdom → undici 8.12.2 |
| `make check-web UV=/home/kali/.local/share/omnis-toolchains/uv-0.12.19` final | exit 0; contracte, 6 teste tooling, typecheck, lint fără warnings/errors, 151 teste web/16 fișiere, design/build și audit |

Numărul celor 151 teste a fost reconciliat programatic din log. Nu există audit omis/slăbit: `check-web-green.log:124–125` execută explicit audit cu dev incluse.

Eșecurile auxiliare sunt păstrate: config npm `/dev/null` încărcat dublu și primul `check-web` exit 2, cauzat de prerequisite-ul `tsx` absent în anti-slop. Instalarea lockului anti-slop neschimbat precedă execuția finală verde; nu este prezentată drept modificare de produs.

Logul original canonical6 are SHA-256 verificat `33252b9a849b8994469e90968fb0403352ecee5744caffb21d4e9bc296b8026b`. El păstrează 3109 API PASS/65 SKIP/7 deselected și testele web trecute, apoi FAIL real la audit (`gate.log:425–440`). Remediul focalizat nu transformă retrospectiv canonical6 în PASS și nu autorizează alte efecte.

## Paritatea artefactului

Am comparat independent bytes, SHA-256, dimensiuni și setul exact de fișiere dintre `dev/web/dist` și `artifacts/bundle-startfix/web`, nu doar verdictul din JSON: **5/5 BYTE_EXACT**, fără fișiere suplimentare/lipsă. Hashurile coincid și cu intrările web din `release.json`:

- `assets/fonts-OFL-bSaZbgNk.txt`
- `assets/index-97com5ii.css`
- `assets/index-wc7DvD2Y.js`
- `index.html`
- `omnis-web.json`

SHA-256 calculat al manifestului `release.json`: **`4ae4e51d41af781b4edfd9aeb5b1443a45e9c5dd5b6a62dcee4ae56404fc3cc1`**, exact bundle-ul de referință. SHA-256 `omnis-web.json`: `7347d02d6c9260103b95cc955305147861674cf4a713685810b29c75327fbdb3`. Comparația/asertările independente au exit 0. Nu am recertificat API/CLI din bundle sau starea instalării curente.

## Limita aprobării

Această actualizare strict dev-transitivă nu schimbă autoritate, Stop, secrete ori contracte cross-runtime; un review independent focalizat este suficient pentru delta ei. Aprobările complementare existente pentru produs/SENT/startup și dovezile Settings/restart/Stop4 rămân la scope-ul lor, fără redeschidere sau extindere. Integrarea și orice gate final aparțin părintelui; T1 rămâne neînchis prin acest verdict.

Nu am rerulat canonical, teste/build/audit, PG, servicii sau browser; nu am instalat/reinstalat, accesat rootul instalat, profiluri/secrete ori HTML-ul protejat și nu am făcut push. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.
Riscul rezidual: auditul este o observație punctuală a advisory-urilor cunoscute, nu dovadă de absență a vulnerabilităților; paritatea web nu este QA nouă de produs.
