"""Finite immutable declared-input universe. No execution, freshness or work grant."""

import base64
from hashlib import sha256

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncConnection

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical
from omnis.modules.tasks import managed_contract as contract
from omnis.modules.tasks import mission_revisions as missions

Data = dict[str, object]
KIND = "coverage-denominator"
REVISION_LIMIT = 64
REFS = {
    "run_ref": "managed-run",
    "context_ref": "contract-input-context",
    "snapshot_ref": "run-snapshot",
    "selection_ref": "execution-selection",
    "mission_ref": "mission",
    "focus_ref": "focus",
    "procedure_ref": "procedure",
    "schema_ref": "schema",
    "inventory_ref": "contract-case-records",
}
FIELDS = set(REFS) | set(
    "version owner_id purpose resolution universe denominator_revision package_refs operations identity_state applicability_state precondition_state reason_codes provenance".split()
)
REASONS = [
    "DECLARED_SYNTHETIC_INPUT_NOT_TARGET_OBSERVATION",
    "IDENTITY_PROOF_UNAVAILABLE",
    "APPLICABILITY_PROOF_UNAVAILABLE",
    "CURRENT_PRECONDITION_PROOF_UNAVAILABLE",
]


async def retained_material(
    conn: AsyncConnection, owner: str, context: Data, graph: list[Data]
) -> tuple[bytes, list[Data], str]:
    """Read qualified retained material; never invoke compiler/PURE/native."""
    from omnis.modules.runs.native_preparation import read_receipt
    from omnis.modules.settings.catalog_models import LocalRef, Manifest, Procedure
    from omnis.modules.settings.catalog_schema import dto
    from omnis.modules.tasks.contract_case_input import require_slots

    # This reader is also reached from ManagedAdmission, outside the CLI's
    # namespace setup. Optional catalog readers must not resolve temp shadows.
    await conn.execute(sql("SET LOCAL search_path = pg_catalog, public, pg_temp"))
    ctx = contract.mapping(context["payload"])
    run = contract.mapping(missions.resolve(graph, ctx["basis_ref"])["payload"])
    preparation_ref = contract.ref(run["preparation_receipt_ref"], "native-preparation-receipt")
    _, receipt = await records.get(conn, owner, preparation_ref)
    prepared = await read_receipt(
        conn, owner, contract.ref(contract.mapping(receipt["payload"])["bundle_ref"])
    )
    bundle = contract.mapping(contract.mapping(prepared["bundle"])["payload"])
    if (
        canonical(prepared["receipt_ref"]) != canonical(preparation_ref)
        or canonical(bundle["selection_ref"]) != canonical(ctx["selection_ref"])
        or canonical(bundle["snapshot_ref"]) != canonical(ctx["snapshot_ref"])
    ):
        raise CatalogError("REF_MISMATCH")
    packages = [contract.mapping(p) for p in contract.sequence(bundle["packages"])]
    documents: dict[str, bytes] = {}
    entity_keys: dict[str, str] = {}
    schema_path = ""
    selected_keys: list[str] = []
    for field, kind in (("procedure_ref", "procedure"), ("schema_ref", "schema")):
        reference = contract.ref(ctx[field], kind)
        row = (
            (
                await conn.execute(
                    sql(
                        "SELECT i.package_key,i.entity_key FROM public.catalog_identity i JOIN public.catalog_reservation r ON r.id=i.id WHERE i.owner_id=:owner AND i.id=:id AND i.entity_kind=:kind AND r.revision=:revision AND r.digest=:digest"
                    ),
                    {**reference, "owner": owner},
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise CatalogError("REF_UNAVAILABLE")
        selected = [p for p in packages if p["package_key"] == row["package_key"]]
        if (
            len(selected) != 1
            or contract.ref(selected[0]["package_ref"], "package")["digest"] != reference["digest"]
        ):
            raise CatalogError("REF_MISMATCH")
        files = {
            contract.text(contract.mapping(f)["path"]): base64.b64decode(
                contract.text(contract.mapping(f)["content_b64"], 16384), validate=True
            )
            for f in contract.sequence(selected[0]["files"])
        }
        manifest = dto(files["omnis.yaml"], Manifest)
        paths = [
            b.path
            for b in manifest.file_bindings
            if b.entity_kind == kind and b.key == row["entity_key"]
        ]
        if kind == "procedure":
            paths = [
                path
                for path in manifest.procedures
                if path in files and dto(files[path], Procedure).key == row["entity_key"]
            ]
        if len(paths) != 1 or paths[0] not in files:
            raise CatalogError("REF_UNAVAILABLE")
        documents[kind] = files[paths[0]]
        entity_keys[kind] = contract.text(row["entity_key"])
        if kind == "schema":
            schema_path = paths[0]
        selected_keys.append(contract.text(row["package_key"]))
    procedure = dto(documents["procedure"], Procedure)
    require_slots(procedure.model_dump(mode="json")["slots"], version=2)
    if (
        procedure.key != "map-records"
        or procedure.key != entity_keys["procedure"]
        or procedure.verification_kind != "CONTRACT"
        or len(set(selected_keys)) != 1
        or not isinstance(procedure.input_schema_ref, LocalRef)
        or procedure.input_schema_ref.entity_kind != "schema"
        or procedure.input_schema_ref.key != entity_keys["schema"]
    ):
        raise CatalogError("DENOMINATOR_UNSUPPORTED")
    return (
        documents["schema"],
        sorted([contract.ref(p["package_ref"], "package") for p in packages], key=canonical),
        schema_path,
    )


async def derive(
    conn: AsyncConnection,
    owner: str,
    graph: list[Data],
    context_ref: object,
    mission_ref: object,
    input_ref: object,
) -> Data:
    from omnis.modules.tasks.contract_case_input import material_section

    missions.validate_graph(graph)
    context = missions.resolve(graph, contract.ref(context_ref, "contract-input-context"))
    ctx = contract.exact(
        context["payload"],
        set(
            "version namespace owner_id basis_ref snapshot_ref procedure_ref schema_ref selection_ref mission_ref focus_ref".split()
        ),
    )
    original = missions.resolve(graph, contract.ref(ctx["mission_ref"], "mission"))
    missions.require_supported(graph, context, original)
    if uuid_string(ctx["owner_id"]) != owner:
        raise CatalogError("REF_UNAVAILABLE")
    run = missions.resolve(graph, contract.ref(ctx["basis_ref"], "managed-run"))
    run_body = contract.mapping(run["payload"])
    for field in ("snapshot_ref", "selection_ref", "mission_ref", "focus_ref"):
        if canonical(contract.ref(ctx[field], REFS[field])) != canonical(
            contract.ref(run_body[field], REFS[field])
        ):
            raise CatalogError("REF_MISMATCH")
    mission = missions.resolve(graph, contract.ref(mission_ref, "mission"))
    if mission["revision"] == 2:
        missions.validate_pair(original, mission)
    elif canonical(records.reference(mission)) != canonical(records.reference(original)):
        raise CatalogError("REF_MISMATCH")
    item = missions.resolve(graph, contract.ref(input_ref, "contract-case-records"))
    raw_schema, packages, schema_path = await retained_material(conn, owner, context, graph)
    # The real input reader validates values/schema/types/full provenance, not selfdigest alone.
    section = material_section(
        context, item, ctx["schema_ref"], raw_schema, schema_path=schema_path
    )
    value = contract.mapping(contract.mapping(section["input"])["payload"])["value"]
    from omnis.modules.tasks.module_registry import Records

    parsed = Records.model_validate_json(canonical(value), strict=True)
    grouped: dict[tuple[str, str], set[int]] = {}
    for row in parsed.records:
        grouped.setdefault((row.path, row.method), set()).add(row.status)
    return {
        "version": 1,
        "owner_id": owner,
        "purpose": "CONTRACT_PROBE",
        "resolution": "NO_MODEL",
        "universe": "DECLARED_CONTRACT_INPUT",
        "run_ref": records.reference(run),
        "context_ref": records.reference(context),
        "mission_ref": records.reference(mission),
        "inventory_ref": records.reference(item),
        **{
            k: ctx[k]
            for k in ("snapshot_ref", "selection_ref", "focus_ref", "procedure_ref", "schema_ref")
        },
        "package_refs": packages,
        "operations": [
            {"method": method, "path": path, "statuses": sorted(statuses)}
            for (path, method), statuses in sorted(grouped.items())
        ],
        "identity_state": "UNKNOWN",
        "applicability_state": "UNKNOWN",
        "precondition_state": "UNKNOWN",
        "reason_codes": list(REASONS),
    }


def payload(value: object) -> Data:
    from omnis.modules.tasks.module_registry import Operations

    body = contract.exact(value, FIELDS)
    contract.integer(body["version"], 1, 1)
    contract.integer(body["denominator_revision"], 1, REVISION_LIMIT)
    uuid_string(body["owner_id"])
    for field, kind in REFS.items():
        contract.ref(body[field], kind)
    for reference in contract.sequence(body["package_refs"]):
        contract.ref(reference, "package")
    Operations.model_validate_json(canonical({"operations": body["operations"]}), strict=True)
    provenance = contract.exact(
        body["provenance"], {"producer_key", "producer_revision", "command_id"}
    )
    uuid_string(provenance["command_id"])
    if (
        body["purpose"] != "CONTRACT_PROBE"
        or body["resolution"] != "NO_MODEL"
        or body["universe"] != "DECLARED_CONTRACT_INPUT"
        or any(
            body[k] != "UNKNOWN"
            for k in ("identity_state", "applicability_state", "precondition_state")
        )
        or body["reason_codes"] != REASONS
        or provenance["producer_key"] != KIND
        or provenance["producer_revision"] != KIND + "-v1"
        or len(canonical(body)) > 32768
    ):
        raise CatalogError("DENOMINATOR_INVALID")
    return body


def material(body: Data) -> Data:
    return {k: v for k, v in body.items() if k not in {"denominator_revision", "provenance"}}


def result_refs(body: Data, item: Data) -> Data:
    return {
        "context_ref": body["context_ref"],
        "mission_ref": body["mission_ref"],
        "input_ref": body["inventory_ref"],
        "denominator_ref": records.reference(item),
    }


def validate_receipt(receipt: object, item: Data, *, command: str) -> None:
    checked = contract.record(receipt, "contract-input-command")
    body = contract.exact(
        checked["payload"],
        set("version owner_id command_id operation request_digest result_refs".split()),
    )
    contract.integer(body["version"], 1, 1)
    uuid_string(body["owner_id"])
    uuid_string(body["command_id"])
    denominator = payload(item["payload"])
    references = contract.exact(
        body["result_refs"], {"context_ref", "mission_ref", "input_ref", "denominator_ref"}
    )
    for key, kind in (
        ("context_ref", "contract-input-context"),
        ("mission_ref", "mission"),
        ("input_ref", "contract-case-records"),
        ("denominator_ref", KIND),
    ):
        contract.ref(references[key], kind)
    request = {
        "schema_version": 1,
        "owner_id": denominator["owner_id"],
        "command_id": command,
        **{k: references[k] for k in ("context_ref", "mission_ref", "input_ref")},
    }
    if (
        body["operation"] != "create-denominator"
        or body["owner_id"] != denominator["owner_id"]
        or body["command_id"] != command
        or body["request_digest"] != sha256(canonical(request)).hexdigest()
        or canonical(references) != canonical(result_refs(denominator, item))
    ):
        raise CatalogError("COMMAND_CONFLICT")


async def validate_graph(conn: AsyncConnection, owner: str, run: str, graph: list[Data]) -> None:
    retained = [contract.record(r, KIND) for r in graph if r["kind"] == KIND]
    revisions: list[int] = []
    materials: set[bytes] = set()
    for item in retained:
        body = payload(item["payload"])
        expected = await derive(
            conn, owner, graph, body["context_ref"], body["mission_ref"], body["inventory_ref"]
        )
        if contract.ref(body["run_ref"])["id"] != run or canonical(material(body)) != canonical(
            expected
        ):
            raise CatalogError("DENOMINATOR_INVALID")
        revisions.append(contract.integer(body["denominator_revision"], 1, REVISION_LIMIT))
        key = canonical(material(body))
        if key in materials:
            raise CatalogError("DENOMINATOR_INVALID")
        materials.add(key)
        command = uuid_string(contract.mapping(body["provenance"])["command_id"])
        receipts = [
            r
            for r in graph
            if r["kind"] == "contract-input-command"
            and contract.mapping(r["payload"]).get("command_id") == command
        ]
        if len(receipts) != 1:
            raise CatalogError("COMMAND_CONFLICT")
        validate_receipt(receipts[0], item, command=command)
    if sorted(revisions) != list(range(1, len(retained) + 1)):
        raise CatalogError("DENOMINATOR_INVALID")
