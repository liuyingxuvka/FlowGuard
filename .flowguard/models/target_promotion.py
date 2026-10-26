"""Promotion writes the checked merge, removes the target, leaves changed components draft, refuses changed inputs.

It starts where the parent target_life_cycle stands right after a clean check
(project_parent_state). Conformance replays each covering trace on a fresh small
shelf project with a clean target and runs the real promote_target.
"""
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, replace
from io import StringIO
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, ReplayObservation, Workflow, replay_trace, select_covering_traces
from flowguard.conformance import projected_output_matches, projected_state_matches
from flowguard.explorer import Explorer
from flowguard.kit import reachable_states

MODEL_ID = "target_promotion"
PARENT = "target_life_cycle"
IMPLEMENTED_BY = {"Promote": "flowguard/map/target.py:promote_target"}
TESTED_BY = {
    "promote_names_stale_components": ["tests/test_flowguard_target.py:test_promote_names_stale_component_to_confirm"],
    "promote_makes_current_equal_merged": [
        "tests/test_flowguard_target.py:test_target_small_promotion_preserves_map_and_model_bytes",
    ],
    "promote_leaves_no_target": [
        "tests/test_flowguard_target.py:test_target_small_promotion_preserves_map_and_model_bytes",
    ],
    "changed_components_become_draft": [
        "tests/test_flowguard_target.py:test_target_small_promotion_preserves_map_and_model_bytes",
    ],
    "refusal_shows_findings": ["tests/test_flowguard_target.py:test_refused_promote_prints_the_report"],
    "changed_inputs_refuse_promotion": [
        "tests/test_flowguard_target.py:test_promote_refuses_inputs_changed_after_its_check",
    ],
}


@dataclass(frozen=True)
class State:
    target_revision: int
    current_map_revision: int
    current_model_revision: int
    expected_model_revision: int
    target_count: int = 1
    edited: bool = False             # the checked inputs changed after the check
    draft: bool = False              # the target's components are draft after promotion
    action: str = ""
    status: str = ""
    findings_shown: bool = True
    stale_components_named: bool = True


def project_parent_state(state):
    """The child's start: the parent has just checked a target with no error and no to-do."""
    if state.action != "CHECK" or state.errors or state.todos or state.target_count != 1:
        return None
    return State(state.target_revision, state.current_map_revision, state.current_model_revision,
                 state.expected_model_revision)


def _starts():
    import target_life_cycle            # inside the function: the parent imports nothing of its children
    return reachable_states(target_life_cycle.build_explorer(), project_parent_state)


class Promote:
    name = "Promote"

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        if event == "REFUSE_ERROR" and state.target_count:
            new = replace(state, action=event, status="refused_error", findings_shown=self.defect != "refuses_silently")
            return (FunctionResult(new.status, new, label=event),)
        if event == "EDIT_AFTER_CHECK":
            new = replace(state, action=event, status="edited" if state.target_count else "no_target",
                          edited=state.edited or bool(state.target_count))
            return (FunctionResult(new.status, new, label=event),)
        if not state.target_count:
            new = replace(state, action=event, status="no_target")
        elif state.edited and self.defect != "promotes_after_edit":
            new = replace(state, action=event, status="refused")
        else:
            new = replace(state, action=event, status="promoted", target_count=0, draft=True,
                          current_map_revision=state.target_revision,
                          current_model_revision=state.expected_model_revision)
            if self.defect == "models_only":
                new = replace(new, current_map_revision=state.current_map_revision)
            if self.defect == "retained_target":
                new = replace(new, target_count=1)
            if self.defect == "keeps_components_confirmed":
                new = replace(new, draft=False)
        if new.status == "promoted" and self.defect == "names_drafts_only":
            new = replace(new, stale_components_named=False)
        return (FunctionResult(new.status, new, label=event),)


def _holds(condition, message):
    return InvariantResult.pass_() if condition else InvariantResult.fail(message)


INVARIANTS = (
    Invariant("promote_names_stale_components", "confirmation guidance includes changed confirmed components",
              lambda s,t: _holds(s.status != "promoted" or s.stale_components_named, "stale component missing from confirmation")),
    Invariant("refusal_shows_findings", "refusal shows the actual design error and changes no current bytes",
              lambda s, t: _holds(s.status != "refused_error" or s.findings_shown, "refusal hid its findings")),
    Invariant("promote_makes_current_equal_merged", "both current map and models equal the prepared merge",
              lambda s, t: _holds(s.status != "promoted" or
                                  (s.current_map_revision == s.target_revision and
                                   s.current_model_revision == s.expected_model_revision),
                                  "current map or model differs from the merge")),
    Invariant("promote_leaves_no_target", "successful promotion removes the target",
              lambda s, t: _holds(s.status != "promoted" or s.target_count == 0, "promotion retained the target")),
    Invariant("changed_components_become_draft", "the target's components are draft after promotion",
              lambda s, t: _holds(s.status != "promoted" or s.draft, "a changed component stayed confirmed")),
    Invariant("changed_inputs_refuse_promotion", "promote refused: checked inputs changed",
              lambda s, t: _holds(s.action != "PROMOTE" or not s.edited or s.status == "refused",
                                  "a target whose checked inputs changed was promoted")),
)


def _explorer(defect=""):
    return Explorer(Workflow((Promote(defect),)), _starts(), ("PROMOTE", "EDIT_AFTER_CHECK", "REFUSE_ERROR"),
                    invariants=INVARIANTS, max_sequence_length=2, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in
            ("models_only", "retained_target", "keeps_components_confirmed", "promotes_after_edit", "refuses_silently", "names_drafts_only")}


class RealPromotion:
    """A fresh copy of a clean shelf target; PROMOTE runs the real promote_target."""

    def __init__(self, base):
        self.base = base

    def reset(self, initial_state):
        from flowguard.map.mapfile import load_map
        from flowguard.map.targetfile import build_target_view, load_target
        self.directory = TemporaryDirectory(prefix="target-promotion-")
        self.root = Path(shutil.copytree(self.base, Path(self.directory.name) / "project"))
        self.expected = build_target_view(self.root, load_map(self.root), load_target(self.root)).data
        self.expected_models = {path.name: path.read_bytes() for path in (self.root / ".flowguard/target/models").glob("*.py")}
        self.state, self.edit = initial_state, False

    def apply_step(self, step):
        from flowguard.map import target as native
        from flowguard.map.mapfile import load_map
        event = step.function_input
        state = replace(self.state, action=event)
        exists = (self.root / ".flowguard/target").exists()
        if event == "REFUSE_ERROR" and exists:
            import json
            target_map = self.root / ".flowguard/target/map.json"
            saved = target_map.read_bytes()
            data = json.loads(saved)
            data["goal"] = ""
            target_map.write_text(json.dumps(data))
            paths = [self.root / ".flowguard/map.json", *(self.root / ".flowguard/models").glob("*.py"),
                     *(self.root / ".flowguard/target/models").glob("*.py"), target_map]
            before = {p: p.read_bytes() for p in paths}
            output = StringIO()
            try:
                with redirect_stdout(output), redirect_stderr(StringIO()):
                    code = native.promote_target(self.root)
                unchanged = all(p.exists() and p.read_bytes() == b for p, b in before.items())
            finally:
                target_map.write_bytes(saved)
            shown = "ERROR" in output.getvalue() and "promote refused: 1 error(s), 0 to-do" in output.getvalue()
            state = replace(state, status="refused_error" if code == 1 else "unexpected_success",
                            findings_shown=shown and unchanged)
        elif event == "EDIT_AFTER_CHECK":
            self.edit = self.edit or exists
            state = replace(state, status="edited" if exists else "no_target", edited=state.edited or exists)
        elif not exists:
            state = replace(state, status="no_target")
        else:
            original = native.check_target
            if self.edit:
                def check_then_edit(root, **options):        # the checked target model changes after its check
                    report = original(root, **options)
                    model = Path(root) / ".flowguard/target/models/shelf_rule.py"
                    model.write_text(model.read_text(encoding="utf-8") + "\n# edited after the check\n", encoding="utf-8")
                    return report
                native.check_target = check_then_edit
            output = StringIO()
            try:
                with redirect_stdout(output), redirect_stderr(StringIO()):
                    code = native.promote_target(self.root)
            finally:
                native.check_target = original
            current = load_map(self.root)
            if code == 0:
                loans = next(c for c in current["components"] if c["id"] == "loans")
                same_models = all((self.root / ".flowguard/models" / name).read_bytes() == content
                                  for name, content in self.expected_models.items())
                state = replace(state, status="promoted", target_count=int((self.root / ".flowguard/target").exists()),
                                draft=loans["status"] == "draft" and any("loans" in line.split()[6:] for line in output.getvalue().splitlines()
                                      if line.startswith("next: python -m flowguard map confirm ")),
                                stale_components_named=any("catalog" in line.split()[6:] for line in output.getvalue().splitlines()
                                      if line.startswith("next: python -m flowguard map confirm ")),
                                current_map_revision=state.target_revision if current == self.expected else -1,
                                current_model_revision=state.expected_model_revision if same_models else -1)
            else:
                refused = "promote refused: checked inputs changed" in output.getvalue()
                state = replace(state, status="refused" if refused else f"exit {code}: {output.getvalue()[:200]}")
        self.state = state
        return ReplayObservation(function_name=step.function_name, observed_output=state.status, observed_state=state)

    def observe_state(self):
        return self.state

    def close(self):
        self.directory.cleanup()


def conformance():
    import target_life_cycle
    from flowguard.map import target as native
    last = None
    with TemporaryDirectory(prefix="target-promotion-base-") as directory:
        base = target_life_cycle.make_project(Path(directory) / "base")
        from flowguard.map import cli
        with redirect_stdout(StringIO()):
            cli.main(["confirm", "all", "--root", str(base)])
        target_life_cycle.stage_target(base)
        target_life_cycle.edit_missing_method(base)
        target_life_cycle.write_method(base)
        changed = base / "shelf/catalog.py"
        changed.write_text(changed.read_text() + "\n# refreshed documentation\n")
        report = native.check_target(base)
        if report.errors or report.todos:
            raise RuntimeError(f"the base target is not clean: {report.errors + report.todos}")
        for trace in select_covering_traces(build_explorer().explore().traces):
            adapter = RealPromotion(base)
            try:
                last = replay_trace(trace=trace, adapter=adapter, invariants=INVARIANTS,
                                    rules=(projected_state_matches(), projected_output_matches()))
            finally:
                adapter.close()
            if not last.ok:
                return last
    return last
