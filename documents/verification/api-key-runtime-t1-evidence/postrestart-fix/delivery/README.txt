OMNIS T1 — instalare normală reparată, date separate

Root: /home/kali/.local/share/omnis-t1-fixed-a5b8939
Origin: http://127.0.0.1:8773/settings/providers
Instance: e10da359-a48f-40f3-ad2f-7641a3f6bb83
Bundle SHA256: a5b89393716f31868e97d7f5201249ab1de76f6395300cecc5d657890e34dba4
Sursă: 5d5bbfb35b3833ef6d8be0f2e2651cf235a515a2 (tree identic 8c527a0)
Profil t1-provider-settings / schema0015_model_test_v2.
Install, install-image, port preflight, Start și status: exit0; READY1/epoch1.

Folosește aceleași roots pentru FIECARE comandă:

env -i \
 HOME=/home/kali/.local/share/omnis-t1-fixed-a5b8939/h \
 XDG_CONFIG_HOME=/home/kali/.local/share/omnis-t1-fixed-a5b8939/c \
 XDG_DATA_HOME=/home/kali/.local/share/omnis-t1-fixed-a5b8939/d \
 XDG_STATE_HOME=/home/kali/.local/share/omnis-t1-fixed-a5b8939/s \
 XDG_RUNTIME_DIR=/home/kali/.local/share/omnis-t1-fixed-a5b8939/r \
 PATH=/home/kali/.local/share/omnis-t1-fixed-a5b8939/cli/bin:/usr/bin:/bin \
 TMPDIR=/home/kali/.hermes/cache/scratch \
 PYTHONDONTWRITEBYTECODE=1 \
 /bin/bash --noprofile --norc

În terminalul izolat:
  omnis status --json
  omnis start --no-open --json    # numai pornire explicită necesară
  omnis stop --json              # oprire normală, date păstrate
  omnis pair                     # numai când este necesar și operatorul este pregătit

Pair: TTY-only, codul numai în terminal/formular, nu chat/log. QTerminal:
selectează numai codul, Ctrl+Shift+C, apoi Ctrl+V în formular. Chrome folosește
profilul dedicat root/browser, nu profil personal sau al instalațiilor vechi.
Cheia se introduce numai write-only în UI de operator. Save model selection
este explicit pe revizia curentă. Refresh/Test/provider/fault cer acord finit
legat de această nouă instanță; nu sunt autorizate automat prin instalare.

omnis recover --json este numai pentru recuperarea explicit autorizată în
precondițiile sale reale. Succesul este STOPPED, nu READY/autoresume. Nu există
force, hotpatch, SQL de restaurare sau retry automat după UNKNOWN.

Vechea instalare /home/kali/.local/share/omnis-t1-recovery-d340a58 a fost găsită
UNAVAILABLE după schimbarea boot ID: toate trei containerele exited255,
forwarder absent, restart_policy=no, port liber. Nu s-a emis Stop/recover pe ea
și nu este declarată STOPPED certificat. Toate containerele/rețeaua/fișierele,
DB/seiful/cheia și rezultatele ei sunt păstrate, fără adopție sau copiere aici.
Celelalte instanțe sunt neatinse. Nu porni două roots pe port8773 simultan.
Rollback operațional: Stop normal numai pentru noua instanță; păstrează toate
rooturile. Vechea instanță nu este repornită sau declarată reparată automat.

Probe existente: două reviewuri SOURCE,57teste/regresii și QA instalată a
primei admiteri după restart; Canonical11 exit0/drained/1953inputs fărădrift.
Provider live pe această nouă instanță este încă NOT_RUN. T1 PARTIAL/NOT_ACCEPTED;
restanțele active Stop, crash-SENT/no-resend și revoke nu se închid prin READY.
Nu T2 automat. Bugetul anterior1Refresh/4Start și UNKNOWN sunt păstrate separat.
Registry unic: /home/kali/OmnisAI/documents/verification/api-key-runtime-t1.md
Dovezi instalare: evidence/. Date private: s/omnis. Fără cleanup global/prune.
