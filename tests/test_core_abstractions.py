import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, Invariant, InvariantResult, Trace, TraceStep


@dataclass(frozen=True)
class State:
    value: int = 0


class CoreAbstractionTests(unittest.TestCase):
    def test_function_result_exposes_new_state_and_state_alias(self):
        result = FunctionResult(
            output="done",
            new_state=State(1),
            label="ok",
            reason="example",
            metadata={"phase": "unit"},
        )

        self.assertEqual(State(1), result.new_state)
        self.assertEqual(State(1), result.state)
        self.assertEqual((("phase", "unit"),), result.metadata)

    def test_function_result_requires_hashable_output_and_state(self):
        with self.assertRaises(TypeError):
            FunctionResult(output=[], new_state=State())
        with self.assertRaises(TypeError):
            FunctionResult(output="ok", new_state={})

    def test_invariant_result_can_represent_violation(self):
        result = InvariantResult.fail("bad state")

        self.assertFalse(result.ok)
        self.assertTrue(result.violation)
        self.assertEqual("bad state", result.message)

    def test_trace_formats_human_readable_steps(self):
        step = TraceStep(
            external_input="external",
            function_name="Block",
            function_input="in",
            function_output="out",
            old_state=State(0),
            new_state=State(1),
            label="moved",
            reason="changed state",
        )
        trace = Trace(initial_state=State(0), external_inputs=("external",)).append(step)

        rendered = trace.format_text()
        self.assertIn("external_inputs", rendered)
        self.assertIn("Block [moved]", rendered)
        self.assertIn("changed state", rendered)

    def test_invariant_checks_state_and_trace(self):
        invariant = Invariant(
            name="positive",
            description="state value is positive",
            predicate=lambda state, trace: state.value > 0,
        )

        self.assertTrue(invariant.check(State(1), Trace()).ok)
        self.assertFalse(invariant.check(State(0), Trace()).ok)


if __name__ == "__main__":
    unittest.main()
