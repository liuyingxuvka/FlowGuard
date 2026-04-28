import unittest
from dataclasses import dataclass

from flowguard import Explorer, FunctionResult, Invariant, InvariantResult, Workflow


@dataclass(frozen=True)
class State:
    attempts: tuple[str, ...] = ()


class ScoreAlways:
    name = "ScoreAlways"
    accepted_input_type = str

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                output=input_obj,
                new_state=State(state.attempts + (input_obj,)),
                label="scored",
                reason="always scores",
            ),
        )


def no_repeated_attempts(state, trace):
    del trace
    if len(state.attempts) != len(set(state.attempts)):
        return InvariantResult.fail("repeated attempt")
    return InvariantResult.pass_()


class CounterexampleTraceTests(unittest.TestCase):
    def test_violation_includes_readable_counterexample_trace(self):
        report = Explorer(
            workflow=Workflow((ScoreAlways(),)),
            initial_states=(State(),),
            external_inputs=("job_001",),
            invariants=(
                Invariant(
                    name="no_repeated_attempts",
                    description="same item is scored at most once",
                    predicate=no_repeated_attempts,
                ),
            ),
            max_sequence_length=2,
        ).explore()

        self.assertFalse(report.ok)
        trace_text = report.violations[0].trace.format_text()
        self.assertIn("ScoreAlways [scored]", trace_text)
        self.assertEqual(2, trace_text.count("ScoreAlways"))
        self.assertIn("external_inputs", trace_text)


if __name__ == "__main__":
    unittest.main()
