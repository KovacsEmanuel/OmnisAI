# Felie UI separată — referință cockpit și light/dark

## Mandat și limite

Admisă explicit de operator după T2/S1 inițial CLOSED_SCOPED și înainte de S2. Baza este `aa81e63d68358ed27b6f50f57a4ae3821ef348e7`. Referința vizuală rămâne `/home/kali/OTPen/omnis/brand/omnis-cockpit-v5.html`, nemodificată, cu baseline-ul acceptat UI/UX §0 / `df17a29`. Cererea actuală aduce tema light în această felie, înlocuind amânarea ei post-MVP, nu direcția vizuală. Aprobarea propunerii nu este acceptarea estetică a unui artefact încă neimplementat.

**Corecția operatorului este obligatorie:** Settings → Models păstrează căutarea, selecția, pașii, hidratarea, assignments, testele și comportamentul existent. Acolo sunt admise numai modificări grafice/CSS pentru consistență și ambele teme, nu rearanjarea sau rescrierea fluxului. Sursele TS/TSX și clientul Models rămân neschimbate; o incompatibilitate reală cere adjudecare, nu extindere tacită.

Nu sunt admise HTTP/ShopShfere, S2–S7, auto-pair A, graph/council, backend/migrare nouă, date/metrici inventate sau inferență plătită nouă de produs. Models nu se reconectează/retestează și metadata nu se actualizează la montare. MONITOR fără plafon total LLM rămâne neschimbat. Nu se importă scripturile/datele/demo-ul sau resursele remote din HTML. Se folosesc fonturile locale existente și stackul curent, fără dependențe oportuniste.

Fișiere absolut protejate: `tempkey.txt` și `documents/Omnis_Notite_Originale.html`: fără citire, copiere, hashing, modificare, ștergere sau staging. Se păstrează seiful, datele, masterul/backupurile, CLI-ul normal, dovezile și checkoutul separat `omnis-strix-s234-catalog`. Fără profil Omnis/worktree nou, cleanup global, reset/rebase/force. Push-ul acestei felii nu este autorizat implicit de mandatul anterior pentru S1.

## Producer → consumer și acceptare

| Rând | Producer existent → suprafață | Rezultat observabil și control negativ |
|---|---|---|
| UI01 | DESIGN/tokenuri și preferință locală nesensibilă → Shell/toate rutele | Dark și light cald fidel referinței, comutator global inclusiv înainte de pairing, preferință după reload/navigare. Storage indisponibil/valoare străină au fallback sigur; numai tema se poate salva local, niciodată sesiune/secrete/context. Comutarea nu remontează/resetează draft, filtre, inspector sau run. |
| UI02 | Projection Dashboard → Home | Antet amplu + creare engagement, atenționări, metrici și recent/bento în compoziția referinței. Valori reale sau UNKNOWN/unavailable explicit distinct de zero; fără agregate fabricate, confidence/precision sau duplicarea engagementului în navigația globală. |
| UI03 | Draft/run/summary persistente → Engagement Overview | Now-bar/stadiu, Needs you, metrici/rezultate, severity, consum MONITOR și context compacte. Controalele, preflightul, identitatea, scope-ul, erorile și consimțământul rămân explicite. Detaliile tehnice sunt secundare, nu șterse; lipsa unui producer nu inventează finding ori assessment. |
| UI04 | Attempts/events/inspection/refs persistente → Brain stream și inspector | Stream cronologic compact, actor/subagent selectabil, fără graph. Inspector contextual Prompt & input / Decisions / Tools & results / Usage cu input/instrucțiuni și decizii efectiv înregistrate, nu chain-of-thought inventat. Păstrează paginarea bounded, limitele reale ale filtrelor, selecția/refs din URL, gaps/UNKNOWN și Inspect consuming Brain. Reload/selectare/temă fără dispatch nou. |
| UI05 | Settings/bootstrap/draft existente → configurare și stări | Settings, pairing, wizard, dialoguri, tabele, input/select/code, loading/error/empty/stale în ambele teme. Models numai grafic: căutare, rezultate, selecții și toate acțiunile au aceeași semantică. Findings/Coverage/Reports primesc tema/carcasă, nu funcționalități viitoare. |
| UI06 | Buildul real DEVELOPMENT + aceeași persistență → browser operator | Artefactul final construit este servit/identificat și inspectat în dark/light, desktop/mobil/zoom/keyboard; Stop rămâne accesibil și imediat, inclusiv în overlay dacă acesta face topbarul inert. Navigarea reală, re-entry și reload păstrează dovezile S1 și nu pornesc inferență. Acceptarea vizuală finală rămâne a operatorului. |

## Ownership și ordine

Orchestratorul admite scope-ul, scrie numai canon/status/probe, gestionează lifecycle/Git, reproduce/adjudecă findings și execută QA în browser. Un developer desemnat este singurul autor al produsului și al remediilor, inițial Sol 6.1 `medium`; `xhigh` numai când analiza/reviewul o justifică. Copiii nu comit în checkoutul comun, nu fac push și nu operează instanța/DB operatorului.

Developer: `web/src`, testele web existente, `web/scripts/sync-design.mjs` și testele lui dacă sunt necesare tokenurilor; `DESIGN.md`/`documents/Omnis_Design.tokens.json` și exporterul existent numai pentru palette/tokenuri canonice. Nu modifică TS/TSX/clientul/contractele Models, API/CLI, schema, lockfile/dependențe, runner, selecția/bugetele testelor sau regulile de siguranță. Citește definițiile și callerii înainte de editare; nu editează generated tokens manual.

Ordine: admitere canonică → primul increment theme/Shell cu RED→GREEN și affected checks → freeze/review independent → primul readback real al temei → următorul increment Dashboard/Overview/stream și armonizare în același mandat. Reviewerii sunt read-only, pe manifest/bytes exacți; doi complementari când delta afectează Stop, autentificare/secrete sau alte frontiere sensibile. Remediile revin developerului, cu affected checks și re-review focalizat. Nu se redeschide scope neschimbat pentru fiecare corecție.

## Verificare și livrare

Comenzile sunt cele existente în Makefile și `web/package.json`, cu PATH/toolchain pinuit. Mai întâi testul comportamental RED, apoi GREEN și lint/typecheck/test/build web afectate; verificarea completă ieftină web precede PG/canonicalul scump. Preflight fără efecte al argv/pinurilor/accesului și producerului/oracle-ului înainte de fixture. Integrarea UI folosește runnerul DB disposable existent, nu DB operatorului; consumerii afectați includ S1 UI și Models UI în fixture deterministă, nu provider live.

Canonicalul obligatoriu `make check UV=/home/kali/.local/share/omnis-toolchains/uv-0.12.19` se rulează o dată la frontiera finală pe inputuri înghețate, după review/affected QA, nu ca buclă de debugging. După editări numai documentare se refolosesc probele produsului neschimbat și se rulează `python -B scripts/render_docs.py --check`, `python -B -m unittest discover -s tests/documentation -v`, `git diff --check`. FAIL/UNKNOWN și limita de două cicluri harness-only sunt păstrate, fără timeout/assertion/runner slăbite.

Instanța rămâne aceeași UUID `d694129b-a3e5-446d-9e5b-fe9bc19abed8`, release `0.1.2`, schema `0019_agent_runs`, `http://127.0.0.1:8780`, DEVELOPMENT. Stop normal înainte de schimbarea surselor montate/rebuild, apoi start normal prin `/home/kali/.local/bin/omnis`; fără upgrade/recover sau bundle cu aceeași versiune și bytes diferiți. Pairingul manual al browserului dedicat a fost confirmat în pagina autentificată; codul nu a intrat în chat/probe. Browserul/profilul sunt păstrate, fără export de cookies/tokens sau sesiuni copiate. Expirarea autentificării cere operator, nu auto-pair ori TTL mărit.

Dovezi private ale feliei: `/home/kali/.local/share/omnis-ui-artifacts/design-light-dark-20261106/`. S1 live/core/canonicalul anterior rămân istorice la scope/revizia lor, nu certifică automat noua interfață. Reticle NOT_INTEGRATED dacă aplicația rămâne neinstrumentată; Chisel BLOCKED_NO_GO. Fără framework/harness nou.

Stare la admitere: **IMPLEMENTATION_ADMITTED / NOT_IMPLEMENTED / QA_NOT_RUN / NOT_REVIEWED**. Ultima observație lifecycle: STOPPED48 după oprirea normală din READY47, înainte de editare. Referințele și dovezile durabile ale S1 se păstrează în [T2 §11](t2-discussion.md#11-registru-s1--implementare-admisa).

Rollback: revert granular al commiturilor acestei felii și rebuild/start normal pe bytes reveniți; preferința nesensibilă din browser poate rămâne ignorată pe versiunea fără teme. Git nu revine asupra DB sau serviciilor; nu se restaurează backupuri peste date mai noi pentru o schimbare UI.
