"""Read exposes bounded component names and model contracts without imports.

The input features are valid adversarial observations, not rejected requests.
Literal abstract outputs witness the promises; conformance checks the same
predicates on render_show itself, over fresh copies of one real project.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import re
import shutil
import sys
import tempfile

from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.kit import Feature, feature_conformance, feature_explorer
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.views import render_show
from flowguard.workflow import Workflow

MODEL_ID = "read_view"
PARENT = "map-analysis"
IMPLEMENTED_BY = {"Show": "flowguard/map/views.py:render_show"}
TESTED_BY = {
    "no_model_import": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "components_visible_or_named": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "within_budget": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "model_purpose_and_three_counts": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "missing_summary_prompt": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "focused_component_visible": ["tests/test_map_views.py:test_read_component_never_hides_the_requested_component"],
}

PURPOSE = "Explain read probe behavior."
MODEL_LINE = "model read_probe: Explain read probe behavior. (2 rules, 2 known-bad, 1 tests)"
LARGE_TESTS = 300
LARGE_MODEL_LINE = MODEL_LINE.replace("1 tests", f"{LARGE_TESTS} tests")
FACETS = ("purpose", "rules", "known-bad", "code", "tests")
MODEL_SOURCE = '''"""Explain read probe behavior."""
from pathlib import Path
Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")
MODEL_ID = "read_probe"
COMPONENTS = ["alpha"]
IMPLEMENTED_BY = {"Run": "alpha.py:run"}
TESTED_BY = {"works": ["tests/test_alpha.py:test_run"]}
RULES = [Invariant("works", "works", None), Invariant("stable", "stable", None)]
def build_explorer(): raise RuntimeError("read must not explore")
def broken_variants(): return {"one": None, "two": None}
'''


@dataclass(frozen=True)
class ReadCase:
    budget: int = 8000
    import_marker: bool = False
    missing_summary: bool = False
    component: str | None = None


FEATURES = (
    Feature("small_budget", False, (), lambda case: replace(case, budget=360)),
    Feature("import_time_marker", False, (), lambda case: replace(case, import_marker=True)),
    Feature("missing_summary", False, (), lambda case: replace(case, missing_summary=True)),
    # One model binds LARGE_TESTS tests and the reader asks for its component.
    Feature("large_component", False, (), lambda case: replace(case, component="alpha")),
)


@dataclass(frozen=True)
class ReadObservation:
    case: ReadCase
    text: str
    imported: bool = False


def _names(observation):
    notice = next((line.partition("not shown:")[2] for line in observation.text.splitlines()
                   if "truncated" in line and "not shown:" in line), "")
    wanted = (observation.case.component,) if observation.case.component else ("alpha", "beta")
    return all(re.search(rf"^## {cid} \[", observation.text, re.M)
               or re.search(rf"\b{cid}\b", notice) for cid in wanted)


def _focused(observation):
    """The requested component is never hidden: its heading and own five facets are always printed."""
    cid = observation.case.component
    if cid is None:
        return True
    match = re.search(rf"^## {cid} \[[^\n]*\n((?:  [^\n]*\n?)*)", observation.text, re.M)
    if match is None or f"not shown: {cid}" in observation.text:
        return False
    own = [line.strip().partition(":")[0] for line in match.group(1).splitlines() if line.startswith("  ") and not line.startswith("   ")]
    return own[:len(FACETS)] == list(FACETS)


def _model_contract(observation):
    rows = tuple(line.strip() for line in observation.text.splitlines() if line.lstrip().startswith("model "))
    # A fully hidden component also hides its models.  Any displayed model must
    # retain purpose and all three literal counts; an untruncated view shows it.
    expected = LARGE_MODEL_LINE if observation.case.component else MODEL_LINE
    return all(row == expected for row in rows) and (bool(rows) or "truncated" in observation.text
                                                     or "shortened" in observation.text)


def _summary(observation):
    if not observation.case.missing_summary or not re.search(r"^## alpha \[", observation.text, re.M):
        return True
    alpha = observation.text.split("## alpha [", 1)[1].split("\n## ", 1)[0]
    return "(no summary yet)" in alpha


RULES = (
    Invariant("no_model_import", "reading never imports a model module", lambda state, trace: not state.imported),
    Invariant("components_visible_or_named", "each component is visible or explicitly named as hidden", lambda state, trace: _names(state)),
    Invariant("within_budget", "output fits the requested character budget", lambda state, trace: len(state.text) <= state.case.budget),
    Invariant("model_purpose_and_three_counts", "displayed models retain purpose and rule/bad/test counts", lambda state, trace: _model_contract(state)),
    Invariant("missing_summary_prompt", "a visible component without summary carries the purpose prompt", lambda state, trace: _summary(state)),
    Invariant("focused_component_visible", "read --component X fits the budget and always shows X's heading and five facets",
              lambda state, trace: _focused(state) and len(state.text) <= state.case.budget),
)


def _cases():
    cases = [ReadCase()]
    for names in feature_explorer(FEATURES).external_inputs:
        case = ReadCase()
        for name in names:
            case = next(feature for feature in FEATURES if feature.name == name).apply(case)
        cases.append(case)
    return tuple(cases)


def _abstract(case):
    # Literal valid witnesses, not a renderer: no file scan or formatting logic
    # is reproduced here.  Native conformance never calls this function.
    if case.component:
        purpose = "(no summary yet)" if case.missing_summary else "Serve alpha"
        text = ("## alpha [-] 1 files/1 loc, 0 rules\n  purpose: " + purpose + "\n  rules: -\n  known-bad: -\n"
                "  code: 1 files/1 loc\n  tests: 1 files: tests/test_alpha.py; 300 functions, 300 bound\n  " + LARGE_MODEL_LINE)
    elif case.budget == 360:
        text = "# read fixture\n... truncated at 360 chars; not shown: alpha, beta; use read --component ID"
    else:
        purpose = "(no summary yet)" if case.missing_summary else "Serve alpha"
        text = "## alpha [-]\n  " + purpose + "\n  " + MODEL_LINE + "\n## beta [-]\n  Serve beta"
    return ReadObservation(case, text)


class Show:
    name = "Show"
    reads = ()
    writes = ("case", "text", "imported")

    def __init__(self, fault=""):
        self.fault = fault

    def apply(self, case, state):
        observed = _abstract(case)
        if self.fault == "drop_component" and case.budget != 360:
            observed = replace(observed, text=observed.text.split("\n## beta [", 1)[0])
        elif self.fault == "import_model":
            observed = replace(observed, imported=True)
        elif self.fault == "overflow":
            observed = replace(observed, text=observed.text + "x" * (case.budget + 1))
        elif self.fault == "drop_model_contract" and case.budget != 360:
            observed = replace(observed, text=observed.text.replace(MODEL_LINE, "model read_probe: "))
        elif self.fault == "drop_summary_prompt" and case.missing_summary:
            observed = replace(observed, text=observed.text.replace("(no summary yet)", ""))
        elif self.fault == "hide_focused" and case.component:
            observed = replace(observed, text=f"# read fixture\n... truncated at {case.budget} chars; "
                                              f"not shown: {case.component}; use read --component ID")
        return (FunctionResult(observed.text, observed, label="read"),)


def _explorer(fault=""):
    return Explorer(Workflow((Show(fault),)), initial_states=(_abstract(ReadCase()),), external_inputs=_cases(),
                    invariants=RULES, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"drops_a_component": _explorer("drop_component"), "imports_a_model": _explorer("import_model"),
            "exceeds_budget": _explorer("overflow"), "drops_model_contract": _explorer("drop_model_contract"),
            "drops_summary_prompt": _explorer("drop_summary_prompt"),
            "hides_focused_component": _explorer("hide_focused")}


def _files():
    return {"alpha.py": "def run(): return True\n", "beta.py": "def run(): return True\n",
            "tests/test_alpha.py": "def test_run(): pass\n"}


def _large_files():
    names = [f"test_case_{index:03d}" for index in range(LARGE_TESTS)]
    tests = "".join(f"def {name}(): pass\n" for name in names)
    bound = ", ".join(f'"tests/test_alpha.py:{name}"' for name in names)
    return tests, f'TESTED_BY = {{"works": [{bound}]}}\n'



def _write(root, relative, source):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _review(template, case):
    with tempfile.TemporaryDirectory(prefix="flowguard-read-case-") as directory:
        root = Path(directory) / "project"
        shutil.copytree(template, root)
        model_source = MODEL_SOURCE if case.import_marker else MODEL_SOURCE.replace(
            'Path(__file__).parents[2].joinpath("model_import.marker").write_text("imported")\n', "")
        if case.component:
            tests, tested_by = _large_files()
            _write(root, "tests/test_alpha.py", tests)
            model_source = model_source.replace('TESTED_BY = {"works": ["tests/test_alpha.py:test_run"]}\n', tested_by)
        _write(root, ".flowguard/models/read_probe.py", model_source)
        components = [dict(id=cid, summary=("Serve " + cid) * 30, responsibilities=[], files=[cid + ".py"],
                           tests=["tests/test_alpha.py"] if cid == "alpha" else [], models=[], depends_on=[],
                           status="draft", fingerprint="", layer="") for cid in ("alpha", "beta")]
        if case.missing_summary:
            components[0].pop("summary")
        data = dict(project="read fixture", layers=[], components=components, flows=[])
        inv = build_inventory(root, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
        text = render_show(root, data, inv, component=case.component, detail=False, budget=case.budget)
        models = (root / ".flowguard/models").resolve()
        imported = (root / "model_import.marker").exists() or any(
            isinstance((file := vars(module).get("__file__")), str) and Path(file).resolve().is_relative_to(models)
            for module in tuple(sys.modules.values()) if module is not None)
        observed = ReadObservation(case, text, imported)
        failed = [rule.name for rule in RULES if not rule.check(observed, None).ok]
        if failed:
            raise RuntimeError(f"native render_show violates {failed!r}: {text!r}")
        return True


def conformance():
    with tempfile.TemporaryDirectory(prefix="flowguard-read-template-") as directory:
        template = Path(directory)
        for relative, source in _files().items():
            _write(template, relative, source)
        return feature_conformance(FEATURES, ReadCase, lambda case: _review(template, case))
