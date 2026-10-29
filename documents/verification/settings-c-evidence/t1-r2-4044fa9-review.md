# R2 independent — 4044fa9 — authority / concurență / Stop / failure boundaries

**Verdict: CHANGES_REQUESTED_SOURCE_SCOPED.** Două constatări MEDIUM reproduse inert; nu am demonstrat pierdere de date, efect provider sau ocolirea barierei DB Stop. Verdictul privește delta upgrade, nu redeschide Remove neschimbat și nu este integrare, QA instalată ori închidere T1.

## Identitate și mandat

- Candidat: `/home/kali/.hermes/cache/scratch/t1-upgrade-20261029`, HEAD `4044fa952cadae8d491f215d62551b11e488065f`, tree `e83286037bfabf6a100d818bb98bccc84d1cda9c`, bază `ed611aa40c90f62f4f511cc1951a68970e2ba51b`.
- FREEZE `/home/kali/.hermes/cache/scratch/t1-upgrade-complete-freeze-4044fa9.json`, SHA256 `fa2f1953d0afa53b65f646e86d2698ece96a6dbf0503e6a5432b93ab8bff9515`.
- Diff SHA256 `93ebc732280a2d355810dfa6ed3655fafbb4c73ada482b6594cf215231d24501`.
- Verificare finală reală: HEAD/tree identice; **29/29 paths blob/SHA, 6/6 artefacte, 10/10 payloaduri bundle**, diff/FREEZE conforme. Manifest nou `81feae118ca6f933a6f423b015067c0058a659e945bc7fc209930cab8a0dd4ec`; vechi `99409cd18adfd4545bbdb03f9edfc6bcc7cca95973f2e13342d2bd54062ef133`.
- Main a rămas `06040a97e1066e5faf8807c7410a9315d40b1811`, tracked/index curate; cele două untracked protejate nu au fost citite/hashuite. În candidat au rămas numai cele trei symlinkuri untracked declarate. Niciun fișier din repo/canon/produs modificat.
- Citit mandatul main `settings-finalization-prompt.md`, arhitectură main §5.5, plan main §8, CURRENT și rândurile relevante din harta de status, AGENTS/CONTRIBUTING/team-slice și skills review/status/Ponytail. Metadata READY istorică din candidat nu a fost adoptată.

## Constatări concrete

### R2-4044-F01 — MEDIUM — fence-ul verificat înainte de lock nu blochează callerul deja admis

**file:line:** `cli/src/omnis_cli/backup.py:599-605`; verificarea inițială este în `cli/src/omnis_cli/start_runtime.py:196-203,223`, iar upgradeul publică intentul sub lock la `cli/src/omnis_cli/upgrade.py:293-335`.

**Reproducer:** `python -B /home/kali/.hermes/cache/scratch/t1-r2-4044fa9-repro.py`, secțiunea `fence_toctou`. Folosește perechea veche release0.1.0/schema0016 și fixture-ul SOURCE existent; fără socket real, Docker sau PG. Ordine legală modelată: B termină admiterea ControlRuntime în absența intentului, apoi este suspendat înainte de lifecycle lock; U ia lockul, persistă `IMAGE_PENDING`, eșuează/iese și eliberează lockul fără să schimbe bindingul sursă ori să lase resurse DB; B continuă cu runtime-ul vechi. Funcția publică reală `cold_command` nu reface fence-ul după lock.

**Rezultat observat:** `cold_identity` este atins cu intentul încă `IMAGE_PENDING`; backupul nativ de fișiere, cu numai operațiile OCI înlocuite prin doubles SOURCE, publică snapshotul și întoarce **exit0**. Controlul negativ pe același intent cu `refuse_upgrade` întoarce `UPGRADE_RECOVERY_REQUIRED`. Deci denegarea unui caller nou nu este barieră pentru unul deja admis. Nu susțin că snapshotul rezultat este corupt; problema confirmată este continuarea unui caller/effect path care trebuia exclus. În produs, `cold_identity` și arhivarea lansează helperi OCI; aceștia NU au fost lansați în reproducere.

**Criteriu încălcat:** arhitectură §5.5, intent durabil care exclude callerii concurenți și blochează continuarea automată în stări neterminale/efect incert. ControlRuntime construit înainte de lock nu reprezintă o autorizație perpetuă.

**Remediu minim:** revalidează fence-ul în callerul public după dobândirea lockului data și înaintea backup/restore, fără a bloca propriul traseu intern upgrade→backup. Aplică aceeași regulă numai callerilor afectați care consumă o admitere făcută înainte de lock. Test mic cu ordinea B-admit→U-intent/release→B-lock și assertion zero helper/effect, nu doar test pe intent preexistent.

### R2-4044-F02 — MEDIUM — selecția RELEASE este numai temporară; configurația DEVELOPMENT supraviețuiește upgradeului

**file:line:** `cli/src/omnis_cli/start.py:1150-1151`; consumerul următor refuză la `1176-1179`, iar un Start nou după Stop folosește configurația rămasă la `1263-1270,1326-1327,1365`.

**Reproducer:** aceeași comandă, secțiunea `development_after_release_upgrade`. Config TOML privat real conține `development_workspace = "/review/source"`; jurnalul post-upgrade este în RELEASE/READY, fără `development_workspace`, exact forma produsă prin `replace(config, development_workspace=None)`. Forma READY este verificată de validatorul real `_ready_record`, nu prin bypass. Următorul `start_instance()` este executat cu frontiera ControlRuntime interzisă explicit.

**Rezultat observat:** **exit2 / CONFIG_MODE_CONFLICT**, fără contact cu daemonul și cu configurația neschimbată. `upgrade` nu scrie și nu cere eliminarea acestei selecții înaintea efectelor. Acest caz contează pentru sursa operatorului declarat DEVELOPMENT, nu numai pentru o combinație ipotetică de flaguri. `status` nu este demonstrat defect aici și nu îl declar astfel.

După un Stop, selecția veche poate fi folosită din nou de Start și poate monta sursele development peste imaginea nouă; asta este o consecință de SOURCE a callerului, **nu o probă runtime executată** și nu o afirmație că readiness ar accepta schema greșită. Tocmai nu trebuie deschis un nou efect incert pentru a descoperi incompatibilitatea configurației rămase.

**Criteriu încălcat:** tranziție coerentă aceeași instalație prin CLI/config/API/control/lifecycle, instalare utilizabilă prin comenzile existente; interdicția publicării combinațiilor incompatibile. Un upgrade care ignoră selecția numai în propria invocare nu rezolvă lifecycle-ul ulterior.

**Remediu minim:** fixează explicit selecția durabilă de mod înaintea tranziției, cu reversibilitate păstrată; alternativ refuză DEVELOPMENT înainte de backup/migrare până la schimbarea explicită prin configurația normală. Nu adăuga updater/flag/framework nou. Adaugă cazul SOURCE pentru următorul Start și apoi QA pe sursă development admisă/config normalizată, nu numai fixture implicit RELEASE.

## Dovezi și limite ale reviewului

- Reproducerul de mai sus a fost executat din `/home/kali/OmnisAI`, Python `-B`, **exit0**; ambele rezultate de defect și controalele sunt assertions reale. Fișierele fixture temporare sunt în TMPDIR scratch și au fost eliminate de context manager. Rezervarea socket din fixture a fost înlocuită cu obiect inert; OCI/cold identity/arhiva sunt doubles declarate, nu QA reală.
- `UpgradeTest` din `cli/tests/test_upgrade.py`, cu aceeași rezervare socket inertă: **8 tests PASS / 0.248s / exit0**. Acestea acoperă refuzul callerului nou, completion/grant păstrate, rollback same-digest în root absent și refuzul OPEN/unknown; nu acoperă cele două scenarii de mai sus.
- SOURCE verificat: ordinea lockurilor host data→root este consecventă; migratorul ține instance_control→supervisor_lease, aceeași ordine ca ownerul existent, prin DDL. Verificatorul fizic0016 este separat de readiness0017. Grantul autentic stocat și starea Stop sunt comparate în tranzacție; migrarea nu consumă grantul, reconcile îl verifică din nou înainte de acquire/OPEN.
- SOURCE verificat: progresul MIGRATION_PENDING/OPEN_PENDING este durabil înaintea efectelor; necunoscutul păstrează intentul și nu introduce retry automat. Rollbackul automat este limitat pre-OPEN, cu inventar absent și stări cunoscute, selecție veche/same-digest, destinație absentă și carantina rootului eșuat. Nu am identificat un traseu demonstrat care să arunce datele noi după OPEN.
- Limitele bundle 2MiB/fișier, 8MiB total, 128 fișiere și CLI fără dependențe API sunt păstrate în parserul revizuit. Nu am introdus arhive ostile/builduri sau o matrice universală de crash-cut-uri. Post-reconcile ACK/cleanup și UNKNOWN rămân lucruri de observat pe consumatorul instalat, nu certitudine fizică din review.
- API/PG40 și developer420/private-wheel, packaging1 sunt dovezile declarate în handoff/FREEZE, nu execuții independente R2. Nu le promovez la QA.

## Admiterea QA bounded și dispoziție propusă

**Pe bytes 4044fa9: SOURCE neadmis pentru integrare/rollout; QA cu efecte upgrade dependentă rămâne NOT_ADMITTED până la reproducerea/adjudecarea părintelui și dispoziția explicită a celor două constatări.** Preflight read-only rămâne admis. Absența QA OCI nu este finding și nu este prerechizit circular: QA trebuie să fie următoarea etapă după remediu și focused re-review al deltei relevante, plus verdictul complementar R1.

Admiterea ulterioară propusă este numai cele două scenarii deja frozen: `test_t1_populated0016_upgrade_installed` și `test_t1_upgrade_known_preopen_failure_restores_installed_snapshot`, pe artefactele finale relegate, fixture fresh, fără operator/provider/target/browser. Păstrează oracle populat, completion byte-exact, UUID/origin/project/systemID/PGDATA/seif, refuz concurrent la frontiera efectelor, readback/Stop și rollback pre-OPEN cu carantină. Pentru cazul DEVELOPMENT, rezolvă mai întâi configurația explicită și verifică următoarea comandă Start pe aceeași selecție durabilă; nu este motiv pentru alt harness sau alte suite largi. Unknown job/reconcile/OPEN rămâne stop-and-preserve, nu retry ori rollback automat.

Stare propusă pentru părinte: implementare upgrade candidat; dovezi SOURCE scoped; review **CHANGES_REQUESTED**, installed upgrade/rollback **NOT_RUN**, operator **neatins/BLOCKED**, T1 neînchis. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

**Fișiere create numai în scratch:** acest raport și `/home/kali/.hermes/cache/scratch/t1-r2-4044fa9-repro.py`. Niciun edit produs/canon/repo/global skill/config și niciun commit/integrare.

Omise: QA OCI/DB, operator, browser, provider, builduri și crash matrix universală; Remove neschimbat nu a fost reaudiat.
Risc rămas: fence-ul nu exclude un caller deja admis, iar modul development rămas poate rupe lifecycle-ul după upgrade; părintelui îi revine adjudecarea și admiterea efectelor.
