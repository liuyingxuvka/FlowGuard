import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import flowguard
from flowguard import (
    BCL_ACTOR_AI_AGENT,
    BCL_ACTOR_AUTOMATION,
    BCL_ACTOR_END_USER,
    BCL_HIT_ROLE_GOVERNING_PROCESS,
    BCL_HIT_ROLE_INVOKED_TARGET,
    BCL_LOOKUP_STATUS_BLOCKED,
    BCL_LOOKUP_STATUS_PERFORMED,
    BCL_PLANE_AGENT_OPERATION,
    BCL_PLANE_DEVELOPMENT_PROCESS,
    BCL_PLANE_PRODUCT_RUNTIME,
    BCL_RELATION_INVOKES,
    BCL_RELATION_VALIDATES,
    BehaviorCommitment,
    BehaviorCommitmentLedger,
    BehaviorCommitmentRelation,
    BehaviorLookupBinding,
    BehaviorLookupQuery,
    behavior_commitment_ledger_fingerprint,
    behavior_commitment_ledger_to_mapping,
    existing_model_preflight_from_project,
    query_behavior_commitments,
    query_behavior_commitments_from_path,
    review_existing_model_preflight,
    write_behavior_commitment_ledger,
)


ROOT = Path(__file__).resolve().parents[1]


def commitment(
    commitment_id: str,
    *,
    plane: str,
    actor_kind: str,
    owner: str,
    terms=(),
    paths=(),
    tools=(),
    errors=(),
    workflows=(),
    relations=(),
    label: str = "",
) -> BehaviorCommitment:
    return BehaviorCommitment(
        commitment_id,
        label=label or commitment_id,
        behavior_plane=plane,
        actor_kind=actor_kind,
        actor=actor_kind,
        trigger="matching task is requested",
        expected_result="the registered behavior is reused",
        failure_boundary="return a visible, repairable failure",
        primary_owner_model_id=owner,
        lookup_binding=BehaviorLookupBinding(
            task_terms=terms,
            path_patterns=paths,
            tool_ids=tools,
            error_signatures=errors,
            workflow_families=workflows,
        ),
        relations=relations,
        validation_boundary="lookup and owner-model evidence",
        rationale="test commitment",
    )


def three_plane_ledger() -> BehaviorCommitmentLedger:
    product = commitment(
        "commitment:product-download",
        plane=BCL_PLANE_PRODUCT_RUNTIME,
        actor_kind=BCL_ACTOR_END_USER,
        owner="model:product-download",
        terms=("download", "export file"),
        paths=("flowguard/ui/download.py",),
        label="user downloads a generated file",
    )
    agent = commitment(
        "commitment:agent-port-bridge",
        plane=BCL_PLANE_AGENT_OPERATION,
        actor_kind=BCL_ACTOR_AI_AGENT,
        owner="model:agent-port-bridge",
        terms=("download", "ui port bridge", "connect test port"),
        paths=("scripts/connect_ui_ports.py",),
        tools=("port-health-check",),
        errors=("ECONNREFUSED:4173",),
        workflows=("ui_test_handoff",),
        relations=(
            BehaviorCommitmentRelation(
                "commitment:product-download",
                BCL_RELATION_INVOKES,
                "The AI operation invokes the product boundary but does not own it.",
            ),
        ),
        label="AI connects the tested UI port before handoff",
    )
    process = commitment(
        "commitment:process-release-validation",
        plane=BCL_PLANE_DEVELOPMENT_PROCESS,
        actor_kind=BCL_ACTOR_AUTOMATION,
        owner="model:release-validation",
        terms=("download", "release validation", "background regression"),
        workflows=("release_process",),
        relations=(
            BehaviorCommitmentRelation(
                "commitment:agent-port-bridge",
                BCL_RELATION_VALIDATES,
                "The development process validates the AI-operation receipt.",
            ),
        ),
        label="release process validates operational receipts",
    )
    commitments = (product, agent, process)
    return BehaviorCommitmentLedger(
        "ledger:three-planes",
        project_boundary="three-plane lookup tests",
        current_revision="rev-1",
        commitments=commitments,
        expected_commitment_ids=tuple(row.commitment_id for row in commitments),
        owner="tests",
        validation_boundary="deterministic lookup",
        rationale="prove same words do not collapse execution planes",
    )


class BehaviorCommitmentLookupTests(unittest.TestCase):
    def test_explicit_plane_filters_before_shared_language_scoring(self):
        report = query_behavior_commitments(
            three_plane_ledger(),
            BehaviorLookupQuery(
                task_summary="download after the UI test",
                primary_plane=BCL_PLANE_AGENT_OPERATION,
            ),
        )

        self.assertTrue(report.ok, report.to_dict())
        self.assertEqual(BCL_PLANE_AGENT_OPERATION, report.selected_plane)
        self.assertEqual(
            ("commitment:agent-port-bridge",),
            tuple(hit.commitment_id for hit in report.primary_hits),
        )
        self.assertNotIn(
            "commitment:product-download",
            {hit.commitment_id for hit in report.primary_hits},
        )

    def test_port_bridge_error_and_tool_are_explainable_exact_matches(self):
        report = query_behavior_commitments(
            three_plane_ledger(),
            BehaviorLookupQuery(
                task_summary="UI handoff failed",
                primary_plane=BCL_PLANE_AGENT_OPERATION,
                changed_paths=("scripts/connect_ui_ports.py",),
                tool_ids=("port-health-check",),
                error_signatures=("ECONNREFUSED:4173 while checking UI",),
                workflow_families=("ui_test_handoff",),
            ),
        )

        hit = report.primary_hits[0]
        self.assertEqual("commitment:agent-port-bridge", hit.commitment_id)
        reasons = set(hit.match_reasons)
        self.assertIn("tool_id:port-health-check", reasons)
        self.assertIn("path_pattern:scripts/connect_ui_ports.py", reasons)
        self.assertIn("error_signature:ECONNREFUSED:4173", reasons)
        self.assertIn("workflow_family:ui_test_handoff", reasons)

    def test_typed_cross_plane_context_never_becomes_primary(self):
        report = query_behavior_commitments(
            three_plane_ledger(),
            BehaviorLookupQuery(
                task_summary="connect test port",
                primary_plane=BCL_PLANE_AGENT_OPERATION,
            ),
        )

        self.assertEqual(
            {"commitment:agent-port-bridge"},
            {hit.commitment_id for hit in report.primary_hits},
        )
        related = {(hit.commitment_id, hit.hit_role) for hit in report.related_hits}
        self.assertIn(
            ("commitment:product-download", BCL_HIT_ROLE_INVOKED_TARGET),
            related,
        )
        self.assertIn(
            ("commitment:process-release-validation", BCL_HIT_ROLE_GOVERNING_PROCESS),
            related,
        )

    def test_unclassified_shared_term_returns_ambiguity_not_a_guessed_owner(self):
        report = query_behavior_commitments(
            three_plane_ledger(),
            BehaviorLookupQuery(task_summary="download"),
        )

        self.assertEqual(BCL_LOOKUP_STATUS_PERFORMED, report.status)
        self.assertTrue(report.plane_ambiguity)
        self.assertEqual((), report.primary_hits)
        self.assertEqual(
            {
                BCL_PLANE_PRODUCT_RUNTIME,
                BCL_PLANE_AGENT_OPERATION,
                BCL_PLANE_DEVELOPMENT_PROCESS,
            },
            set(report.plane_candidates),
        )
        self.assertTrue(report.candidate_hits)

    def test_top_k_is_bounded_and_deterministic(self):
        ledger = three_plane_ledger()
        query = BehaviorLookupQuery(
            task_summary="download",
            primary_plane=BCL_PLANE_PRODUCT_RUNTIME,
            top_k=1,
        )

        first = query_behavior_commitments(ledger, query).to_dict()
        second = query_behavior_commitments(ledger, query).to_dict()

        self.assertEqual(first, second)
        self.assertLessEqual(len(first["primary_hits"]), 1)

    def test_missing_ledger_is_a_blocked_lookup_with_status_reason(self):
        report = query_behavior_commitments_from_path(
            Path("missing") / "ledger.json",
            BehaviorLookupQuery(task_summary="download"),
        )

        self.assertEqual(BCL_LOOKUP_STATUS_BLOCKED, report.status)
        self.assertFalse(report.ok)
        self.assertIn("ledger", report.status_reason.lower())
        self.assertNotIn("fallback_reason", report.to_dict())

    def test_fingerprint_and_canonical_json_are_stable_and_content_bound(self):
        ledger = three_plane_ledger()
        same = three_plane_ledger()
        changed_rows = list(same.commitments)
        changed_rows[0] = commitment(
            "commitment:product-download",
            plane=BCL_PLANE_PRODUCT_RUNTIME,
            actor_kind=BCL_ACTOR_END_USER,
            owner="model:product-download",
            terms=("download",),
            label="changed label",
        )
        changed = BehaviorCommitmentLedger(
            same.ledger_id,
            project_boundary=same.project_boundary,
            current_revision=same.current_revision,
            commitments=tuple(changed_rows),
            expected_commitment_ids=same.expected_commitment_ids,
            owner=same.owner,
            validation_boundary=same.validation_boundary,
            rationale=same.rationale,
        )

        self.assertEqual(
            behavior_commitment_ledger_fingerprint(ledger),
            behavior_commitment_ledger_fingerprint(same),
        )
        self.assertNotEqual(
            behavior_commitment_ledger_fingerprint(ledger),
            behavior_commitment_ledger_fingerprint(changed),
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "ledger.json"
            write_behavior_commitment_ledger(target, ledger)
            payload = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(behavior_commitment_ledger_to_mapping(ledger), payload)

    def test_lookup_api_stays_under_existing_route_owners(self):
        self.assertNotIn("behavior_commitment_lookup", flowguard.FLOWGUARD_ROUTE_API)
        self.assertIn(
            "query_behavior_commitments",
            flowguard.FLOWGUARD_ROUTE_API["behavior_commitment_ledger"],
        )
        self.assertIn(
            "query_behavior_commitments",
            flowguard.FLOWGUARD_ROUTE_API["existing_model_preflight"],
        )

    def test_read_only_cli_matches_api_result_and_does_not_change_ledger(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
            write_behavior_commitment_ledger(target, three_plane_ledger())
            before = target.read_bytes()
            query = BehaviorLookupQuery(
                task_summary="connect test port",
                primary_plane=BCL_PLANE_AGENT_OPERATION,
                top_k=2,
            )
            api = query_behavior_commitments(three_plane_ledger(), query)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "flowguard",
                    "behavior-commitment-query",
                    query.task_summary,
                    "--root",
                    directory,
                    "--plane",
                    BCL_PLANE_AGENT_OPERATION,
                    "--top-k",
                    "2",
                    "--json",
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(0, completed.returncode, completed.stdout + completed.stderr)
            payload = json.loads(completed.stdout)
            self.assertEqual(api.to_dict()["primary_hits"], payload["primary_hits"])
            self.assertEqual(api.ledger_fingerprint, payload["ledger_fingerprint"])
            self.assertEqual(before, target.read_bytes())

    def test_existing_model_preflight_uses_plane_lookup_before_path_inventory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / ".flowguard" / "behavior_commitment_ledger" / "ledger.json"
            write_behavior_commitment_ledger(target, three_plane_ledger())

            preflight = existing_model_preflight_from_project(
                root,
                "UI handoff hit ECONNREFUSED:4173",
                behavior_plane=BCL_PLANE_AGENT_OPERATION,
                error_signatures=("ECONNREFUSED:4173",),
                downstream_routes=("model_miss_review", "development_process_flow"),
            )
            report = review_existing_model_preflight(preflight)

            self.assertTrue(report.ok, report.format_text())
            self.assertEqual(BCL_LOOKUP_STATUS_PERFORMED, preflight.behavior_lookup_status)
            self.assertEqual(BCL_PLANE_AGENT_OPERATION, preflight.primary_behavior_plane)
            self.assertEqual(
                ("commitment:agent-port-bridge",),
                tuple(hit.commitment_id for hit in preflight.primary_commitment_hits),
            )
            self.assertIn(
                "commitment:product-download",
                {hit.commitment_id for hit in preflight.related_commitment_hits},
            )
            self.assertIn(
                "model:agent-port-bridge",
                {hit.model_id for hit in preflight.relevant_models},
            )


if __name__ == "__main__":
    unittest.main()
