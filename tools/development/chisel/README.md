# Chisel — NO-GO pentru activare pe repo

Cerere: [ckanthony/Chisel](https://github.com/ckanthony/Chisel/tree/main). Skill-ul de evaluare este disponibil, dar **serverul nu este înregistrat în Hermes și nu are acces la Omnis**. Folosim în continuare uneltele native `read_file`, `search_files`, `patch` și `write_file`.

## Ce s-a verificat efectiv

Parentul a rerulat executabilul real în Bubblewrap, pe fișiere sintetice, cu home-ul hostului absent și rețea numai loopback. [audit.json](audit.json) păstrează fiecare rezultat și identitatea artefactului:

- sursă `b2a7c90cbc1a9f27c546d6f70d7ca564d858930e`;
- release `v0.1.7`, dar binarul/handshake-ul raportează `0.1.6`;
- 53 verificări: 43 trecute, 7 verificări de securitate eșuate, 2 incompatibilități și 1 contradicție de instrucțiuni;
- exit 0 al harnessului înseamnă audit terminat, **nu** acceptare de securitate.

Cele șapte eșecuri sunt verificări ale patru clase de probleme, nu șapte vulnerabilități independente: ocolirea root confinement prin argumente/path-uri de shell, subprocess permis printr-un utilitar din whitelist, mutații de shell în read-only și o limită HTTP configurată de 128 bytes care nu a refuzat cererea de 183 bytes. Nu generalizăm ultima probă într-o afirmație că orice corp este nelimitat.

Probele de fișiere/patch și autentificare HTTP au funcționat, dar nu repară garanțiile infirmate. Whitelist-ul nu permite `rg`/`npm` din exemple. Nu s-au testat compilarea din sursă, Docker, WASM sau runtime-ul aplicației Omnis.

## Licență și distribuire

Manifestul bundle declară MIT, însă checkoutul auditat nu conține text LICENSE/COPYING/NOTICE și manifestele Cargo nu indică licența. Nu redistribuim binarul sau codul și nu considerăm declarația drept verificare juridică completă. Clarificarea upstream este necesară înainte de includerea într-o distribuție.

## Criterii de reevaluare

1. Revizie fixată cu licență clarificată; analiză a diff-ului, artefactului și dependențelor.
2. Eliminarea/corectarea `shell_exec` sau broker strict separat; OS-level izolarea filesystem/rețea și limite de timp/output rămân necesare. `--root` și `--read-only` nu sunt suficiente.
3. Teste cu read-only impus de mount, root/symlink/subprocess, auth și body cap; eșecurile de infrastructură nu devin protecții demonstrate.
4. Doar fixture/worktree dispensabil, fără secrete, înainte de orice configurație MCP. Inventarierea uneltelor și schemas din runtime, nu din README.
5. Decizie explicită înainte de activare. Fără fallback nesandboxat sau modificare automată a profilului.

Raportul și rezultatele sunt un gate de adopție, nu o copie concurentă a arhitecturii Omnis. Auditul original reproductibil rămâne în locația locală consemnată în JSON; dovezile esențiale de aici nu depind de păstrarea cache-ului scratch.
