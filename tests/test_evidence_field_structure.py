import unittest

from flowguard import (
    BackgroundEvidenceDetail,
    CommandEvidenceDetail,
    EVIDENCE_GATE_STATUS_NOT_RUN,
    EVIDENCE_GATE_STATUS_PASSED,
    EVIDENCE_GATE_STATUS_PROGRESS_ONLY,
    EvidenceGate,
    MeshSplitEvidenceDetail,
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

    def test_background_progress_only_does_not_pass(self):
        gate = BackgroundEvidenceDetail(
            background=True,
            has_exit_artifact=False,
            has_result_artifact=False,
            progress_only=True,
        ).to_gate()

        self.assertEqual(EVIDENCE_GATE_STATUS_PROGRESS_ONLY, gate.result_status)
        self.assertFalse(gate.passing)
        self.assertTrue(gate.visible_gap)

    def test_command_detail_preserves_result_artifact_reference(self):
        gate = CommandEvidenceDetail(
            command="python -m pytest",
            result_status=EVIDENCE_GATE_STATUS_PASSED,
            current=True,
            result_path="tmp/full_pytest_output.txt",
        ).to_gate("full_pytest")

        self.assertTrue(gate.passing)
        self.assertEqual(("tmp/full_pytest_output.txt",), gate.proof_evidence_ids)
        self.assertEqual("python -m pytest", gate.metadata["command"])

    def test_mesh_split_detail_remains_not_run_until_current(self):
        gate = MeshSplitEvidenceDetail(
            gate_id="auto_split",
            current=False,
            confidence="scoped",
            suggested_child_ids=("child-a",),
            scoped_reasons=("too-large",),
        ).to_gate()

        self.assertEqual(EVIDENCE_GATE_STATUS_NOT_RUN, gate.result_status)
        self.assertFalse(gate.passing)
        self.assertEqual(("too-large",), gate.scoped_reasons)

    def test_process_like_conversion_keeps_progress_only_gap(self):
        evidence = ProcessEvidence(
            evidence_id="full-regression",
            evidence_kind="test",
            producer_route="development_process_flow",
            status=EVIDENCE_GATE_STATUS_PASSED,
            command="python -m pytest",
            background=True,
            has_exit_artifact=False,
            has_result_artifact=False,
            progress_only=True,
            auto_split_gate_id="split",
            auto_split_current=False,
        )

        gates = evidence_gates_from_process_like(evidence)
        summary = summarize_evidence_gates(gates)

        self.assertFalse(summary["ok"])
        self.assertIn("process_background", summary["visible_gap_ids"])
        self.assertIn("split", summary["visible_gap_ids"])


if __name__ == "__main__":
    unittest.main()
