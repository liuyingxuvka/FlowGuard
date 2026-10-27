"""Shared finite engine fixtures and three disjoint feature tables, without model metadata."""

from __future__ import annotations

from dataclasses import dataclass, replace

from flowguard.checks import no_duplicate_values
from flowguard.conformance import replay_trace
from flowguard.core import FunctionResult, Invariant, invoke_block
from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.loop import GraphEdge, LoopCheckConfig, check_loops
from flowguard.explorer import Explorer
from flowguard.replay import ReplayInput, ReplayObservation
from flowguard.workflow import Workflow

WRONG_HOOK = "wrong_hook"


@dataclass(frozen=True)
class State:
    records: tuple[str, ...] = ()
    cache: tuple[str, ...] = ()


@dataclass(frozen=True)
class ResultObject:
    """A block result given as a plain object; the engine coerces it."""

    output: str
    state: State
    label: str


class RouterBase:
    """The block under test: what it does depends on the input token."""

    name = "Router"

    def __init__(self, objects: bool = False) -> None:
        self.objects = objects
        self.calls = 0

    def can_accept(self, token) -> bool:                  # input hook: 'reject' becomes a dead branch
        return token != "reject"

    def _result(self, value: str, state: State, duplicate: bool = False):
        records = state.records + (value,) if duplicate or value not in state.records else state.records
        new = replace(state, records=records)
        return ResultObject(value, new, value) if self.objects else FunctionResult(value, new, label=value)

    def route(self, token: str, state: State):
        self.calls += 1
        if token == "raise":
            raise ValueError("deliberate block failure")
        if token == "empty":
            return ()
        if token == "invalid":
            return "not a result"
        if token == "noninvocable":
            return invoke_block(object(), token, state)
        if token == "fork":                               # the right branch breaks an invariant
            return (self._result("left", state), self._result("right", state))
        if token == "both":                               # two safe branches; both labels are required
            return (self._result("both:a", state), self._result("both:b", state))
        return (self._result(token, state, duplicate=token == "dup"),)

    def wrong(self, token: str, state: State):
        return (FunctionResult(WRONG_HOOK, replace(state, records=state.records + (WRONG_HOOK,)), label=WRONG_HOOK),)


HOOKS = ("apply", "run", "transition", "__call__")          # invocation priority, highest first


def router(hook: str = "apply", objects: bool = False) -> RouterBase:
    """A router whose ``hook`` routes; every lower-priority hook answers wrongly and must never run."""
    methods = {name: (lambda self, token, state: self.route(token, state)) if name == hook else
               (lambda self, token, state: self.wrong(token, state)) for name in HOOKS[HOOKS.index(hook):]}
    return type(f"Router_{hook.strip('_')}", (RouterBase,), methods)(objects)


class Tail:
    """Second block: a terminal output must stop the path before it."""

    name = "Tail"

    def apply(self, value, state):
        if value == "stop":
            raise AssertionError("the terminal predicate did not stop the path")
        return (FunctionResult(value, state),)


class Record:
    name = "Record"
    reads = ("records",)
    writes = ("records",)

    def apply(self, value, state):
        records = state.records if value in state.records else state.records + (value,)
        return (FunctionResult(value, replace(state, records=records), label="recorded",
                               metadata={"operation": "record"}),)


class Adapter:
    """Real independent state update: never receives an expected trace step."""

    def __init__(self, duplicates: bool = False) -> None:
        self.duplicates = duplicates

    def reset(self, initial_state):
        self.state = initial_state

    def apply_step(self, request):
        if type(request) is not ReplayInput or any(hasattr(request, key) for key in
                                                   ("function_output", "new_state", "old_state", "label", "reason")):
            raise AssertionError("replay leaked an expected output or state")
        value = request.function_input
        if self.duplicates or value not in self.state.records:
            self.state = replace(self.state, records=self.state.records + (value,))
        return ReplayObservation(request.function_name, value, self.state, "recorded")


def _raises(state, trace):
    raise ValueError("deliberate invariant failure")


def clean_fixture() -> dict:
    trace = Workflow((Record(), Record())).execute(State(), "a").completed_paths[0].trace
    return {"tokens": ("record", "both", "stop"), "hook": "apply", "objects": False, "extra_invariants": (),
            "labels": ("record", "both:a", "both:b"), "max_transitions": None,
            "replay_trace": trace, "adapter_duplicates": False, "cycle": False}


def _add(key: str, value):
    return lambda fixture: {**fixture, key: fixture[key] + (value,)}


def _set(key: str, value):
    return lambda fixture: {**fixture, key: value}


def _corrupt_first_step(fixture):
    trace = fixture["replay_trace"]
    return {**fixture, "replay_trace": replace(trace, steps=(replace(trace.steps[0], new_state=State(("wrong",))),)
                                                + trace.steps[1:])}








def _explore(fixture: dict) -> tuple[object, list[str]]:
    block = router(fixture["hook"], fixture["objects"])
    invariants = (no_duplicate_values("records_unique", "retries preserve uniqueness", lambda state: state.records),
                  Invariant("right_branch_unsafe", "the right branch is unsafe", lambda s, t: "right" not in s.records),
                  Invariant("hooks_by_priority", "only the highest-priority hook runs",
                            lambda s, t: WRONG_HOOK not in s.records)) + fixture["extra_invariants"]
    explorer = Explorer(
        workflow=Workflow((block, Tail())), initial_states=(State(),), external_inputs=fixture["tokens"],
        invariants=invariants, max_sequence_length=2, max_transitions=fixture["max_transitions"],
        terminal_predicate=lambda output, state, trace: output == "stop", required_labels=fixture["labels"])
    return explorer.explore(), []


def run_engine(fixture: dict):
    """Run the real engine on the fixture; every finding becomes a code (accepted = no finding)."""
    report, codes = _explore(fixture)
    codes += [f"dead:{branch.function_input}" for branch in report.dead_branches]
    codes += [f"exception:{branch.function_input}:{branch.error_type}" for branch in report.exception_branches]
    codes += [f"invariant_error:{v.invariant_name}" if v.message.startswith("invariant raised ")
              else f"violation:{v.invariant_name}" for v in report.violations]
    codes += [f"unreachable:{failure.name}" for failure in report.reachability_failures]
    if not report.exploration_complete:
        codes.append(f"incomplete:{report.termination_reason}")
    for trace in report.traces:                           # the state chain of every explored trace is intact
        if any(step.old_state != before.new_state for before, step in zip(trace.steps, trace.steps[1:])):
            codes.append("trace_state_chain_broken")
    replayed = replay_trace(fixture["replay_trace"], Adapter(fixture["adapter_duplicates"]))
    if not replayed.ok:
        codes.append(f"replay:{replayed.violations[0].rule_name}")
    if fixture["cycle"]:
        loops = check_loops(LoopCheckConfig(initial_states=(0,), transition_fn=lambda s: (GraphEdge(s, s, "retry"),),
                                            is_terminal=lambda s: False))
    else:
        loops = check_loops(LoopCheckConfig(
            initial_states=(0,), transition_fn=lambda s: (GraphEdge(s, 1, "finish"),) if s == 0 else (),
            is_terminal=lambda s: s == 1, is_success=lambda s: s == 1, required_success=True))
    if not loops.ok:
        codes.append("loop:non_terminating" if loops.non_terminating_components else "loop:not_ok")
    return not codes, tuple(codes)



WORKFLOW_COMPOSITION_FEATURES = (
    Feature("noninvocable_block", True, ("exception:noninvocable:TypeError",), _add("tokens", "noninvocable")),
    Feature("invalid_result", True, ("exception:invalid:TypeError",), _add("tokens", "invalid")),
    Feature("raising_block", True, ("exception:raise:ValueError",), _add("tokens", "raise")),
    Feature("block_invoked_through_run", False, (), _set("hook", "run")),
    Feature("block_invoked_as_callable", False, (), _set("hook", "__call__")),
    Feature("results_as_objects", False, (), _set("objects", True)),
)

ENGINE_EXPLORE_FEATURES = (
    Feature("rejected_input", True, ("dead:reject",), _add("tokens", "reject")),
    Feature("empty_result", True, ("dead:empty",), _add("tokens", "empty")),
    Feature("unsafe_second_branch", True, ("violation:right_branch_unsafe",), _add("tokens", "fork")),
    Feature("duplicate_record", True, ("violation:records_unique",), _add("tokens", "dup")),
    Feature("raising_invariant", True, ("invariant_error:raises",),
            _add("extra_invariants", Invariant("raises", "must fail closed", _raises))),
    Feature("unreachable_required_label", True, ("unreachable:label:never_reached",), _add("labels", "never_reached")),
    Feature("transition_budget_spent", True, ("incomplete:max_transitions_exhausted",), _set("max_transitions", 1),
            exclusive=True),
    Feature("bottom_cycle", True, ("loop:non_terminating",), _set("cycle", True)),
)

REPLAY_CONFORMANCE_FEATURES = (
    Feature("corrupt_expected_trace", True, ("replay:projected_state_matches",), _corrupt_first_step),
    Feature("duplicating_adapter", True, ("replay:projected_state_matches",), _set("adapter_duplicates", True)),
)

FEATURES = WORKFLOW_COMPOSITION_FEATURES + ENGINE_EXPLORE_FEATURES + REPLAY_CONFORMANCE_FEATURES
