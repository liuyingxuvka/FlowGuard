from __future__ import annotations

from dataclasses import replace
import unittest

from flowguard.model_path_quality import (
    PathQualityResult,
    PathQualitySubject,
    canonical_fingerprint,
    derive_retained_elements,
    lightweight_path_review,
    normalized_model_facts_fingerprint,
)
from flowguard.portable_checker import check_portable_model, execute_portable_model
from flowguard.portable_model import (
    PortableInvariant,
    PortableModel,
    PortableState,
    PortableTemporalObligation,
    PortableTransition,
)
from flowguard.portable_path_quality import compile_portable_path_quality_facts


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


def _fingerprint(value: str) -> str:
    return canonical_fingerprint({"value": value})


def path_quality_pair(
    model: PortableModel,
) -> tuple[PathQualitySubject, PathQualityResult]:
    facts = compile_portable_path_quality_facts(model)
    active_obligation_ids = tuple(row["id"] for row in facts["obligations"])
    subject = PathQualitySubject(
        model_id=model.model_id,
        boundary_id=f"portable:{model.model_id}",
        model_fingerprint=model.fingerprint,
        normalized_facts_fingerprint=normalized_model_facts_fingerprint(facts),
        retained_element_inventory_fingerprint=canonical_fingerprint(
            dict(derive_retained_elements(facts))
        ),
        purpose_fingerprint=_fingerprint("portable-purpose"),
        intent_fingerprint=_fingerprint("portable-intent"),
        obligation_fingerprint=canonical_fingerprint(list(active_obligation_ids)),
        provider_fingerprint=_fingerprint("portable-provider"),
        dependency_fingerprint=_fingerprint("portable-dependencies"),
        code_fingerprint=_fingerprint("portable-code-not-required"),
        test_fingerprint=_fingerprint("portable-tests"),
        oracle_fingerprint=_fingerprint("portable-oracles"),
        evidence_fingerprint=_fingerprint("portable-evidence"),
        currentness_id="revision:portable:1",
    )
    result = lightweight_path_review(
        subject,
        facts,
        active_obligation_ids=active_obligation_ids,
    )
    return subject, result


class PortableCheckerTests(unittest.TestCase):
    def test_weak_fairness_excludes_only_declared_starvation_cycle(self):
        report = check_portable_model(eventual_model(fairness=True))
        self.assertTrue(report.ok, report.to_json_text())
        self.assertIn("finish-not-starved", report.checked_obligation_ids)
        self.assertNotIn("path_quality_result", report.to_dict())

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

    def test_current_path_quality_intake_outputs_only_the_compact_record(self):
        model = eventual_model()
        subject, result = path_quality_pair(model)

        report = check_portable_model(
            model,
            path_quality_subject=subject,
            path_quality_result=result,
        )

        self.assertEqual("pass", report.status, report.to_json_text())
        compact = report.to_dict()["path_quality_result"]
        self.assertEqual(result.to_compact_dict(), compact)
        self.assertEqual("unresolved", compact["conclusion"])
        self.assertNotIn("candidates", compact)
        self.assertNotIn("necessity_witnesses", compact)
        self.assertTrue(any("ModelMaturation" in item for item in report.residual_risk))

    def test_path_quality_intake_rejects_partial_stale_or_wrong_model_bindings(self):
        model = eventual_model()
        subject, result = path_quality_pair(model)

        partial = check_portable_model(model, path_quality_subject=subject)
        self.assertEqual("blocked", partial.status)
        self.assertTrue(any("path_quality_result_missing" in item for item in partial.blockers))

        stale = check_portable_model(
            model,
            path_quality_subject=subject,
            path_quality_result=replace(result, currentness_id="revision:portable:old"),
        )
        self.assertEqual("blocked", stale.status)
        self.assertTrue(
            any("path_quality_result_currentness_mismatch" in item for item in stale.blockers)
        )

        changed_model = replace(model, metadata={"revision": "changed"})
        mismatched = check_portable_model(
            changed_model,
            path_quality_subject=subject,
            path_quality_result=result,
        )
        self.assertEqual("blocked", mismatched.status)
        self.assertTrue(
            any("path_quality_model_fingerprint_mismatch" in item for item in mismatched.blockers)
        )
        self.assertTrue(
            any("path_quality_normalized_facts_mismatch" in item for item in mismatched.blockers)
        )


if __name__ == "__main__":
    unittest.main()
