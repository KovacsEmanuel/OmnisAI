# R1 — review independent cold backup/restore

## Verdict: CHANGES_REQUESTED_SOURCE_SCOPED — R1-COLD-01

Snapshot readonly: `5ffa130ce1b0bd4f80add2105ef54b6a38bf51eb`, tree `b2acd878d17f9fcd681a96f1ecfad185d5f70971`; baseline `fea84e2d987d56db3a3f701f0b3d396f7fe21a64`. Scope: cele nouă căi din diff; callerul Start/restart, receiverul real `omnis.stop_reconcile` și tranzacția `InstanceService.reconcile_stop`, plus status pentru rezultatul operatorului. Fără integrare, editări de produs, servicii, PG/OCI/provider, instalare ori credentiale reale. Cerință → consumer → risc → decizie: restore stopped verificabil → restore/status/primul Start → proiecție falsă, autoritate istorică reutilizată sau reconciliere retrimisă → admitere QA versus remediu.

## Must fix

### R1-COLD-01 — MEDIUM: restore reușit nu are proiecție operator stopped

- **Loc:** `cli/src/omnis_cli/backup.py:599–603` (mesajul nou), `backup.py:441–477` (publică instance/restore, deliberat fără startup curent); consumer afectat `cli/src/omnis_cli/status.py:39–40,60–81,114–125`.
- **Repro:** `python -B /home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/logs/reviewer-cold1-probe.py` → exit0 al reproducerului. CLI `backup`/`restore` reale, filesystem real; PG/OCI/cold_identity doubles declarate, zero sockets/servicii. Restore exit0 afișează `RESTORE_COMPLETED: target STOPPED`; marker valid `state=STOPPED`, UUID păstrat, fără startup curent. Imediat `main(["status", "--json"])` întoarce **exit3, state=UNAVAILABLE, reason=CONTROL_UNAVAILABLE**, nu distinge restore complet și sănătos de control plane defect. Probe-ul confirmă și că status nu execută Engine. Acesta este rezultatul actual, nu output inventat ori restore real.
- **Criteriu încălcat:** contractul operatorului „restore rămâne stopped” și cerința atribuirii de a verifica adevărul comenzilor pe noul root; status nu are consumer pentru noua admitere fizică. Un receipt STOPPED istoric nu trebuie copiat ca autoritate pentru a ascunde lipsa.
- **Remediu minim:** ramură status read-only pentru root restaurat fără startup, care validează admiterea nouă/absența resurselor actuale și proiectează explicit `RESTORED_STOPPED` (sau STOPPED cu provenance distinctă), fără a reutiliza vechile PID/CID/receipturi ca autoritate. Test mic restore→status și marker invalid→refuz pe același canal. Nu slăbi guardurile normale.
- **Risc dacă se omite:** operatorul vede o eroare după o restaurare reușită și nu poate distinge starea sănătoasă pre-Start de o instanță pierdută; nu am demonstrat bypass de admitere sau pierdere de date din acest defect.

## Cerințe urmărite, fără alt defect concret confirmat în scope R1

| Cerință | Cod/constatare SOURCE |
|---|---|
| Backup numai după Stop verificat; fără Start implicit | `backup:222–238,269–287`: `readback_stopped` înainte/după, control PG shut down/system_id, lock global și root în `cold_command:593–598`. |
| Proveniență immutable versus admitere fizică nouă | `restore:386–387,441–477` păstrează bytes în restore-source; marker separat cu identități root/PG/vault/key și hashuri. `admit_restore:480–565` validează identitățile și schema; istoricul rămâne istoric. |
| Root nou, fără overwrite, fără master export | Publicare exclusivă prin `publish_directory`/renameat2 NOREPLACE; output/target preexistent refuzat; set fix snapshot fără master, import separat explicit. `_put` fsync fișier, directoarele/publicarea sunt fsync. |
| First explicit Start, fără adoptare normală inode nou | `start:1125–1134,1186–1201` capturează markerul înainte de lock, compară sub lock, păstrează UNOWNED guard; `prepare_restore:568–582` verifică admission+system_id înaintea intenției. |
| ID proaspăt și persistență înainte de efecte | `_prepare_reconciliation:79–106` salvează originalul byte-exact și request cu uuid4, persistă/readback PREPARED înainte de journal și DB create; marker STARTING împiedică reluarea unui cut intermediar. |
| DB identity → receiver real → Supervisor/lease/OPEN | `start:1327–1389` verifică system_id și instance UUID înainte de `reconcile_database`; acesta fixează jobul `python -I -m omnis.stop_reconcile`, stdin bounded și JOB_PENDING durabil înainte de create/start. `restart:235–249` cere ACK exact, job cleanup și ACKED durabil înainte de `start:1419–1453` Supervisor/API. |
| Receiver/CAS și readback după commit | `stop_reconcile:31–62,85–93`: JSON ≤16KiB, expected system ID, serviciul real; `service:764–884`: schema+system_id, closed generation/epoch/commands, grant exact, insert receipt și delete fence CAS sub lock, readback în aceeași tranzacție și încă un readback după commit. Nu acordă OPEN/lease. Nu am identificat incompatibilitate de format care să facă receiverul inexercitabil. |
| Lost ACK fără resend și fără teardown DB | `restart:142–143` scrie JOB_PENDING înainte de efect; `start:1568–1593` păstrează DB/datele, UNCERTAIN; marker STARTING/journal/intent refuză un nou Start. Testul nou restore/lost și faulturile normale verifică lipsa de evenimente suplimentare. |
| Restart normal păstrat | `prepare_restart:48–66` menține verify_stop_completion, STOPPED, byte readback și intent preexistent refuzat; factorizează doar construcția comună. Guardul queued Start și UNOWNED nu sunt eliminate. |
| Limite | Manifest/set fix, tar/expanded1GiB, deadline și no-overwrite prezente în source. Validarea adversarială completă tar/FD/cleanup/helper este scope R2, nu certificată de R1. |

## Dovezi și limite

- Proba proprie de mai sus: exit0, reproduce exact findingul; test SOURCE cu FS real, nu restore PG/OCI real. Fișierul probei este singurul script privat nou; fixture-ul său temporar este în scratch și este închis de context manager. Niciun bind de socket.
- Logul original `cold-affected-final.log` citit: `Ran 57 tests in 4.315s`, `OK`; nu l-am rerulat și nu îl transform în runtime PASS. Contextul părintelui declară separat quality0 și probe crypto reale cu PG/OCI doubles.
- Codul receiverului este aplicabil SOURCE; restaurare reală fresh PG/OCI, schema/istoric/usage prin cititori reali și lifecycle installed rămân NOT_RUN pentru acest review. Lipsa acestora nu este defect de cod și nu este condiție circulară pentru admiterea QA după remediu/reviewurile obligatorii.
- Canonul `Omnis_MVP_Architecture.md:522` cere și reactivare explicită a conexiunilor după restore. Patchul CLI nu introduce o astfel de tranziție DB; nu am executat consumerul provider/DB ca să stabilesc dacă acordul manual de Test/Save existent satisface acel criteriu. Rămâne criteriu distinct de verificat/adjudecat, nu finding confirmat sau PASS implicit.
- CLI complet rămâne negreen conform contextului: nu atribui toate erorile baseline-ului și nu declar automat un nou defect cold din acel total. Canonical final post-integrare rămâne la părinte. R2 auth/FD/archive/helper cleanup separat; Reticle NOT_APPLICABLE, Chisel BLOCKED_NO_GO.
- Nu am creat/modificat skills, produs, mapă de status ori commituri; review bounded, fără workflow nou de salvat. Rapoartele originale sunt păstrate. Verdictul nu este integrare sau închidere T1.

**Predare:** R1 CHANGES_REQUESTED_SOURCE_SCOPED pentru R1-COLD-01; restul traseului R1 de mai sus fără defect confirmat, cu QA runtime încă NOT_RUN. Părintele reproduce/adjudecă, autorul remediază, apoi re-review focalizat și QA admisă pe bytes înghețați.

Neefectuate: restore PG/OCI/installed real, efecte provider, reviewul R2 și gate-ul canonic complet. Risc restant: proiecție status contradictorie; reactivarea conexiunilor după snapshot trebuie verificată separat înaintea acceptării criteriului canonic.
