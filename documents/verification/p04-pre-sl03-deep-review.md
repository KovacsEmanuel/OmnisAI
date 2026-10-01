# P0.4 / SL02 — audit aprofundat înainte de continuare

## Contract și snapshot inițial

Cererea operatorului: verificare mai profundă a implementării, gap-urilor și calității codului înainte de continuare, cu evaluarea explicită Reticle/Chisel în fiecare review. **Audit în curs, nu verdict nou de acceptare.** Bază `b7cc556752bce03d0591655b176f590d85ee41b4`, branch `p04-control-topology-wip`, produs `b8217cb`. Tracked/index curate; numai `documents/Omnis_Notite_Originale.html` untracked/protejat. Nu se schimbă AGENTS.

Autoritate: plan §4.2/§5/§19.2, arhitectură §4.1–4.5, [registrul SC01/SC02](p04-start-remediation.md) și [harta](implementation-status.md). **Nu confundăm:** SL02 are acceptare delimitată; G00 cere inclusiv livrabilele SL03/SL04 și nu este o precondiție circulară pentru a începe SL03. Auditul poate găsi un blocker nou; acesta cere reproducer și adjudecare, nu simpla redenumire a unui PARTIAL ca bug sau a unui PASS vechi ca PASS nou.

### Direcții și criterii de închidere a auditului

1. Review independent adversarial pe lifecycle/ownership/procese/semnale/reap/incertitudine/cleanup, cu probe safe pe copii locali proprii. Separăm efectele daemon substituite de real Docker; nicio oprire a DB incerte sau a resurselor operatorului.
2. Review independent al celor șase PARTIAL M03/M09/M18/M20/M21/M22 și al calității codului/contractelor. Pentru fiecare: defect confirmat, probă absentă, scope ulterior sau datorie de mentenanță; owner/gate și test de închidere, dacă blochează SL03 ori numai G00.
3. Părintele verifică actualitatea dovezilor și reproduce constatările importante; inspectează uneltele și readbackul operațional. Nicio afirmație universală «nu există buguri». Repetarea unor smoke-uri nu dovedește exhaustivitatea produsului.
4. Livrare: concluzii adjudecate, matrice de pași prioritizați legată de planul existent, comenzi/exit/limite reale, skill de review actualizat cu cerința operatorului și commituri locale separate. Fără push sau implementare SL03/SL04.

### Perimetru și efecte

Produsul rămâne read-only în această analiză. Probe/scripts numai în `/home/kali/.hermes/cache/scratch/omnis-deep-readiness/`, cu deadline și cleanup propriu. Fișierele versionate permise: acest registru, procedura locală `omnis-review-qa` și numai proiecțiile de status afectate de constatări confirmate. Nu refactor general, gate slăbit, DB/owner harness nou, instalări globale, conturi/LLM/provider/ținte sau modificate profile personale. Orice remediere de produs rezultată va avea contract și RED→GREEN separat, nu va fi confundată cu această cercetare.

Reticle este instrument de observație UI, nu reviewer de cod; Chisel este adaptor de fișiere, nu agent care emite o opinie. Reviewurile trebuie să numească pentru ambele `EXECUTED`/`NOT_APPLICABLE`/`BLOCKED` și motivul. Reticle poate rula numai fixture-ul inert admis până la instrumentare dev-only a aplicației. Chisel rămâne NO-GO pe repo; reevaluarea ar cere artefact pin-uit și fixture OS-izolat fără home/secrete. Nu se fabrică perspective sau verdict din disponibilitatea unui tool.

Readback inițial read-only: DB incertă `7bc89950a39362bd13b8909887f02cc2434b28666ae863a94aa72a253e6af8f0` este running, proiect `omnis-local-bc4dc709912d4f119cd271e70fcba384`, attempt `f8e93e10-1c04-4c2d-a43b-f6ad3167fd51`, conform locatorului anterior. Nu este adoptată ca DB de test și nu se recuperează prin semnalizarea PID-urilor numerice. Recuperarea necesită o probă/decizie proprie, nu un PASS nou pe alt proiect.

Rollback documentar: revert al fiecărui commit coerent după verificarea dependențelor. Auditul nu inversează și nu modifică datele/serviciile externe; resursele/probele proprii trebuie citite înapoi separat.
