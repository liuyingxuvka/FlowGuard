import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from flowguard import (
    BudgetedGraphConfig,
    Invariant,
    InvariantResult,
    budgeted_graph_fingerprint,
    run_budgeted_graph_checks,
)


class BudgetedGraphRunnerTests(unittest.TestCase):
    def test_single_shard_completion_reports_ok(self):
        def transition(state):
            if state < 2:
                return (("advance", state + 1),)
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "single-shard",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=10,
                required_labels=("advance",),
                progress_steps=0,
            )

            report = run_budgeted_graph_checks(config)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(report.status, "complete")
        self.assertTrue(report.complete)
        self.assertEqual(report.processed_state_count, 3)
        self.assertEqual(report.pending_state_count, 0)
        self.assertEqual(report.edge_count, 2)
        self.assertEqual(report.missing_labels, ())

    def test_budget_cap_splits_work_and_resume_does_not_restart(self):
        visited = []

        def transition(state):
            visited.append(state)
            if state < 3:
                return (("advance", state + 1),)
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "resume",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=2,
                progress_steps=0,
            )

            first = run_budgeted_graph_checks(config)
            second = run_budgeted_graph_checks(config)

        self.assertFalse(first.ok)
        self.assertEqual(first.status, "incomplete")
        self.assertEqual(first.processed_this_run, 2)
        self.assertEqual(first.pending_state_count, 1)
        self.assertEqual(second.status, "complete")
        self.assertEqual(second.processed_state_count, 4)
        self.assertEqual(second.processed_this_run, 2)
        self.assertEqual(visited, [0, 1, 2, 3])

    def test_complete_result_is_reused_without_rerunning_transitions(self):
        calls = []

        def transition(state):
            calls.append(state)
            if state < 1:
                return (("advance", state + 1),)
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "reuse-complete",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=10,
                progress_steps=0,
            )

            first = run_budgeted_graph_checks(config)
            second = run_budgeted_graph_checks(config)

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertTrue(second.reused_complete_result)
        self.assertEqual(second.processed_this_run, 0)
        self.assertEqual(calls, [0, 1])

    def test_fingerprint_change_uses_separate_ledger(self):
        def transition(state):
            if state < 1:
                return (("advance", state + 1),)
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            v1 = BudgetedGraphConfig(
                "fingerprint",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=10,
                fingerprint_parts=("v1",),
                progress_steps=0,
            )
            v2 = BudgetedGraphConfig(
                "fingerprint",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=10,
                fingerprint_parts=("v2",),
                progress_steps=0,
            )

            first = run_budgeted_graph_checks(v1)
            second = run_budgeted_graph_checks(v2)

        self.assertTrue(first.ok)
        self.assertTrue(second.ok)
        self.assertNotEqual(budgeted_graph_fingerprint(v1), budgeted_graph_fingerprint(v2))
        self.assertNotEqual(first.run_dir, second.run_dir)
        self.assertEqual(second.processed_this_run, 2)

    def test_required_label_is_checked_across_whole_group(self):
        def transition(state):
            if state == 0:
                return (("early", 1),)
            if state == 1:
                return (("middle", 2),)
            if state == 2:
                return (("late", 3),)
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "global-label",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=2,
                required_labels=("late",),
                progress_steps=0,
            )

            first = run_budgeted_graph_checks(config)
            second = run_budgeted_graph_checks(config)

        self.assertEqual(first.status, "incomplete")
        self.assertEqual(first.missing_labels, ("late",))
        self.assertTrue(second.ok, second.format_text())
        self.assertIn("late", second.labels)
        self.assertEqual(second.missing_labels, ())

    def test_invariant_failure_in_later_shard_fails_whole_group(self):
        def transition(state):
            if state < 3:
                return (("advance", state + 1),)
            return ()

        def below_three(state, _trace):
            if state < 3:
                return InvariantResult.pass_()
            return InvariantResult.fail("state reached forbidden value")

        invariant = Invariant("below_three", "State must remain below three.", below_three)

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "late-failure",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=2,
                invariants=(invariant,),
                progress_steps=0,
            )

            first = run_budgeted_graph_checks(config)
            second = run_budgeted_graph_checks(config)

        self.assertEqual(first.status, "incomplete")
        self.assertEqual(first.failure_count, 0)
        self.assertFalse(second.ok)
        self.assertEqual(second.status, "failed")
        self.assertEqual(second.failure_count, 1)
        self.assertEqual(second.failures[0].name, "below_three")

    def test_duplicate_state_is_not_reprocessed(self):
        visited = []

        def transition(state):
            visited.append(state)
            if state == 0:
                return (("left", 1), ("right", 1))
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "duplicates",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=10,
                progress_steps=0,
            )

            report = run_budgeted_graph_checks(config)

        self.assertTrue(report.ok, report.format_text())
        self.assertEqual(report.known_state_count, 2)
        self.assertEqual(report.processed_state_count, 2)
        self.assertEqual(report.edge_count, 2)
        self.assertEqual(visited, [0, 1])

    def test_progress_output_contains_shard_and_group_context(self):
        def transition(state):
            if state < 2:
                return (("advance", state + 1),)
            return ()

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            config = BudgetedGraphConfig(
                "progress-output",
                (0,),
                transition,
                run_root=Path(tmp),
                budget_per_shard=2,
                progress_steps=2,
            )
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                report = run_budgeted_graph_checks(config)

        output = stderr.getvalue()
        self.assertEqual(report.status, "incomplete")
        self.assertIn("[flowguard-budget] start model=progress-output shard=1", output)
        self.assertIn("[flowguard-budget] progress model=progress-output shard=1", output)
        self.assertIn("total_processed=", output)
        self.assertIn("pending=", output)
        self.assertIn("[flowguard-budget] shard_end model=progress-output shard=1", output)


if __name__ == "__main__":
    unittest.main()
