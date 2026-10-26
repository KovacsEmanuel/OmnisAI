OMNIS T1 — instalare durabilă cu recuperare explicită

Root: /home/kali/.local/share/omnis-t1-recovery-d340a58
Origin: http://127.0.0.1:8773/settings/providers
Instance: 62b43306-2bca-4e2f-a56e-3b4df790c6cb
Release SHA256: d340a58a8e9912304613086f644b4f9c5f32aac50e4bd3ce8aa3b7c9d9bae177
Profil: t1-provider-settings; schema0015_model_test_v2.
Ultima pornire verificată: READY generation1 / supervisor_epoch1, exit0.
CLI, bundle și release instalat sunt durabile, în afara scratch-ului.

Instalarea anterioară omnis-t1-ready-33ee99 și datele ei sunt păstrate separat;
nu au fost actualizate, adoptate, mutate sau copiate aici. Cheia și selecția veche
nu sunt configurație implicită a acestei instanțe. Agentul nu a introdus chei,
nu a făcut Refresh/Test și nu are acord pentru apeluri provider suplimentare.

Terminal izolat — folosiți ACELEAȘI roots pentru toate comenzile:

env -i \
 HOME=/home/kali/.local/share/omnis-t1-recovery-d340a58/h \
 XDG_CONFIG_HOME=/home/kali/.local/share/omnis-t1-recovery-d340a58/c \
 XDG_DATA_HOME=/home/kali/.local/share/omnis-t1-recovery-d340a58/d \
 XDG_STATE_HOME=/home/kali/.local/share/omnis-t1-recovery-d340a58/s \
 XDG_RUNTIME_DIR=/home/kali/.local/share/omnis-t1-recovery-d340a58/r \
 PATH=/home/kali/.local/share/omnis-t1-recovery-d340a58/cli/bin:/usr/bin:/bin \
 TMPDIR=/home/kali/.hermes/cache/scratch \
 PYTHONDONTWRITEBYTECODE=1 \
 /bin/bash --noprofile --norc

În acel terminal:
  omnis status --json
  omnis start --no-open --json    # numai când este necesară pornirea explicită
  omnis pair                     # numai dacă nu există sesiune/cod valabil
  omnis stop --json              # oprire normală, cu date păstrate

Pair este TTY-only. Codul rămâne numai în terminal/formular, nu chat sau log.
Folosiți QTerminal, selectați doar codul și Ctrl+Shift+C → Ctrl+V în formular.
Pentru instanțe pe porturi diferite, folosiți contexte browser separate pentru
cookie-uri; nu înlocuiți tacit sesiunea browserului vechii instanțe.

Recuperare după crash, NUMAI în scope-ul documentat și cu acord explicit:
  omnis recover --json
Succesul este STOPPED verificat, nu READY. Start rămâne ulterior explicit.
Comanda refuză instanța sănătoasă, ownerul/IPC-ul încă activ, identități străine,
Stop/emergency/recuperare incertă. Nu există --force sau retry automat. La exit4,
păstrați datele/jurnalele și diagnosticul; nu modificați receipturile manual.

Setările cheii se fac exclusiv write-only în UI. Save este local, fără provider IO.
Save model selection trebuie făcut explicit pe conexiunea/revizia curentă.
Modelul folosit în instalarea veche a fost deepseek/deepseek-v4.1-flash-1017,
output128, fără override-uri; aceasta NU este selecție salvată sau acord nou aici.
Refresh metadata și orice Test model/fault nou cer acord finit separat.

Verificat: două reviewuri complementare pe cod, remediu IPC, QA normală fără chei
cu un singur SIGKILL→recover→Stop/Start/Stop; canonical10 pe083e6f6 exit0/drained,
1953inputs identice. Erorile istorice QA/canonical9 sunt păstrate în registrul T1.
Neprobat încă pe frontiera finală: active provider Cancel/Stop/revoke/reuse,
pending-SENT/no-resend și R2-NEW-01 final. T1 PARTIAL/NOT_ACCEPTED, fără T2 automat.
Registre: /home/kali/OmnisAI/documents/verification/api-key-runtime-t1.md
Date private: s/omnis. Evidence operațională: evidence/. Fără prune sau ștergere.
