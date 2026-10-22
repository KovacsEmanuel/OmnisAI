# Prompt pentru implementarea T1 — Settings și Test model

**HANDOFF_ONLY în sesiunea care a scris acest fișier.** Prompt pregătit, nu developer lansat și nu implementare autorizată de T0. Devine mandat numai când operatorul cere explicit executarea lui într-o sesiune de implementare, după acceptarea T0 din registru. Nu continua automat T2 sau M-LAB.

## Mandat pentru sesiunea de implementare

Lucrăm în `/home/kali/OmnisAI`, branch `checkpoint/p2-batch2-pause-20261015`. Livrează **T1 cap-coadă**: web Settings → conexiune API-key/seif → operație de sistem → sender nou → Test model finit → outcome/consum/readback și Cancel/Stop. Nu livra numai un helper sau un UI care refuză permanent. Baza de produs anterioară T0 este `9eda496061604fbbbe60f3c980a5c4636cf827c5`; amendamentele și acceptarea exactă sunt în `documents/verification/api-key-runtime-t0.md`. Reconfirmă HEAD/status/diff și citește unicul CURRENT; nu presupune că ramura sau bytes au rămas neschimbați.

Citește AGENTS și contractul de lucru din CONTRIBUTING, apoi numai:
- arhitectură §4/§5–5.5/§8.1, plan §4/§7–8/§19.2;
- stack §1–4/§7/§9–10, UI/UX Settings/Test model/stări/readback;
- rândurile SL07/SL10/SL11/SL12 și nucleele SL02/SL04 afectate din harta de status;
- definițiile și callerii reali ai fișierelor de mai jos, manifestele și comenzile lor.

Nu reciti toate registrele istorice. Nu relua Codex/openfix/P2, native startup/idle/preparation sau vechiul smoke. `documents/Omnis_Notite_Originale.html` este untracked preexistent protejat: nu îl citi, modifica, șterge sau comite.

T1 nu este finalul produsului: păstrează în tracking T2 agent/tool loop → T3 HTTP/evidence/auth și sandbox cu primul consumer → T4 M-LAB IDOR/BOLA + triage + validator → T5 raport/retest → T6 funcții/skills/tooluri/UI extinse și E1–E4. Plan §15.1 și UI/UX §7.1 sunt ruta de extensie, fără alt backlog sau redesign implicit. Nu implementezi aceste etape anticipat și nu le declari livrate din Test model.

## Contracte obligatorii deja decise

1. **Owner:** supervisorul existent; API transmite pe controlul privat autentificat, nu execută modelul. Root `system_operation` autentic/persistent, fără engagement, managed-run fictiv, MissionSpec, catalog, Publish sau provision Hermes. UNIQUE(instance, command), payload digest și config snapshot immutable; replay receive-only, conflict 409, Cancel cu ID și revision proprii.
2. **Seif:** criptare AEAD locală, master key privată separată, autounlock după restart, write-only din web și fără reveal. Nicio cheie în log/prompt/DB public/export/argv/browser storage. LOCKED fără master key, fără regenerare peste date. Fișier durabil înaintea publicării referinței DB, revocare/rotație și backup/restore minim probate. Nu protecție pretinsă de root/same-UID.
3. **Config:** OpenRouter/OrcaRouter API keys, model implicit + override BRAIN/INVESTIGATOR/VALIDATOR reprezentabile; primul consumer real poate fi OpenRouter. Endpointuri de release allowlisted, nu URL arbitrar. Save local zero provider IO; catalog refresh explicit. Snapshotul unui run/operații nu se schimbă la editarea defaultului.
4. **Dispatch:** ModelDispatchV2, permit finit → SENT durabil → veto final → sender → outcome; verifică authority/config/secret revision/DATA/deadline inclusiv conexiuni reutilizate. Nicio tranzacție DB ținută cât răspunde providerul. Client și Runner fără retry/fallback implicit, tracing extern oprit. Bibliotecă candidat `openai-agents` la T2, client `openai` distinct; nu adopta pinurile de cercetare drept dependențe admise.
5. **Test:** mesaj sintetic fix afișat, maximum un apel/300 secunde de la admitere, input/output bounded conform canonului, fără tools/target/auxiliare. Un test activ, fără overlap assessment; închiderea tabului nu-l anulează. Reload/restart nu retrimit. Re-test explicit după reconciliere locală, fără ștergerea UNKNOWN/consumului precedent.
6. **Outcome:** operație locală vs provider status vs usage separate; requested nu devine observed prin copiere; parțial/eroare/UNKNOWN/TRUNCATED nu devin COMPLETE. Cost observat/estimat/necunoscut fără zero inventat ori dublă contabilizare. Runurile ulterioare folosesc MONITOR fără plafon total LLM, credit/quota HOLD și Resume manual; T1 fără run păstrează refuzul, nu creează engagement HOLD.
7. **Distribuție:** release nou/instanță nouă, fără adopția DB/granturilor operatorului; sender provider prin canal privat finit, nu rețea control deschisă general. Noile calleri nu lansează Hermes. Păstrează V1/migrațiile/date/licențe/readeri și raportează exact categoriile istorice încă nesuportate. Nu ștergere după numele fișierului.

## Producer, consumer și fișiere

Producer intenție: operatorul în Settings. Producer autoritate/identity/config: supervisorul și store-urile sale. Primul consumer: transportul nou de model; primul readback: API/decoderul web pe același operation ID. Înainte de developer fixează forma completă și dimensiunea inputului pe acest traseu; frame-ul vechi de control nu se mărește sau fragmentează implicit.

Frontieră existentă: `api/src/omnis/modules/settings/provider_models.py`, `provider_routes.py`; `modules/runs/model_test_models.py`, `model_test_routes.py`, `model_test_operation.py`; `supervisor/__main__.py`, `modules/instance/service.py`, `schemas.py`, `transport/local_control.py`; `policy/model_dispatch_contract.py`, `budgets.py`; `web/src/features/engagement/ProviderSettings.tsx`, `ModelTest.tsx`, callerul real de Settings și decoderii din `web/src/shared/api/`. Inspectează definițiile/usages înainte de schimbare; numele nu garantează compatibilitatea V2.

Introdu numai modulele de conexiune/seif/operație/sender și migrarea aditivă cerute de consumer, după 0013; actualizează schema/readiness/CLI/bundle și manifest/lock/export inseparabile. Modifică `contracts/omnis.openapi.json` și tipurile generate numai din endpointurile reale; decoderii manuali nu se repară automat. `cli/src/omnis_cli/{release,compose,start,start_runtime,status,stop}.py`, `forwarder.py` și build/Compose sunt în scope numai unde noul artefact le cere. Nu muta frameworkuri sau implementa shell/sandbox/triage/validator/T2–T6 aici.

## Efecte și autorizații

Activarea promptului autorizează implementarea T1 și verificările locale necesare în scope-ul lui; **nu autorizează chei personale, apeluri plătite sau ținte**. Înainte de DB/Docker/build/download, precizează comanda reală, prerechizitele, rooturile noi owned și efectele; obține acord dacă sesiunea nu le-a autorizat explicit. Nu adopta `.omnis*`, r1/PGDATA/containere existente, profiluri globale sau credentiale ambientale. Nu instala global, nu remote scripts/MCP/watchers/cron, nu push.

Inferența developer/reviewer este distinctă de inferența produsului. Pentru prima probă live, după guardurile/reviewurile necesare, cere numai conexiunea/modelul/parametrii, inputul sintetic și acordul testului finit. Operatorul introduce cheia în web; nu accepta secretul în chat. Lipsa acordului live este BLOCKED_LIVE/NOT_RUN, nu motiv să nu implementezi traseul inert și nici permisiune de a fabrica un răspuns.

## Livrare și verificare

Orchestrator → un developer desemnat → FREEZE exact → două reviewuri complementare read-only pentru secrete/authority/Stop → remedii de același autor → QA independentă pe artefactul real afectat. Folosește team-slice; nu echipă permanentă de audit. Preflight fără efecte devreme; după minimum SOURCE/review, prima probă bounded a consumerului înainte de breadth auxiliar. După două cicluri numai harness pe aceeași acceptance row, restrânge sau raportează blockerul, nu alt verifier.

Pozitive: Save→readback fără rețea; secret persistent/autounlock; test explicit prin owner/sender; rezultat/consum exact după reload și restart; Cancel/Stop; re-test nou legitim. Negative: master key absentă/greșită, secret echo, config străină/stale/revocată, același ID cu payload diferit, duplicate fără send, Stop între reserve/send și conexiune reutilizată, 401/credit/quota/rate limit distincte, error/incomplete/UNKNOWN/lost reply fără resend, crash file↔DB, ledger fără dublare. Testează consumerul instalat, nu numai imports/helper mocks; protocol/local fixtures nu sunt provider live.

Comenzi: citește manifestele/Makefile/runner help și folosește comenzile existente pentru API/PostgreSQL/CLI/web/contracte; adaptează gate-ul activ pentru release nou fără skip global sau dependență nativă moartă. `make check` are efecte DB și nu este dry-run. Quality/gates afectate după ultima editare; canonical la integrare, fără rescanarea acceptărilor neschimbate. Pentru docs: renderer/check și unittest documentation.

Commit după fiecare schimbare coerentă cu rationale, verificări, limite și rollback; stage numai căile intenționate. Menține un CURRENT și rândurile afectate din `implementation-status.md`/registrul consumerului, fără backlog paralel. Continuă până la rezultatul T1 sau blocker real, nu handoff după fiecare fix. Raport final în română: ce funcționează, snapshot/commituri, probe și review, live NOT_RUN/BLOCKED unde lipsește, efecte/cleanup, următorul pas. **Nu lansa T2 automat.**
