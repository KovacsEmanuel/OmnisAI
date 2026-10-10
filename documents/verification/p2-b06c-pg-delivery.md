# B06c — PG/copy-installed verificat; predare serială pentru B06m

## Verdict bounded

READY_FOR_INTEGRATION pentru componenta ModelProjection v1, cu probe PG/copy-installed independente PASS_SCOPED. READY_FOR_NEXT_HOLDER_B06M după readbackul cleanupului; holderul NU este schimbat aici. SL10/G-DATA-EARLY complet, G02 și faza2 rămân NOT_CLOSED: consumerul SDK/pre-send autentic este NOT_INTEGRATED și nu există acord pentru model/provider/target. Nu redenumim cold în warm.

Snapshot final test/Makefile: `d1b8e01a5509e08ad36d831fd2886f1f22c3224f`; codul produs revizuit rămâne byte-identic cu `77b4b01`. Baza locală rămâne c0261a7. Main/C03 și WIP B06m nu au fost modificate/adoptate. Transferul operatorului a permis numai targetul minimal Makefile, testul PG nou și fixture-uri NOI UDS/no-network/copy-installed, zero model/provider/target; effects holder=b06c a fost recitit înaintea efectelor. Nu este gate canonic make check.

## Ce a fost exercitat real

Helperul C03 de calificare/publicare → snapshot/selection/context/input RUN noi persistente → InstanceService/fence și ManagedAdmission.prepare/commit_binding reale → ModelProjections.prepare pe PostgreSQL18.6 atestat → rollback după INSERT, commit, replay/count1 și trigger imuabil → proces instalat nou ModelProjections.read → serializer și bytes gate reale. Resolverul, SQL, proiecția și serializerul nu sunt dublate.

Prerechizitele NativePreparation/stage sunt seed-ul de protocol sintetic existent, declarat `SYNTHETIC_PROTOCOL_SEED_NOT_NATIVE_PROOF`, nu loader/root/copil nativ autentic. Acest seed nu acordă model/tool/target authority. Cele patru origini runtime sunt în site-packages, nlink1 și bytes identici cu sursa revizuită; wheel-ul API/Hermes este non-editable/copy și dependențele locked/offline/hash-required. ROOT/HOME/cwd sunt noi, în afara checkoutului; SDK/provider imports sunt refuzate. Zero model/provider/target este proprietate structurală a traseului cold/protocol, nu tracer universal al unui SDK warm.

Datele probei sunt sintetice, explicit clasificate. Markerul rămâne în inputul privat și lipsește din proiecție/carrier; path=`/[redacted]`. Proiecția persistentă și carrierul au digests distincte, ambele verificate; niciunul nu este digestul requestului SDK complet.

## Probe și reparații păstrate

1. Target absent: RED make exit2. Primul PG `proc_db0c551f7a3e` a eșuat înaintea proiecției: root sintetic repetat sub același boot încălca UNIQUE(runtime_boot,native_root_id). pytest1FAIL/gate2, family_drained=true și cleanup exact. Numai fixture-ul a primit root/child/session distincte; fără modificare de produs. [Eșecul păstrat](p2-b06c-pg-attempt1.json).
2. Părinte `proc_8f7b93223069`, inputurile ulterior comise în e4c3c4d: make test-model-projection-pg exit0; pytest1PASS, family_drained=true;124inputuri/4artefacte identice. SQL/proces nou/carrier6720bytes probate. Această probă rămâne istorică, nu este transferată automat fixului ulterior.
3. Reviewurile A/B `deleg_7365af35` au cerut schimbare pentru aceeași problemă A-01/B1: journey-ul installed era colectat implicit de canonical fără preflightul installed și ar utiliza baza comună. Părintele a reprodus intrarea neactivată în prerechizite (1FAIL), apoi d1b8e01 a adăugat doar opt-in exact în target și decoratorul installed-only. Implicit1SKIP explicit, activat fără fixture1FAIL. Targetul nu poate obține PASS prin SKIP; test-api/check-components/runnerul și toate aserțiunile PG anterioare sunt neschimbate. Nicio slăbire a gate-urilor existente.
4. Re-reviewuri complementare `deleg_8957a514` pe exactd1b8e01: A `sa-0-a41a75d1`, APPROVED_SCOPED/A-01 RESOLVED_VERIFIED_SCOPED; B `sa-1-1dd4c3b3`, APPROVED_SCOPED/B1 REMEDIAT_SCOPED. SHA/status/bloburi stabile înainte/după; default/activated/missing-manifest probate offline. A a rulat și206PASS/5PGdeselected; B ruff/format/mypy exit0. Locatoare: `/home/kali/.hermes/cache/delegation/live/deleg_8957a514/task-{0,1}.log`. Aprobările componentei77b4b01 sunt păstrate separat.

## QA independentă după ultima editare

`deleg_10672bb6`, `sa-0-3bffad72`, snapshot exactd1b8e01, root NOU `/home/kali/.hermes/cache/scratch/p6c-d94877fc`, resurse/cleanup înregistrate înainte de launch. Comanda reală:

    env -i HOME=/home/kali/.hermes/cache/scratch/p6c-d94877fc/home PATH=/home/kali/.hermes/cache/scratch/r3-5gjabhuw/tools:/usr/bin:/bin TMPDIR=/home/kali/.hermes/cache/scratch/p6c-d94877fc make --no-print-directory test-model-projection-pg UV=/home/kali/.hermes/cache/scratch/r3-5gjabhuw/tools/uv

Outer/gate exit0, family_drained=true; pytest1PASS/0SKIP în37.00s. Producer și reader în procese distincte, Ref/digest/readback/replay/rollback/immutabilitate reale.7prepare,7read,7source-extra,10carrier-extra,3bytes/limită/duplicate și2policy/known-secret controale refuzate; sunt familii de aserțiuni în același journey, nu un total de teste inventat. Carrier6720bytes, SHA256 `3c6d1356bd1148a3d851452b22b73e64b0fd66e61dc08b532154f71c221c526c`, marker absent.124inputuri și4artefacte identice înainte/după; manifestul `ed18a189a6b9f43774d6b911c51196cb2cdf182332d23ed3190863b3b574a46a` stabil. Părintele a reverificat separat inputurile, artefactele, receipturile și carrierul după QA.

Raport complet privat: `/home/kali/.hermes/cache/scratch/p6c-d94877fc/qa-result.json`; transcript `/home/kali/.hermes/cache/delegation/live/deleg_10672bb6/task-0.log`. Receiptul versionat al predării este [p2-b06c-pg-final.json](p2-b06c-pg-final.json). Nu sunt probe physical PG restart/restore ori native/full SDK; restartul demonstrat este al procesului consumerului.

## Cleanup și trecerea rândului

Runnerul existent a oprit/retras exact cele trei CIDs proprii ale acestei felii; niciun cleanup paralel/global:

- FAIL driver: `fbb94ff22eb49a1414367f1bf1a30369d9f52242363198a76a156a0ec15bcdef`.
- PASS părinte: `a2ebe3046b6930f8063b5dfdba3ed7694c841bc8e24028ef99b02c55d3701d95`.
- QA independentă: `bd884ce831518152c191f69e1a7b0775375d0ad9e1889e08d613864b93083916`.

Fresh GET-only independent + părinte: fiecare CID absent, inventar project gol, rețele absente, UDS/lock absente; cele13identități publice foreign neschimbate. PGDATA (`data/18/docker/PG_VERSION=18`, `global/pg_control`), corpus/catalog, wheels/venvs și receipturi/loguri păstrate. Baza nouă omnis_test NU a fost DROP-uită; SQL count1proiecție/count2binding a fost verificat înainte de stop. Păstrarea files nu este test de restaurare sau ACK reconstruit. Fără r1/profile/credențiale vechi, prune, upgrade global, push ori original HTML protejat.

B06c nu mai deține procese/containere/socketuri live din probe și poate preda rândul. Coordonatorul poate transfera holderul către b06m pe baza readbackului exact din `b06c/pg-final-readback.json`; noi NU edităm effects.holder și nu lansăm sesiuni/cronuri succesoare.

## Restul cross-worktree

B06m poate importa commiturile B06c înghețate/revizuite în worktree-ul lui, nu main. Integrarea trebuie să lege readerul calificat și carrierul de binding/purpose/InstanceControl/Stop înaintea reserve și de întregul request la sinkul nativ real, inclusiv options/tool/results/errors/logs/retry/fallback. Native-turn producer și veto-ul fizic terminal rămân necesare; fără patch către API inventat sau client fake.

Registrele globale/status/README/plan/HTML, schema/core/CLI/upstream/pin rămân ale integrării. B06m nu trebuie să editeze Makefile concurent; schimbarea noastră este numai targetul minimal opt-in. La integrarea finală, gate-ul global și browserul rulează o singură dată serial pe buildul integrat; partea installed-only PG se activează explicit cu fixture nouă, nu prin reutilizarea acestor DB-uri. SL10 nu se închide din această probă de componentă.
