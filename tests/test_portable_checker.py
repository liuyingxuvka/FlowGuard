from __future__ import annotations

from dataclasses import replace
import unittest

from flowguard.portable_checker import check_portable_model, execute_portable_model
from flowguard.portable_model import (
    PortableInvariant,
    PortableModel,
    PortableState,
    PortableTemporalObligation,
    PortableTransition,
)


def eventual_model(*, fairness: bool = True) -> PortableModel:
    obligations = [
        PortableTemporalObligation(
            "eventually-done",
            "eventually",
            trigger_state_ids=("start",),
            target_state_ids=("done",),
        )
    ]
    if fairness:
        obligations.append(
            PortableTemporalObligation(
                "finish-not-starved",
                "weak_fairness",
                trigger_state_ids=("work",),
                transition_ids=("finish",),
            )
        )
    return PortableModel(
        model_id="eventual-work",
        states=(PortableState("start"), PortableState("work"), PortableState("done")),
        transitions=(
            PortableTransition("begin", "start", "go", "started", "work"),
            PortableTransition("wait", "work", "tick", "waiting", "work"),
            PortableTransition("finish", "work", "tick", "complete", "done"),
        ),
        initial_state_ids=("start",),
        terminal_state_ids=("done",),
        temporal_obligations=tuple(obligations),
    )


class PortableCheckerTests(unittest.TestCase):
    def test_weak_fairness_excludes_only_declared_starvation_cycle(self):
        report = check_portable_model(eventual_model(fairness=True))
        self.assertTrue(report.ok, report.to_json_text())
        self.assertIn("finish-not-starved", report.checked_obligation_ids)

    def test_unfair_closed_schedule_is_an_eventual_counterexample(self):
        report = check_portable_model(eventual_model(fairness=False))
        self.assertFalse(report.ok)
        self.assertIn("eventual_cycle", {item.finding_id for item in report.findings})
        self.assertTrue(report.counterexamples)

    def test_forbidden_reachable_state_fails_safety(self):
        model = replace(
            eventual_model(),
            invariants=(PortableInvariant("never-work", ("work",), "work is forbidden"),),
        )
        report = check_portable_model(model)
        self.assertIn(
            "invariant_forbidden_state_reachable",
            {item.finding_id for item in report.findings},
        )

    def test_bounded_eventuality_rejects_late_target(self):
        model = PortableModel(
            model_id="late-target",
            states=(PortableState("a"), PortableState("b"), PortableState("c")),
            transitions=(
                PortableTransition("ab", "a", "tick", "next", "b"),
                PortableTransition("bc", "b", "tick", "done", "c"),
            ),
            initial_state_ids=("a",),
            terminal_state_ids=("c",),
            temporal_obligations=(
                PortableTemporalObligation(
                    "done-in-one",
                    "bounded_eventually",
                    trigger_state_ids=("a",),
                    target_state_ids=("c",),
                    max_steps=1,
                ),
            ),
        )
        report = check_portable_model(model)
        self.assertIn("bounded_eventually_exceeded", {item.finding_id for item in report.findings})

    def test_never_enabled_fairness_transition_is_rejected(self):
        model = PortableModel(
            model_id="unreachable-fairness",
            states=(PortableState("start"), PortableState("ghost"), PortableState("done")),
            transitions=(PortableTransition("ghost-finish", "ghost", "go", "ok", "done"),),
            initial_state_ids=("start",),
            terminal_state_ids=("done",),
            temporal_obligations=(
                PortableTemporalObligation(
                    "ghost-fair",
                    "weak_fairness",
                    trigger_state_ids=("ghost",),
                    transition_ids=("ghost-finish",),
                ),
            ),
        )
        report = check_portable_model(model)
        self.assertIn("fairness_transition_unreachable", {item.finding_id for item in report.findings})

    def test_reachable_graph_bound_is_visible_blocker(self):
        report = check_portable_model(eventual_model(), max_states=1)
        self.assertEqual("blocked", report.status)
        self.assertTrue(report.blockers)

    def test_explicit_execution_preserves_nondeterministic_traces(self):
        model = PortableModel(
            model_id="branches",
            states=(PortableState("a"), PortableState("b"), PortableState("c")),
            transitions=(
                PortableTransition("left", "a", "go", "left", "b"),
                PortableTransition("right", "a", "go", "right", "c"),
            ),
            initial_state_ids=("a",),
            terminal_state_ids=("b", "c"),
        )
        report = execute_portable_model(model, ("go",))
        self.assertEqual("pass", report.status)
        self.assertEqual(2, len(report.traces))
        blocked = execute_portable_model(model, ("go",), max_traces=1)
        self.assertEqual("blocked", blocked.status)


if __name__ == "__main__":
    unittest.main()
