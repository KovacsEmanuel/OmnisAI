# R1 — APPROVED_SCOPED

Review independent, read-only asupra checkoutului `/home/kali/.hermes/cache/scratch/t1-33ee99/dev`. Niciun finding concret în delta admisă; fără aprobare de integrare sau runtime.

## Identitate și limită

- Bază: `4eb0bfc149c099380af653740329726a5a9bf38f`.
- HEAD: `1ef4df28bbb0b19e3d08e7d90426dbbd4d7573e8`, checkout curat la început și la readback.
- Singurul fișier schimbat: `cli/integration/test_release.py`, +9/−3; numai cele două fixtures nominalizate.
- Blob: `e9b37980e236e775b10ad0811b703e207de4bea5`.
- SHA256 fișier: `cabab5d4908b3c0f9eba5e7af9b8f56fc0f241d60e98647816ae0fc20fa9e32c`.
- SHA256 diff: `0127f9596194116f30c0020aca304a8df9e2dd37646638aa79f29d367b5e96bb`.
- Identitățile au fost calculate direct și coincid cu `freeze.json`; `git diff --check` exit0. Produsul, helperii și gate-urile nu sunt modificate.

## Cerință → consumer → risc → verdict

Restaurarea premisei fixture-urilor trebuie să permită exercitarea oracle-ului real de cleanup fără ocolirea controalelor private/daemon și fără transformarea timeoutului în succes.

1. **Premisa de director este corectată, nu controlul slăbit.** L239/L318 creează explicit `data` cu `0o700`. `cleanup_image_install` transmite `root=data/omnis` către `_docker_id` (L485); acesta apelează `_run` (`compose.py:301–306`), care validează `cwd.parent=data` înaintea creării clientului privat (`compose.py:40–67`). `instance.py:16–33` respinge în continuare permisiunile nesigure. Nu există patch pentru `private_dir` sau `_docker_id` în cele două teste.
2. **Mockurile urmează producerul actual.** L269–272/L350–353 acceptă `docker --config <director>` numai cu părintele exact `data` și sufixul exact `--host <socketul fixture-ului> info --format {{.ID}}`. Acesta este argv construit de `_run`; parserul real `_docker_id` rămâne activ. Ramurile `image inspect/rm` păstrează endpointul explicit al helperului. Comenzile neașteptate continuă să eșueze, nu primesc succes generic.
3. **Oracle-ul nu este înlocuit de un PASS de mock.** Timeoutul setează `uncertain=True`, iar `finally` execută cleanup (L657–664). Traseul existent este validare receipt/socket/daemon → inspect → verificare labels/identitate → reverificare daemon → ștergere tag → inspect absent și reverificare daemon → eroare `uncertain` (L458–539). Primul test cere atât eroarea, cât și `removed=True` (L308–310).
4. **Late image și recuperarea rămân observabile.** Al doilea mock întoarce absent la prima inspectare, apoi imaginea deținută, apoi absent după ștergere. Testul păstrează eroarea `uncertain`, `removed`, `inspected>=3` și existența intentului (L390–394). Controlul daemon-switch înaintea ștergerii (L396–456), retenția `bundle_scratch`, helperul cleanup și propagarea incertitudinii sunt neschimbate; comparația AST a confirmat acest lucru. Nu s-a adăugat census sau harness nou.

## Dovezi și limite

Am citit outputurile originale: `evidence/red.log` — 2 ERROR, `Unsafe private directory`; `private-parent-only.log` — 2 FAIL pe argv vechi; `green.log` — 2 PASS/0.111s; `release-full.log` — 73 PASS/18.940s. Exit-urile 1/1/0/0 sunt în freeze. Acestea sunt execuțiile autorului citite, nu rerulări R1. Hashurile producerilor `compose.py` și `instance.py` coincid cu identitatea SOURCE consemnată în `cli-installed-identity.json`.

Verdict: **APPROVED_SCOPED pentru remediul test-only și păstrarea oracle-ului**, pe bytes exacți de mai sus. Reviewurile anterioare ale produsului neschimbat nu sunt redeschise și nu sunt extinse. Integrarea și acceptarea aparțin părintelui.

Creat numai acest raport scratch; niciun fișier din checkout modificat. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Neexecutat: QA, teste fresh, OCI/PG, servicii, provider, rebuild ori audit legacy general; fără acces la chei sau HTML protejat.
Risc/limită: Docker și timeoutul sunt simulate în aceste fixtures; aprobarea nu certifică cleanup live și nu închide T1/canonical.
