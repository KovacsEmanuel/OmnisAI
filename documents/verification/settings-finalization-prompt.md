# Sesiune nouă — numai minimul necesar pentru închiderea T1

> Mandat executabil numai când operatorul îl transmite explicit pentru execuție. Pregătirea acestui prompt nu pornește implementare, diagnostic sau efecte pe operator.
> Bază verificată la pregătire: `6ce8fc8b1e3be26a3245bd48601190b046a38a90`; reverifică Git, nu trata snapshotul ca stare perpetuă.

Lucrează în `/home/kali/OmnisAI`, `/ponytail:ponytail full`, în română. Finalizează cele patru obligații de mai jos până la rezultat verificat sau blocker concret. Fără audit general, refactor, funcționalități noi, suite repetate pentru număr ori checkpoint după fiecare commit. T2 nu este inclus.

## Citește minim; nu redeschide ce este livrat

Respectă AGENTS/CONTRIBUTING și CURRENT din README, apoi:
- `documents/verification/settings-c-evidence/models-polish-20261029/blocked-resume.md`;
- `documents/verification/settings-c-evidence/ui-result.json` → `models_refinement_20261030`, iar pentru web numai `default_web_gate`/dispoziția lui;
- `documents/verification/api-key-runtime-t1.md` → „Finalizare Settings și Remove — instalat scoped, T1 neînchis”.
Încarcă numai skillurile relevante la frontieră; nu toate rapoartele/arhivele.

**Models/UI/Remove/upgrade0017 sunt livrate scoped.** Final `a1857dd`, merge `ae92a65`; healthy API/PG/TLS/browser1PASS66.59s și Stop/readback1PASS13.76s, reviewuri aprobate, assets instalate/servite/executate la8780. Reutilizează dovezile pe bytes neafectați; nu reimplementa și nu rerula separat Models pentru încurajare. O regresie nouă direct afectată cere verificarea ei, nu întreaga matrice.

Ultimul operator readback: **exit4/UNAVAILABLE/RECOVERY_REQUIRED**, DEVELOPMENT0.1.1/schema0017; UUID `d694129b-a3e5-446d-9e5b-fe9bc19abed8`, origin `http://127.0.0.1:8780`, root `/home/kali/.local/share/omnis-settings-c-9e51d10`. Shellul public nu dovedește funcționarea Models autentificat. Reverifică starea, nu presupune READY din istoric.

## 1. Supervisor — cauza întârzierii, apoi remediul demonstrat

Expirarea lease este reală/fail-closed; cauza5852ms este UNKNOWN. Noul commit264.947069ms corelat cu COMMIT/IO/WalSync și progres client/martor nu explică incidentul istoric. Restartul sau absența recurenței nu sunt remediu.

Bugetul anterior2din2 este consumat. **Retransmiterea explicită a acestui prompt admite cel mult o invocare diagnostică suplimentară, material diferită,≤600s**, într-o fixture nouă proprie cu topologia instalată Docker/TCP, nu repetarea probei native UDS. Contoarele vechi nu se resetează. Reutilizează consumerul/observația existente, fără alt harness/supervisor. Preflight fără efecte: argv/source/imagine/schema/acces/colecție/emisia martorului/cleanup. Dacă prerechizitul necesită infrastructură nouă, raportează lipsa înainte de efecte.

Pentru același ciclu, separă commitul/backendul/wait-event, confirmarea către client și progresul independent. Așteptare server WAL → investighează stocarea/VM; server terminat/client blocat → transport/driver/pool; lipsa progresului → callback/scheduling. Nu alege cauza anticipat. Dacă hostul VMware este necesar și inaccesibil, spune exact ce acces/martor lipsește; modificările hostului cer acord distinct.

Doar cauza/reproducerul demonstrat admit remediul minim, review și QA afectată bounded, distinctă de diagnosticul consumat. Fără lease/deadline mai mari, durabilitate dezactivată, expirare mutată după commit, autorestart/watchers sau fault injection în operator. Dacă diagnosticul este neconcludent: păstrează UNKNOWN, oprește această ramură, fără altă rundă; termină numai ramura independentă admisă.

## 2. Web — numai eșecurile relevante, nu presupusa soluție

Istoricul are două **rulări** eșuate, nu două buguri demonstrate; default-web2/SOURCEobserver2 rămân consumate. QueryClient/teardown/cereri rămase este o ipoteză, nu un fix obligatoriu.

Admis: o investigație SOURCE îngustă în testele existente, cu selecția inițială explicită și control pozitiv/negativ. Localizează prima etapă care nu avansează: sesiune, răspuns, decodare sau DOM; pentru izolarea testelor, verifică dacă munca precedentă intră în mockurile următorului. Compară callerul cu revizia FAIL-ului. Nu recrea loguri dispărute și nu atribui retrospectiv cauza dintr-un PASS actual.

Corectează fixture/oracle numai dacă testul este demonstrat greșit; produsul numai pentru defect reprodus. RED→GREEN și regresii afectate după remediu, fără timeout/workers relaxate, teste eliminate sau infrastructură nouă. Fără al treilea retry larg înaintea unei dispoziții cauzale justificate; fără traseul legacy32models/2Starts/2Cancels. Un PASS izolat nu este gate complet. Fără progres după controlul îngust: blocker precis, nu alte cicluri de harness.

## 3. Instalația mea — aceeași identitate și date

După remediul justificat și clearance: revenire controlată pe instalația existentă, nu profil nou/reinstalare. Înaintea efectelor lifecycle: before/after nesensibil, backup actual compatibil0017 și restaurare/inversă verificate conform procedurii acceptate. Nu restaura orbește backupul0016 și nu face downgrade după OPEN. Dacă păstrarea sigură nu este stabilită, oprește efectul.

Python se modifică în worktree separat; integrarea în checkoutul montat așteaptă oprirea verificată a API/operatorului. Nu suprascrie releaseuri imuabile. Recovery/Start numai pentru livrarea remediului, nu inventar sau mascarea cauzei.

Verifică buildul executat și Settings într-o sesiune autentificată, cu comparație înainte/după pentru modele, selecții/capuri și istoric; modificările lifecycle lease/generation se consemnează separat. Fără Test/Refresh/apel model/ștergere/Replace de chei reale. Tabul agentului neasociat nu dovedește expirarea sesiunii desktop; pairing uman numai când accesul necesar chiar lipsește. Nu exporta sesiuni/cookies/coduri.

## 4. O singură poartă finală completă

După prerechizite reale, dispozițiile de mai sus și review/QA afectată: **un singur `check-components`,≤5400s,0din1 consumate**, prin runnerul existent, în background urmărit, cu preflight fără efecte:

`PATH=/home/kali/.local/share/omnis-toolchains/bin:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch api/.venv/bin/python -I -B ops/run_test_db_gate.py --check --target check-components --uv /home/kali/.local/share/omnis-toolchains/bin/uv --timeout-seconds 5400`

Fără schimbarea selecției/limitelor sau substituirea cu o suită parțială. Citește exitul/outputul relevant și verifică exact cleanupul propriu, păstrând PGDATA/logurile. După FAIL: finding concret, nu încă un canonical implicit; altă încercare completă cere buget nou.

## Reguli comune și închidere

Un orchestrator, un developer desemnat, review independent pe FREEZE exact, apoi QA reală afectată. Două reviewuri complementare numai pentru autoritate/concurență/dispatch/Stop/secrete; unul proporțional pentru test/presentation-only. Nu reaudita aprobările neschimbate. Commituri mici, stage explicit, readback; fără amend/rebase/squash/push/fetch. Nu cere acord cosmetic pentru munca deja admisă.

Cleanup numai pentru delta proprie, exact și verificat; păstrează date/rollback/backupuri/refuri/dependențe și incertitudinile istorice. Fără prune/purge sau cleanup general. `tempkey.txt` și `documents/Omnis_Notite_Originale.html` sunt absolut protejate: nu citi/modifica/hash/stage/șterge. Fără credentiale personale, raw Docker Env, chei/master/DSN/cookies/coduri, provider/model/Refresh live, conturi noi, trafic țintă sau buget LLM nou; peerii sintetici izolați sunt permiși.

Fără rapoarte intermediare suplimentare. Păstrează originalele necesare și actualizează în loc registrul/recovery point existent. La final aliniază numai statusul factual/CURRENT/rândurile afectate; rulează verificările documentare obligatorii, fără HTML regenerat dacă sursa canonică randată nu s-a schimbat.

`T1_CLOSED / T2_READY` numai după toate obligațiile verificate, inclusiv poarta completă; T2 rămâne mandat separat. Altfel `T1_BLOCKED / T2_NOT_READY`, cu cauza demonstrată sau martorul/accesul exact lipsă și ramurile independente încheiate. Raport scurt: ce funcționează efectiv în instalația mea, dovezi, commituri, date/cleanup și blocker. Nu promite termen sau absența tuturor bugurilor; nu prelungi cu retry-uri pentru verde.
