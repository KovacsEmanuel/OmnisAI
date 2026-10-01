# SL02 — execuția remedierii auditului aprofundat

Bază reală: `9dd45ea31370c0e35fe79fa62431fce45c13d0f7`, branch `p04-control-topology-wip`. Munca preexistentă: numai `documents/Omnis_Notite_Originale.html` untracked/protejat; AGENTS neatins. Fără push, SL03/SL04, owner WIP, upgrade global sau recuperare DB incertă. Gate-urile existente nu se slăbesc.

## Contract RT-F01 / RT-M01

Cerință: orice ieșire după spawn păstrează handle-ul forwarderului pentru cleanup, inclusiv finalizarea logului/stdout și handofful. Pozitiv: forwarder real verificat, oprit/reaped și listener absent înainte rescue. Negativ: lipsa pidfd ori cleanup nereconciliat produce UNCERTAIN și păstrează DB/locatorul; niciodată FAILED_CLEANED cu listener viu.

Fișiere: `cli/src/omnis_cli/start.py`, `cli/tests/test_forwarder_handoff.py`, test de integrare a callerului dacă necesar. Efecte permise: copii forwarder proprii, socketuri loopback/UDS private în scratch; Docker/DB substituite în regresii, etichetate explicit. Fără semnale pe PID-uri din metadate. Test: `cli/.venv/bin/python -I -m unittest discover -s cli/tests -p test_forwarder_handoff.py -v`, apoi controale caller/cleanup și suita CLI. Rollback: revert commit remediu + rebuild/retest; Git nu recuperează DB.

Model ownership: callerul deține un holder înainte de spawn; publicarea procesului/pidfd precedă toate close/finally și rămâne accesibilă la excepții. Semnalele de stop ale frontierei CLI sunt amânate, nu ignorate, numai peste spawn/publicarea handle-urilor; după publicare stopul intră în cleanup. Nu se presupune că tuple return sau returncode=None constituie handoff atomic. Nu se normalizează politica de semnale a unui caller de bibliotecă.

## Inventar și readback inițial

`make test-cli`: exit 0 pe baseline; log scratch `omnis-remediation-baseline-cli.log`. Python din venvurile API/CLI este 3.13.15; uv verificat 0.12.19 și Node 24.21.0 în toolchainul scratch istoric. Python global 3.13.12 nu este folosit drept pin de produs. Docker 27.5.1 și Compose 2.32.4 disponibile; topologia UDS/fără porturi publicate se păstrează.

RECOVERY_PENDING: receiptul vechi `/home/kali/.hermes/cache/scratch/s2i-841796q5/probe-receipt.json` există și declară UNCERTAIN. Readback Docker exact CID `7bc89950a39362bd13b8909887f02cc2434b28666ae863a94aa72a253e6af8f0`: running/healthy, proiect `omnis-local-bc4dc709912d4f119cd271e70fcba384`, attempt `f8e93e10-1c04-4c2d-a43b-f6ad3167fd51`, bind PG18 în state rootul vechi. Identitatea neschimbată nu dovedește drenarea familiei/daemonului. Fără mutații/stop/adopție/rescue; recuperarea rămâne separată BLOCKED/RECOVERY_PENDING, nu ALL_CLEAN.

## Registru obligatoriu

RT-F01, RT-F02, AR01, AR02, RT-PG01, AR03, RT-M01, M03, M09, M18, M20, M21, M22 și RECOVERY_PENDING sunt urmărite separat. Stare inițială: ÎN LUCRU, fără PASS nou. Matricea celor 26 și verdictele finale se vor completa numai după execuții și review adjudecat.
