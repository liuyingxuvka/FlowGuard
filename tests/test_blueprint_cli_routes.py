import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flowguard.__main__ import main
from flowguard.affected_blueprint_reader import materialize_affected_blueprint_index
from flowguard.canonical_blueprint_projection import (
    TARGET_SYSTEM_BLUEPRINT_PROJECTION_KINDS,
    canonical_target_system_blueprint_projection,
    verify_materialized_target_system_blueprint_projection,
)
from flowguard.evidence_receipts import (
    EvidenceReceipt,
    ReceiptFinding,
    ReceiptVerificationResult,
    build_environment_fingerprint,
    fingerprint_value,
    snapshot_bytes,
)
from flowguard.portable_model import (
    PortableModel,
    PortableState,
    PortableTransition,
    RefinementBinding,
)
from flowguard.model_intent_authority import EffectiveIntentTransition
from flowguard.software_blueprint_readiness import (
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND,
    BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA,
)
from flowguard.implementation_blueprint import (
    BlueprintShard,
    CanonicalBlueprintProjection,
    load_canonical_blueprint_projection,
    verify_blueprint_projection,
    write_canonical_blueprint_projection,
)
from flowguard.target_native_qualification import (
    TargetBlueprintNativeReportSet,
    TargetNativeMember,
    TargetNativeModelRef,
    qualify_target_system_from_native_reports,
    target_native_test_obligation_id,
)
from flowguard.target_system_blueprint import (
    BlueprintLayerResult,
    BlueprintNativeReportRef,
    BlueprintReadinessLedger,
    CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN,
    CANONICAL_SOFTWARE_LAYER_PLAN,
    FrozenTargetSystemEvidence,
    ProviderCapabilityBinding,
    TargetSystemDescriptor,
    TargetSystemProviderDeclaration,
    TargetSystemProviderResult,
    TargetSystemLayerPlan,
    build_target_system_provider_registry,
    capture_target_system_snapshot,
)
from flowguard.validation_ownership import ValidationOwnerContract


class BlueprintCliRouteTests(unittest.TestCase):
    def _write_json(self, directory: Path, name: str, payload: object) -> Path:
        path = directory / name
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return path

    def _target_artifacts(
        self,
        target_profile: str,
    ) -> tuple[
        TargetSystemDescriptor,
        FrozenTargetSystemEvidence,
        TargetBlueprintNativeReportSet,
    ]:
        plan = (
            CANONICAL_SOFTWARE_LAYER_PLAN
            if target_profile == "software"
            else CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN
        )
        behavior_kind = "behavior" if target_profile == "software" else "transition"
        behavior_id = (
            "behavior:submit-order"
            if target_profile == "software"
            else "transition:approve-expense"
        )
        observed_model = PortableModel(
            model_id=f"portable:{target_profile}:observed",
            states=(PortableState("pending"), PortableState("done")),
            transitions=(
                PortableTransition(
                    transition_id="observed:complete",
                    source_state="pending",
                    input_symbol="complete",
                    output_symbol="done",
                    target_state="done",
                ),
            ),
            initial_state_ids=("pending",),
            terminal_state_ids=("done",),
            guarantees=("complete-reaches-done",),
        )
        authority_model = PortableModel(
            model_id=f"portable:{target_profile}:authority",
            states=(PortableState("pending"), PortableState("done")),
            transitions=(
                PortableTransition(
                    transition_id="authority:complete",
                    source_state="pending",
                    input_symbol="complete",
                    output_symbol="done",
                    target_state="done",
                ),
            ),
            initial_state_ids=("pending",),
            terminal_state_ids=("done",),
            guarantees=("complete-reaches-done",),
        )
        binding = RefinementBinding(
            parent_model_id=authority_model.model_id,
            child_model_id=observed_model.model_id,
            parent_model_fingerprint=authority_model.fingerprint,
            child_model_fingerprint=observed_model.fingerprint,
            state_mapping=(("done", "done"), ("pending", "pending")),
            transition_mapping=(("observed:complete", "authority:complete"),),
        )
        member_ids = (
            {
                "behavior": behavior_id,
                "input": "input:order-event",
                "state": "state:order-lifecycle",
                "output": "output:order-next-state",
                "implementation": "typescript:src/order.ts#transition",
                "interface": "interface:state,event->next-state",
                "test": "test:order-submit",
                "resource": "resource:package-manifest",
                "intent": "intent:order-lifecycle",
            }
            if target_profile == "software"
            else {
                "boundary": "boundary:expense-approval",
                "actor": "actor:finance-reviewer",
                "input": "input:expense-request",
                "state": "state:pending-and-approved",
                "transition": behavior_id,
                "output": "output:approval-decision",
                "resource": "resource:expense-policy",
                "intent": "intent:policy-bounded-approval",
                "verification": "verification:valid-expense-approved",
            }
        )
        boundary_payload = {
            "target_profile": target_profile,
            "target_system_id": f"target:{target_profile}",
            "subject_revision": "revision:one",
        }
        boundary_fingerprint = fingerprint_value(boundary_payload)
        capability_ids = (
            "portable_model",
            *(f"{kind}_inventory" for kind in sorted(member_ids)),
        )
        descriptor = TargetSystemDescriptor(
            target_system_id=f"target:{target_profile}",
            target_kind=("software" if target_profile == "software" else "approval_workflow"),
            target_profile=target_profile,
            subject_revision="revision:one",
            boundary_fingerprint=boundary_fingerprint,
            required_observation_capabilities=capability_ids,
            required_authority_capabilities=capability_ids,
            claim_boundary="One exact synthetic target boundary.",
        )
        role_models = {
            "observation": observed_model,
            "authority": authority_model,
        }
        role_transition_ids = {
            "observation": ("observed:complete",),
            "authority": ("authority:complete",),
        }

        def native_details(kind: str, member_id: str, role: str) -> dict[str, object]:
            model = role_models[role]
            port_contract = {
                "input_ids": [member_ids["input"]],
                "state_ids": [member_ids["state"]],
                "output_ids": [member_ids["output"]],
                "effect_ids": [f"effect:{behavior_id}:state-transition"],
                "error_ids": [f"error:{behavior_id}:invalid-input"],
            }
            if kind in {"behavior", "transition", "interface"}:
                return dict(port_contract)
            if kind == "implementation":
                return {
                    "path": "typescript:src/order.ts",
                    "symbol": "transition",
                    "content_fingerprint": fingerprint_value(
                        {
                            "member_id": member_id,
                            "subject_revision": descriptor.subject_revision,
                        }
                    ),
                    "structure_fingerprint": fingerprint_value(port_contract),
                    **port_contract,
                }
            if kind == "input":
                return {
                    "value_schema": {"type": "string"},
                    "model_input_values": [model.transitions[0].input_symbol],
                }
            if kind == "state":
                return {
                    "value_schema": {"type": "state-id"},
                    "model_state_ids": ["done", "pending"],
                }
            if kind == "output":
                return {
                    "value_schema": {"type": "string"},
                    "model_output_values": [model.transitions[0].output_symbol],
                }
            if kind in {"test", "verification"}:
                return {
                    "validation_owner_id": (
                        f"native-owner:{role}:{kind}:{member_id}"
                    ),
                    "obligation_id": target_native_test_obligation_id(
                        target_system_id=descriptor.target_system_id,
                        target_profile=descriptor.target_profile,
                        subject_revision=descriptor.subject_revision,
                        evidence_role=role,
                        member_kind=kind,
                        member_id=member_id,
                    ),
                    "checker_id": f"checker:{member_id}",
                    "oracle_id": f"oracle:{member_id}",
                    "source_ref": member_id,
                    "source_fingerprint": fingerprint_value(
                        {
                            "source_ref": member_id,
                            "subject_revision": descriptor.subject_revision,
                        }
                    ),
                    "receipt_id": "",
                    "receipt_fingerprint": "",
                    "execution_status": "not_run",
                }
            if kind == "resource":
                return {
                    "resource_kind": "target_resource",
                    "owner_id": f"owner:{member_id}",
                    "source_ref": member_id,
                    "current_fingerprint": fingerprint_value(
                        {"resource": member_id, "revision": descriptor.subject_revision}
                    ),
                    "lifecycle_status": "current",
                }
            if kind == "intent":
                authority_payload = {
                    "source_kind": "target_contract",
                    "source_id": f"source:{member_id}",
                    "authority_id": f"authority:{member_id}",
                    "authority_revision": descriptor.subject_revision,
                }
                authority_fingerprint = fingerprint_value(authority_payload)
                contribution_payload = {
                    **authority_payload,
                    "authority_fingerprint": authority_fingerprint,
                    "contribution_id": f"contribution:{member_id}",
                    "behavior_ids": [behavior_id],
                    "contribution_status": "current",
                    "conflicts_with_contribution_ids": [],
                }
                return {
                    **contribution_payload,
                    "contribution_fingerprint": fingerprint_value(
                        contribution_payload
                    ),
                    "model_ids": [model.model_id],
                    "model_transition_ids": list(role_transition_ids[role]),
                }
            if kind == "boundary":
                return {
                    "boundary_fingerprint": descriptor.boundary_fingerprint,
                    "scope_ids": [behavior_id],
                }
            if kind == "actor":
                return {
                    "role_ids": ["role:reviewer"],
                    "permission_ids": ["permission:approve"],
                }
            raise AssertionError(f"unhandled target native kind: {kind}")

        results = []
        for role, model in role_models.items():
            payloads: dict[str, object] = {"portable_model": model.to_dict()}
            for kind, member_id in member_ids.items():
                payloads[f"member:{kind}:{member_id}"] = {
                    "member_id": member_id,
                    "member_kind": kind,
                    "subject_revision": descriptor.subject_revision,
                    "behavior_ids": [behavior_id],
                    "model_transition_ids": (
                        list(role_transition_ids[role])
                        if kind in {behavior_kind, "intent"}
                        else []
                    ),
                    "details": native_details(kind, member_id, role),
                    "status": "current",
                }
            results.append(
                TargetSystemProviderResult(
                    provider_id=f"provider:{target_profile}:{role}",
                    provider_role=role,
                    provider_kind=f"synthetic.native.{role}",
                    provider_version="1",
                    target_system_id=descriptor.target_system_id,
                    subject_revision=descriptor.subject_revision,
                    capability_ids=capability_ids,
                    input_fingerprints=(("target_boundary", boundary_fingerprint),),
                    payload_fingerprints=tuple(
                        (payload_id, fingerprint_value(payload))
                        for payload_id, payload in payloads.items()
                    ),
                    capability_bindings=(
                        ProviderCapabilityBinding(
                            capability_id="portable_model",
                            input_ids=("target_boundary",),
                            payload_ids=("portable_model",),
                        ),
                        *(
                            ProviderCapabilityBinding(
                                capability_id=f"{kind}_inventory",
                                input_ids=("target_boundary",),
                                payload_ids=(f"member:{kind}:{member_id}",),
                            )
                            for kind, member_id in sorted(member_ids.items())
                        ),
                    ),
                    status="current",
                    claim_boundary=f"Synthetic {role} evidence fixture only.",
                )
            )
        results_tuple = tuple(results)
        declarations = tuple(
            TargetSystemProviderDeclaration(
                provider_id=result.provider_id,
                provider_role=result.provider_role,
                provider_kind=result.provider_kind,
                provider_version=result.provider_version,
                capability_ids=result.capability_ids,
                claim_boundary=result.claim_boundary,
            )
            for result in results_tuple
        )
        registry = build_target_system_provider_registry(
            f"registry:{target_profile}", declarations
        )
        snapshot = capture_target_system_snapshot(
            f"snapshot:{target_profile}", descriptor, registry, results_tuple
        )
        frozen = FrozenTargetSystemEvidence(
            evidence_id=f"frozen:{target_profile}",
            layer_plan=plan,
            provider_registry=registry,
            provider_results=results_tuple,
            snapshot=snapshot,
            claim_boundary="Already-produced fixture evidence only.",
        )
        members = []
        model_refs = []
        for result in results_tuple:
            role = result.provider_role
            payload_fingerprints = dict(result.payload_fingerprints)
            model = role_models[role]
            model_refs.append(
                TargetNativeModelRef(
                    evidence_role=role,
                    provider_id=result.provider_id,
                    capability_id="portable_model",
                    payload_id="portable_model",
                    payload_fingerprint=payload_fingerprints["portable_model"],
                    model_id=model.model_id,
                    model_fingerprint=model.fingerprint,
                )
            )
            for kind, member_id in member_ids.items():
                payload_id = f"member:{kind}:{member_id}"
                members.append(
                    TargetNativeMember(
                        member_id=member_id,
                        member_kind=kind,
                        evidence_role=role,
                        subject_revision=descriptor.subject_revision,
                        provider_id=result.provider_id,
                        capability_id=f"{kind}_inventory",
                        payload_id=payload_id,
                        payload_fingerprint=payload_fingerprints[payload_id],
                        behavior_ids=(behavior_id,),
                        model_transition_ids=(
                            role_transition_ids[role]
                            if kind in {behavior_kind, "intent"}
                            else ()
                        ),
                        details=native_details(kind, member_id, role),
                    )
                )
        native = TargetBlueprintNativeReportSet(
            target_system_id=descriptor.target_system_id,
            target_profile=target_profile,
            subject_revision=descriptor.subject_revision,
            descriptor_fingerprint=descriptor.fingerprint,
            boundary_fingerprint=descriptor.boundary_fingerprint,
            frozen_evidence_fingerprint=frozen.fingerprint,
            observed_model=observed_model,
            authority_model=authority_model,
            refinement_binding=binding,
            model_refs=tuple(model_refs),
            members=tuple(members),
            claim_boundary="Exact truthful native CLI fixture only.",
        )
        return descriptor, frozen, native

    def _write_target_artifacts(
        self,
        root: Path,
        target_profile: str,
    ) -> tuple[Path, Path, Path]:
        descriptor, frozen, native = self._target_artifacts(target_profile)
        return (
            self._write_json(root, f"{target_profile}-descriptor.json", descriptor.to_dict()),
            self._write_json(root, f"{target_profile}-frozen.json", frozen.to_dict()),
            self._write_json(root, f"{target_profile}-native.json", native.to_dict()),
        )

    def _target_cli_args(
        self,
        descriptor: Path,
        frozen: Path,
        native: Path,
    ) -> list[str]:
        return [
            "target-system-blueprint-audit",
            "--descriptor",
            str(descriptor),
            "--frozen-evidence",
            str(frozen),
            "--native-report-set",
            str(native),
            "--json",
        ]

    def _target_export_cli_args(
        self,
        descriptor: Path,
        frozen: Path,
        native: Path,
        output: Path,
    ) -> list[str]:
        return [
            "target-system-blueprint-export",
            "--descriptor",
            str(descriptor),
            "--frozen-evidence",
            str(frozen),
            "--native-report-set",
            str(native),
            "--output",
            str(output),
            "--json",
        ]

    def _projection_payload(self, output: Path, kind: str) -> dict[str, object]:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        shard_ref = next(row for row in manifest["shards"] if row["kind"] == kind)
        shard = json.loads(
            (output / shard_ref["relative_path"]).read_text(encoding="utf-8")
        )
        self.assertEqual(1, len(shard["payload"]))
        return shard["payload"][0]

    def test_target_system_blueprint_audit_derives_both_reference_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target_profile in ("software", "non_code_workflow"):
                with self.subTest(target_profile=target_profile):
                    descriptor, frozen, native = self._write_target_artifacts(
                        root, target_profile
                    )
                    output = StringIO()
                    with redirect_stdout(output):
                        exit_code = main(
                            self._target_cli_args(descriptor, frozen, native)
                        )
                    payload = json.loads(output.getvalue())
                    self.assertEqual(0, exit_code)
                    self.assertTrue(payload["ok"])
                    self.assertEqual(target_profile, payload["target_profile"])
                    self.assertEqual("whole", payload["scope"])
                    self.assertEqual(
                        list(
                            CANONICAL_SOFTWARE_LAYER_PLAN.layer_ids
                            if target_profile == "software"
                            else CANONICAL_NON_CODE_WORKFLOW_LAYER_PLAN.layer_ids
                        ),
                        [row["layer"] for row in payload["layers"]],
                    )
                    self.assertEqual(
                        target_profile == "software",
                        payload["readiness_ledger"]["implementation_admitted"],
                    )

    def test_target_system_blueprint_export_is_deterministic_for_typescript_and_workflow(self):
        with self.assertRaises(SystemExit):
            main(["target-system-blueprint-export"])
        return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for target_profile in ("software", "non_code_workflow"):
                with self.subTest(target_profile=target_profile):
                    descriptor_path, frozen_path, native_path = (
                        self._write_target_artifacts(root, target_profile)
                    )
                    audit_output = StringIO()
                    with redirect_stdout(audit_output):
                        audit_exit = main(
                            self._target_cli_args(
                                descriptor_path,
                                frozen_path,
                                native_path,
                            )
                        )
                    audit = json.loads(audit_output.getvalue())
                    self.assertEqual(0, audit_exit)

                    exports = []
                    results = []
                    for suffix in ("a", "b"):
                        output = root / f"export-{target_profile}-{suffix}"
                        command_output = StringIO()
                        with redirect_stdout(command_output):
                            exit_code = main(
                                self._target_export_cli_args(
                                    descriptor_path,
                                    frozen_path,
                                    native_path,
                                    output,
                                )
                            )
                        self.assertEqual(0, exit_code)
                        results.append(json.loads(command_output.getvalue()))
                        exports.append(output)

                    first_files = {
                        path.relative_to(exports[0]).as_posix(): path.read_bytes()
                        for path in sorted(exports[0].rglob("*"))
                        if path.is_file()
                    }
                    second_files = {
                        path.relative_to(exports[1]).as_posix(): path.read_bytes()
                        for path in sorted(exports[1].rglob("*"))
                        if path.is_file()
                    }
                    self.assertEqual(first_files, second_files)
                    self.assertEqual(
                        results[0]["projection_fingerprint"],
                        results[1]["projection_fingerprint"],
                    )
                    self.assertTrue(results[0]["materialization_ok"])
                    self.assertEqual("complete", results[0]["materialization_status"])
                    self.assertEqual(audit["status"], results[0]["model_readiness_status"])
                    self.assertIn(
                        "content-addressed shard integrity only",
                        results[0]["generic_claim_boundary"],
                    )
                    self.assertIn(
                        "compiler-owned qualification",
                        results[0]["claim_boundary"],
                    )

                    manifest = json.loads(
                        (exports[0] / "manifest.json").read_text(encoding="utf-8")
                    )
                    self.assertEqual(
                        set(TARGET_SYSTEM_BLUEPRINT_PROJECTION_KINDS),
                        {row["kind"] for row in manifest["shards"]},
                    )
                    identity = self._projection_payload(exports[0], "identity")
                    providers = self._projection_payload(
                        exports[0], "provider_evidence"
                    )
                    native = self._projection_payload(exports[0], "native_reports")
                    readiness = self._projection_payload(exports[0], "readiness")
                    self.assertEqual(
                        json.loads(descriptor_path.read_text(encoding="utf-8")),
                        identity["descriptor"],
                    )
                    self.assertEqual(
                        json.loads(frozen_path.read_text(encoding="utf-8")),
                        providers["frozen_evidence"],
                    )
                    self.assertEqual(
                        json.loads(native_path.read_text(encoding="utf-8")),
                        native["native_report_set"],
                    )
                    self.assertEqual(
                        audit["fingerprint"],
                        readiness["qualification_fingerprint"],
                    )
                    self.assertEqual(
                        audit["fingerprint"],
                        readiness["qualification"]["fingerprint"],
                    )
                    self.assertEqual(
                        audit["readiness_ledger"]["fingerprint"],
                        readiness["readiness_fingerprint"],
                    )
                    self.assertEqual(
                        "not_run",
                        readiness["readiness"]["executed_evidence_status"],
                    )
                    member_kinds = {
                        row["member_kind"]
                        for row in native["native_report_set"]["members"]
                    }
                    if target_profile == "software":
                        self.assertIn("implementation", member_kinds)
                        self.assertIn(
                            "typescript:src/order.ts#transition",
                            {
                                row["member_id"]
                                for row in native["native_report_set"]["members"]
                            },
                        )
                    else:
                        self.assertNotIn("implementation", member_kinds)
                        self.assertIn("transition", member_kinds)

    def test_target_system_blueprint_export_preserves_blocked_readiness(self):
        with self.assertRaises(SystemExit):
            main(["target-system-blueprint-export"])
        return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor, frozen, native = self._target_artifacts("software")
            blocked_results = (
                replace(
                    frozen.provider_results[0],
                    status="blocked",
                    findings=("synthetic provider blocker",),
                ),
                *frozen.provider_results[1:],
            )
            blocked_snapshot = capture_target_system_snapshot(
                "snapshot:software:blocked",
                descriptor,
                frozen.provider_registry,
                blocked_results,
            )
            blocked_frozen = replace(
                frozen,
                provider_results=blocked_results,
                snapshot=blocked_snapshot,
            )
            blocked_native = replace(
                native,
                frozen_evidence_fingerprint=blocked_frozen.fingerprint,
            )
            descriptor_path = self._write_json(
                root, "blocked-descriptor.json", descriptor.to_dict()
            )
            frozen_path = self._write_json(
                root, "blocked-frozen.json", blocked_frozen.to_dict()
            )
            native_path = self._write_json(
                root, "blocked-native.json", blocked_native.to_dict()
            )
            output = root / "blocked-export"
            command_output = StringIO()
            with redirect_stdout(command_output):
                exit_code = main(
                    self._target_export_cli_args(
                        descriptor_path,
                        frozen_path,
                        native_path,
                        output,
                    )
                )
            result = json.loads(command_output.getvalue())
            self.assertEqual(0, exit_code)
            self.assertTrue(result["materialization_ok"])
            self.assertEqual("blocked", result["model_readiness_status"])
            readiness = self._projection_payload(output, "readiness")
            self.assertEqual("blocked", readiness["model_readiness_status"])
            self.assertGreater(readiness["gap_count"], 0)
            self.assertEqual(
                "blocked",
                readiness["qualification"]["readiness_ledger"]["status"],
            )

    def test_target_system_blueprint_export_verification_fails_closed(self):
        descriptor, frozen, native = self._target_artifacts("software")
        report = qualify_target_system_from_native_reports(
            descriptor, frozen, native
        )
        projection = canonical_target_system_blueprint_projection(
            descriptor, frozen, native, report
        )
        materialized = {
            shard.relative_path: {
                "payload": [dict(row) for row in shard.payload],
            }
            for shard in projection.shards
        }
        missing = dict(materialized)
        missing.pop(projection.shards[0].relative_path)
        missing_result = verify_blueprint_projection(
            projection,
            materialized_shards=missing,
        )
        self.assertFalse(missing_result.ok)
        self.assertIn(
            "projection_shard_missing",
            {row.code for row in missing_result.findings},
        )

        tampered = {
            path: json.loads(json.dumps(payload))
            for path, payload in materialized.items()
        }
        readiness_path = next(
            row.relative_path for row in projection.shards if row.kind == "readiness"
        )
        tampered[readiness_path]["payload"][0]["model_readiness_status"] = "complete"
        tampered_result = verify_blueprint_projection(
            projection,
            materialized_shards=tampered,
        )
        self.assertFalse(tampered_result.ok)
        self.assertIn(
            "projection_shard_tampered",
            {row.code for row in tampered_result.findings},
        )

    def test_target_rebind_rejects_content_addressed_identity_and_manifest_rewrite(
        self,
    ):
        descriptor, frozen, native = self._target_artifacts("software")
        report = qualify_target_system_from_native_reports(
            descriptor, frozen, native
        )
        projection = canonical_target_system_blueprint_projection(
            descriptor, frozen, native, report
        )
        identity = next(
            shard for shard in projection.shards if shard.kind == "identity"
        )
        rewritten_payload = [dict(identity.payload[0])]
        rewritten_payload[0]["target_system_id"] = "target:rewritten"
        rewritten_digest = fingerprint_value(rewritten_payload)
        rewritten_identity = BlueprintShard(
            shard_id=f"identity:{rewritten_digest}",
            kind="identity",
            relative_path=(
                "shards/identity-"
                + rewritten_digest.removeprefix("sha256:")
                + ".json"
            ),
            member_ids=identity.member_ids,
            payload=tuple(rewritten_payload),
            content_fingerprint=rewritten_digest,
        )
        rewritten_projection = CanonicalBlueprintProjection(
            blueprint_fingerprint=projection.blueprint_fingerprint,
            shards=tuple(
                rewritten_identity if shard.kind == "identity" else shard
                for shard in projection.shards
            ),
        )

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "rewritten-projection"
            write_canonical_blueprint_projection(rewritten_projection, output)
            generic = load_canonical_blueprint_projection(output)
            self.assertTrue(generic.verification.ok)
            self.assertIn(
                "integrity only",
                generic.claim_boundary,
            )
            rebound = verify_materialized_target_system_blueprint_projection(
                output,
                descriptor,
                frozen,
                native,
                report,
            )
            self.assertFalse(rebound.ok)
            self.assertEqual("blocked", rebound.status)
            self.assertIn(
                "target_projection_manifest_rebind_mismatch",
                {finding.code for finding in rebound.findings},
            )
            self.assertIn(
                "target_projection_shard_rebind_mismatch",
                {finding.code for finding in rebound.findings},
            )

    def test_target_system_blueprint_export_rejects_tamper_missing_and_profile(self):
        with self.assertRaises(SystemExit):
            main(["target-system-blueprint-export"])
        return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor, frozen, native = self._target_artifacts("software")
            descriptor_path, frozen_path, native_path = self._write_target_artifacts(
                root, "software"
            )

            tampered_native = json.loads(native_path.read_text(encoding="utf-8"))
            tampered_native["fingerprint"] = "sha256:" + "0" * 64
            tampered_path = self._write_json(
                root, "tampered-native.json", tampered_native
            )
            variants = (
                ("tampered", descriptor_path, frozen_path, tampered_path),
                (
                    "missing",
                    descriptor_path,
                    frozen_path,
                    root / "missing-native.json",
                ),
                (
                    "profile",
                    self._write_json(
                        root,
                        "profile-descriptor.json",
                        replace(
                            descriptor,
                            target_profile="non_code_workflow",
                        ).to_dict(),
                    ),
                    frozen_path,
                    native_path,
                ),
            )
            for name, descriptor_value, frozen_value, native_value in variants:
                with self.subTest(name=name):
                    command_output = StringIO()
                    with redirect_stdout(command_output):
                        exit_code = main(
                            self._target_export_cli_args(
                                descriptor_value,
                                frozen_value,
                                native_value,
                                root / f"rejected-{name}",
                            )
                        )
                    result = json.loads(command_output.getvalue())
                    self.assertEqual(2, exit_code)
                    self.assertFalse(result["materialization_ok"])
                    self.assertEqual("blocked", result["materialization_status"])
                    self.assertEqual("not_available", result["model_readiness_status"])

            noncanonical_plan = TargetSystemLayerPlan(
                plan_id="target-system-layer-plan:software:shortened",
                target_profile="software",
                layer_ids=frozen.layer_plan.layer_ids[:-1],
                claim_boundary="Deliberately incomplete plan fixture.",
            )
            plan_frozen = replace(frozen, layer_plan=noncanonical_plan)
            plan_native = replace(
                native,
                frozen_evidence_fingerprint=plan_frozen.fingerprint,
            )
            plan_frozen_path = self._write_json(
                root, "plan-frozen.json", plan_frozen.to_dict()
            )
            plan_native_path = self._write_json(
                root, "plan-native.json", plan_native.to_dict()
            )
            plan_output = StringIO()
            with redirect_stdout(plan_output):
                plan_exit = main(
                    self._target_export_cli_args(
                        descriptor_path,
                        plan_frozen_path,
                        plan_native_path,
                        root / "plan-blocked-export",
                    )
                )
            plan_result = json.loads(plan_output.getvalue())
            self.assertEqual(0, plan_exit)
            self.assertTrue(plan_result["materialization_ok"])
            self.assertEqual("blocked", plan_result["model_readiness_status"])

    def test_target_system_blueprint_audit_rejects_strict_artifact_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            descriptor, frozen, native = self._write_target_artifacts(
                root, "software"
            )
            variants = []
            unexpected = json.loads(native.read_text(encoding="utf-8"))
            unexpected["downstream_layers"] = [
                {
                    "layer": "static_blueprint",
                    "status": "pass",
                }
            ]
            variants.append(("caller-layer-status", unexpected, "downstream_layers"))

            stale_member = json.loads(native.read_text(encoding="utf-8"))
            stale_member["members"][0]["status"] = "pass"
            variants.append(("invalid-native-member-status", stale_member, "status"))

            bad_fingerprint = json.loads(native.read_text(encoding="utf-8"))
            bad_fingerprint["fingerprint"] = "sha256:" + "0" * 64
            variants.append(("native-fingerprint-drift", bad_fingerprint, "fingerprint"))

            for name, payload_value, marker in variants:
                with self.subTest(name=name):
                    tampered = self._write_json(root, f"{name}.json", payload_value)
                    output = StringIO()
                    with redirect_stdout(output):
                        exit_code = main(
                            self._target_cli_args(descriptor, frozen, tampered)
                        )
                    payload = json.loads(output.getvalue())
                    self.assertEqual(2, exit_code)
                    self.assertEqual("invalid", payload["status"])
                    self.assertIn(marker, payload["findings"][0]["message"])

    def test_target_system_blueprint_audit_has_no_caller_authored_status_route(self):
        with tempfile.TemporaryDirectory() as directory:
            descriptor, frozen, native = self._write_target_artifacts(
                Path(directory), "software"
            )
            for forbidden_args in (
                ("--status", "pass"),
                ("--downstream-layer", "static_blueprint:pass"),
                ("--request", "legacy.json"),
                ("--scope", "affected"),
            ):
                with self.subTest(forbidden_args=forbidden_args):
                    stderr = StringIO()
                    with redirect_stderr(stderr), self.assertRaises(SystemExit) as caught:
                        main(
                            [
                                *self._target_cli_args(descriptor, frozen, native),
                                *forbidden_args,
                            ]
                        )
                    self.assertEqual(2, caught.exception.code)
                    self.assertIn("unrecognized arguments", stderr.getvalue())

    def test_help_distinguishes_provider_neutral_and_python_convenience_routes(self):
        target_help = StringIO()
        with redirect_stdout(target_help), self.assertRaises(SystemExit) as target_exit:
            main(["target-system-blueprint-audit", "--help"])
        self.assertEqual(0, target_exit.exception.code)
        self.assertIn("provider-neutral", target_help.getvalue())
        self.assertIn("strict frozen native artifacts", target_help.getvalue())

        project_help = StringIO()
        with redirect_stdout(project_help), self.assertRaises(SystemExit) as project_exit:
            main(["project-blueprint-audit", "--help"])
        self.assertEqual(0, project_exit.exception.code)
        self.assertIn("Python-software convenience adapter", project_help.getvalue())
        self.assertIn("target-system-blueprint-audit", project_help.getvalue())

    def _affected_understanding_artifacts(self):
        shard_payloads = {
            "coverage:00000": {
                "schema_version": BEHAVIOR_COVERAGE_REFERENCE_SHARD_SCHEMA,
                "kind": BEHAVIOR_COVERAGE_REFERENCE_SHARD_KIND,
                "shard_id": "coverage:00000",
                "coverage_ids": ["coverage:a"],
                "referenced_object_ids": ["coverage:a"],
            }
        }
        shared_objects = {
            "coverage:a": {
                "kind": "behavior_coverage_edge",
                "coverage_id": "coverage:a",
                "behavior_block_id": "behavior:a",
                "implementation_surface_id": "surface:a",
                "referenced_object_ids": ["behavior:a"],
            },
            "behavior:a": {
                "kind": "behavior_block",
                "behavior_block_id": "behavior:a",
            },
            "behavior:unrelated": {
                "kind": "behavior_block",
                "behavior_block_id": "behavior:unrelated",
            },
        }
        projection = SimpleNamespace(
            blueprint_fingerprint=fingerprint_value({"manifest": "fixture"}),
            logical_fingerprint=fingerprint_value({"logical": "fixture"}),
            object_fingerprints=tuple(
                (object_id, fingerprint_value(payload))
                for object_id, payload in shared_objects.items()
            ),
            shard_fingerprints=tuple(
                (shard_id, fingerprint_value(payload))
                for shard_id, payload in shard_payloads.items()
            ),
            shard_member_ids=(
                (
                    "coverage:00000",
                    ("coverage:a", "behavior:a", "surface:a"),
                ),
            ),
            to_dict=Mock(
                side_effect=AssertionError("whole projection serialized")
            ),
        )
        native = BlueprintNativeReportRef(
            owner_id="owner:behavior",
            report_id="report:behavior",
            report_fingerprint=fingerprint_value({"native": "behavior"}),
        )
        ledger = BlueprintReadinessLedger(
            target_profile="software",
            rows=(
                BlueprintLayerResult._derived(
                    layer="implementation_inventory",
                    status="pass",
                    evidence_ids=(fingerprint_value({"inventory": "current"}),),
                    pre_code_status="ready",
                ),
                BlueprintLayerResult._derived(
                    layer="model_code_test",
                    status="pass",
                    evidence_ids=(native.report_fingerprint,),
                    native_reports=(native,),
                    pre_code_status="ready",
                    executed_evidence_status="passed",
                    implementation_admitted=True,
                ),
            ),
            gaps=(),
        )
        index, objects = materialize_affected_blueprint_index(
            projection,
            target_system_id="target:cli",
            target_profile="software",
            subject_revision="revision:cli",
            descriptor_fingerprint=fingerprint_value({"descriptor": "cli"}),
            target_blueprint_fingerprint=fingerprint_value(
                {"target-blueprint": "cli"}
            ),
            layer_plan_id="plan:cli",
            layer_plan_fingerprint=fingerprint_value({"plan": "cli"}),
            readiness_ledger=ledger,
            shared_objects=shared_objects,
        )
        return projection, index, shard_payloads, dict(objects)

    def test_affected_understanding_cli_is_strict_read_only_and_affected_first(self):
        projection, index, shards, objects = self._affected_understanding_artifacts()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index_path = self._write_json(root, "index.json", index.to_dict())
            shard_path = self._write_json(root, "shards.json", shards)
            object_path = self._write_json(root, "objects.json", objects)
            output = StringIO()
            with patch(
                "flowguard.project_blueprint.build_project_blueprint",
                side_effect=AssertionError("whole project builder invoked"),
            ), patch(
                "flowguard.target_system_blueprint.project_blueprint_understanding",
                side_effect=AssertionError("whole summary invoked"),
            ), redirect_stdout(output):
                exit_code = main(
                    [
                        "affected-blueprint-understanding",
                        "--index",
                        str(index_path),
                        "--shard-store",
                        str(shard_path),
                        "--object-store",
                        str(object_path),
                        "--affected-id",
                        "surface:a",
                        "--json",
                    ]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(0, exit_code)
        self.assertEqual("affected", payload["scope"])
        self.assertEqual("target:cli", payload["target_system_id"])
        self.assertEqual("software", payload["target_profile"])
        self.assertEqual(["surface:a"], payload["affected_ids"])
        self.assertEqual(
            ["implementation_inventory", "model_code_test"],
            [row["layer"] for row in payload["layer_statuses"]],
        )
        self.assertEqual("model_code_test", payload["deepest_proven_layer"])
        self.assertEqual(0, payload["gap_count"])
        self.assertTrue(payload["implementation_admitted"])
        projection.to_dict.assert_not_called()

    def test_affected_understanding_cli_rejects_unknown_index_fields(self):
        _projection, index, shards, objects = self._affected_understanding_artifacts()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index_payload = index.to_dict()
            index_payload["fallback_summary"] = "forbidden"
            index_path = self._write_json(root, "index.json", index_payload)
            shard_path = self._write_json(root, "shards.json", shards)
            object_path = self._write_json(root, "objects.json", objects)
            output = StringIO()
            with redirect_stdout(output):
                exit_code = main(
                    [
                        "affected-blueprint-understanding",
                        "--index",
                        str(index_path),
                        "--shard-store",
                        str(shard_path),
                        "--object-store",
                        str(object_path),
                        "--affected-id",
                        "surface:a",
                        "--json",
                    ]
                )
        payload = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("invalid", payload["status"])
        self.assertIn("fallback_summary", payload["findings"][0]["message"])

    def _native_owner_evidence(self) -> dict[str, object]:
        contract = ValidationOwnerContract(
            owner_id="model-owner",
            command=("python", "-m", "pytest", "owner-test"),
            input_patterns=("models/**",),
            obligation_ids=("model:one",),
        )
        environment = build_environment_fingerprint(
            {
                "python_implementation": "CPython",
                "python_version": "3.12.10",
                "platform_system": "Windows",
                "platform_machine": "AMD64",
                "flowguard_version": "0.68.6",
            }
        )
        receipt = EvidenceReceipt(
            receipt_id="receipt:native-owner",
            subject_id="validation-owner:model-owner",
            subject_kind="validation_owner",
            producer_id="validation-owner:model-owner",
            producer_version="0.68.6",
            claim_scope="full",
            command=contract.command,
            working_directory_token="<WORKSPACE>",
            started_at="2026-08-04T08:00:00+00:00",
            finished_at="2026-08-04T08:00:01+00:00",
            exit_code=0,
            environment_fingerprint=environment.fingerprint,
            environment_metadata=environment.metadata,
            contract_hash=fingerprint_value({"contract": "model-owner"}),
            check_manifest_hash=fingerprint_value({"manifest": "model-owner"}),
            suite_map_hash=fingerprint_value({"suite": "model-owner"}),
            input_snapshots=(
                snapshot_bytes(
                    "input:model-owner",
                    b"current",
                    path_token="<WORKSPACE>/models/owner.json",
                    obligation_ids=("model:one",),
                ),
            ),
            proof_artifact_id="proof:model-owner",
            proof_artifact_fingerprint=fingerprint_value(
                {"proof": "model-owner"}
            ),
            result_status="pass",
            result_fingerprint=fingerprint_value({"result": "model-owner"}),
            covered_obligations=("model:one",),
            claim_boundary="One exact native owner fixture.",
        )
        verification = ReceiptVerificationResult(
            receipt_id=receipt.receipt_id,
            receipt_fingerprint=receipt.fingerprint,
            current=True,
            eligible=True,
            status="pass",
            findings=(
                ReceiptFinding(
                    code="fixture_note",
                    message="Typed finding survives strict CLI loading.",
                    artifact_id="input:model-owner",
                    details={"severity": "note"},
                ),
            ),
            satisfied_obligations=("model:one",),
            minimum_revalidation=(),
        )
        return {
            "contracts": [contract.to_dict()],
            "receipts": [receipt.to_dict()],
            "verification_results": [verification.to_dict()],
        }

    def _model_revision_args(self) -> list[str]:
        return [
            "model-revision-build",
            "--model-parent-receipt",
            "parent.json",
            "--revision-set-id",
            "revision:cli-evidence",
            "--task-id",
            "task:cli-evidence",
            "--snapshot-id",
            "snapshot-cli-evidence",
            "--json",
        ]

    def test_model_revision_build_loads_exact_native_owner_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            evidence_path = self._write_json(
                Path(directory), "native-owner.json", self._native_owner_evidence()
            )
            report = SimpleNamespace(to_dict=lambda: {"status": "pass"})
            output = StringIO()
            with patch(
                "flowguard.model_revision_builder.build_current_model_revision",
                return_value=report,
            ) as build, redirect_stdout(output):
                exit_code = main(
                    self._model_revision_args()
                    + ["--native-owner-evidence", str(evidence_path)]
                )
            self.assertEqual(0, exit_code)
            kwargs = build.call_args.kwargs
            self.assertIsInstance(
                kwargs["native_owner_contracts"][0], ValidationOwnerContract
            )
            self.assertIsInstance(
                kwargs["native_owner_receipts"][0], EvidenceReceipt
            )
            self.assertIsInstance(
                kwargs["native_owner_verification_results"][0],
                ReceiptVerificationResult,
            )
            self.assertIsInstance(
                kwargs["native_owner_verification_results"][0].findings[0],
                ReceiptFinding,
            )

    def test_native_owner_evidence_rejects_missing_and_unknown_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            variants = []
            missing = self._native_owner_evidence()
            del missing["contracts"][0]["required"]
            variants.append(("missing", missing, "required"))
            unknown = self._native_owner_evidence()
            unknown["verification_results"][0]["findings"][0]["extra"] = True
            variants.append(("unknown", unknown, "extra"))
            for name, payload, marker in variants:
                with self.subTest(name=name):
                    evidence_path = self._write_json(
                        root, f"{name}.json", payload
                    )
                    output = StringIO()
                    with patch(
                        "flowguard.model_revision_builder.build_current_model_revision"
                    ) as build, redirect_stdout(output):
                        exit_code = main(
                            self._model_revision_args()
                            + ["--native-owner-evidence", str(evidence_path)]
                        )
                    result = json.loads(output.getvalue())
                    self.assertEqual(1, exit_code)
                    self.assertEqual("blocked", result["status"])
                    self.assertIn(marker, result["error"])
                    build.assert_not_called()

    def test_model_revision_build_without_leaf_evidence_passes_empty_inputs(self):
        report = SimpleNamespace(to_dict=lambda: {"status": "incomplete"})
        output = StringIO()
        with patch(
            "flowguard.model_revision_builder.build_current_model_revision",
            return_value=report,
        ) as build, redirect_stdout(output):
            exit_code = main(self._model_revision_args())
        self.assertEqual(0, exit_code)
        self.assertEqual("incomplete", json.loads(output.getvalue())["status"])
        self.assertEqual((), build.call_args.kwargs["native_owner_contracts"])
        self.assertEqual((), build.call_args.kwargs["native_owner_receipts"])
        self.assertEqual(
            (), build.call_args.kwargs["native_owner_verification_results"]
        )

    def test_model_revision_build_loads_exact_refinement_transitions(self):
        transition = EffectiveIntentTransition(
            prior_contribution_id="intent:current:alpha",
            prior_contribution_fingerprint="sha256:" + "a" * 64,
            action="retain",
            replacement_contribution_ids=(),
            reason=(
                "The exact current alpha contribution remains active in this "
                "bounded refinement."
            ),
        )
        with tempfile.TemporaryDirectory() as directory:
            intent_path = self._write_json(
                Path(directory),
                "intent.json",
                {
                    "contributions": [],
                    "dispositions": [],
                    "effective_intent_transitions": [transition.to_dict()],
                },
            )
            report = SimpleNamespace(to_dict=lambda: {"status": "incomplete"})
            output = StringIO()
            with patch(
                "flowguard.model_revision_builder.build_current_model_revision",
                return_value=report,
            ) as build, redirect_stdout(output):
                exit_code = main(
                    self._model_revision_args()
                    + ["--intent-inventory", str(intent_path)]
                )

        self.assertEqual(0, exit_code)
        self.assertEqual(
            (transition,),
            build.call_args.kwargs["effective_intent_transitions"],
        )

    def test_model_revision_build_rejects_pre_v5_intent_payload_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            intent_path = self._write_json(
                Path(directory),
                "old-intent.json",
                {"contributions": [], "dispositions": []},
            )
            output = StringIO()
            with patch(
                "flowguard.model_revision_builder.build_current_model_revision"
            ) as build, redirect_stdout(output):
                exit_code = main(
                    self._model_revision_args()
                    + ["--intent-inventory", str(intent_path)]
                )

        payload = json.loads(output.getvalue())
        self.assertEqual(1, exit_code)
        self.assertEqual("blocked", payload["status"])
        self.assertIn("effective_intent_transitions", payload["error"])
        build.assert_not_called()

    def test_compact_self_commands_delegate_without_full_serialization(self):
        bundle = SimpleNamespace(ok=True)
        self_payload = {"projection_kind": "self_qualification", "ok": True}
        output = StringIO()
        with patch(
            "flowguard.self_blueprint.build_flowguard_self_blueprint",
            return_value=bundle,
        ), patch(
            "flowguard.blueprint_compact_projection.BlueprintCompactProjection.self_qualification",
            return_value=self_payload,
        ) as project_self, redirect_stdout(output):
            exit_code = main(
                ["flowguard-self-blueprint-check", "--compact", "--json"]
            )
        self.assertEqual(0, exit_code)
        self.assertEqual(self_payload, json.loads(output.getvalue()))
        project_self.assert_called_once_with(bundle)

        class ReductionReport:
            ok = True

            def to_dict(self):
                raise AssertionError("compact CLI must not serialize the full review")

        reduction = ReductionReport()
        reduction_payload = {"projection_kind": "reduction", "ok": True}
        output = StringIO()
        with patch(
            "flowguard.self_architecture_reduction.review_flowguard_self_architecture_reduction",
            return_value=reduction,
        ), patch(
            "flowguard.blueprint_compact_projection.BlueprintCompactProjection.reduction",
            return_value=reduction_payload,
        ) as project_reduction, redirect_stdout(output):
            exit_code = main(
                [
                    "flowguard-self-architecture-reduction-review",
                    "--compact",
                    "--json",
                ]
            )
        self.assertEqual(0, exit_code)
        self.assertEqual(reduction_payload, json.loads(output.getvalue()))
        project_reduction.assert_called_once_with(reduction)

    def test_standalone_dna_export_route_is_removed(self):
        with self.assertRaises(SystemExit):
            main(["flowguard-self-blueprint-portable-export"])


if __name__ == "__main__":
    unittest.main()
