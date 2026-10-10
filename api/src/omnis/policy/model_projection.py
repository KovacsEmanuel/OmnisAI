"""ModelProjection v1: trusted synthetic classification, never model authority.

No provider/native imports, I/O, logs or universal DLP. The caller supplies an
immutable approval out of band; deriving it from model/source data is forbidden.
"""

from dataclasses import dataclass, field
from hashlib import sha256

from omnis.modules.settings import candidate_store as records
from omnis.modules.settings.candidate_catalog import uuid_string
from omnis.modules.settings.catalog_models import CatalogError
from omnis.modules.settings.catalog_schema import canonical, load_json
from omnis.modules.tasks.managed_contract import mapping, ref, sequence, text

POLICY = {
    "version": 1,
    "source_kind": "SYNTHETIC",
    "max_model_input_bytes": 32768,
    "max_text_bytes": 8192,
    "max_records": 128,
    "screenshot": "OFF",
    "path": "/[redacted]",
    "raw_capture": "DENY",
    "unclassified": "DENY",
    "known_secret": "DENY",
    "parameters": "DENY",
    "request_fields": ["messages", "tools"],
}
POLICY_DIGEST = sha256(canonical(POLICY)).hexdigest()


def reject() -> CatalogError:
    return CatalogError("MODEL_PROJECTION_REJECTED")


@dataclass(frozen=True)
class SyntheticApproval:
    """Trusted backend-only pins, not a JSON request or a self-approved DTO.

    composition_ref is canonical bytes to prevent mutable-ref substitution.
    Approved digests classify exact emitted text, not arbitrary raw containers.
    Known secrets stay private; refusing an entire request eliminates them from
    outbound, rather than rewriting mandatory instructions or signed records.
    """

    owner_id: str
    run_id: str
    composition_ref: bytes
    approved_text_digests: frozenset[str]
    known_secrets: tuple[str, ...] = field(repr=False)

    def __post_init__(self) -> None:
        uuid_string(self.owner_id)
        uuid_string(self.run_id)
        if type(self.composition_ref) is not bytes or len(self.composition_ref) > 256:
            raise reject()
        reference = ref(load_json(self.composition_ref), "prompt-composition")
        if canonical(reference) != self.composition_ref:
            raise reject()
        if (
            type(self.approved_text_digests) is not frozenset
            or not 0 <= len(self.approved_text_digests) <= 512
        ):
            raise reject()
        for digest in self.approved_text_digests:
            if (
                type(digest) is not str
                or len(digest) != 64
                or any(c not in "0123456789abcdef" for c in digest)
            ):
                raise reject()
        if type(self.known_secrets) is not tuple or len(self.known_secrets) > 128:
            raise reject()
        for secret in self.known_secrets:
            text(secret, 8192)

    @property
    def digest(self) -> str:
        # Never persist/log secret values or their fingerprints.
        return sha256(
            canonical(
                {
                    "policy_digest": POLICY_DIGEST,
                    "owner_id": self.owner_id,
                    "run_id": self.run_id,
                    "composition_ref": load_json(self.composition_ref),
                    "approved_text_digests": sorted(self.approved_text_digests),
                }
            )
        ).hexdigest()

    def classified(self, value: object) -> str:
        result = text(value, 8192)
        if len(result.encode()) > 8192 or any(s in result for s in self.known_secrets):
            raise reject()
        if sha256(result.encode()).hexdigest() not in self.approved_text_digests:
            raise reject()
        return result


def projection_input(
    composition: dict[str, object], approval: SyntheticApproval
) -> dict[str, object]:
    """Called only after the actual composer has validated all source sections."""
    try:
        if type(approval) is not SyntheticApproval or canonical(records.reference(composition)) != (
            approval.composition_ref
        ):
            raise reject()
        sections = [
            mapping(s)
            for s in sequence(load_json(text(mapping(composition["payload"])["text"], 65536)))
        ]
        base, role, brief, bound = [mapping(s["record"]) for s in sections[:4]]
        body = mapping(brief["payload"])
        header = mapping(body["header"])
        if header["run_id"] != approval.run_id or body["identities"] != []:
            raise reject()
        procedure = mapping(mapping(bound["payload"])["resolved_procedure"])
        instructions: list[dict[str, object]] = [
            {
                "source_ref": records.reference(base),
                "kind": "base",
                "text": approval.classified(mapping(base["payload"])["text"]),
            },
            {
                "source_ref": records.reference(role),
                "kind": "role",
                "text": approval.classified(mapping(role["payload"])["text"]),
            },
        ]
        has_input = sections[4].get("section") == "case-input"
        input_ref: object = None
        projected_records: list[dict[str, object]] = []
        if has_input:
            section = sections[4]
            if section["version"] != 2:
                # Raw capture is not a classified fragment. Cold capture unchanged.
                raise reject()
            context = mapping(mapping(section["context"])["payload"])
            if context["owner_id"] != approval.owner_id or context["namespace"] != "RUN":
                raise reject()
            item = mapping(section["input"])
            input_ref = records.reference(item)
            values = sequence(mapping(mapping(item["payload"])["value"])["records"])
            for index, raw in enumerate(values):
                value = mapping(raw)
                projected_records.append(
                    {
                        "index": index,
                        "method": value["method"],
                        "path": "/[redacted]",
                        "status": value["status"],
                    }
                )
        for skill in sections[5 if has_input else 4 :]:
            for raw in sequence(skill["content"]):
                value = mapping(raw)
                instructions.append(
                    {
                        "source_ref": ref(skill["package_ref"], "package"),
                        "kind": "skill",
                        "text": approval.classified(value["text"]),
                    }
                )
        requirements = []
        for raw in sequence(procedure["method_requirements"]):
            value = mapping(raw)
            requirements.append(
                {
                    "key": approval.classified(value["key"]),
                    "description": approval.classified(value["description"]),
                    "required": value["required"],
                    "step_ids": [approval.classified(s) for s in sequence(value["step_ids"])],
                }
            )
        steps = []
        for group in ("baseline", "probe", "control", "cleanup"):
            for raw in sequence(procedure[group]):
                step = mapping(raw)
                if step["parameters"] != {}:
                    raise reject()
                # Typed bindings are validated by the cold assignment contract;
                # no arbitrary parameter/selector/code or output bytes are copied.
                steps.append(
                    {
                        "id": approval.classified(step["id"]),
                        "action_definition_ref": step["action_definition_ref"],
                    }
                )
        system = {
            "instructions": instructions,
            "method": {
                "source_ref": records.reference(bound),
                "objective": approval.classified(procedure["objective"]),
                "requirements": requirements,
                "steps": steps,
            },
        }
        user = {
            "header": header,
            "role": body["role"],
            "objective_summary": approval.classified(body["objective_summary"]),
            "hypothesis": approval.classified(body["hypothesis"]),
            "priority_reason": approval.classified(body["priority_reason"]),
            "non_goals": [approval.classified(v) for v in sequence(body["non_goals"])],
            "context": [
                {**mapping(v), "summary": approval.classified(mapping(v)["summary"])}
                for v in sequence(body["context"])
            ],
            "input_ref": input_ref,
            "records": projected_records,
        }
        result: dict[str, object] = {
            "messages": [
                {"role": "system", "content": canonical(system).decode()},
                {"role": "user", "content": canonical(user).decode()},
            ],
            "tools": [],
        }
        raw_result = canonical(result)
        if len(raw_result) > 32768 or any(s.encode() in raw_result for s in approval.known_secrets):
            raise reject()
        return result
    except (CatalogError, ValueError, TypeError, KeyError, UnicodeError, RecursionError):
        raise reject() from None
