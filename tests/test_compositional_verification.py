from __future__ import annotations

from dataclasses import replace
import unittest

from flowguard.portable_checker import check_composition, check_refinement
from flowguard.portable_model import (
    PortableModel,
    PortableState,
    PortableTransition,
    RefinementBinding,
)


def parent_model() -> PortableModel:
    return PortableModel(
        model_id="parent",
        states=(PortableState("p0"), PortableState("p1")),
        transitions=(PortableTransition("parent-complete", "p0", "go", "done", "p1"),),
        initial_state_ids=("p0",),
        terminal_state_ids=("p1",),
        assumptions=("request.valid",),
        guarantees=("request.completed",),
    )


def child_model() -> PortableModel:
    return PortableModel(
        model_id="child",
        states=(PortableState("c0"), PortableState("prepared"), PortableState("c1")),
        transitions=(
            PortableTransition("prepare", "c0", "prepare", "ready", "prepared"),
            PortableTransition("child-complete", "prepared", "go", "done", "c1"),
        ),
        initial_state_ids=("c0",),
        terminal_state_ids=("c1",),
        assumptions=(),
        guarantees=("request.completed", "audit.recorded"),
    )


def valid_binding() -> RefinementBinding:
    return RefinementBinding(
        parent_model_id="parent",
        child_model_id="child",
        state_mapping=(("c0", "p0"), ("prepared", "p0"), ("c1", "p1")),
        transition_mapping=(("child-complete", "parent-complete"),),
        allowed_stutter_transition_ids=("prepare",),
    )


def component(model_id: str, assumption: str, guarantee: str, *, conflicts=()) -> PortableModel:
    return PortableModel(
        model_id=model_id,
        states=(PortableState("ready"),),
        transitions=(),
        initial_state_ids=("ready",),
        terminal_state_ids=("ready",),
        assumptions=(assumption,),
        guarantees=(guarantee,),
        conflicts=conflicts,
    )


class CompositionalVerificationTests(unittest.TestCase):
    def test_explicit_stutter_and_step_mapping_pass(self):
        report = check_refinement(parent_model(), child_model(), valid_binding())
        self.assertTrue(report.ok, report.to_json_text())

    def test_unmapped_child_transition_fails_with_transition_id(self):
        binding = replace(valid_binding(), transition_mapping=())
        report = check_refinement(parent_model(), child_model(), binding)
        finding = next(item for item in report.findings if item.finding_id == "refinement_transition_unmapped")
        self.assertEqual(("child-complete",), finding.transition_ids)

    def test_mapped_symbol_mismatch_fails_with_both_steps(self):
        changed = replace(
            child_model(),
            transitions=(
                child_model().transitions[0],
                PortableTransition("child-complete", "prepared", "go", "wrong", "c1"),
            ),
        )
        report = check_refinement(parent_model(), changed, valid_binding())
        finding = next(item for item in report.findings if item.finding_id == "refinement_step_mismatch")
        self.assertEqual(("child-complete", "parent-complete"), finding.transition_ids)
        self.assertIn("output_symbol", finding.details["mismatched_fields"])

    def test_stronger_child_assumption_and_missing_guarantee_fail(self):
        changed = replace(
            child_model(),
            assumptions=("request.valid", "database.available"),
            guarantees=("audit.recorded",),
        )
        report = check_refinement(parent_model(), changed, valid_binding())
        ids = {item.finding_id for item in report.findings}
        self.assertIn("refinement_stronger_child_assumption", ids)
        self.assertIn("refinement_missing_parent_guarantee", ids)

    def test_peer_guarantees_close_component_assumptions(self):
        left = component("left", "from.right", "from.left")
        right = component("right", "from.left", "from.right")
        report = check_composition((left, right))
        self.assertTrue(report.ok, report.to_json_text())

    def test_missing_assumption_provider_fails(self):
        report = check_composition((component("alone", "external.missing", "own"),))
        self.assertIn("composition_assumption_unprovided", {item.finding_id for item in report.findings})

    def test_declared_guarantee_conflict_fails(self):
        left = component(
            "left", "from.right", "from.left", conflicts=(("from.left", "from.right"),)
        )
        right = component("right", "from.left", "from.right")
        report = check_composition((left, right))
        self.assertIn("composition_guarantee_conflict", {item.finding_id for item in report.findings})


if __name__ == "__main__":
    unittest.main()
