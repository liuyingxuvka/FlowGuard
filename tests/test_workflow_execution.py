import unittest
from dataclasses import dataclass

from flowguard import FunctionResult, Workflow


@dataclass(frozen=True)
class State:
    seen: tuple[str, ...] = ()


@dataclass(frozen=True)
class Token:
    value: str


class BranchBlock:
    name = "BranchBlock"
    accepted_input_type = str

    def apply(self, input_obj, state):
        return (
            FunctionResult(Token(input_obj + "-a"), state, "branch_a"),
            FunctionResult(Token(input_obj + "-b"), state, "branch_b"),
        )


class ConsumeToken:
    name = "ConsumeToken"
    accepted_input_type = Token

    def apply(self, input_obj, state):
        return (
            FunctionResult(
                output=input_obj.value,
                new_state=State(state.seen + (input_obj.value,)),
                label="consumed",
            ),
        )


class EmptyBlock:
    name = "EmptyBlock"
    accepted_input_type = str

    def apply(self, input_obj, state):
        return ()


class WorkflowExecutionTests(unittest.TestCase):
    def test_branching_workflow_preserves_traces(self):
        workflow = Workflow((BranchBlock(), ConsumeToken()))
        run = workflow.execute(State(), "item")

        self.assertEqual(2, len(run.completed_paths))
        self.assertEqual(0, len(run.dead_branches))
        outputs = sorted(path.current_input for path in run.completed_paths)
        self.assertEqual(["item-a", "item-b"], outputs)
        for path in run.completed_paths:
            self.assertIn(
                path.trace.labels,
                (("branch_a", "consumed"), ("branch_b", "consumed")),
            )

    def test_non_consumable_branch_is_reported(self):
        workflow = Workflow((BranchBlock(), EmptyBlock()))
        run = workflow.execute(State(), "item")

        self.assertEqual(0, len(run.completed_paths))
        self.assertEqual(2, len(run.dead_branches))
        self.assertIn("cannot consume", run.dead_branches[0].reason)

    def test_zero_result_branch_is_reported(self):
        workflow = Workflow((EmptyBlock(),))
        run = workflow.execute(State(), "item")

        self.assertEqual(0, len(run.completed_paths))
        self.assertEqual(1, len(run.dead_branches))
        self.assertIn("returned zero results", run.dead_branches[0].reason)


if __name__ == "__main__":
    unittest.main()
