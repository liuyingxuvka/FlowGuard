"""Adding a model copies safe current bytes and moves only real tracked edits."""
from contextlib import redirect_stdout
from dataclasses import dataclass
from hashlib import sha256
from io import StringIO
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.common import normalize_newlines
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "target_add"
PARENT = "map-target"
IMPLEMENTED_BY = {"Add": "flowguard/map/target.py:_add"}
TESTED_BY = {'target_add_keeps_untracked_model': ['tests/test_target_add.py:test_target_add_keeps_untracked_model'], 'in_place_edit_moves_into_target': ['tests/test_target_add.py:test_target_add_moves_in_place_edit_of_committed_model'], 'uncommitted_promote_is_copied': ['tests/test_target_add.py:test_target_add_after_uncommitted_promote_copies']}


@dataclass(frozen=True)
class State:
    case: str = ""
    moved: bool = False


class Add:
    name = "Add"
    reads = ()
    writes = ("case", "moved")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        moved = event == "dirty"
        if self.defect == "moves_untracked_model" and event == "untracked":
            moved = True
        if self.defect == "copies_in_place_edit" and event == "dirty":
            moved = False
        if self.defect == "restores_promoted_model_from_head" and event == "promoted":
            moved = True
        return (FunctionResult(moved, State(event, moved), label=event),)


INVARIANTS = (
    Invariant("target_add_keeps_untracked_model", "untracked/no-git current models stay in place",
              lambda s, t: InvariantResult.fail("current was moved") if s.case in {"untracked", "no_git"} and s.moved else InvariantResult.pass_()),
    Invariant("in_place_edit_moves_into_target", "tracked dirty edits move while HEAD becomes current again",
              lambda s, t: InvariantResult.fail("edit stayed current") if s.case == "dirty" and not s.moved else InvariantResult.pass_()),
    Invariant("uncommitted_promote_is_copied", "a just-promoted current digest is never reverted to HEAD",
              lambda s, t: InvariantResult.fail("promoted version reverted") if s.case == "promoted" and s.moved else InvariantResult.pass_()),
)


def _explorer(defect=""):
    return Explorer(Workflow((Add(defect),)), (State(),), ("untracked", "dirty", "promoted", "no_git"),
                    invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("moves_untracked_model", "copies_in_place_edit", "restores_promoted_model_from_head")}


def conformance():
    import target_life_cycle
    from flowguard.map import target as native
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import load_target
    facts = []
    for case in ("untracked", "dirty", "promoted", "no_git"):
        with TemporaryDirectory(prefix="fg-add-") as directory:
            root = target_life_cycle.make_project(Path(directory))
            current = root / ".flowguard/models/shelf_rule.py"
            original = current.read_bytes()
            if case != "no_git":
                def git(*args):
                    return subprocess.run(["git", "-c", "user.name=Guard validation", "-c", "user.email=guard@example.invalid", *args],
                                          cwd=root, check=True, capture_output=True)
                git("init", "-q")
                if case == "untracked":
                    git("add", "shelf", ".flowguard/map.json")
                else:
                    git("add", "shelf", ".flowguard")
                git("commit", "-qm", "baseline")
            with redirect_stdout(StringIO()):
                native.start_target(root, "edit the shelf")
            if case != "untracked":
                current.write_bytes(original + b"\n# new current bytes\n")
            edited = current.read_bytes()
            data = load_map(root)
            # Pass the real snapshot directly: old readers need not understand the new optional map key yet.
            data["model_digests"] = {".flowguard/models/shelf_rule.py": sha256(normalize_newlines(edited if case == "promoted" else original)).hexdigest()}
            with redirect_stdout(StringIO()):
                native._add(root, data, load_target(root), "shelf_rule")
            copied = root / ".flowguard/target/models/shelf_rule.py"
            expected_current = original if case == "dirty" else edited
            ok = (normalize_newlines(current.read_bytes()) == normalize_newlines(expected_current)
                  and normalize_newlines(copied.read_bytes()) == normalize_newlines(edited))
            facts.append(Fact(case, ok, "current and target byte identities"))
    return CodeFactsReport(tuple(facts))
