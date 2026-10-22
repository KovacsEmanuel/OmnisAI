# QA independentă — reluare installed API/CLI/seif: PASS_SCOPED

## Verdict și limite

**PASS pentru cele două acceptance rows anterior blocate:** Start explicit pe aceeași instalare/date → autounlock și readback identic; apoi master absent → LOCKED fără regenerare, input blocat și Revoke local real → GET/receipt/PostgreSQL. Ambele cicluri s-au încheiat cu Stop exit0 și cleanup fizic exact. Cheia a fost restaurată numai după STOPPED și absența writerilor; final STOPPED generation6, admission_open=false.

**Nu închide T1/G04a, QA globală sau QA-SETTINGS-FOCUS-01.** Findingul de focus FAIL din raportul original rămâne nerezolvat pe acest artefact și nu a fost rerulat. Nu am importat fixul web concurent. Nu este probă de inferență, provider connectivity ori funcționalitate completă backup/restore.

Q = `/home/kali/.hermes/cache/scratch/ot1-0zxf62th/t1q`.

## Frontiera sursă/artefact și integritate

- Repo inspectat read-only: `/home/kali/OmnisAI`, HEAD `506c1e409ea209f6bcb8ee61261a3fc1d39a98cf`; numai HTML-ul untracked protejat preexistent, neatins. Niciun product edit/commit/push.
- Sursa produsului instalat rămâne `af8c3ba5c64c5d6122a5fde6deaeba09e2ff4873`, nu checkoutul dezvoltatorului și nu un web dist nou.
- Singurul consumer executat: `Q/venv/bin/omnis`, release instalat `Q/d/omnis/releases/0.1.0`, profile `t1-provider-settings`, schema `0014_provider_settings`.
- SHA256 release.json: `9ef854c6d2cca95a81bae032b9e7667e5c067517a40ed73f2b40da5173b63616`.
- API wheel: `ca2096d466c0b8ec4a31ccb26cf31b43458c77ee08f626384824a4fda271dcae`; CLI wheel: `3cf775e962b85716542207af48f05be38396ef7e4aba078ffa339d2e2f7e0f9e`.
- Toate cele10 payload hashes ale release-ului au fost reverificate înainte/după. Fișierele Python instalate ale CLI au fost comparate byte-exact cu wheelul instalat înainte de Start; count exact în `resume-identity.json`.
- Instanță `647f4297-2eb1-4f1a-9093-0a974b44c622`; proiect `omnis-local-24d5844fce7947e8bd9afab001d3a981`; origine `http://127.0.0.1:48765`; PG system_identifier `7699608422299463723`, păstrat în ambele booturi.
- Imaginea/jurnalul pinned rămân `sha256:59df70b899383f776cb71412135fead2942f3a6250afc0e0f05fc4063569e25e`.
- Cele112 fișiere originale selectate (toate evidence existente, raportul, driverele și capturile originale) au hashes identice la final. Manifest: `Q/evidence/resume-original-hashes.json`. Nu am suprascris raportul/logurile originale; forwarder.log runtime legitim a putut primi append de la produs.

## Refuzul original și precondiția schimbată

Originalul `restart-start.*` rămâne **exit2 / REFUSED / PORT_CONFLICT**, fără errno original. Nu atribui retrospectiv o cauză exclusivă; observația istorică TIME_WAIT este doar compatibilă cu guardul de bind existent.

Înaintea noii tentative am recitit identitatea, jurnalul STOPPED, master metadata/ciphertext și absența exactă a vechilor3 CIDs/network/forwarder/IPC/listener. Apoi am apelat efectiv funcția din CLI instalat:

`Q/venv/bin/python -I -B -c 'from omnis_cli.start import preflight_port; preflight_port(48765)'`

- Restart/autounlock: exit0 la0.117s; imediat urmat de un singur Start explicit.
- Bootul cu master absent: după Stop, observațiile fără Start au refuzat temporar bindul; primul exit0 a venit la31.293s. Observația/wait foreground a rămas sub75s; toate rezultatele, inclusiv refuzurile, sunt păstrate în `resume-locked-bind-preflight.json`. **Un singur Start** după acel pozitiv, nu start retry loop.
- Nicio modificare SO_REUSEADDR/sysctl/guard/deadline/port/root; aceleași120/90s.

## Comenzi reale și exituri

Prefixul CLI este `Q/venv/bin/omnis`. Mediul folosește helperul existent `qa_local.environment()`: HOME/XDG/TMPDIR exclusiv Q; OMNIS/DOCKER/COMPOSE/PG ambient eliminate. PATH începe cu `/home/kali/.local/share/omnis-toolchains/bin`; `PLAYWRIGHT_BROWSERS_PATH=/home/kali/.cache/ms-playwright`.

| Comandă / evidence label | Exit / rezultat |
|---|---|
| `status --json` / resume-pre-status | 0 / STOPPED generation2 |
| `start --no-open --port 48765 --json --startup-timeout 120 --cleanup-timeout 90` / resume-restart-start | 0 / READY generation3, epoch2;15.630s |
| `status --json` / resume-restart-status | 0 / READY;3.025s |
| pinned `node Q/resume-journey.mjs resume-restart` | 0 / browser readback PASS,0PUT;2.175s |
| `stop --json --shutdown-timeout 120` / resume-restart-stop | 0 / STOPPED;9.703s |
| `status --json` / resume-restart-stopped-status | 0 / STOPPED generation4;0.616s |
| același Start exact / resume-locked-start | 0 / READY generation5, epoch3;16.539s |
| `status --json` / resume-locked-status | 0 / READY;2.725s |
| pinned `node Q/resume-journey.mjs resume-locked` | 0 / LOCKED și Revoke real PASS,1PUT;2.627s |
| `docker exec <db CID> psql -U omnis -d omnis -A -t -c 'BEGIN READ ONLY; ...; COMMIT;'` / resume-locked-pg-metadata | 0 / metadata și receipt concordante; SQL/argv integral în command.json |
| `stop --json --shutdown-timeout 120` / resume-locked-stop | 0 / STOPPED;8.454s |
| `status --json` / resume-locked-stopped-status | 0 / STOPPED generation6;0.567s |
| `status --json` / resume-final-status, după restaurarea cheii | 0 / STOPPED generation6;0.567s |

Readbackurile `python -B Q/observe.py resume-{pre-stopped,restart-live,restart-stopped,locked-live,locked-revoked-live,locked-stopped,final-stopped}` au ieșit0. Funcția existentă face inspect exact, metadata și, la `*-live`, PG READ ONLY/log capture. Browserul a fost paired prin helperul existent private-PTY `tty_pair`, CLI instalat; codul a rămas numai în memorie/stdin, fără argv/log/chat. Chromium pinned153.0.8010.12, fără download/instalare nouă; ambele contexte/browser procese închise.

## Matrice observabilă

| Criteriu | Verdict / dovadă |
|---|---|
| Restart aceeași instanță și date | PASS; status real, system_identifier PG și inode PGDATA păstrate; configurație GET deep-equal cu `browser-continue.json.expectedRestart`. |
| Autounlock fără write pozitiv simulat | PASS; UI și GET UNLOCKED, rev5 enabled=true/credential_present=true;0PUT. Default `Exact/Default:Case`,137, connection_revision5; selection rev3 și override-uri null identice. |
| Missing master → LOCKED | PASS; după rename doar în STOPPED, Start real; key path absent și înainte/după browser, fără regenerare; GET/UI LOCKED, input API key disabled. |
| Revoke local în LOCKED | PASS; exact1PUT prin butonul real, current GET rev6 enabled=false, GET exact receipt HTTP200 și receipt PG identic. |
| Persistență | PASS; PG6 connection revisions,3 selection revisions,9 commands; toate liniile de istoric originale se regăsesc în readbackul PG final live. |
| Cookies/IndexedDB canary scan | PASS_SCOPED; un cookie,0canary hits;0IndexedDB databases/stores/rows; local/session storage0canary hits. Numai summary nesensitiv păstrat, fără cookie values. Scan noul context paired, nu toate profilele browserului. |
| Public GET/DOM și capturi | PASS_SCOPED; răspunsuri/DOM fără canary; input gol înainte de capturi; `resume-*-browser.json` și `screens/resume-*.png`. Capturi de evidență, nu aprobare vizuală/WCAG. |
| Fără IO de provider/model/refresh | Nicio asemenea acțiune trimisă;0 cereri externe observate. Browser route permite doar aceeași origine și blochează extern, fără răspunsuri pozitive fabricate. Reachability rămâne NOT_VERIFIED. Nu este packet/syscall proof universal. |
| Cleanup fizic și retenție | PASS; readbackurile exacte de mai jos, Stop0, date/key/pending/logs/receipts păstrate. |
| QA-SETTINGS-FOCUS-01 | FAIL istoric / UNRESOLVED / NOT_RERUN, nu mascat de acest PASS scoped. |
| Contrast numeric /200%/forced colors | NOT_RUN; breadth opțional omis. |
| Model T1 / full backup-restore | NOT_RUN și ne-revendicate. Reticle NOT_INTEGRATED; Chisel BLOCKED_NO_GO. |

Revoke command UUID: `7f830281-fda5-45a3-8aaf-5edd62e94ed0`. În LOCKED, API expune `credential_present=false` (indisponibilitate), **nu dovadă de ștergere ciphertext**. Ciphertextul a rămas byte-identic. Receiptul istoric păstrează corect LOCKED la momentul operației. După restaurarea fișierului nu am făcut încă un Start: finalul rămâne STOPPED și conexiunea este legitim revocată rev6, nu reactivată.

## Custodie cheie, metadata și inversă exactă

Înainte de fault: STOPPED generation4,6 etape teardown complete; toate CIDs/network/forwarder/IPC absente, project `docker ps -a` gol. Planul cu metadata și inversă a fost scris înainte de rename.

- Sursă: `Q/s/omnis/vault-key/master.key`.
- Holding privat creat0700: `Q/resume-key-hold/master.key`.
- Singura operație: `os.rename(source, holding)`; fără read/hash/copy al cheii.
- După al doilea Stop și cleanup verificat: `os.rename(holding, source)`. Metadata readback identică; holding file absent; directorul holding gol a fost eliminat cu rmdir. **Nicio inversă restantă.**
- Plan/efect/inversă: `resume-missing-key-plan.json`, `resume-missing-key-rename.json`, `resume-key-restore-plan.json`, `resume-key-restored.json`.

Toate obiectele de mai jos sunt pe device2049. Metadata complete before/after în `resume-acceptance-summary.json` și readbackurile adiacente.

| Obiect relativ la Q/s/omnis | Before → after |
|---|---|
| postgres bind-root | inode9056352,uid/gid1000:1000,0711,size4096,mtime_ns1792704784556172813 → identic |
| postgres/18/docker PGDATA | inode9060550,999:0,0700,size4096 → păstrate; mtime_ns1792705029624161432 →1792706134624102699 după scrieri/Stop legitime |
| vault dir | inode9056337,1000:1000,0700,size4096,mtime_ns1792704973295968782 → identic |
| vault/vault.json | inode9085192,1000:1000,0600,size1280,mtime_ns1792704973295968782 → identic |
| vault/vault.pending | inode9085255,1000:1000,0600,size0,mtime_ns1792704889468212825 → identic |
| vault-key dir | inode9056338,1000:1000,0700,size4096 → păstrate; mtime_ns1792704889472212826 →1792706136452233698 prin rename/inversă |
| vault-key/master.key | inode9085320,1000:1000,0600,size32,mtime_ns1792704889473867925 → identic inclusiv în holding și după inversă |

SHA256 ciphertext vault.json înainte/după: `8153fdd7c74ed5ae688db0824b45634c63aa9d20d0c2c1d7103c16c80b00fe04`. **Master key nu a fost citită/hash-uită de QA.** Nu am inspectat/modificat intern fișierele PG owned999. Instalarea, imaginea, PGDATA, ciphertext, pending, runtime logs și Stop/command receipts sunt retenționate.

## Cleanup exact — verificat fizic la final

Toate cele9 CIDs (inclusiv originale) au fost inspectate din nou la final: exit1 / No such object, nu dedus din status sau din listă goală.

| Ciclu | Serviciu | CID absent |
|---|---|---|
| original | api | `9fd87650c864939a5c9c37d9f8a0eb1b9f61773cf38a0e21aa1e0b0e38179892` |
| original | db | `b500b1e3f6128e766156b72b631a1bec718e689bb4bda5b36579ab69203e5eca` |
| original | supervisor | `0bb6f93d3f244cdf5dfb675f60871c2d011b3f6eb4703479b38a9913d024ba38` |
| resume autounlock | api | `69fa76c9cc2858108700fd472ba6bca39b3870dc152b04d8d6b9d3c7eea983bd` |
| resume autounlock | db | `244a9e5142672f641e5ddde100e62adaa697a10c526fcd7e29e38457071e84d3` |
| resume autounlock | supervisor | `d8f1a6a861990cfe3594387e3dcb5528d3cfe0fdabd8ba6f6a5818f1c4c54680` |
| resume LOCKED | api | `3fe5921171bdaaa2a6bbcdae3f000872b05b7fcf6576de5dd5bb84d7f2a30bfa` |
| resume LOCKED | db | `542db446452390518a2e3fc645924c7161ad76a5af16be2a8513b38ba605e5ad` |
| resume LOCKED | supervisor | `3cf476159283f75164054b24bcf3234e437b3fc79ef664d522c32eccd382f180` |

Exact network inspect exit1/not found pentru toate3:

- original `608c79b73ba87ea4895a39c3d16b17aecd61c285ccd7ba18158ae1b966f01c86`;
- autounlock `cd2cc9c7219174ee7bd2c8b8103a7158b464cc7e948f7f3e801bb0bd3fab60f2`;
- LOCKED `759ec5eec75a6b86677049e726a1e2676632eeac512a03eafa3aaacf7673e7b5`.

Project networks list goală. Forwarders `/proc/PID` absente: original690680/start_ticks14318289, autounlock711471/14432661, LOCKED723433/14447387. Loopback48765 connect_ex111; `ss -ltnp 'sport = :48765'` exit0 numai antet/fără listener. `Q/r/omnis/control.sock` și `Q/s/omnis/http/api.sock` absente prin metadata/lstat, zero socket entries în ambele directoare owned. Jurnalul final STOPPED/teardown_completed forwarder,api,supervisor,db,network,ipc; status final generation6/admission_open=false.

Dovezi: `resume-restart-stopped-readback.json`, `resume-locked-stopped-readback.json`, `resume-final-stopped-readback.json`, `resume-final-listener.stdout`, `resume-final-status.*`, `resume-acceptance-summary.json`. Niciun cleanup blind, prune/down-v, kill străin ori ștergere date.

## Fișiere și probleme

Creat numai în Q: driverul finit `resume-journey.mjs`, `evidence/resume-*`,3 capturi `screens/resume-*.png` și acest raport nou. Driverele/originalele au rămas byte-exact. Singurele schimbări legitime de date produs: lifecycle generations3–6, pairing sessions, Revoke rev6 și command/Stop receipts. Rename-ul master a fost inversat exact.

Nu au apărut erori noi de driver ori failed Start; nu au fost necesare cicluri de reparare harness. Refuzurile temporare ale preflightului înainte de bootul LOCKED sunt păstrate, nu redenumite PASS. Rezultatele nu justifică o cauză exclusivă a refuzului original și nu rezolvă findingul de focus.

Omis: CAS/lost-reply/reload/revoke UNLOCKED deja trecute, contrast/zoom200%/forced colors și orice model/provider/target IO. Risc rămas: focus FAIL pe artefactul neschimbat; conexiunea fixture este acum rev6 disabled, iar autounlock după restaurare nu a fost rerulat pentru a păstra finalul STOPPED.
