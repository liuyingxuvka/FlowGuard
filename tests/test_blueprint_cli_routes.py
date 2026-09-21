import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import replace
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from flowguard.__main__ import _JsonObjectStoreLocator, main
from flowguard.affected_blueprint_reader import materialize_affected_blueprint_index
from flowguard.affected_blueprint_reader import load_affected_blueprint_projection
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
from flowguard.model_authority_store import load_current_model_authority_state
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

    def test_retired_target_system_blueprint_audit_route_is_rejected(self):
        self._assert_retired_compact_route(
            "target-system-blueprint-audit",
            "--descriptor",
            "descriptor.json",
            "--frozen-evidence",
            "frozen.json",
            "--native-report-set",
            "native.json",
        )

    def test_retired_target_system_blueprint_export_route_is_rejected(self):
        self._assert_retired_compact_route(
            "target-system-blueprint-export",
            "--descriptor",
            "descriptor.json",
            "--frozen-evidence",
            "frozen.json",
            "--native-report-set",
            "native.json",
            "--output",
            "projection",
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

    def test_retired_target_system_blueprint_export_rejects_legacy_artifacts(self):
        for arguments in (
            ("--descriptor", "tampered.json"),
            ("--frozen-evidence", "missing.json"),
            ("--native-report-set", "stale.json"),
            ("--scope", "affected"),
        ):
            with self.subTest(arguments=arguments):
                self._assert_retired_compact_route(
                    "target-system-blueprint-export", *arguments
                )

    def test_retired_target_system_blueprint_audit_rejects_legacy_artifacts(self):
        for arguments in (
            ("--status", "pass"),
            ("--downstream-layer", "static_blueprint:pass"),
            ("--request", "legacy.json"),
            ("--scope", "affected"),
        ):
            with self.subTest(arguments=arguments):
                self._assert_retired_compact_route(
                    "target-system-blueprint-audit", *arguments
                )

    def test_compact_help_exposes_only_current_routes(self):
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main(["--help"])
        help_text = output.getvalue()
        self.assertEqual(0, exit_code)
        self.assertIn("{read,change,release}", help_text)
        self.assertIn("read (side-effect free)", help_text)
        self.assertIn("legacy profiles and command names are rejected", help_text)
        self.assertNotIn("target-system-blueprint-audit", help_text)
        self.assertNotIn("project-blueprint-audit", help_text)

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

    def _assert_retired_affected_understanding_route(self, *arguments: str) -> None:
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main([
                "affected-blueprint-understanding",
                *arguments,
                "--json",
            ])
        payload = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(
            "unknown operation: affected-blueprint-understanding",
            payload["error"],
        )
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def _assert_retired_compact_route(
        self, operation: str, *arguments: str
    ) -> None:
        """Retired pre-compact routes must fail before any producer starts."""
        output = StringIO()
        with redirect_stdout(output):
            exit_code = main([operation, *arguments, "--json"])
        payload = json.loads(output.getvalue())
        self.assertEqual(2, exit_code)
        self.assertEqual("blocked", payload["status"])
        self.assertEqual("block", payload["decision"])
        self.assertEqual(0, payload["producer_count"])
        self.assertEqual(f"unknown operation: {operation}", payload["error"])
        self.assertEqual(["read", "change", "release"], payload["allowed_operations"])

    def test_retired_affected_understanding_cli_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--index", "missing-index.json", "--affected-id", "surface:a"
        )

    def test_retired_affected_understanding_batch_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--affected-id", "surface:a", "--affected-id", "behavior:a"
        )

    def test_retired_affected_projection_merge_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--projection-root", "projection", "--changed-path", "src/a.py"
        )

    def test_retired_affected_index_validation_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--index", "index.json", "--shard-store", "shards.json",
            "--object-store", "objects.json", "--affected-id", "surface:a",
        )

    def _write_selective_projection_fixture(self, directory: Path) -> Path:
        _projection, index, shard_payloads, objects = self._affected_understanding_artifacts()
        authority = load_current_model_authority_state(Path.cwd())
        canonical_blueprint_fingerprint = fingerprint_value(
            {"canonical": "affected-cli", "snapshot": authority.snapshot.fingerprint}
        )

        def shard(kind: str, payload: list[dict[str, object]]) -> BlueprintShard:
            digest = fingerprint_value(payload)
            return BlueprintShard(
                shard_id=f"{kind}:{digest}",
                kind=kind,
                relative_path=f"shards/{kind}-{digest.removeprefix('sha256:')}.json",
                member_ids=tuple(
                    str(row.get("object_id", row.get("shard_id", "")))
                    for row in payload
                    if isinstance(row, dict)
                ),
                payload=tuple(payload),
                content_fingerprint=digest,
            )

        identity = {
            "schema_version": "1.2",
            "blueprint_id": "fixture-blueprint",
            "projection_kind": "project_blueprint",
            "blueprint_fingerprint": canonical_blueprint_fingerprint,
            "project_blueprint_fingerprint": canonical_blueprint_fingerprint,
            "target_blueprint_fingerprint": index.blueprint_fingerprint,
            "subject_revision": authority.snapshot.fingerprint,
            "software_manifest": {
                "observed_snapshot_fingerprint": authority.snapshot.fingerprint,
            },
            "child_fingerprints": {"affected_index": index.fingerprint},
        }
        inventory = {
            "inventory_id": "inventory:fixture",
            "surfaces": [
                {
                    "surface_id": "surface:a",
                    "path": "src/a.py",
                    "symbol": "run",
                }
            ],
        }
        projection = CanonicalBlueprintProjection(
            blueprint_fingerprint=canonical_blueprint_fingerprint,
            shards=(
                shard("identity", [identity]),
                shard("affected_index", [index.to_dict()]),
                shard("behavior_shards", list(shard_payloads.values())),
                shard(
                    "shared_objects",
                    [
                        {"object_id": object_id, "value": value}
                        for object_id, value in sorted(objects.items())
                    ],
                ),
                shard("implementation_inventory", [inventory]),
            ),
        )
        output = directory / "projection"
        write_canonical_blueprint_projection(projection, output)
        return output

    def test_retired_affected_projection_reader_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--projection-root", "projection", "--affected-id", "surface:a"
        )

    def test_retired_affected_snapshot_verification_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--accepted-snapshot-verified", "--affected-id", "surface:a"
        )

    def test_retired_affected_projection_path_validation_route_is_rejected(self):
        self._assert_retired_affected_understanding_route(
            "--projection-root", "..\\outside", "--affected-id", "surface:a"
        )

    def test_json_object_store_locator_reuses_one_index_and_resets_after_close(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "objects.json"
            path.write_text(
                json.dumps({f"object:{index}": {"value": index} for index in range(10)}),
                encoding="utf-8",
            )
            locator = _JsonObjectStoreLocator(path, "fixture object store")
            with patch.object(locator, "_scan_value_end", wraps=locator._scan_value_end) as scan:
                self.assertEqual(9, locator.load("object:9")["value"])
                self.assertEqual(0, locator.load("object:0")["value"])
                self.assertEqual(9, locator.load("object:9")["value"])
                self.assertEqual(10, scan.call_count)
            locator.close()
            self.assertEqual(5, locator.load("object:5")["value"])
            locator.close()

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

    def test_retired_model_revision_build_route_is_rejected(self):
        self._assert_retired_compact_route(
            "model-revision-build",
            "--model-parent-receipt",
            "parent.json",
            "--revision-set-id",
            "revision:cli-evidence",
            "--task-id",
            "task:cli-evidence",
            "--snapshot-id",
            "snapshot-cli-evidence",
        )

    def test_retired_model_revision_build_rejects_native_owner_arguments(self):
        self._assert_retired_compact_route(
            "model-revision-build",
            "--native-owner-evidence",
            "native-owner.json",
        )

    def test_retired_model_revision_build_rejects_without_leaf_evidence(self):
        self._assert_retired_compact_route("model-revision-build")

    def test_retired_model_revision_build_rejects_intent_inventory(self):
        self._assert_retired_compact_route(
            "model-revision-build",
            "--intent-inventory",
            "intent.json",
        )

    def test_retired_model_revision_build_rejects_legacy_intent_shape(self):
        self._assert_retired_compact_route(
            "model-revision-build",
            "--intent-inventory",
            "old-intent.json",
        )

    def test_retired_compact_self_commands_are_rejected(self):
        self._assert_retired_compact_route(
            "flowguard-self-blueprint-check", "--compact"
        )
        self._assert_retired_compact_route(
            "flowguard-self-architecture-reduction-review", "--compact"
        )

if __name__ == "__main__":
    unittest.main()
