# APPROVED_DISTRIBUTION_SCOPED — distribuție normală T1

Artefact: `/home/kali/.hermes/cache/scratch/ot1-final-l9s2t70o/artifacts/bundle-t1-candidate`.
release.json SHA256: `36ab4ad267e048ad4d5598a5a336c19d32f9d43647c131440ab7650d31a92c54`.
SOURCE: fd1459b2edd0fa4f6cb895f964ff0d027f5b9dce / tree18799fcb8dac08697e8eac61e30607c249c5c2fb, worktree curat.

Cerință → consumer → risc → decizie: bundle offline/image/CLI backup/restore cu modulele/pinurile/assets/schema curente → parser real din wheel CLI + callerii instalării/reconcile → lipsă/stale/suplimentar/native implicit → admitere exclusiv la QA pe artefactul exact.

Constatări blocante: niciuna în scope.

## Verificări reale
10 payloaduri SHA; parserul _manifest importat din wheel distribuit; seturile complete113API/26CLI și toate bytes egale cu sursa tracked/binding; RECORD complet și toate lungimile/hash-urile; resurse și metadata; schema0015 și codul restore-mode/backup/wiring prezente. requirements pin/hash în api/uv.lock și export byte-equal cu logul locked: OpenAI2.24.0/cryptography50.0.1, fără runtime Hermes/Codex. Web manifest închis/hash-valid, index closure și bytes egale cu buildul integration-src/web/dist, inclusiv OFL. Dockerfile/compose byte-equal sursei: imagini digest-pinned, --require-hashes, --no-deps, USER65532, UID/GID explicit, API/supervisor read_only, cap_drop ALL/no-new-privileges/control intern. DB secrets sunt referințe externe, nu secrete incluse; fără fișiere CA/sitecustomize/chei/native suplimentare. Callerii și attestorul restore/UID/read-only sunt inspectați static, nu executați. SourceBuild nu a fost atestat separat; comparația Dockerfile/compose și sursa exactă nu reprezintă probă de build/rulare a imaginii. Readerii/modulele istorice păstrate byte-exact; nicio revendicare native execution sau acoperire SDK universală.

Citite logurile curente API/CLI/export-locked/bundle2: builds reale și BUNDLE_READY. Nu transfer PASS vechiului bundle3077.

## Limite / procedură
Comenzi: git status/rev-parse/diff; Python -B stdlib ZIP/hash/CSV/tomllib și parserul real. Verificarea finală a produs rezultatele de mai jos. Trei tentative anterioare au ieșit1 pe ipoteze ale probei: directoare ZIP incluse eronat în RECORD, apoi ordine/spații ale intervalului Requires-Python. Diagnosticarea a păstrat aceleași clauze semantice și toate fișierele RECORD, fără schimbare de produs/input/gate. Bugetul de apeluri a fost depășit pentru diagnostic și raport; nu este defect al produsului.

Aprob numai integritatea distribuției și admiterea la instalare/QA. Installed PASS/imagine construită ori rulată/restore fizic/restart/crash/browser/provider: NOT_RUN de reviewer; T1 NOT_CLOSED. Restore fizic lipsă nu este prerequisite circular al reviewului. Canonical global rămâne FAIL în contextul delegat, fără transfer din alte teste sau schimbările test-only altui autor. Reticle NOT_APPLICABLE; Chisel BLOCKED_NO_GO.

Nicio instalare/build/Docker/PG/browser/provider/credentiale/profiluri private/servicii/Git write. HTML untracked protejat necitit/neatins. Numai raportul prezent scris. Părintele adjudecă, verifică handle-ul și folosește exact bundle-ul normal.

## Rezultate calculate
```json
{
  "actual_bundled_CLI_manifest_parser": "PASS: exact sealed shape/files/checksums, profile t1-provider-settings, schema0015, no-native format3",
  "api": {
    "modules": 113,
    "RECORD_files_verified": 116,
    "nonmodule_files": [
      "omnis_api-0.1.0.dist-info/METADATA",
      "omnis_api-0.1.0.dist-info/RECORD",
      "omnis_api-0.1.0.dist-info/WHEEL"
    ],
    "requires_python": ">=3.13.15, <3.14",
    "requires_dist": [
      "alembic==1.20.0",
      "cryptography==50.0.1",
      "fastapi==0.141.1",
      "greenlet==3.5.6",
      "httpcore==1.0.9",
      "httpx==0.28.1",
      "openai==2.24.0",
      "jsonschema==4.26.0",
      "psycopg[binary]==3.3.6",
      "pydantic==2.13.5",
      "pyyaml==6.0.3",
      "sqlalchemy==2.0.54",
      "uvicorn==0.54.0"
    ]
  },
  "cli": {
    "modules": 26,
    "RECORD_files_verified": 30,
    "nonmodule_files": [
      "omnis_cli-0.1.0.dist-info/METADATA",
      "omnis_cli-0.1.0.dist-info/RECORD",
      "omnis_cli-0.1.0.dist-info/WHEEL",
      "omnis_cli-0.1.0.dist-info/entry_points.txt"
    ],
    "requires_python": ">=3.13.15, <3.14",
    "requires_dist": []
  },
  "locked_requirements": 39,
  "web_manifest_assets_verified": 4
}
```

## Calleri inspectați static
```text
cli/src/omnis_cli/release.py
148:                    not in wheel.read(f"omnis_api-{_RELEASE}.dist-info/METADATA")
149:                    for dependency in (
150:                        "cryptography==50.0.1",
151:                        "openai==2.24.0",
152:                        "httpx==0.28.1",
153:                        "httpcore==1.0.9",
154:                    )
155:                ):
cli/src/omnis_cli/restart.py
196:        "-m",
197:        "omnis.stop_reconcile",
198:        *(("--restore",) if restoring else ()),
199:        env={
200:            "OMNIS_DATABASE_URL": env["OMNIS_DATABASE_URL"],
201:            "OMNIS_EXPECTED_SYSTEM_ID": str(payload["system_identifier"]),
202:        },
cli/src/omnis_cli/start_runtime.py
585:        }[role]
586:        if restore:
587:            expected_command.append("--restore")
588:        state = mapping(item.get("State"))
589:        networks = mapping(net.get("Networks"))
590:        network_name = "none" if role == "runtime" else self.receipt.project + "_control"
591:        image_id = (
683:        if role != "db" and (
684:            config.get("User") != f"{os.getuid()}:{os.getgid()}"
685:            or host.get("ReadonlyRootfs") is not True
686:            or host.get("CapDrop") != ["ALL"]
687:            or host.get("SecurityOpt") != ["no-new-privileges:true"]
688:        ):
689:            raise StartError("CONTROL_CONFINEMENT_MISMATCH", 3)
697:            not isinstance(image_config.get("User"), str)
698:            or config.get("User") != image_config["User"]
699:            or host.get("ReadonlyRootfs") is not False
700:            or host.get("CapDrop") not in (None, [])
701:            or host.get("SecurityOpt") not in (None, [])
702:        ):
703:            raise StartError("DATABASE_CONFINEMENT_MISMATCH", 3)
```
