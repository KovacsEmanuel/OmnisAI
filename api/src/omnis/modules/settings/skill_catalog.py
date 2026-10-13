"""B06a-1 source compiler: pure, bounded and explicitly non-durable.

compile_catalog(tuple[Path, ...], Path) -> CompiledCatalog
Source templates resolve to qualified package/digest refs, never invented IDs.
No provider, runtime boot, publication, storage or executable package imports.
"""

import hashlib
import os
import stat
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, NoReturn, cast

from .catalog_models import (
    DEFAULT_PREFERENCE,
    CatalogError,
    CompiledCatalog,
    CompiledStep,
    LocalRef,
    Manifest,
    Preference,
    Procedure,
    Profile,
    PureEvaluation,
    QualifiedRef,
    ReleaseRef,
    SlotRef,
    StepOutputRef,
    TemplateRef,
)
from .catalog_schema import canonical, dto, load_json, load_yaml, schema, validate

if TYPE_CHECKING:
    from .candidate_resolution import ReleasePackage

NATIVE_HERMES_REVISION = "ee5ee84a345204a3b1d6ef6ba1ab747e602867b9"

HANDLERS = {
    "contract.parse-capture": ("capture", "records"),
    "contract.normalize-operations": ("records", "operations"),
    "contract.build-map": ("operations", "surface_map"),
}


def safe_path(name: str) -> None:
    path = PurePosixPath(name)
    if (
        len(name.encode("utf-8")) > 240
        or not name
        or path.is_absolute()
        or "\\" in name
        or "\x00" in name
        or any(part in ("", ".", "..") for part in name.split("/"))
    ):
        raise CatalogError("INVALID_PATH")


def read_file(path: Path, maximum: int = 1048576) -> bytes:
    absolute = path.absolute()
    directory = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    descriptor: int | None = None
    try:
        for component in absolute.parts[1:-1]:
            child = os.open(
                component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
            )
            os.close(directory)
            directory = child
        descriptor = os.open(
            absolute.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
        )
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise CatalogError("UNSAFE_FILE")
        if before.st_size > maximum:
            raise CatalogError("SIZE_LIMIT")
        chunks: list[bytes] = []
        size = 0
        while chunk := os.read(descriptor, min(65536, maximum + 1 - size)):
            chunks.append(chunk)
            size += len(chunk)
            if size > maximum:
                raise CatalogError("SIZE_LIMIT")
        after = os.fstat(descriptor)

        def fence(s: os.stat_result) -> tuple[int, ...]:
            return (
                s.st_dev,
                s.st_ino,
                s.st_mode,
                s.st_nlink,
                s.st_size,
                s.st_mtime_ns,
                s.st_ctime_ns,
            )

        if fence(before) != fence(after) or size != before.st_size:
            raise CatalogError("MATERIAL_CHANGED")
        return b"".join(chunks)
    except OSError:
        raise CatalogError("UNSAFE_FILE") from None
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def require_no_model(preference: Preference | None) -> Preference:
    result = preference or DEFAULT_PREFERENCE
    if (
        result.model_key is not None
        or result.effort is not None
        or result.requirement == "REQUIRED"
    ):
        raise CatalogError("MODEL_UNAVAILABLE")
    if result.on_unavailable != "BLOCK":
        raise CatalogError("UNSUPPORTED_PREFERENCE")
    return result


def compile_catalog(
    package_roots: tuple[Path, ...],
    profile_path: Path,
    *,
    dependencies: tuple["ReleasePackage", ...] = (),
) -> CompiledCatalog:
    from .candidate_resolution import artifact, body, verify
    from .candidate_store import reference as record_ref

    compiled = _compile_catalog(package_roots, profile_path, dependencies=dependencies)
    if dependencies and any(
        slot.expected_kind in {"contract-case-input", "contract-case-records"}
        for slot in compiled.slots
    ):
        raise CatalogError("UNSUPPORTED_CAPTURE_DEPENDENCY")
    by_ref = {canonical(record_ref(artifact(d))): d for d in dependencies}
    # Each exact release is checked once against its own profile and transitive inventory.
    for dependency in dependencies:
        release = verify(dependency)
        record = artifact(dependency)
        descendants: dict[bytes, ReleasePackage] = {}
        queue = list(cast(list[dict[str, object]], release["dependency_artifact_refs"]))
        for ref in queue:
            token = canonical(ref)
            if token in descendants:
                continue
            child = by_ref.get(token)
            if child is None:
                raise CatalogError("DEPENDENCY_UNAVAILABLE")
            descendants[token] = child
            queue.extend(cast(list[dict[str, object]], verify(child)["dependency_artifact_refs"]))
        directory = dependency.root / "candidates" / str(record["id"])
        qualified = body(cast(dict[str, object], load_json(dependency.qualification_json)))
        checked = _compile_catalog(
            (directory / "packages/0",),
            directory / "profile.yaml",
            dependencies=tuple(descendants[token] for token in sorted(descendants)),
        )
        if (
            qualified["material_digest"] != checked.material_digest
            or qualified["resolved_index_digest"] != checked.resolved_index_digest
            or qualified["dependency_closure_refs"] != list(checked.dependency_closure_refs)
        ):
            raise CatalogError("RELEASE_UNQUALIFIED")
        try:
            outputs = [
                raw.decode("utf-8")
                for raw in evaluate_pure(checked, qualified["pure_input"]).outputs_json
            ]
        except CatalogError:
            raise CatalogError("RELEASE_UNQUALIFIED") from None
        if outputs != qualified["outputs"]:
            raise CatalogError("RELEASE_UNQUALIFIED")
    return compiled


def _compile_catalog(
    package_roots: tuple[Path, ...],
    profile_path: Path,
    *,
    dependencies: tuple["ReleasePackage", ...],
) -> CompiledCatalog:
    from .candidate_resolution import artifact, verify
    from .candidate_store import reference as record_ref

    if not package_roots or len(package_roots) > 128:
        raise CatalogError("COUNT_LIMIT")
    if len(dependencies) > 128:
        raise CatalogError("COUNT_LIMIT")
    releases = [verify(dependency) for dependency in dependencies]
    release_records = [artifact(dependency) for dependency in dependencies]
    declared_graph = {
        str(record["id"]): [
            str(ref["id"])
            for ref in cast(list[dict[str, object]], release["dependency_artifact_refs"])
        ]
        for release, record in zip(releases, release_records, strict=True)
    }
    declared_active: set[str] = set()
    declared_visited: set[str] = set()

    def check_declared(identifier: str) -> None:
        if identifier in declared_active:
            raise CatalogError("DEPENDENCY_CYCLE")
        if identifier in declared_visited:
            return
        if identifier not in declared_graph:
            raise CatalogError("DEPENDENCY_UNAVAILABLE")
        declared_active.add(identifier)
        for child in declared_graph[identifier]:
            check_declared(child)
        declared_active.remove(identifier)
        declared_visited.add(identifier)

    for identifier in declared_graph:
        check_declared(identifier)
    release_roots = [
        dependency.root / "candidates" / str(record["id"]) / "packages/0"
        for dependency, record in zip(dependencies, release_records, strict=True)
    ]
    external_keys = {str(release["package_key"]) for release in releases}
    if len(external_keys) != len(releases):
        raise CatalogError("PACKAGE_SHADOW")
    exact_bindings: dict[bytes, tuple[str, str, str]] = {}
    for release in releases:
        for release_binding in cast(list[dict[str, object]], release["bindings"]):
            token = canonical(release_binding["ref"])
            if token in exact_bindings:
                raise CatalogError("PACKAGE_SHADOW")
            exact_bindings[token] = (
                str(release_binding["package_key"]),
                str(release_binding["entity_kind"]),
                str(release_binding["key"]),
            )
    manifests: dict[str, Manifest] = {}
    files_by_package: dict[str, dict[str, bytes]] = {}
    entities: dict[tuple[str, str, str], bytes | Procedure | None] = {}
    digests: dict[str, str] = {}
    names: set[str] = set()
    total_bytes = 0
    for root in (*package_roots, *release_roots):
        if root.is_symlink() or not root.is_dir():
            raise CatalogError("UNSAFE_PACKAGE")
        manifest_bytes = read_file(root / "omnis.yaml", 262144)
        manifest = dto(manifest_bytes, Manifest)
        key = manifest.package_key
        if key in manifests or manifest.native_name in names:
            raise CatalogError("PACKAGE_SHADOW")
        names.add(manifest.native_name)
        require_no_model(manifest.execution_preference)
        declared = (
            "omnis.yaml",
            manifest.skill_path,
            *manifest.procedures,
            *manifest.support_files,
        )
        if len(set(declared)) != len(declared) or len(declared) > 128:
            raise CatalogError("DUPLICATE_FILE")
        files: dict[str, bytes] = {}
        for name in declared:
            safe_path(name)
            path = root / name
            if any(parent.is_symlink() for parent in path.parents if parent != root.parent):
                raise CatalogError("UNSAFE_FILE")
            # One captured byte string owns both DTO validation and release hashing.
            files[name] = manifest_bytes if name == "omnis.yaml" else read_file(path)
            total_bytes += len(files[name])
            if total_bytes > 8 * 1048576:
                raise CatalogError("SIZE_LIMIT")
        actual: set[str] = set()
        directories = [root]
        visited = 0
        while directories:
            directory_path = directories.pop()
            with os.scandir(directory_path) as entries:
                for entry in entries:
                    visited += 1
                    if visited > 256:
                        raise CatalogError("COUNT_LIMIT")
                    if entry.is_symlink():
                        raise CatalogError("UNSAFE_FILE")
                    if entry.is_dir(follow_symlinks=False):
                        directories.append(Path(entry.path))
                    elif entry.is_file(follow_symlinks=False):
                        actual.add(str(Path(entry.path).relative_to(root)))
                    else:
                        raise CatalogError("UNSAFE_FILE")
        if actual != set(declared):
            raise CatalogError("UNDECLARED_FILE")
        skill_text = files["SKILL.md"].decode("utf-8")
        if not skill_text.startswith("---\n") or "\n---\n" not in skill_text[4:]:
            raise CatalogError("NATIVE_SKILL_MISMATCH")
        frontmatter = load_yaml(skill_text[4:].split("\n---\n", 1)[0].encode("utf-8"))
        if not isinstance(frontmatter, dict) or set(frontmatter) != {
            "name",
            "description",
            "version",
            "provenance",
        }:
            raise CatalogError("NATIVE_SKILL_MISMATCH")
        if (
            frontmatter.get("name") != manifest.native_name
            or frontmatter.get("version") != manifest.version
        ):
            raise CatalogError("NATIVE_SKILL_MISMATCH")
        if any(
            not isinstance(frontmatter[field], str)
            or not frontmatter[field]
            or len(frontmatter[field]) > 4096
            for field in frontmatter
        ):
            raise CatalogError("NATIVE_SKILL_MISMATCH")
        digest = hashlib.sha256(
            canonical(
                [
                    {
                        "path": name,
                        "sha256": hashlib.sha256(files[name]).hexdigest(),
                        "size": len(files[name]),
                    }
                    for name in sorted(files, key=lambda value: value.encode("utf-8"))
                ]
            )
        ).hexdigest()
        digests[key] = digest
        manifests[key] = manifest
        files_by_package[key] = files
        entities[(key, "package", key)] = None
        seen_paths: set[tuple[str, str]] = set()
        identity: tuple[str, str, str]
        for binding in manifest.file_bindings:
            identity = (key, binding.entity_kind, binding.key)
            if identity in entities or (binding.entity_kind, binding.path) in seen_paths:
                raise CatalogError("DUPLICATE_BINDING")
            if binding.path not in files:
                raise CatalogError("MISSING_FILE")
            seen_paths.add((binding.entity_kind, binding.path))
            entities[identity] = (
                schema(files[binding.path])
                if binding.entity_kind == "schema"
                else files[binding.path]
            )
        for technique in manifest.techniques:
            identity = (key, "technique", technique.key)
            if identity in entities:
                raise CatalogError("DUPLICATE_ENTITY")
            if technique.method_ref not in files:
                raise CatalogError("MISSING_FILE")
            if (
                technique.applicability_predicate_ids
                or technique.technologies
                or technique.standards
            ):
                raise CatalogError("UNSUPPORTED_FEATURE")
            entities[identity] = None
        for name in manifest.procedures:
            if not name.startswith("templates/procedures/"):
                raise CatalogError("INVALID_PATH")
            procedure = dto(files[name], Procedure)
            identity = (key, "procedure", procedure.key)
            if identity in entities:
                raise CatalogError("DUPLICATE_ENTITY")
            entities[identity] = procedure
        compatibility = manifest.compatibility
        if compatibility.hermes_revision != NATIVE_HERMES_REVISION:
            raise CatalogError("INCOMPATIBLE_HERMES")
        if any(
            (
                compatibility.adapter_refs,
                compatibility.tool_refs,
                compatibility.predicate_refs,
                compatibility.oracle_refs,
            )
        ):
            raise CatalogError("DEPENDENCY_UNAVAILABLE")
        if not manifest.provenance:
            raise CatalogError("MISSING_PROVENANCE")
        for source in manifest.provenance:
            if (
                source.path not in files
                or not source.notice_paths
                or any(n not in files for n in source.notice_paths)
            ):
                raise CatalogError("PROVENANCE_FILE")
            if hashlib.sha256(files[source.path]).hexdigest() != source.source_digest:
                raise CatalogError("PROVENANCE_DIGEST")

    local_keys = set(manifests) - external_keys
    for release in releases:
        release_key = str(release["package_key"])
        if digests[release_key] != release["package_digest"]:
            raise CatalogError("RELEASE_MISMATCH")
        if set(identity for identity in entities if identity[0] == release_key) != {
            identity for identity in exact_bindings.values() if identity[0] == release_key
        }:
            raise CatalogError("RELEASE_MISMATCH")
    refs: list[QualifiedRef] = []
    closure: dict[bytes, dict[str, object]] = {}
    edges: dict[str, set[str]] = {key: set() for key in external_keys}
    direct_dependencies: set[str] = set()

    def external_identity(reference: ReleaseRef, expected: str) -> tuple[str, str, str]:
        if reference.ref.kind != expected:
            raise CatalogError("REF_TYPE")
        exact = reference.ref.model_dump(mode="json")
        identity = exact_bindings.get(canonical(exact))
        if identity is None:
            raise CatalogError("DEPENDENCY_UNAVAILABLE")
        closure[canonical(exact)] = exact
        return identity

    def resolve(package: str, reference: TemplateRef, expected: str) -> bytes | Procedure | None:
        if isinstance(reference, ReleaseRef):
            identity = external_identity(reference, expected)
            if package in external_keys:
                edges[package].add(identity[0])
            else:
                direct_dependencies.add(identity[0])
        else:
            if reference.entity_kind != expected:
                raise CatalogError("REF_TYPE")
            identity = (package, expected, reference.key)
        if identity not in entities:
            raise CatalogError("MISSING_REF")
        qualified = QualifiedRef(*identity, digests[identity[0]])
        if qualified not in refs:
            refs.append(qualified)
        return entities[identity]

    def get_schema(package: str, reference: TemplateRef) -> bytes:
        value = resolve(package, reference, "schema")
        if not isinstance(value, bytes):
            raise CatalogError("REF_TYPE")
        return value

    for key, manifest in manifests.items():
        get_schema(key, manifest.input_schema_ref)
        get_schema(key, manifest.output_schema_ref)
        for technique in manifest.techniques:
            for reference in technique.procedure_refs:
                resolve(key, reference, "procedure")

    profile_bytes = read_file(profile_path, 262144)
    profile = dto(profile_bytes, Profile)
    require_no_model(profile.execution_preference)
    if len(profile.agent_recipes) != 1:
        raise CatalogError("UNSUPPORTED_RECIPE_COUNT")
    recipe = profile.agent_recipes[0]
    requested = require_no_model(recipe.execution_preference or profile.execution_preference)
    if recipe.requested_capabilities or not recipe.package_refs or len(recipe.procedure_refs) != 1:
        raise CatalogError("UNSUPPORTED_RECIPE")
    selected_packages: set[str] = set()
    selected_procedure: tuple[str, Procedure] | None = None
    for expected, references in (
        ("package", recipe.package_refs),
        ("technique", recipe.technique_refs),
        ("procedure", recipe.procedure_refs),
        ("overlay", recipe.overlay_refs),
    ):
        for profile_reference in references:
            if isinstance(profile_reference, ReleaseRef):
                package = external_identity(profile_reference, expected)[0]
                direct_dependencies.add(package)
                template_reference: TemplateRef = profile_reference
            else:
                package = profile_reference.package_key
                if package not in local_keys:
                    raise CatalogError("MISSING_REF")
                template_reference = LocalRef(
                    kind="LOCAL",
                    entity_kind=profile_reference.entity_kind,
                    key=profile_reference.key,
                )
            if expected != "package" and package not in selected_packages:
                raise CatalogError("PROFILE_PACKAGE_MISMATCH")
            # Profile references select a release, not a dependency edge from it to itself.
            profile_identity = (
                external_identity(profile_reference, expected)
                if isinstance(profile_reference, ReleaseRef)
                else None
            )
            value = (
                entities[profile_identity]
                if profile_identity is not None
                else resolve(package, template_reference, expected)
            )
            if profile_identity is not None:
                qualified = QualifiedRef(*profile_identity, digests[package])
                if qualified not in refs:
                    refs.append(qualified)
            if expected == "package":
                selected_packages.add(package)
            if isinstance(value, Procedure):
                selected_procedure = (package, value)
    if selected_procedure is None:
        raise CatalogError("MISSING_REF")

    def build_procedure(key: str, procedure: Procedure) -> tuple[list[CompiledStep], bytes, bytes]:
        resolve(key, procedure.technique_ref, "technique")
        if not procedure.method_requirements:
            raise CatalogError("MISSING_METHOD_REQUIREMENT")
        requirement_keys: set[str] = set()
        declared_steps = {step.id for step in procedure.probe}
        for requirement in procedure.method_requirements:
            if (
                requirement.key in requirement_keys
                or not requirement.step_ids
                or not set(requirement.step_ids) <= declared_steps
            ):
                raise CatalogError("METHOD_REQUIREMENT_REF")
            requirement_keys.add(requirement.key)
            if requirement.evidence_kinds:
                raise CatalogError("UNSUPPORTED_FEATURE")
            for artifact_schema in requirement.artifact_schema_refs:
                get_schema(key, artifact_schema)
        from omnis.modules.tasks.managed_contract import requirement_conditions

        requirement_conditions(procedure.model_dump(mode="json"))
        if any(
            (
                procedure.applicability_predicate_ids,
                procedure.technologies,
                procedure.identity_requirements,
                procedure.requested_capabilities,
                procedure.evidence_requirements,
                procedure.invalidation_predicate_ids,
                procedure.stop_reason_ids,
                procedure.oracle_ref,
            )
        ):
            raise CatalogError("UNSUPPORTED_FEATURE")
        if (
            procedure.baseline
            or procedure.control
            or procedure.cleanup
            or not procedure.cleanup_not_needed_reason
        ):
            raise CatalogError("UNSUPPORTED_GROUP")
        if {item.group for item in procedure.non_applicable_groups} != {
            "BASELINE",
            "CONTROL",
        } or len(procedure.non_applicable_groups) != 2:
            raise CatalogError("NON_APPLICABLE_REASON")
        slots_by_name = {slot.name: slot for slot in procedure.slots}
        if len(slots_by_name) != len(procedure.slots) or any(
            slot.min_items > slot.max_items for slot in procedure.slots
        ):
            raise CatalogError("SLOT_DECLARATION")
        used_slots: set[str] = set()

        def check_slot(reference: SlotRef, expected_kind: str, scalar: bool) -> None:
            slot = slots_by_name.get(reference.name)
            if (
                slot is None
                or slot.expected_kind != expected_kind
                or (scalar and (slot.min_items != 1 or slot.max_items != 1))
            ):
                raise CatalogError("SLOT_DECLARATION")
            used_slots.add(reference.name)

        for business_reference in procedure.business_rule_refs:
            if isinstance(business_reference, SlotRef):
                check_slot(business_reference, "business_rule", False)
            else:
                resolve(key, business_reference, "business_rule")
        if procedure.preconditions:
            from omnis.modules.tasks.managed_contract import requirement_conditions

            requirement_conditions(procedure.model_dump(mode="json"))
            for condition in procedure.preconditions:
                for reference in condition.input_refs:
                    if not isinstance(reference, SlotRef):
                        raise CatalogError("DEPENDENCY_UNAVAILABLE")
                    check_slot(reference, "contract-case-records", True)
        input_schema = get_schema(key, procedure.input_schema_ref)
        output_schema = get_schema(key, procedure.output_schema_ref)
        get_schema(key, procedure.handoff_schema_ref)
        from omnis.modules.tasks.contract_case_input import (
            first_binding,
            require_slots,
        )
        from omnis.modules.tasks.contract_case_input import (
            input_schema as case_schema,
        )

        case_version = 2 if procedure.key == "map-records" else 1
        handlers = tuple(HANDLERS)[case_version - 1 :]
        if (
            len(procedure.probe) != len(handlers)
            or procedure.limits.max_actions < len(handlers)
            or recipe.limits.max_actions < len(handlers)
        ):
            raise CatalogError("UNSUPPORTED_STEP_COUNT")

        def field_type(raw: bytes, field: str, required_type: str) -> None:
            parsed_schema = cast(dict[str, object], load_json(raw))
            properties = parsed_schema.get("properties")
            required = parsed_schema.get("required")
            if (
                not isinstance(properties, dict)
                or not isinstance(required, list)
                or field not in required
            ):
                raise CatalogError("SCHEMA_TYPE")
            definition = properties.get(field)
            if not isinstance(definition, dict) or definition.get("type") != required_type:
                raise CatalogError("SCHEMA_TYPE")
            if required_type == "array":
                items = definition.get("items")
                if not isinstance(items, dict) or items.get("type") != "object":
                    raise CatalogError("SCHEMA_TYPE")
                signatures = {
                    "records": {"method": "string", "path": "string", "status": "integer"},
                    "operations": {"method": "string", "path": "string", "statuses": "array"},
                    "surface_map": {
                        "path": "string",
                        "methods": "array",
                        "operation_count": "integer",
                    },
                }
                published_fields = items.get("properties")
                required_fields = items.get("required")
                if not isinstance(published_fields, dict) or not isinstance(required_fields, list):
                    raise CatalogError("SCHEMA_TYPE")
                for name, value_type in signatures[field].items():
                    published_field = published_fields.get(name)
                    if (
                        name not in required_fields
                        or not isinstance(published_field, dict)
                        or published_field.get("type") != value_type
                    ):
                        raise CatalogError("SCHEMA_TYPE")
                    if value_type == "array":
                        nested_items = published_field.get("items")
                        nested_type = "integer" if name == "statuses" else "string"
                        if (
                            not isinstance(nested_items, dict)
                            or nested_items.get("type") != nested_type
                        ):
                            raise CatalogError("SCHEMA_TYPE")

        if case_version == 2 or any(
            slot.expected_kind in {"contract-case-input", "contract-case-records"}
            for slot in procedure.slots
        ):
            require_slots(
                [s.model_dump(mode="json") for s in procedure.slots], version=case_version
            )
            if not isinstance(procedure.input_schema_ref, LocalRef):
                raise CatalogError("UNSUPPORTED_CAPTURE_DEPENDENCY")
            schema_paths = [
                binding.path
                for binding in manifests[key].file_bindings
                if binding.entity_kind == "schema" and binding.key == procedure.input_schema_ref.key
            ]
            if len(schema_paths) != 1:
                raise CatalogError("REF_TYPE")
            case_schema(files_by_package[key][schema_paths[0]], version=case_version)
            if [b.model_dump(mode="json") for b in procedure.probe[0].input_bindings] != [
                first_binding(case_version)
            ]:
                raise CatalogError("INPUT_BINDING")
        field_type(
            input_schema,
            "records" if case_version == 2 else "capture",
            "array" if case_version == 2 else "string",
        )
        field_type(output_schema, "surface_map", "array")
        compiled: list[CompiledStep] = []
        outputs: dict[str, tuple[str, bytes]] = {}
        for index, step in enumerate(procedure.probe):
            if step.id in outputs:
                raise CatalogError("DUPLICATE_STEP")
            action = step.action_definition_ref
            if isinstance(action, ReleaseRef):
                raise CatalogError("DEPENDENCY_UNAVAILABLE")
            if action.entity_kind != "action_definition" or action.key not in HANDLERS:
                raise CatalogError("UNKNOWN_HANDLER")
            handler = action.key
            expected_input, expected_output = HANDLERS[handler]
            if handler != handlers[index] or step.tool_ref is not None:
                raise CatalogError("UNSUPPORTED_HANDLER_ORDER")
            parameters_schema = get_schema(key, step.parameter_schema_ref)
            validate(parameters_schema, step.parameters)
            if step.parameters:
                raise CatalogError("UNSUPPORTED_PARAMETERS")
            out_schema = get_schema(key, step.output_schema_ref)
            field_type(out_schema, expected_output, "array")
            published = cast(dict[str, object], load_json(out_schema)).get("properties")
            if not isinstance(published, dict) or expected_output not in published:
                raise CatalogError("OUTPUT_REF")
            in_schema = input_schema if index == 0 else compiled[-1].output_schema
            if index == 0 and step.input_bindings:
                require_slots(
                    [s.model_dump(mode="json") for s in procedure.slots], version=case_version
                )
                if [b.model_dump(mode="json") for b in step.input_bindings] != [
                    first_binding(case_version)
                ]:
                    raise CatalogError("INPUT_BINDING")
            if index > 0:
                if len(step.input_bindings) != 1:
                    raise CatalogError("INPUT_BINDING")
                input_binding = step.input_bindings[0]
                if isinstance(input_binding.source_ref, SlotRef):
                    raise CatalogError("UNSUPPORTED_SLOT_BINDING")
                if not isinstance(input_binding.source_ref, StepOutputRef):
                    raise CatalogError("INPUT_BINDING")
                step_source = input_binding.source_ref
                if step_source.step_id not in outputs:
                    raise CatalogError("FORWARD_OUTPUT_REF")
                if (
                    step_source.output_name != outputs[step_source.step_id][0]
                    or step_source.output_name != expected_input
                ):
                    raise CatalogError("OUTPUT_REF")
                if (
                    step_source.step_id != compiled[-1].id
                    or input_binding.name != expected_input
                    or input_binding.selector is not None
                ):
                    raise CatalogError("BINDING_TYPE")
            outputs[step.id] = (expected_output, out_schema)
            compiled.append(
                CompiledStep(step.id, handler, step.input_bindings, in_schema, out_schema)
            )
        return compiled, input_schema, output_schema

    key, procedure = selected_procedure
    compiled, input_schema, output_schema = build_procedure(key, procedure)
    for (other_package, other_kind, _), other_value in entities.items():
        if (
            other_kind == "procedure"
            and isinstance(other_value, Procedure)
            and (other_package, other_value) != selected_procedure
        ):
            build_procedure(other_package, other_value)
    # Qualification consumes the retained profile as well as exported templates.
    # Its RELEASE selectors therefore belong to this artifact's dependency graph,
    # not the outer caller's direct selection. Full profile checks still run in
    # the exact per-artifact qualification replay in compile_catalog.
    for release, dependency, record in zip(releases, dependencies, release_records, strict=True):
        retained_profile = dto(
            read_file(dependency.root / "candidates" / str(record["id"]) / "profile.yaml", 262144),
            Profile,
        )
        for retained_recipe in retained_profile.agent_recipes:
            for expected, references in (
                ("package", retained_recipe.package_refs),
                ("technique", retained_recipe.technique_refs),
                ("procedure", retained_recipe.procedure_refs),
                ("overlay", retained_recipe.overlay_refs),
            ):
                for profile_reference in references:
                    if isinstance(profile_reference, ReleaseRef):
                        resolve(str(release["package_key"]), profile_reference, expected)
    visited_releases: set[str] = set()
    active: set[str] = set()

    def visit(package: str) -> None:
        if package in active:
            raise CatalogError("DEPENDENCY_CYCLE")
        if package in visited_releases:
            return
        active.add(package)
        for child in sorted(edges[package]):
            visit(child)
        active.remove(package)
        visited_releases.add(package)

    artifacts_by_key = {
        str(release["package_key"]): record_ref(record)
        for release, record in zip(releases, release_records, strict=True)
    }
    for release_key in direct_dependencies:
        visit(release_key)
    if visited_releases != external_keys:
        raise CatalogError("RELEASE_MISMATCH")
    for release in releases:
        release_key = str(release["package_key"])
        visit(release_key)
        declared_edges = cast(list[dict[str, object]], release["dependency_artifact_refs"])
        if sorted(declared_edges, key=canonical) != sorted(
            [artifacts_by_key[key] for key in edges[release_key]], key=canonical
        ):
            raise CatalogError("RELEASE_MISMATCH")
        package_binding = next(
            binding
            for binding in cast(list[dict[str, object]], release["bindings"])
            if binding["entity_kind"] == "package"
        )
        package_exact = cast(dict[str, object], package_binding["ref"])
        closure[canonical(package_exact)] = package_exact
    closure_refs = tuple(closure[token] for token in sorted(closure))
    artifact_refs = tuple(sorted(artifacts_by_key.values(), key=canonical))
    catalog_bindings = tuple(
        sorted(
            [
                binding
                for release in releases
                for binding in cast(list[dict[str, object]], release["bindings"])
            ],
            key=canonical,
        )
    )
    material_digest = hashlib.sha256(
        canonical(
            {
                "packages": [
                    {"package_key": key, "digest": digests[key]} for key in sorted(local_keys)
                ],
                "profile_sha256": hashlib.sha256(profile_bytes).hexdigest(),
            }
        )
    ).hexdigest()
    index_digest = hashlib.sha256(
        canonical(
            {
                "refs": [
                    asdict(ref)
                    for ref in sorted(refs, key=lambda r: (r.package_key, r.entity_kind, r.key))
                ],
                "steps": [
                    {
                        "id": step.id,
                        "handler": step.handler,
                        "input_schema_sha256": hashlib.sha256(step.input_schema).hexdigest(),
                        "output_schema_sha256": hashlib.sha256(step.output_schema).hexdigest(),
                    }
                    for step in compiled
                ],
                "requested": requested.model_dump(mode="json"),
                "resolution": "NO_MODEL",
                "dependency_closure_refs": list(closure_refs),
                "dependency_artifact_refs": list(artifact_refs),
                "catalog_bindings": list(catalog_bindings),
            }
        )
    ).hexdigest()
    return CompiledCatalog(
        material_digest,
        index_digest,
        "NO_MODEL",
        requested,
        tuple(refs),
        tuple(compiled),
        input_schema,
        output_schema,
        procedure.verification_kind,
        procedure.slots,
        min(procedure.limits.max_output_bytes, recipe.limits.max_output_bytes),
        closure_refs,
        artifact_refs,
        catalog_bindings,
    )


def evaluate_pure(
    candidate: CompiledCatalog, input_object: object, *, capture_material: object | None = None
) -> "PureEvaluation":
    from omnis.modules.tasks.contract_case_input import (
        first_binding,
        input_contract,
        slot_contract,
        validate_material,
    )
    from omnis.modules.tasks.module_registry import run_handler

    from .catalog_models import PureEvaluation

    capture_value: dict[str, object] | None = None
    version = 1
    if candidate.slots:
        if capture_material is None or input_object is not None:
            raise CatalogError("UNBOUND_SLOT")
        version = slot_contract([s.model_dump(mode="json") for s in candidate.slots])
        if not candidate.steps or [
            b.model_dump(mode="json") for b in candidate.steps[0].bindings
        ] != [first_binding(version)]:
            raise CatalogError("UNBOUND_SLOT")
        if not isinstance(capture_material, dict):
            raise CatalogError("UNBOUND_SLOT")
        context = capture_material.get("context")
        body = context.get("payload") if isinstance(context, dict) else None
        owner = body.get("owner_id") if isinstance(body, dict) else None
        if not isinstance(owner, str):
            raise CatalogError("UNBOUND_SLOT")
        material = validate_material(capture_material, namespace="PACKAGE_EVAL", owner_id=owner)
        if material["version"] != version:
            raise CatalogError("UNBOUND_SLOT")
        material_schema = cast(dict[str, object], material["schema"])
        if canonical(material_schema["document"]) != candidate.input_schema:
            raise CatalogError("UNBOUND_SLOT")
        capture_value = cast(
            dict[str, object],
            cast(dict[str, object], cast(dict[str, object], material["input"])["payload"])["value"],
        )
        input_object = capture_value
    elif capture_material is not None:
        raise CatalogError("UNBOUND_SLOT")
    if candidate.verification_kind != "CONTRACT":
        raise CatalogError("SECURITY_REQUIRES_FIXTURE")
    validate(candidate.input_schema, input_object)
    output_bytes: list[bytes] = []
    succeeded: dict[str, object] = {}
    for step_index, step in enumerate(candidate.steps):
        bound_input = input_object
        if step.bindings:
            bound: dict[str, object] = {}
            for binding in step.bindings:
                source = binding.source_ref
                if (
                    isinstance(source, SlotRef)
                    and step is candidate.steps[0]
                    and capture_value is not None
                ):
                    name, _ = input_contract(version)
                    if source.name != name or binding.name != name or binding.selector != name:
                        raise CatalogError("UNBOUND_SLOT")
                    bound[binding.name] = capture_value[name]
                    continue
                if not isinstance(source, StepOutputRef):
                    raise CatalogError("UNBOUND_SLOT")
                if (
                    step_index == 0
                    or source.step_id != candidate.steps[step_index - 1].id
                    or source.output_name != HANDLERS[candidate.steps[step_index - 1].handler][1]
                    or binding.name != HANDLERS[step.handler][0]
                    or source.output_name != binding.name
                    or binding.selector is not None
                ):
                    raise CatalogError("MISSING_STEP_OUTPUT")
                output = succeeded.get(source.step_id)
                if not isinstance(output, dict) or source.output_name not in output:
                    raise CatalogError("MISSING_STEP_OUTPUT")
                bound[binding.name] = output[source.output_name]
            bound_input = bound
        validate(step.input_schema, bound_input)
        output = run_handler(step.handler, bound_input)
        validate(step.output_schema, output)
        raw = canonical(output)
        if (
            len(raw) > candidate.max_output_bytes
            or sum(map(len, output_bytes)) + len(raw) > candidate.max_output_bytes
        ):
            raise CatalogError("OUTPUT_LIMIT")
        succeeded[step.id] = output
        output_bytes.append(raw)
    validate(candidate.output_schema, succeeded[candidate.steps[-1].id])
    return PureEvaluation(
        candidate.material_digest, candidate.resolved_index_digest, "NO_MODEL", tuple(output_bytes)
    )


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    class SafeParser(argparse.ArgumentParser):
        def error(self, message: str) -> "NoReturn":
            raise CatalogError("INVALID_ARGUMENTS")

    parser = SafeParser()
    parser.add_argument("command", choices=("compile", "evaluate"))
    parser.add_argument("--package", action="append", required=True)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--input")
    try:
        args = parser.parse_args(argv)
        if (args.command == "evaluate") != (args.input is not None):
            raise CatalogError("INVALID_ARGUMENTS")
        candidate = compile_catalog(tuple(Path(path) for path in args.package), Path(args.profile))
        report: dict[str, object] = {
            "status": "STATIC_PASS",
            "material_digest": candidate.material_digest,
            "resolved_index_digest": candidate.resolved_index_digest,
            "resolution": "NO_MODEL",
            "requested": candidate.requested.model_dump(mode="json"),
            "effective": None,
            "scope": "B06a-1_PARTIAL_NON_DURABLE",
            "resolved_refs": [asdict(ref) for ref in candidate.refs],
        }
        if args.command == "evaluate":
            result = evaluate_pure(candidate, load_json(read_file(Path(args.input))))
            report["status"] = "PURE_PASS"
            report["outputs"] = list(result.outputs)
        print(canonical(report).decode("utf-8"))
        return 0
    except CatalogError as error:
        print(canonical({"status": "BLOCKED", "reason": error.reason}).decode(), file=sys.stderr)
        return 2
    except (OSError, UnicodeError, RecursionError):
        print('{"status":"BLOCKED","reason":"INPUT_UNAVAILABLE"}', file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
