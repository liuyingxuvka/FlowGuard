"""A design gap describes native code; missing tests and adapter errors do not."""
from dataclasses import dataclass
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "gap_lines"
COMPONENTS = ["map-target", "map-read"]
IMPLEMENTED_BY = {"GapLines": "flowguard/map/target.py:gap_lines", "GoalRules": "flowguard/map/facets.py:target_goal_rules"}
TESTED_BY = {'changed_rule_gap_is_expected': ['tests/test_gap_lines.py:test_rule_broken_by_old_code_is_an_expected_gap', 'tests/test_gap_lines.py:test_missing_bound_test_is_never_a_gap'], 'moved_rules_expect_no_gap': ['tests/test_gap_lines.py:test_split_into_child_prints_moved_rules_only'], 'recorded_rule_prints_no_gap': ['tests/test_gap_lines.py:test_recorded_rule_prints_no_gap'], 'exception_through_anchor_is_code_gap': ['tests/test_gap_lines.py:test_exception_classification']}
EXPECTED = {"native": "EXPECTED GAP", "missing_test": "NO GAP", "moved": "moved rules only",
            "recorded": "NO GAP", "anchor_exception": "EXPECTED GAP", "engine_exception": "ERROR"}


@dataclass(frozen=True)
class State:
    case: str = ""
    line: str = ""


class Classify:
    name = "GapLines"
    reads = ()
    writes = ("case", "line")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        line = EXPECTED[event]
        wrong = {"missing_bound_test_counts_as_gap": "missing_test", "reports_moved_rule_as_new": "moved",
                 "counts_recorded_rule_as_gap": "recorded", "counts_engine_exception_as_gap": "engine_exception"}
        if wrong.get(self.defect) == event:
            line = "EXPECTED GAP"
        return (FunctionResult(line, State(event, line), label=event),)


def _check(state, cases):
    return InvariantResult.fail(f"{state.case}: {state.line}") if state.case in cases and state.line != EXPECTED[state.case] else InvariantResult.pass_()


INVARIANTS = (
    Invariant("changed_rule_gap_is_expected", "a real native gap matters; an absent bound test does not",
              lambda s, t: _check(s, ("native", "missing_test"))),
    Invariant("moved_rules_expect_no_gap", "moving a rule does not invent a code change",
              lambda s, t: _check(s, ("moved",))),
    Invariant("recorded_rule_prints_no_gap", "already implemented rules are recorded honestly",
              lambda s, t: _check(s, ("recorded",))),
    Invariant("exception_through_anchor_is_code_gap", "only an active anchor stack frame licenses an exception gap",
              lambda s, t: _check(s, ("anchor_exception", "engine_exception"))),
)


def _explorer(defect=""):
    return Explorer(Workflow((Classify(defect),)), (State(),), tuple(EXPECTED), invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("missing_bound_test_counts_as_gap", "reports_moved_rule_as_new",
            "counts_recorded_rule_as_gap", "counts_engine_exception_as_gap")}


def conformance():
    from flowguard.map import target
    if getattr(target, "gap_lines", None) is None:
        return CodeFactsReport((Fact("native_gap_lines", False, "the native design gap classifier is not written"),))
    from _gap_cases import native_cases
    return CodeFactsReport(tuple(native_cases()))
