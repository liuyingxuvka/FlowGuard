import unittest

import flowguard
from flowguard import (
    EVIDENCE_GATE_STATUS_NOT_RUN,
    EVIDENCE_GATE_STATUS_PASSED,
    EVIDENCE_GATE_STATUS_PROGRESS_ONLY,
    EvidenceGate,
    ProcessEvidence,
    evidence_gates_from_process_like,
    summarize_evidence_gates,
)


class EvidenceFieldStructureTests(unittest.TestCase):
    def test_required_gate_keeps_skipped_and_stale_visible(self):
        gates = (
            EvidenceGate("fresh", "test", result_status=EVIDENCE_GATE_STATUS_PASSED, current=True),
            EvidenceGate("skipped", "test", result_status="skipped", current=True),
            EvidenceGate("stale", "test", result_status=EVIDENCE_GATE_STATUS_PASSED, current=False),
        )

        summary = summarize_evidence_gates(gates)

        self.assertFalse(summary["ok"])
        self.assertEqual(["skipped", "stale"], summary["visible_gap_ids"])
        self.assertEqual(["passed", "skipped"], summary["non_passing_statuses"])

    def test_evidence_gate_replaces_duplicate_detail_helpers(self):
        command = EvidenceGate(
            "full_pytest",
            "command",
            result_status=EVIDENCE_GATE_STATUS_PASSED,
            current=True,
            proof_evidence_ids=("tmp/full_pytest_output.txt",),
            metadata={"command": "python -m pytest"},
        )
        background = EvidenceGate(
            "background",
            "background",
            result_status=EVIDENCE_GATE_STATUS_PROGRESS_ONLY,
            current=False,
        )

        self.assertTrue(command.passing)
        self.assertEqual(("tmp/full_pytest_output.txt",), command.proof_evidence_ids)
        self.assertEqual("python -m pytest", command.metadata["command"])
        self.assertFalse(background.passing)
        self.assertTrue(background.visible_gap)

    def test_duplicate_detail_helpers_are_not_public_api(self):
        removed = {
            "CommandEvidenceDetail",
            "BackgroundEvidenceDetail",
            "MeshSplitEvidenceDetail",
        }

        for name in removed:
            self.assertNotIn(name, flowguard.__all__)
            self.assertNotIn(name, flowguard.EVIDENCE_API)
            self.assertNotIn(name, flowguard.EVIDENCE_FIELD_STRUCTURE_API)
            self.assertFalse(hasattr(flowguard, name), name)

    def test_process_like_conversion_keeps_progress_only_gap_without_split_projection(self):
        evidence = ProcessEvidence(
            evidence_id="full-regression",
            evidence_kind="test",
            producer_route="development_process_flow",
            status=EVIDENCE_GATE_STATUS_PASSED,
            command="python -m pytest",
            result_path="tmp/full-regression.txt",
            background=True,
            has_exit_artifact=False,
            has_result_artifact=False,
            progress_only=True,
        )

        gates = evidence_gates_from_process_like(evidence)
        summary = summarize_evidence_gates(gates)

        self.assertEqual(("process_command", "process_background"), tuple(gate.gate_id for gate in gates))
        self.assertFalse(summary["ok"])
        self.assertIn("process_background", summary["visible_gap_ids"])
        self.assertNotIn("process_mesh_split", summary["visible_gap_ids"])

    def test_old_auto_split_fields_are_rejected_by_process_evidence(self):
        for kwargs in (
            {"observed_state_count": 20_000},
            {"duration_seconds": 301},
            {"auto_split_gate_id": "split"},
            {"auto_split_current": False},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(TypeError):
                    ProcessEvidence("evidence", **kwargs)


if __name__ == "__main__":
    unittest.main()
