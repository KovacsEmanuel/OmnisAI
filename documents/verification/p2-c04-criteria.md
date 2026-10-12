# B06b C04 — criterii nonempty pe metoda records existentă

Autoritate: contractul [C04](p2-b06b-next-contract.md), arhitectură §9.5/§9.10 și plan §7.1. Nu este plan nou. Baza de produs `93b7700897c13e31ba1f7e6d99ca57b8ea72b61e` are first-late-held/restart reader acceptate separat în [registrul metodei](p2-contract-method.md). C04 rămâne **NOT_IMPLEMENTED / BLOCKED / NOT_REVIEWED** la tentativa de mai jos; continuarea autorizată nu îi transferă acceptare.

## Contractul vertical și limitele

Același seed records calificat/publicat și același input → CriterionBinding explicit, două criterii distincte pe aceeași BoundProcedure → copil AIAgent real/read/PURE → CriterionResult cu exact perechile alocate → regulă trusted fixată, aplicată de backend după rezultatul autentic și receipts/MethodCheck → CriterionOutcome persistent/readback/reconcile idempotent. Header/criteriu omis, duplicat sau străin sunt refuzate. Suportul zero-binding/cold v1–v3 rămâne distinct.

Procedura publicată actuală are `oracle_ref=null` și `control=[]`. Testele evaluatorului asupra datelor invalide nu sunt controale ale acestei execuții. Outcome-ul permis în acest subset este BLOCKED/INCONCLUSIVE, nu un PASS funcțional fabricat; MethodCheck COMPLETE nu este verdict de criteriu. Un oracle pozitiv și alte forme C04 rămân obligații distincte.

Fără alt owner/emitter/provider, model/target/r1/profil/daemon/push, fără schema migration nejustificată, seed/input nou sau reducerea datasetului. Capul **65536**, inputul anterior **65418** și deadline-ul nativ **4.5s** se păstrează; overflow se rezolvă numai lossless, cu constrângerile/header/refs exact conservate. Fișiere permise: consumatorii API/runtime necesari, teste afectate și distribuția/pins exactă; autorul nu scrie documentele/profilurile și nu comite în checkoutul comun.

## Tentativa inițială — păstrată, nu promovată

Worktree owned `work/p2-c04-criteria` din HEAD local `93b7700`, `/home/kali/.hermes/cache/scratch/omnis-p2-c04-criteria`. Candidatul incomplet a produs două bindings/propuneri BLOCKED pe seamuri SOURCE, dar nu a livrat schema/checkerul complet ori persistarea outcome-urilor. Testul consumerului de outcome a întâlnit și o mutație de fixture nereînchisă (`STORAGE_INCOMPATIBLE`), nu un PASS al produsului.

1. Preflight PG `proc_2d389a21d033` **exit1**: contextul delegării lipise greșit versiunea `0.12.19` de calea executabilului uv. Parserul/preflightul stock a refuzat înainte de fixture/DB. Greșeală de orchestration/prerequisite, nu RED C04. Calea corectă este exact `/home/kali/.local/share/omnis-toolchains/bin/uv`.
2. Proba PG reală `proc_d08bb8010469`, runnerul existent `prove_private_fixture("test-contract-method-native-pg", pinned_uv, 600)`: **exit2, 1PASS/2FAIL în27.43s**, family_drained=true. Singurul PASS este regresia stderr existentă, nu C04. Ambele scenarii normal/first-late-held au refuzat `CONTEXT_OVERFLOW` înainte de stage/lansare nativă: graph **53280** + pregătire **14828** = **68108 bytes**, **2572** peste capul65536. Diferența față de assignmentul65418 era2690. Aceasta măsoară candidatul concret, **nu dovedește imposibilitatea compactării lossless**. Observerele native sunt goale/native_exit=null; native method/result C04 sunt NOT_RUN.
3. Candidatul a fost arhivat pentru investigație, nu integrat: `/home/kali/.hermes/cache/scratch/p2-c04-rejected-candidate`, patch SHA256 `c23a05ae4517b2a330a645ed55f4c9dc4cd6c60527ca0ff323de4616a31c6eef`. Arhiva nu este snapshotul exact de la lansarea PG: o funcție de outcome neterminată fusese editată în timpul probei. Nicio aprobare ori PASS nu este transferată acestor bytes. Autorul a restaurat numai schimbările proprii; părintele a confirmat checkoutul fără diff tracked, cu linkul owned `api/.venv` păstrat. Nu se integrează scaffoldul abandonat.

Raport complet scratch: `p2-c04-criteria-author-result.json`, SHA256 `841b84e2e6ffceac396f4a10a2cdb5bd6538fcd908a8e94b9db7bc83b11eed43`. Părintele a verificat toate hashes din inventarul artefactelor, receiptul `gate.log.result.json` code2/drained și suma din ambele probe de sizes; fără citire/afișare a DSN/capability/runtime.boot/tracebacks private.

## Cleanup și continuare punctuală

Fixture proprie `/home/kali/.hermes/cache/scratch/db-097ebce35186490e`, proiect exact `omnis-p01-bff858977d9049828206d738b85c6acc`: runner readback DB/rețea/socket absente, uncertain=false. Părintele a verificat din nou **0 containers/0 networks** sub labelul proiectului exact și absența socket/boot/lock pentru ambele directoare native own; nicio lansare nativă C04 nu avusese loc. Datele/logurile private sunt păstrate.

Continuarea este corecția aceleiași frontiere de produs: măsurare SOURCE a reprezentării compacte, fără pierderea semanticii/schema guards, apoi consumerul autentic/persistarea/readbackul. Nu un al treilea harness sau un rerun general. Bytes sunt înghețate înaintea probei, apoi cer reviewuri complementare exacte și integrare byte-exact. Dacă nu încape ori lipsește dovada, rămâne BLOCKED; cap/input/deadline nu se relaxează. `make check` post-fix rămâne NOT_RUN până la snapshotul final integrat; FAIL-ul canonic anterior este păstrat.
