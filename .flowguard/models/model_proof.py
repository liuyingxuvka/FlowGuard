"""Feature model of native model proof: each malformed proof is rejected.

The first reported problem follows native proof order. Every singleton and pair
of text edits is executed in process; no cached proof or subprocess can supply
anchor credit. The fixture's target module and model module are restored after
one native invocation so distinct temporary projects cannot share target code.
"""
from pathlib import Path
import sys
import tempfile

from flowguard.kit import Feature, feature_conformance, feature_explorer, feature_variants
from flowguard.map.proof import run_model_in_process

MODEL_ID = "model_proof"
PARENT = "map-proof"
IMPLEMENTED_BY = {"RunModel": "flowguard/map/proof.py:run_model_in_process"}
TESTED_BY = {
    "each_defect_rejected": [
        "tests/test_flowguard_map_proof.py:test_tested_by_must_name_a_design_invariant"
    ],
    "clean_input_accepted": [
        "tests/test_flowguard_map_proof.py:test_fixed_code_passes_and_every_run_executes"
    ],
    "benign_features_neutral": [
        "tests/test_flowguard_map_proof.py:test_plain_function_invariant_is_accepted"
    ],
    "first_defect_reported": [
        "tests/test_flowguard_map_proof.py:test_tested_by_must_name_a_design_invariant"
    ]
}

BASE = '''from types import SimpleNamespace
from flowguard import Workflow, FunctionResult, Invariant, InvariantResult
from flowguard.explorer import Explorer
from flowguard.map.facts import load_anchor
MODEL_ID = "proof_case"
IMPLEMENTED_BY = {"Advance": "proof_target.py:advance"}
TESTED_BY = {"one_step": ["tests/test_target.py:test_advance"]}
class Step:
    name = "Advance"
    def apply(self, event, state):
        return (FunctionResult(1, 1, label="advanced"),)
class Bad(Step):
    def apply(self, event, state):
        return (FunctionResult(2, 2, label="advanced"),)
RULE = Invariant("one_step", "advance returns one", lambda state, trace:
    InvariantResult.pass_() if state in (0, 1) else InvariantResult.fail("wrong advance"))
def make(step):
    return Explorer(Workflow((step,)), (0,), ("advance",), invariants=(RULE,),
                    max_sequence_length=1, progress_steps=0)
def build_explorer():
    return make(Step())
def broken_variants():
    return {"wrong_advance": make(Bad())}
def conformance():
    actual = load_anchor(IMPLEMENTED_BY["Advance"])(0)
    return SimpleNamespace(ok=actual == 1, format_text=lambda **kwargs: "advance differs")
'''


def _edit(old, new):
    def apply(source):
        assert old in source
        return source.replace(old, new, 1)
    return apply


# Declaration order is the native first-problem order, including short-circuit
# placeholder validation; codes="first" models that observable contract.
FEATURES = (
    Feature("placeholder_anchor", True, ("placeholder_anchor",),
            _edit("proof_target.py:advance", "REPLACE_ME.py:advance")),
    Feature("unknown_test_invariant", True, ("unknown_test_invariant",),
            _edit('TESTED_BY = {"one_step":', 'TESTED_BY = {"unknown_rule":')),
    Feature("uncaught_known_bad", True, ("uncaught_known_bad",),
            _edit('"wrong_advance": make(Bad())', '"wrong_advance": make(Step())')),
    Feature("missing_conformance", True, ("missing_conformance",),
            _edit("def conformance():", "def _unused_conformance():")),
    Feature("unconsulted_anchor", True, ("unconsulted_anchor",),
            _edit('actual = load_anchor(IMPLEMENTED_BY["Advance"])(0)', "actual = 1")),
    Feature("additional_description", False, (), lambda source: source + "\n# Another description of this proof.\n"),
    Feature("unused_helper", False, (), lambda source: source + "\ndef unused_helper():\n    return 17\n"),
)


def build_explorer():
    return feature_explorer(FEATURES, codes="first")


def broken_variants():
    return feature_variants(FEATURES, codes="first")


def _review(source):
    saved_path = sys.path[:]
    names = ("proof_target", "_flowguard_model_proof_case")
    saved_modules = {name: sys.modules.pop(name) for name in names if name in sys.modules}
    try:
        with tempfile.TemporaryDirectory(prefix="flowguard-proof-model-") as directory:
            root = Path(directory)
            (root / "proof_target.py").write_text("def advance(value):\n    return value + 1\n", encoding="utf-8")
            path = root / ".flowguard/models/proof_case.py"
            path.parent.mkdir(parents=True)
            path.write_text(source, encoding="utf-8")
            test = root / "tests/test_target.py"
            test.parent.mkdir()
            test.write_text("from proof_target import advance\ndef test_advance():\n    assert advance(0) == 1\n", encoding="utf-8")
            result = run_model_in_process(root, path)
    finally:
        sys.path[:] = saved_path
        for name in names:
            sys.modules.pop(name, None)
        sys.modules.update(saved_modules)
    if result.status == "pass":
        return True, ()
    first = result.problems[0] if result.problems else "no problem was reported"
    for fragment, category in (
        ("placeholder anchor", "placeholder_anchor"),
        ("TESTED_BY names", "unknown_test_invariant"),
        ("known-bad variant", "uncaught_known_bad"),
        ("abstract boundary only", "missing_conformance"),
        ("never ran", "unconsulted_anchor"),
    ):
        if fragment in first:
            return False, (category,)
    return False, ("unexpected_proof_problem:" + first.splitlines()[0],)


def conformance():
    return feature_conformance(FEATURES, lambda: BASE, _review, codes="first")
