import json
import unittest
from dataclasses import dataclass

from flowguard import (
    AssumptionCard,
    Explorer,
    FunctionResult,
    Invariant,
    Workflow,
    assumption_card,
    conditional_assumption,
)


@dataclass(frozen=True)
class TinyState:
    done: bool = False


class TinyBlock:
    name = "TinyBlock"
    reads = ("done",)
    writes = ("done",)

    def apply(self, input_obj, state):
        del input_obj, state
        return (FunctionResult("ok", TinyState(done=True), label="done"),)


def make_card() -> AssumptionCard:
    item = conditional_assumption(
        "same_prompt_same_oracle",
        "AI response for an exact prompt and unchanged external inputs",
        boundary="uncontrolled AI or fetch result",
        preconditions=("prompt text is byte-for-byte identical", "candidate materials are unchanged"),
        why_not_modeled=(
            "The model can compare the prompt and input snapshot, but it cannot derive "
            "the external oracle's exact text response without replaying that oracle."
        ),
        rationale="FlowGuard cannot deterministically replay an external oracle response.",
        invalidated_by=("prompt changes", "candidate materials change", "external source snapshot changes"),
        checks=("compare prompt text", "compare candidate-material snapshot id"),
        scope="migration equivalence",
    )
    return assumption_card(
        (item,),
        checked_scope="recommendation migration",
        not_covered="new model version or changed live web data",
    )


class AssumptionCardTests(unittest.TestCase):
    def test_conditional_assumption_requires_explicit_conditions(self):
        with self.assertRaises(ValueError):
            conditional_assumption(
                "missing_conditions",
                "AI output",
                boundary="external oracle",
                preconditions=(),
                why_not_modeled="The exact external oracle response is not derivable from the model.",
                rationale="FlowGuard cannot replay it.",
                invalidated_by="prompt changes",
                checks="compare prompt",
            )

    def test_assumption_card_rejects_duplicate_names(self):
        item = make_card().assumptions[0]
        with self.assertRaises(ValueError):
            assumption_card((item, item))

    def test_assumption_card_formats_and_exports_visible_boundaries(self):
        card = make_card()

        rendered = card.format_text()
        self.assertIn("Conditional Assumptions", rendered)
        self.assertIn("preconditions", rendered)
        self.assertIn("why_not_modeled", rendered)
        self.assertIn("invalidated_by", rendered)
        self.assertIn("not_covered", rendered)

        exported = json.loads(card.to_json_text())
        self.assertEqual("same_prompt_same_oracle", exported["assumptions"][0]["name"])
        self.assertIn("external oracle", exported["assumptions"][0]["why_not_modeled"])
        self.assertIn("compare prompt text", exported["assumptions"][0]["checks"])

    def test_conditional_assumption_requires_why_not_modeled(self):
        with self.assertRaises(ValueError):
            conditional_assumption(
                "weather_always_sunny",
                "Weather remains sunny",
                boundary="external weather",
                preconditions="location and time window are unchanged",
                why_not_modeled="",
                rationale="Weather is external.",
                invalidated_by="weather forecast changes",
                checks="compare weather source timestamp",
            )

    def test_explorer_report_carries_assumption_card_without_changing_pass_fail(self):
        card = make_card()
        report = Explorer(
            workflow=Workflow((TinyBlock(),), name="tiny"),
            initial_states=(TinyState(),),
            external_inputs=("go",),
            invariants=(Invariant("must_finish", "state is done", lambda state, trace: state.done),),
            assumption_card=card,
        ).explore()

        self.assertTrue(report.ok, report.format_text())
        self.assertIn("same_prompt_same_oracle", report.format_text())
        self.assertEqual(
            "same_prompt_same_oracle",
            report.to_dict()["assumption_card"]["assumptions"][0]["name"],
        )

    def test_assumption_card_cannot_mask_invariant_failure(self):
        report = Explorer(
            workflow=Workflow((TinyBlock(),), name="tiny"),
            initial_states=(TinyState(),),
            external_inputs=("go",),
            invariants=(Invariant("always_fails", "forced failure", lambda state, trace: False),),
            assumption_card=make_card(),
        ).explore()

        self.assertFalse(report.ok)
        self.assertEqual(("always_fails",), tuple(v.invariant_name for v in report.violations))


if __name__ == "__main__":
    unittest.main()
