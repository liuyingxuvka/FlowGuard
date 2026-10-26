"""One target at a time; promote only a clean target and leave current equal to the merge.

Protect single-target storage, clean-only promotion and target removal through real
target commands and filesystem observations. MESH states the handoffs between the
child models: target check (target_findings) turns a written target into a report,
and only a clean report reaches promotion (target_promotion, which starts from this
model's clean checked states and owns the merge rules).
"""
from contextlib import chdir, redirect_stderr, redirect_stdout
from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.closure import (MESH_CLOSURE_FAILURE_EXIT, MeshClosureModel, MeshClosureTerminal,
                               MeshClosureTransition, review_mesh_closure_model)
from flowguard.explorer import Explorer
from flowguard.map import target as native
from flowguard.map.facts import CodeFactsReport, Fact
from flowguard.map.mapfile import load_map
from flowguard.map.proof import run_model_in_process
from flowguard.map.targetfile import build_target_view, load_target

MODEL_ID = "target_life_cycle"
PARENT = "map-target"
IMPLEMENTED_BY = {
    "Start": "flowguard/map/target.py:start_target",
    "Add": "flowguard/map/target.py:add_to_target",
    "Check": "flowguard/map/target.py:check_target",
    "Promote": "flowguard/map/target.py:promote_target",
    "Drop": "flowguard/map/target.py:drop_target",
}
NOT_MODELED = {
    "flowguard/map/target.py:main": "Argument parsing only; it calls start_target, add_to_target, check_target, "
                                    "promote_target and drop_target, which this model anchors.",
}
TESTED_BY = {
    "target_check_runs_no_bound_tests": ["tests/test_flowguard_target.py:test_target_check_runs_no_pytest_and_promote_runs_one_check"],
    "promote_runs_one_full_check": ["tests/test_flowguard_target.py:test_target_check_runs_no_pytest_and_promote_runs_one_check"],
    "one_target_at_a_time": [
        "tests/test_flowguard_target.py:test_target_start_add_drop_and_read_line",
    ],
    "promote_only_when_clean": [
        "tests/test_flowguard_target.py:test_target_small_promotion_preserves_map_and_model_bytes",
    ],
    "handoffs_close": [
        "tests/test_flowguard_target.py:test_target_small_promotion_preserves_map_and_model_bytes",
    ],
    "noop_target_never_promoted": [
        "tests/test_flowguard_target.py:test_unchanged_target_is_target_noop",
    ],
}

PROGRAMS = (
    ("storage", ("START", "ADD_COMPONENT", "ADD_MODEL", "START_AGAIN", "CHECK", "DROP_PREVIEW", "DROP_YES")),
    ("todo", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "CHECK", "PROMOTE")),
    ("error", ("START", "ADD_COMPONENT", "EDIT_ERROR", "CHECK", "PROMOTE")),
    ("clean", ("START", "ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "WRITE_CODE", "CHECK", "PROMOTE")),
    # A copied component and nothing else changed: CHECK reports target_noop, PROMOTE is refused.
    ("noop", ("START", "ADD_COMPONENT", "CHECK", "PROMOTE")),
)


@dataclass(frozen=True)
class State:
    scenario: str
    position: int = 0
    target_count: int = 0
    target_revision: int = 0
    current_map_revision: int = 0
    current_model_revision: int = 0
    expected_map_revision: int = 0
    expected_model_revision: int = 0
    errors: int = 0
    todos: int = 0
    action: str = ""
    status: str = ""
    before: tuple = ()
    changed: bool = False      # the target differs from the current tree (a comment-only model copy does not)
    bound_test_runs: int = 0
    pending: tuple = ()        # MESH tokens handed over and not yet consumed


def _revisions(state):
    return (state.target_count, state.target_revision,
            state.current_map_revision, state.current_model_revision)


class Advance:
    name = "Advance"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        program = dict(PROGRAMS)[state.scenario]
        if state.position == len(program):
            return (FunctionResult("done", state, label="done"),)
        action = program[state.position]
        new = replace(state, position=state.position + 1, action=action,
                      status="ok", before=(*_revisions(state), state.bound_test_runs))
        if action == "START":
            new = replace(new, target_count=1, target_revision=1)
        elif action == "START_AGAIN":
            new = (replace(new, target_count=2, target_revision=state.target_revision + 1)
                   if self.defect == "second_target" else replace(new, status="refused"))
        elif action in ("ADD_COMPONENT", "ADD_MODEL", "EDIT_MISSING", "EDIT_ERROR"):
            new = replace(new, target_revision=state.target_revision + 1)
            if action == "ADD_MODEL":
                new = replace(new, expected_model_revision=1)
            if action == "EDIT_MISSING":
                new = replace(new, todos=1, changed=True)
            if action == "EDIT_ERROR":
                new = replace(new, errors=1, changed=True)
        elif action == "CHECK":
            if not state.changed and self.defect != "promotes_unchanged_copy":
                new = replace(new, errors=max(state.errors, 1))
            new = replace(new, pending=("design_error",) if new.errors else ("code_todo",) if new.todos else ("clean_report",))
            if self.defect == "check_runs_bound_tests":
                new = replace(new, bound_test_runs=state.bound_test_runs + 1)
        elif action == "WRITE_CODE":
            new = replace(new, todos=0)
        elif action == "DROP_PREVIEW":
            new = replace(new, status="refused")
        elif action == "DROP_YES":
            new = replace(new, target_count=0)
        elif action == "PROMOTE":
            if (state.errors or state.todos) and self.defect != "unclean_promote":
                new = replace(new, status="refused")
            elif self.defect == "clean_report_unconsumed":
                new = replace(new, status="skipped")
            else:
                merged = state.target_revision
                new = replace(new, status="promoted", target_count=0, pending=("current_equals_merged",),
                              expected_map_revision=merged,
                              current_map_revision=merged,
                              current_model_revision=state.expected_model_revision)
        if action == "PROMOTE" and new.status == "promoted":
            new = replace(new, bound_test_runs=state.bound_test_runs + (2 if self.defect == "promote_checks_twice" else 1))
        return (FunctionResult(new.status, new, label=action),)


def _holds(condition, message):
    return InvariantResult.pass_() if condition else InvariantResult.fail(message)


def _mesh():
    """Check turns a written target into one report kind; only a clean report is promoted."""
    transitions = (MeshClosureTransition("check", consumes=("target_written",),
                                         emits=("design_error", "code_todo", "warning", "clean_report"),
                                         consumer_model_id="target_findings"),
                   MeshClosureTransition("promote", consumes=("clean_report",), emits=("current_equals_merged",),
                                         consumer_model_id="target_promotion"))
    return MeshClosureModel(
        parent_model_id=MODEL_ID, root_entries=("target_written",), transitions=transitions,
        terminals=(MeshClosureTerminal("refused", consumes=("design_error", "code_todo"),
                                       terminal_kind=MESH_CLOSURE_FAILURE_EXIT),
                   MeshClosureTerminal("reported", consumes=("warning",)),
                   MeshClosureTerminal("promoted", consumes=("current_equals_merged",))))
    # No required_outputs: the closure review treats a transition's outputs as produced together, so a
    # required clean_report would "leak" at the refused exit. Every consumed token must still be produced,
    # and a normal exit must be reachable.


MESH = _mesh()
EXITS = {token for terminal in MESH.terminals for token in terminal.consumes}


def _handoffs_close(state):
    """MESH closes (review_mesh_closure_model), and at the end of a program every handed-over token is at an exit."""
    if not review_mesh_closure_model(MESH).ok:
        return InvariantResult.fail("the target handoff mesh does not close")
    if state.position == len(dict(PROGRAMS)[state.scenario]) and set(state.pending) - EXITS:
        return InvariantResult.fail(f"handed-over {', '.join(sorted(set(state.pending) - EXITS))} was never consumed")
    return InvariantResult.pass_()


INVARIANTS = (
    Invariant("target_check_runs_no_bound_tests", "design CHECK never runs the bound tests",
              lambda s,t: _holds(s.action != "CHECK" or s.bound_test_runs == s.before[-1], "CHECK ran bound tests")),
    Invariant("promote_runs_one_full_check", "a clean promotion runs its full bound check once",
              lambda s,t: _holds(s.action != "PROMOTE" or s.status != "promoted" or s.bound_test_runs == s.before[-1] + 1,
                                  "PROMOTE repeated its full check")),
    Invariant("one_target_at_a_time", "a second start refuses without any revision change",
              lambda s, t: _holds(s.action != "START_AGAIN" or
                                  (s.status == "refused" and _revisions(s) == s.before[:4]),
                                  "second start replaced an existing target")),
    Invariant("promote_only_when_clean", "ERROR and TODO each block all promotion writes",
              lambda s, t: _holds(s.action != "PROMOTE" or not (s.errors or s.todos) or
                                  (s.status == "refused" and _revisions(s) == s.before[:4]),
                                  "an unclean target was promoted")),
    Invariant("noop_target_never_promoted", "a target equal to the current tree fails its check and is never promoted",
              lambda s, t: _holds(s.changed or (s.action != "CHECK" or s.errors) and
                                  (s.action != "PROMOTE" or (s.status == "refused" and _revisions(s) == s.before[:4])),
                                  "an unchanged target passed its check or was promoted")),
    Invariant("handoffs_close", "every report a check hands over reaches an exit of MESH; a clean report is promoted",
              lambda s, t: _handoffs_close(s)),
)




def _explorer(defect=""):
    return Explorer(Workflow((Advance(defect),)),
                    tuple(State(name) for name, _ in PROGRAMS), ("advance",),
                    invariants=INVARIANTS, max_sequence_length=7, progress_steps=0)





def build_explorer():
    return _explorer()


def broken_variants():
    return {"check_runs_bound_tests": _explorer("check_runs_bound_tests"),
            "promote_checks_twice": _explorer("promote_checks_twice"), "second_target": _explorer("second_target"), "unclean_promote": _explorer("unclean_promote"),
            "promotes_unchanged_copy": _explorer("promotes_unchanged_copy"),
            "clean_report_unconsumed": _explorer("clean_report_unconsumed")}


# This is an executable regular contract, not a runner, DTO or design-only model.
# Its deliberate lack of binding produces a genuine fixture WARN, recorded in
# observations. It invokes the actual shelf anchor to obtain its conformance.
REGULAR_CONTRACT = '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.closure import (MESH_CLOSURE_FAILURE_EXIT, MeshClosureModel, MeshClosureTerminal,
                               MeshClosureTransition, review_mesh_closure_model)
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = "shelf_rule"
PARENT = "loans"
IMPLEMENTED_BY = {"Advance": "shelf/loans.py:advance"}
NOT_MODELED = {
    "flowguard/map/target.py:main": "Argument parsing only; it calls start_target, add_to_target, check_target, "
                                    "promote_target and drop_target, which this model anchors.",
}
TESTED_BY = {}
class Advance:
    name = "Advance"
    def __init__(self, delta=1): self.delta = delta
    def apply(self, event, state):
        return (FunctionResult(self.delta, self.delta, label="advanced"),)
RULE = Invariant("one_loan_step", "one loan step advances by one", lambda s,t:
    InvariantResult.pass_() if s in (0,1) else InvariantResult.fail("wrong loan step"))
def make(delta):
    return Explorer(Workflow((Advance(delta),)), (0,), ("advance",),
                    invariants=(RULE,), max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(1)
def broken_variants(): return {"advance_twice": make(2)}
def conformance():
    actual = load_anchor(IMPLEMENTED_BY["Advance"], root=Path.cwd())(0)
    return CodeFactsReport((Fact("native_loan_step", actual == 1, repr(actual)),))
'''


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def make_project(root):
    """Fresh small shelf fixture only; no prior check/proof result is reused."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "shelf").mkdir()
    (root / "tests").mkdir()
    (root / ".flowguard/models").mkdir(parents=True)
    (root / "shelf/__init__.py").write_text("", encoding="utf-8")
    (root / "shelf/catalog.py").write_text("def capacity():\n    return 1\n", encoding="utf-8")
    (root / "shelf/loans.py").write_text(
        "from shelf.catalog import capacity\n\ndef advance(value):\n    return value + capacity()\n",
        encoding="utf-8")
    (root / "tests/test_shelf.py").write_text(
        "from shelf.loans import advance\ndef test_advance():\n    assert advance(0) == 1\n",
        encoding="utf-8")
    components = []
    for cid, layer, files, anchor, deps, state in (
        ("loans", "lending", ["shelf/loans.py"], "shelf/loans.py:advance", ["catalog"], ["active loans"]),
        ("catalog", "records", ["shelf/catalog.py", "shelf/__init__.py"], "shelf/catalog.py:capacity", [], ["stock count"]),
    ):
        components.append(dict(id=cid, layer=layer, summary="Own " + cid,
                               responsibilities=["maintain " + cid], files=files,
                               entrypoints=[anchor], state=state, side_effects=[],
                               depends_on=deps, tests=["tests/test_shelf.py"] if cid == "loans" else [],
                               models=[".flowguard/models/shelf_rule.py"] if cid == "loans" else [],
                               status="draft"))
    data = dict(schema="flowguard.map.v1", project="small-shelf", layers=["lending", "records"],
                ignore=[], test_command="python -m pytest -q", components=components,
                flows=[dict(id="borrow", summary="borrow one book", steps=["loans:advance"])],
                accepted_debts=[])
    write_json(root / ".flowguard/map.json", data)
    (root / ".flowguard/models/shelf_rule.py").write_text(REGULAR_CONTRACT, encoding="utf-8")
    return root


def call_target(root, *arguments):
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return native.main([*arguments, "--root", str(root)])


def stage_target(root, *, with_model=True):
    assert call_target(root, "start", "extend the shelf") == 0
    assert call_target(root, "add", "component:loans") == 0
    if with_model:
        assert call_target(root, "add", "model:shelf_rule") == 0
        path = root / ".flowguard/target/models/shelf_rule.py"
        # A real (non-comment) revision, so the target is not a no-op copy.
        path.write_text(path.read_text(encoding="utf-8") + "\nTARGET_REVISION = 2  # revised target shelf contract\n",
                        encoding="utf-8")


def edit_missing_method(root):
    path = root / ".flowguard/target/map.json"
    target = json.loads(path.read_text(encoding="utf-8"))
    loans = target["components"][0]
    loans["entrypoints"].append("shelf/loans.py:hold")
    loans["responsibilities"].append("record a reservation")
    target["remove"].append("flow:borrow")
    write_json(path, target)
    model = root / ".flowguard/target/models/shelf_rule.py"
    if model.is_file():      # the new entrypoint is tied to a new known-bad variant of the target model
        source = model.read_text(encoding="utf-8")
        model.write_text(source.replace('return {"advance_twice": make(2)}',
                                        'return {"advance_twice": make(2), "advance_thrice": make(3)}'), encoding="utf-8")


def write_method(root):
    path = root / "shelf/loans.py"
    path.write_text(path.read_text(encoding="utf-8") +
                    "\ndef hold(member):\n    return member\n", encoding="utf-8")


def snapshot(root):
    """Exact contents, including presence; missing files never equal empty bytes."""
    return {p.relative_to(root).as_posix(): p.read_bytes()
            for p in sorted(root.rglob("*")) if p.is_file() and "__pycache__" not in p.parts}


def probe_regular_model(root, logical_model, *, view):
    """Fresh finite fixture proof using the real engine and its model namespace.

    Keep Path.cwd()-based fixture conformance equivalent to run_model's child
    process, and restore the caller even when the actual proof raises.
    """
    with chdir(root):
        return run_model_in_process(root, logical_model, view=view)


def _native_replay(scenario, program):
    facts = []
    with TemporaryDirectory(prefix="target-lifecycle-") as directory:
        root = make_project(Path(directory))
        for action in program:
            before = snapshot(root)
            code = None
            if action == "START":
                code = call_target(root, "start", "extend the shelf")
                ok = code == 0 and (root / ".flowguard/target/map.json").is_file()
            elif action == "ADD_COMPONENT":
                code = call_target(root, "add", "component:loans")
                ok = code == 0 and load_target(root).data["components"][0]["id"] == "loans"
            elif action == "ADD_MODEL":
                code = call_target(root, "add", "model:shelf_rule")
                path = root / ".flowguard/target/models/shelf_rule.py"
                ok = code == 0 and path.read_bytes() == (root / ".flowguard/models/shelf_rule.py").read_bytes()
                path.write_text(path.read_text(encoding="utf-8") + "\n# revised target shelf contract\n", encoding="utf-8")
            elif action == "START_AGAIN":
                code = call_target(root, "start", "second target")
                ok = code == 2 and snapshot(root) == before
            elif action == "EDIT_MISSING":
                edit_missing_method(root)
                ok = "shelf/loans.py:hold" in load_target(root).data["components"][0]["entrypoints"]
            elif action == "EDIT_ERROR":
                path = root / ".flowguard/target/map.json"
                target = json.loads(path.read_text(encoding="utf-8"))
                target["components"][0]["depends_on"].append("unknown-owner")
                write_json(path, target)
                ok = "unknown-owner" in load_target(root).data["components"][0]["depends_on"]
            elif action == "WRITE_CODE":
                write_method(root)
                ok = "def hold(" in (root / "shelf/loans.py").read_text(encoding="utf-8")
            elif action == "CHECK":
                report = native.check_target(root)
                ok = (bool(report.todos) and not report.errors if scenario == "todo" else
                      bool(report.errors) if scenario == "error" else
                      any(f.code == "target_noop" for f in report.errors) if scenario in ("storage", "noop") else
                      not report.errors and not report.todos)
                facts.append(Fact(scenario + ":actual_check_buckets", ok,
                                  repr((report.errors, report.todos, report.warnings))))
                ok = ok and snapshot(root) == before
            elif action == "DROP_PREVIEW":
                code = call_target(root, "drop")
                ok = code == 1 and snapshot(root) == before
            elif action == "DROP_YES":
                current = {n: v for n, v in before.items() if not n.startswith(".flowguard/target/")}
                code = call_target(root, "drop", "--yes")
                ok = code == 0 and not (root / ".flowguard/target").exists() and snapshot(root) == current
            elif action == "PROMOTE":
                target = load_target(root)
                expected = build_target_view(root, load_map(root), target).data
                models = {name: (root / rel).read_bytes() for name, rel in target.models.items()}
                with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                    code = native.promote_target(root)
                if scenario in ("todo", "error", "noop"):
                    ok = code == 1 and snapshot(root) == before
                else:
                    ok = (code == 0 and load_map(root) == expected and
                          all((root / ".flowguard/models" / name).read_bytes() == content
                              for name, content in models.items()) and
                          not (root / ".flowguard/target").exists() and
                          not any(flow["id"] == "borrow" for flow in load_map(root)["flows"]) and
                          all(c["status"] == "draft" and "fingerprint" not in c
                              for c in load_map(root)["components"] if c["id"] == "loans"))
            else:
                raise ValueError("unknown finite replay operation " + action)
            after = snapshot(root)
            changed = sorted(name for name in before.keys() | after.keys()
                             if before.get(name) != after.get(name))
            detail = dict(native_exit=code, changed_files=changed,
                          target_exists=(root / ".flowguard/target").exists(),
                          current_map_sha256=hashlib.sha256((root / ".flowguard/map.json").read_bytes()).hexdigest(),
                          current_model_sha256=hashlib.sha256((root / ".flowguard/models/shelf_rule.py").read_bytes()).hexdigest())
            facts.append(Fact(scenario + ":" + action, bool(ok), json.dumps(detail, sort_keys=True)))
    return facts


def _bound_counts():
    from flowguard.map import proof
    with TemporaryDirectory(prefix="target-counts-") as directory:
        root = make_project(Path(directory))
        stage_target(root)
        edit_missing_method(root)
        write_method(root)
        calls, actual = [], proof.run_bound_tests
        def counted(*args, **kwargs):
            calls.append(True)
            return actual(*args, **kwargs)
        proof.run_bound_tests = counted
        try:
            native.check_target(root)
            design = len(calls)
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                code = native.promote_target(root)
            total = len(calls)
        finally:
            proof.run_bound_tests = actual
        return [Fact("target_check_runs_no_bound_tests", design == 0, f"bound calls after CHECK: {design}"),
                Fact("promote_runs_one_full_check", code == 0 and total - design == 1,
                     f"bound calls in PROMOTE: {total - design}; exit {code}")]


def conformance():
    return CodeFactsReport(tuple(_bound_counts()) + tuple(fact for scenario, program in PROGRAMS
                                 for fact in _native_replay(scenario, program)))
