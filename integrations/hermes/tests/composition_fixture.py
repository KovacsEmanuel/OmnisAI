"""Synthetic two-small-skill cold composition; no catalog/runtime effects."""

from uuid import uuid4

from omnis_hermes.managed_admission_contract import canonical, digest, ref


def record(kind, payload):
    value = dict(schema_version=1, kind=kind, id=str(uuid4()), revision=1, payload=payload)
    return {**value, "digest": digest(canonical(value))}


def seal(value):
    value["digest"] = digest(canonical({k: v for k, v in value.items() if k != "digest"}))
    return value


def reference(kind):
    return ref(record(kind, {}))


def fixture():
    from omnis_hermes import prompt_bundle as composer

    skills = []
    for name in ("alpha", "beta"):
        content = [
            {
                "path": "SKILL.md",
                "text": f"---\nname: {name}\ndescription: Inert test\n---\n# {name}\n",
            },
        ]
        if name == "alpha":
            content.append(
                {"path": "references/method.md", "text": "# Method\nKeep all requirements.\n"}
            )
        files = sorted(
            [
                {
                    "path": c["path"],
                    "sha256": digest(c["text"].encode()),
                    "size": len(c["text"].encode()),
                }
                for c in content
            ]
            + [{"path": "omnis.yaml", "sha256": digest(b"inert metadata\n"), "size": 15}],
            key=lambda f: f["path"].encode(),
        )
        package_ref = {**reference("package"), "digest": digest(canonical(files))}
        skills.append(
            dict(
                section="skill",
                package_ref=package_ref,
                native_name=name,
                files=files,
                content=content,
            )
        )
    packages = [s["package_ref"] for s in skills]
    base = record(
        "prompt-content",
        {
            "text": "CONTRACT_PROBE. No provider, model, tools, targets, or domain reads. Return NO_MODEL only."
        },
    )
    role = record(
        "prompt-content",
        {"role": "RECON", "text": "SUPPORT-only cold admission probe; not an assessment."},
    )
    bundle = record(
        "prompt-bundle",
        dict(
            base_ref=ref(base),
            role_refs=[{"role": "RECON", "content_ref": ref(role)}],
            composer_revision=composer.composer_revision(),
            brief_schema=1,
            result_schema=1,
            package_refs=packages,
            max_context_bytes=65536,
            max_context_tokens=65536,
            tokenizer_revision="utf8-byte-upper-bound-v1",
            provenance=composer.PROVENANCE,
        ),
    )
    mission, focus, procedure_ref, technique = (
        reference("mission"),
        reference("focus"),
        reference("procedure"),
        reference("technique"),
    )
    limits = dict(
        max_attempts=1, max_actions=1, deadline_seconds=60, max_output_bytes=2048, max_fanout=1
    )
    requirement = dict(
        key="retain",
        description="Retain complete method.",
        required=True,
        applies_if=[],
        step_ids=["inspect"],
        artifact_schema_refs=[],
        evidence_kinds=[],
    )
    step = dict(
        id="inspect",
        action_definition_ref=reference("action_definition"),
        tool_ref=None,
        parameter_schema_ref=reference("schema"),
        parameters={},
        input_bindings=[],
        output_schema_ref=reference("schema"),
    )
    procedure = dict(
        schema_version=1,
        key="inert",
        technique_ref=technique,
        verification_kind="CONTRACT",
        non_applicable_groups=[
            {"group": "BASELINE", "reason": "Inert"},
            {"group": "CONTROL", "reason": "Inert"},
        ],
        objective="Retain complete method.",
        applicability_predicate_ids=[],
        technologies=[],
        input_schema_ref=reference("schema"),
        output_schema_ref=reference("schema"),
        preconditions=[],
        method_requirements=[requirement],
        identity_requirements=[],
        business_rule_refs=[],
        requested_capabilities=[],
        requested_effect_ceiling="PURE",
        predicted_signal="No execution",
        baseline=[],
        probe=[step],
        control=[],
        evidence_requirements=[],
        oracle_ref=None,
        slots=[],
        false_positives=[],
        invalidation_predicate_ids=[],
        limits=limits,
        stop_reason_ids=[],
        cleanup=[],
        cleanup_not_needed_reason="No effects",
        handoff_schema_ref=reference("schema"),
        outcomes=["BLOCKED"],
    )
    bound = record(
        "bound-procedure",
        dict(
            procedure_ref=procedure_ref,
            slot_values=[],
            resolved_procedure=procedure,
            mission_ref=mission,
        ),
    )
    requirement_plan = dict(
        ref={"bound_procedure_ref": ref(bound), "requirement_key": "retain"},
        applicability="APPLIES",
        applicability_basis_refs=[],
        required=True,
    )
    header = dict(
        schema_version=1,
        run_id=str(uuid4()),
        task_id=str(uuid4()),
        attempt_id=str(uuid4()),
        snapshot_ref=reference("run-snapshot"),
        mission_revision=mission,
        focus_ref=focus,
        through_cursor=str(uuid4()),
        brief_revision=1,
        result_schema_ref=reference("schema"),
    )
    selection = reference("execution-selection")
    brief = record(
        "task-brief",
        dict(
            header=header,
            prompt_bundle_ref=ref(bundle),
            execution_selection_ref=selection,
            assessment_mode="FULL_ASSESSMENT",
            objective_summary=procedure["objective"],
            non_goals=["No effects"],
            role="RECON",
            hypothesis="Native refusal",
            operation_refs=[],
            priority_reason="SUPPORT cold probe",
            done_when=[],
            return_when=[],
            context=[
                {"ref": r, "epistemic_state": "OBSERVED", "summary": "Inert", "mandatory": True}
                for r in (mission, focus)
            ],
            contradiction_refs=[],
            prior_attempt_refs=[],
            package_refs=packages,
            technique_refs=[technique],
            procedure_refs=[procedure_ref],
            procedure_bindings=[
                {
                    "procedure_ref": procedure_ref,
                    "slot_values": [],
                    "bound_procedure_ref": ref(bound),
                }
            ],
            method_plan={"requirements": [requirement_plan]},
            review_request=None,
            criterion_bindings=[],
            overlay_refs=[],
            input_artifact_refs=[],
            identities=[],
            allowed_capability_ids=[],
            limits=limits,
            deadline="2026-10-09T12:00:00Z",
            validation_reserve={"actions": 0, "seconds": 0},
            stop_conditions=[],
            required_evidence=[],
        ),
    )
    sections = [
        {"section": label, "record": value}
        for label, value in (("base", base), ("role", role), ("brief", brief), ("method", bound))
    ] + skills
    receipt = reference("native-preparation-receipt")
    composition = record("prompt-composition", composer.compose(bundle, receipt, sections))
    entry = dict(
        batch_index=0,
        task_id=header["task_id"],
        attempt_id=header["attempt_id"],
        brief_ref=ref(brief),
        composition_ref=ref(composition),
        goal=procedure["objective"],
    )
    manifest = record(
        "launch-manifest",
        dict(
            run_id=header["run_id"],
            selection_ref=selection,
            resolution="NO_MODEL",
            effective=None,
            composition_version=1,
            entries=[entry],
        ),
    )
    return dict(
        protocol="omnis-managed-admission-v2", manifest=manifest, compositions=[composition]
    )
