"""Synthetic inspect shapes, NOT captures or metadata claims about pinned OCI blobs."""

import os

from omnis_cli.start_runtime import POSTGRES

ROLES = ("db", "api", "supervisor", "migrate", "reconcile")


def image_item(runtime, role):
    db = role == "db"
    native = role == "runtime"
    return {
        "Id": runtime.pg_image
        if db
        else runtime.receipt.runtime_image_id
        if native
        else runtime.receipt.image_id,
        "Os": "linux",
        "Architecture": "amd64",
        "RepoDigests": [POSTGRES.replace(":18.6-bookworm", "")] if db else [],
        "Config": {
            "User": "" if db else "65532:65532",
            "Entrypoint": ["docker-entrypoint.sh"] if db else None,
            "Env": ["PATH=/synthetic/image/bin", "LANG=synthetic.UTF-8"]
            + (
                ["PGDATA=/var/lib/postgresql/18/docker"]
                if db
                else ["OMNIS_WEB_ROOT=/opt/omnis/web"]
            ),
        },
    }


def container_item(runtime, role, cid, root, control, port, state="running"):
    db = role == "db"
    image = image_item(runtime, role)
    env = dict(v.split("=", 1) for v in image["Config"]["Env"])
    if db:
        env.update(
            POSTGRES_USER="omnis",
            POSTGRES_DB="omnis",
            POSTGRES_PASSWORD_FILE="/run/secrets/db_password",
            POSTGRES_INITDB_ARGS="--auth-host=scram-sha-256",
        )
    elif role == "runtime":
        env["OMNIS_RUNTIME_DIR"] = "/runtime"
    else:
        env["OMNIS_DATABASE_URL"] = "postgresql+psycopg://omnis:" + "a" * 48 + "@db:5432/omnis"
        if role in {"migrate", "reconcile"}:
            env["OMNIS_EXPECTED_SYSTEM_ID"] = "12345"
        else:
            env["OMNIS_CONTROL_DIR"] = "/run/omnis-control"
        if role == "api":
            env.update(OMNIS_HTTP_DIR="/run/omnis-http", OMNIS_HTTP_PORT=str(port))
    if role == "supervisor" and getattr(runtime.receipt, "profile", None):
        env["OMNIS_RUNTIME_DIR"] = "/runtime"
        if getattr(runtime, "model_test", False) is True:
            env.update(
                OMNIS_NATIVE_PREPARATION_CATALOG_ROOT="/catalog",
                OMNIS_MANAGED_TASKS="1",
                OMNIS_MODEL_TEST_SOURCE_ROOT="/opt/omnis/model-test",
            )
    mounts = []
    if db:
        mounts = [
            (str(root / "postgres"), "/var/lib/postgresql", True),
            (str(root / "db-password"), "/run/secrets/db_password", False),
        ]
    elif role in {"api", "supervisor"}:
        mounts = [(str(control), "/run/omnis-control", role == "supervisor")]
        if role == "api":
            mounts.append((str(root / "http"), "/run/omnis-http", True))
        elif getattr(runtime.receipt, "profile", None):
            mounts.append((str(root / "native-ipc"), "/runtime", True))
            if getattr(runtime, "model_test", False) is True:
                mounts.append((str(root / "catalog"), "/catalog", True))
    elif role == "runtime":
        mounts = [
            (str(root / "native-ipc"), "/runtime", True),
            (str(root / "provider"), "/state/provider", True),
        ]
        if getattr(runtime, "model_test", False) is True:
            mounts.append((str(root / "native-ipc"), "/state/tmp", True))
    name = runtime.receipt.project + "-" + role + ("-1" if role in ROLES[:3] else "")
    return {
        "Id": cid,
        "Name": "/" + name,
        "Image": image["Id"],
        "Config": {
            "Cmd": {
                "runtime": ["/opt/hermes/venv/bin/python", "-I", "-m", "omnis_hermes.runtime_host"],
                "db": ["postgres"],
                "api": ["python", "-I", "-m", "omnis.serve"],
                "supervisor": ["python", "-I", "-m", "omnis.supervisor"],
                "migrate": ["python", "-I", "-m", "omnis.migrate", "--initialize"],
                "reconcile": ["python", "-I", "-m", "omnis.stop_reconcile"],
            }[role],
            "Entrypoint": image["Config"]["Entrypoint"],
            "User": "" if db else f"{os.getuid()}:{os.getgid()}",
            "Env": [f"{k}={v}" for k, v in env.items()],
            "Labels": {
                "com.docker.compose.project": runtime.receipt.project,
                "com.docker.compose.service": role,
                "org.omnis.start-attempt": runtime.attempt,
            },
            "Volumes": None,
            "Tty": False,
            **dict.fromkeys(
                ("OpenStdin", "StdinOnce", "AttachStdin", "AttachStdout", "AttachStderr"),
                role == "reconcile",
            ),
        },
        "HostConfig": {
            "Privileged": False,
            "PublishAllPorts": False,
            "PortBindings": {},
            "NetworkMode": "none" if role == "runtime" else runtime.receipt.project + "_control",
            "PidMode": "",
            "IpcMode": "private",
            "CapAdd": None,
            "Devices": [],
            "DeviceRequests": None,
            "DeviceCgroupRules": None,
            "ReadonlyRootfs": not db,
            "CapDrop": None if db else ["ALL"],
            "SecurityOpt": None if db else ["no-new-privileges:true"],
            "Tmpfs": None,
            "RestartPolicy": {"Name": "no", "MaximumRetryCount": 0},
        },
        "NetworkSettings": {
            "Ports": {"5432/tcp": None} if db else {},
            "Networks": {"none": {"NetworkID": "2" * 64}}
            if role == "runtime"
            else {
                runtime.receipt.project + "_control": {
                    "NetworkID": "1" * 64,
                    "Aliases": [name, role] if role in ROLES[:3] else None,
                    "DNSNames": [name, cid[:12]],
                    "DriverOpts": None,
                    "IPAMConfig": None,
                    "Links": None,
                }
            },
        },
        "State": {"Running": state == "running", "Status": state},
        "Mounts": [
            {"Type": "bind", "Source": src, "Destination": dst, "RW": rw, "Propagation": "rprivate"}
            for src, dst, rw in mounts
        ],
    }
