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


def test_choice_workflow_runs_only_the_accepting_block():
    import pytest
    from flowguard.explorer import Explorer

    @dataclass(frozen=True)
    class Set:
        value: str = "x"
    @dataclass(frozen=True)
    class Del:
        value: str = "x"
    class SetBlock:
        name = "Set"
        accepted_input_type = Set
        def apply(self, inp, state):
            return (FunctionResult(inp, State(state.seen + (inp.value,)), label="set"),)
    class DelBlock:
        name = "Del"
        accepted_input_type = Del
        def apply(self, inp, state):
            return (FunctionResult(inp, State(tuple(v for v in state.seen if v != inp.value)), label="del"),)

    workflow = Workflow((SetBlock(), DelBlock()), mode="choice")
    report = Explorer(workflow, initial_states=(State(),), external_inputs=(Set(), Del()),
                      max_sequence_length=2, progress_steps=0).explore()
    assert report.ok and report.explored_sequence_count == 6
    assert sum(len(trace.steps) == 2 for trace in report.traces) == 4
    for trace in report.traces:
        assert 1 <= len(trace.steps) <= len(trace.external_inputs)
        assert tuple(step.function_name for step in trace.steps) == tuple(type(inp).__name__ for inp in trace.external_inputs[:len(trace.steps)])
        assert "pass" not in trace.labels
    unknown = workflow.execute(State(), 1)
    assert not unknown.completed_paths and unknown.dead_branches[0].reason == "no block accepts int"
    ambiguous = Workflow((SetBlock(), SetBlock()), mode="choice").execute(State(), Set())
    assert not ambiguous.completed_paths and ambiguous.exception_branches[0].error_type == "AmbiguousChoice"
    assert ambiguous.exception_branches[0].message.count("Set") == 2
    with pytest.raises(ValueError, match="mode"):
        Workflow((), mode="other")


def test_choice_reuses_acceptance_once_and_preserves_terminal_results_and_errors():
    from types import SimpleNamespace
    calls = []
    block = SimpleNamespace(name="only", can_accept=lambda inp, state: calls.append("guard") or True,
                            apply=lambda inp, state: [FunctionResult(inp, state, label="ran")])
    workflow = Workflow((block,), mode="choice")
    assert workflow.execute(State(), "x").completed_paths[0].trace.labels == ("ran",)
    assert calls == ["guard"]
    calls.clear()
    ended = workflow.execute(State(), "x", terminal_predicate=lambda inp, state, trace: True)
    assert len(ended.completed_paths) == 1 and not ended.completed_paths[0].trace.steps and calls == []
    def crash(*args):
        raise ValueError("actual error")
    for key in ("can_accept", "apply"):
        broken = SimpleNamespace(name="broken", can_accept=lambda *args: True,
                                 apply=lambda inp, state: [FunctionResult(inp, state)])
        setattr(broken, key, crash)
        run = Workflow((broken,), mode="choice").execute(State(), "x")
        assert not run.completed_paths and run.exception_branches[0].error_type == "ValueError"
        assert run.exception_branches[0].function_name == "broken"
    empty = Workflow((EmptyBlock(),), mode="choice").execute(State(), "x")
    assert empty.dead_branches[0].reason == "EmptyBlock returned zero results"
