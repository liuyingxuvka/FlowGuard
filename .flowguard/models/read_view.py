"""Read shows each requested component, its five static facets and model contracts within budget, without imports.

The input features are valid adversarial observations, not rejected requests.
Literal abstract outputs witness the promises; conformance checks the same
predicates on render_show itself, over fresh copies of one real project.
"""
from dataclasses import dataclass, replace
from pathlib import Path
import importlib.util
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
PARENT = "map-read"
IMPLEMENTED_BY = {"Show": "flowguard/map/views.py:render_show", "Review": "flowguard/map/review.py:render_review",
                  "Find": "flowguard/map/views.py:find_owners"}
NOT_MODELED = {
    "flowguard/map/facets.py:_StaticModel._module": "memoizes one parsed helper file per read; the names it yields "
        "are what static_rules_match_model checks on real render_show output",
    "flowguard/map/facets.py:_StaticModel.explorer_rules": "remembers the kit case table found while reading rules; "
        "the cases line is checked by static_rules_match_model through the kit probe",
    "flowguard/map/facets.py:_StaticModel._defined": "records the AST of each rule's defining call so goal rules can "
        "compare versions; tests/test_flowguard_target.py:test_behaviour_target_without_a_rule_is_untied checks that line",
    "flowguard/map/facets.py:_StaticModel.bad_keys": "collects known-bad names written by loops and comprehensions; "
        "tests/test_map_views.py:test_static_known_bad_follow_loops_and_tuple_targets checks them",
}
TESTED_BY = {
    "no_model_import": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "components_visible_or_named": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "within_budget": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "model_purpose_and_three_counts": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "missing_summary_prompt": ["tests/test_map_views.py:test_read_observes_hidden_names_missing_summary_and_model_counts"],
    "focused_component_visible": ["tests/test_map_views.py:test_read_component_never_hides_the_requested_component"],
    "components_in_layer_order": ["tests/test_map_views.py:test_read_orders_components_by_layer"],
    "relied_rules_shown": ["tests/test_map_views.py:test_read_component_lists_the_rules_it_relies_on"],
    "component_flows_shown": ["tests/test_map_views.py:test_read_component_lists_its_flows_and_their_rules"],
    "review_ranks_errors_first": ["tests/test_map_views.py:test_review_ranks_defects_and_states_true_strengths"],
    "review_strengths_are_true": ["tests/test_map_views.py:test_review_ranks_defects_and_states_true_strengths"],
    "review_steps_name_a_recipe": ["tests/test_map_views.py:test_review_ranks_defects_and_states_true_strengths"],
    "find_matches_word_forms": ["tests/test_map_views.py:test_find_matches_word_forms"],
    "static_rules_match_model": ["tests/test_map_views.py:test_static_rules_follow_helpers_and_wrappers",
                                 "tests/test_map_views.py:test_static_known_bad_follow_loops_and_tuple_targets",
                                 "tests/test_map_views.py:test_kit_model_facets_are_static_and_complete"],
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
def build_explorer(): return Explorer(Workflow(()), (0,), (), invariants=RULES)
def broken_variants(): return {"one": None, "two": None}
'''
_PROBE_HEAD = '''"""Probe."""
from flowguard.core import Invariant
from flowguard.explorer import Explorer
from flowguard.workflow import Workflow
'''
_PROBE_EXPLORER = "def _explorer(kind=\"\"):\n    return Explorer(Workflow(()), (0,), (), invariants=RULES)\n"
# Valid model shapes from the documented recipes and from projects using FlowGuard.
PROBE_FILES = {
    "helper_split": {
        ".flowguard/models/_probe_common.py": _PROBE_HEAD + (
            "def _ok(state, trace): return True\n"
            "A = Invariant(\"a_rule\", \"a holds\", _ok)\nB = Invariant(\"b_rule\", \"b holds\", _ok)\nBOTH = (A, B)\n"),
        ".flowguard/models/probe_child.py": _PROBE_HEAD + (
            "from _probe_common import A, B\nMODEL_ID = \"probe_child\"\nPARENT = \"probe_parent\"\n"
            "IMPLEMENTED_BY = {\"Run\": \"alpha.py:run\"}\nTESTED_BY = {\"a_rule\": [\"tests/test_alpha.py:test_run\"]}\n"
            "def _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=(A, B))\n"
            "def build_explorer(): return _explorer()\ndef broken_variants(): return {\"child_bad\": _explorer()}\n"),
        ".flowguard/models/probe_parent.py": _PROBE_HEAD + (
            "from _probe_common import BOTH\nMODEL_ID = \"probe_parent\"\nIMPLEMENTED_BY = {\"Run\": \"alpha.py:run\"}\n"
            "def _explorer():\n    return Explorer(Workflow(()), (0,), (), invariants=BOTH)\n"
            "def build_explorer(): return _explorer()\ndef broken_variants(): return {\"parent_bad\": _explorer()}\n"),
    },
    "wrapper": {
        ".flowguard/models/probe_wrapper.py": _PROBE_HEAD + (
            "MODEL_ID = \"probe_wrapper\"\nIMPLEMENTED_BY = {\"Run\": \"alpha.py:run\"}\n"
            "def _rule(name, text):\n    return Invariant(name, text, lambda state, trace: True)\n"
            "RULES = (_rule(\"x_rule\", \"x holds\"), _rule(\"y_rule\", \"y holds\"))\n" + _PROBE_EXPLORER +
            "def build_explorer(): return _explorer()\n"
            "def broken_variants():\n    return {name: _explorer(name) for name in (\"x_bad\", \"y_bad\")}\n"),
    },
    "loops": {
        ".flowguard/models/probe_tuple.py": _PROBE_HEAD + (
            "MODEL_ID = \"probe_tuple\"\nIMPLEMENTED_BY = {\"Run\": \"alpha.py:run\"}\n"
            "RULES = (Invariant(\"t_rule\", \"t holds\", lambda state, trace: True),)\n" + _PROBE_EXPLORER +
            "def build_explorer(): return _explorer()\n"
            "def broken_variants():\n"
            "    return {name: _explorer(kind) for name, kind in ((\"a_bad\", \"a\"), (\"b_bad\", \"b\"))}\n"),
        ".flowguard/models/probe_loop.py": _PROBE_HEAD + (
            "MODEL_ID = \"probe_loop\"\nIMPLEMENTED_BY = {\"Run\": \"alpha.py:run\"}\n"
            "RULES = (Invariant(\"l_rule\", \"l holds\", lambda state, trace: True),)\n"
            "FEATURES = {\"one\": (\"x\", \"m_one\", 1), \"two\": (\"y\", \"m_two\", 2)}\n"
            "EXPECTED = {\"alpha\": 1, \"beta\": 2}\n" + _PROBE_EXPLORER +
            "def build_explorer(): return _explorer()\n"
            "def broken_variants():\n    result = {}\n"
            "    for _, mutation, _ in FEATURES.values():\n        result[mutation] = _explorer(mutation)\n"
            "    for case in EXPECTED:\n        result[f\"ignore_{case}\"] = _explorer(case)\n    return result\n"),
    },
    "kit": {
        ".flowguard/models/probe_kit.py": (
            '"""Probe."""\nfrom flowguard.kit import Feature, feature_explorer, feature_variants\n'
            'MODEL_ID = "probe_kit"\nIMPLEMENTED_BY = {"Run": "alpha.py:run"}\n'
            'FEATURES = (Feature("d_one", True, ("c1",), lambda plan: plan), Feature("d_two", True, ("c2",), lambda plan: plan),\n'
            '            Feature("b_one", False, (), lambda plan: plan))\n'
            'def build_explorer(): return feature_explorer(FEATURES, codes="first")\n'
            'def broken_variants(): return feature_variants(FEATURES, codes="first")\n'),
    },
}
# The runtime names of PROBE_FILES (conformance re-derives them by importing the probes).
PROBE_TRUTH = {
    "helper_split": (("probe_child", (("a_rule", "a holds"), ("b_rule", "b holds")), ("child_bad",), ("a_rule",)),
                     ("probe_parent", (("a_rule", "a holds"), ("b_rule", "b holds")), ("parent_bad",), ())),
    "wrapper": (("probe_wrapper", (("x_rule", "x holds"), ("y_rule", "y holds")), ("x_bad", "y_bad"), ()),),
    "loops": (("probe_loop", (("l_rule", "l holds"),), ("ignore_alpha", "ignore_beta", "m_one", "m_two"), ()),
              ("probe_tuple", (("t_rule", "t holds"),), ("a_bad", "b_bad"), ())),
    "kit": (("probe_kit", (("benign_features_neutral", "removing legal benign features does not change the verdict"),
                           ("clean_input_accepted", "an input with no defect is accepted"),
                           ("each_defect_rejected", "an input with any defect is rejected"),
                           ("first_defect_reported", "a rejection reports the declared codes of the expected defects")),
             ("ignores_d_one", "rejects_b_one", "reports_last_defect_only"), ()),),
}
KIT_CASES = "cases: 2 defects (d_one, d_two), 1 benign (b_one)"


@dataclass(frozen=True)
class ReadCase:
    budget: int = 8000
    import_marker: bool = False
    missing_summary: bool = False
    component: str | None = None
    probe: str = ""
    layered: bool = False      # beta (last in map.json) sits in the upper layer "top", alpha in "low"
    relied: bool = False       # beta.py calls alpha.py:run, the anchor of read_probe; read --component beta
    flowing: bool = False      # flow chain = beta:run -> alpha:run with model read_probe; read --component beta
    sources: bool = False      # alpha lists four entrypoints: model-anchored, test-named, NOT_MODELED, unexplained
    review: bool = False       # read --review on REVIEW_FILES: a cycle, a hub, an unexplained writer, a flow with no model
    query: str = ""            # read --find <query>: alpha owns "reject expired tokens", the query is another word form


FEATURES = (
    Feature("small_budget", False, (), lambda case: replace(case, budget=420)),
    Feature("import_time_marker", False, (), lambda case: replace(case, import_marker=True)),
    Feature("missing_summary", False, (), lambda case: replace(case, missing_summary=True)),
    # One model binds LARGE_TESTS tests and the reader asks for its component.
    Feature("large_component", False, (), lambda case: replace(case, component="alpha")),
    Feature("late_upper_component", False, (), lambda case: replace(case, layered=True)),
    Feature("relied_component", False, (), lambda case: replace(case, relied=True, component="beta"),
            conflicts=("large_component",)),
    Feature("component_in_flow", False, (), lambda case: replace(case, flowing=True, component="beta"),
            conflicts=("large_component",)),
    # Rules from a _helper module, a wrapper function, and known-bad built by loops: read
    # and read --component alpha are both observed.
    Feature("helper_split_model", False, (), lambda case: replace(case, probe="helper_split"), exclusive=True),
    Feature("wrapper_rule_model", False, (), lambda case: replace(case, probe="wrapper"), exclusive=True),
    Feature("loop_built_variants_model", False, (), lambda case: replace(case, probe="loops"), exclusive=True),
    # A feature-kit model: two defects and one benign feature, codes="first".
    Feature("kit_model", False, (), lambda case: replace(case, probe="kit"), exclusive=True),
    # read --review on a project with an unaccepted cycle (ERROR), a hub component (used by 3,
    # uses 3, 7 duties), an unexplained state writer and a flow with no model.
    Feature("review_fixture", False, (), lambda case: replace(case, review=True), exclusive=True),
    # read --find expire: alpha's duty says "expired"; the owner must still be found.
    Feature("inflected_query", False, (), lambda case: replace(case, query="expire"), exclusive=True),
)


@dataclass(frozen=True)
class ReadObservation:
    case: ReadCase
    text: str
    imported: bool = False
    runtime: tuple = ()        # (model id, sorted rule names, sorted known-bad names) of the probes


def _names(observation):
    if observation.case.review or observation.case.query:
        return True
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
    if observation.case.review or observation.case.query:
        return True
    rows = tuple(line.strip() for line in observation.text.splitlines() if line.lstrip().startswith("model read_probe:"))
    # A fully hidden component also hides its models.  Any displayed model must
    # retain purpose and all three literal counts; an untruncated view shows it.
    expected = LARGE_MODEL_LINE if observation.case.component else MODEL_LINE
    if observation.case.component not in (None, "alpha"):
        return not rows                 # read_probe lives in alpha
    return all(row == expected for row in rows) and (bool(rows) or "truncated" in observation.text
                                                     or "shortened" in observation.text)


def _static(observation):
    """Static counts and names equal the explorer's invariants and broken_variants() keys."""
    lines = observation.text.splitlines()
    complete = "truncated" not in observation.text and "shortened" not in observation.text
    for mid, rules, bads in observation.runtime:
        rows = [index for index, line in enumerate(lines) if line.strip().startswith(f"model {mid}: ")]
        if complete and not rows:
            return False
        for index in rows:
            counts = re.search(r"\((\S+) rules, (\S+) known-bad", lines[index])
            if counts is None or counts.groups() != (str(len(rules)), str(len(bads))):
                return False
            facets = {line.strip().partition(": ")[0]: line.strip().partition(": ")[2] for line in lines[index + 1:index + 6]}
            if "rules" in facets:
                shown = {item.partition(": ")[0] for item in facets["rules"].split("; ") if not item.startswith("cases: ")}
                if shown != set(rules) or {item for item in facets["known-bad"].split(", ")} != set(bads):
                    return False
    return True


RELIED_LINE = "relies on: model read_probe (stable, works) via alpha: run"


def _relied(observation):
    """read --component beta names the rules of alpha's model that beta's code calls."""
    if not observation.case.relied or "shortened" in observation.text or "truncated" in observation.text:
        return True
    return any(line.strip() == RELIED_LINE for line in observation.text.splitlines())


COVERAGE_LINE = ("coverage: entrypoints 3/4 explained (model 1, test 1, reason 1); "
                 "state writers 0/0 explained (model 0, test 0, reason 0)")


def _by_source(observation):
    """The coverage line counts explanations by model, test and reason; they add up to the explained count."""
    if not observation.case.sources:
        return True
    line = next((row for row in observation.text.splitlines() if row.startswith("coverage:")), "")
    parts = re.findall(r"(\d+)/(\d+) explained \(model (\d+), test (\d+), reason (\d+)\)", line)
    return line == COVERAGE_LINE and len(parts) == 2 and all(
        int(done) == int(model) + int(test) + int(reason) for done, _, model, test, reason in parts)


FLOW_LINE = "flows: chain (step 1 of 2; model read_probe: stable, works)"


def _flows(observation):
    """read --component X lists each flow with a step in X, with the flow's model and its rules."""
    if not observation.case.flowing or "shortened" in observation.text or "truncated" in observation.text:
        return True
    return any(line.strip() == FLOW_LINE for line in observation.text.splitlines())


def _layer_order(observation):
    """Top-level components appear top-down by layer; within a layer the map.json order holds."""
    if not observation.case.layered:
        return True
    rank = {"beta": 0, "alpha": 1}
    shown = [cid for cid in dict.fromkeys(re.findall(r"^## (\S+) \[", observation.text, re.M)) if cid in rank]
    return shown == sorted(shown, key=rank.get)


# The review fixture: what read --review must find, and the strengths that are false there.
REVIEW_FALSE_STRENGTHS = ("no dependency cycles", "every flow has a model", "every state writer explained")
REVIEW_HUB = "hub"
REVIEW_FILES = {
    "app.py": "import store\ndef run(): return store.save()\n",
    "store.py": "import app\ndef save(): return True\n",
    "hub.py": "import lib1\nimport lib2\nimport lib3\ndef run(): return lib1.run() and lib2.run() and lib3.run()\n",
    "lib1.py": "class Box:\n    def put(self, value):\n        self.value = value\ndef run(): return Box()\n",
    "lib2.py": "def run(): return True\n",
    "lib3.py": "def run(): return True\n",
    "u1.py": "import hub\ndef run(): return hub.run()\n",
    "u2.py": "import hub\ndef run(): return hub.run()\n",
    "u3.py": "import hub\ndef run(): return hub.run()\n",
}
REVIEW_TEXT = (
    "# read fixture review: 11 components, 1 models, 1 flows; architecture: 1 error(s), 3 warning(s), 0 accepted debt(s)\n"
    "strengths: no layer violations; one owner per responsibility, state and side effect; no accepted debts\n"
    "defects:\n  ERROR dependency_cycle x1: app: app <-> store\n  WARN  untested_component x10: app: no tests mapped\n"
    "components: id layer files/loc duties uses/used-by models(rules/known-bad) tests(bound/functions) unexplained\n"
    "  hub - 1/4 7 3/3 0(0/0) 0/0 0\n"
    "optimise next:\n"
    "  1. fix dependency_cycle app: app <-> store; references/architecture_review.md (dependency_cycle)\n"
    "  2. split hub: hub (used by 3, uses 3, 7 duties, 4 loc); references/tree_operations.md#Add or split a component, as a target\n"
    "  3. explain lib1: 1 unexplained entrypoints and state writers; python -m flowguard read --component lib1\n"
    "  4. model flow trip: no model; references/map_format.md")


def _review_section(text, heading):
    lines = text.splitlines()
    start = next((index for index, line in enumerate(lines) if line.startswith(heading)), None)
    if start is None:
        return None
    rows = []
    for line in lines[start + 1:]:
        if not line.startswith("  "):
            break
        rows.append(line.strip())
    return rows


def _ranked(observation):
    """Every ERROR defect is a `fix <code>` step, and every fix step comes before any other step."""
    if not observation.case.review:
        return True
    defects, steps = _review_section(observation.text, "defects:"), _review_section(observation.text, "optimise next:")
    if defects is None or steps is None:
        return False
    errors = {row.split()[1] for row in defects if row.startswith("ERROR ")}
    fixes = [index for index, row in enumerate(steps) if re.match(r"\d+\. fix ", row)]
    named = {row.split()[2] for row in steps if re.match(r"\d+\. fix ", row)}
    return bool(errors) and errors <= named and fixes == list(range(len(fixes)))


def _true_strengths(observation):
    """No strength line claims what the fixture contradicts."""
    if not observation.case.review:
        return True
    line = next((row for row in observation.text.splitlines() if row.startswith("strengths: ")), None)
    if line is None:
        return False
    claimed = {item.strip() for item in line[len("strengths: "):].split(";")}
    return not claimed & set(REVIEW_FALSE_STRENGTHS)


def _recipes(observation):
    """Every optimise-next step names a references/... recipe or a python -m flowguard command."""
    if not observation.case.review:
        return True
    steps = _review_section(observation.text, "optimise next:")
    return bool(steps) and all("references/" in row or "python -m flowguard" in row for row in steps)


FIND_DUTY = "reject expired tokens"


def _word_forms(observation):
    """read --find ranks the component whose duty differs from the query only by a common word ending first."""
    if not observation.case.query:
        return True
    return observation.text.splitlines()[:1] == ["alpha"]


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
    Invariant("static_rules_match_model", "static rule and known-bad names and counts equal the model's explorer and variants",
              lambda state, trace: _static(state)),
    Invariant("relied_rules_shown", "read --component X lists the other components' model rules X's code calls",
              lambda state, trace: _relied(state)),
    Invariant("component_flows_shown", "read --component X lists the flows that have a step in X, with model and rules",
              lambda state, trace: _flows(state)),
    Invariant("components_in_layer_order", "read lists top-level components by layer, parents before children",
              lambda state, trace: _layer_order(state)),
    Invariant("review_ranks_errors_first", "every ERROR finding is in optimise next, before every non-ERROR step",
              lambda state, trace: _ranked(state)),
    Invariant("review_strengths_are_true", "every strength read --review claims holds on the project",
              lambda state, trace: _true_strengths(state)),
    Invariant("review_steps_name_a_recipe", "every optimise next step names a references recipe or a flowguard command",
              lambda state, trace: _recipes(state)),
    Invariant("find_matches_word_forms", "a query word matches a duty word that differs only by a common ending",
              lambda state, trace: _word_forms(state)),
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


def _abstract(case, file_order=False):
    # Literal valid witnesses, not a renderer: no file scan or formatting logic
    # is reproduced here.  Native conformance never calls this function.
    if case.review:
        return ReadObservation(case, REVIEW_TEXT)
    if case.query:
        return ReadObservation(case, "alpha")
    if case.probe:
        rows, details = [], []
        for mid, rules, bads, _keys in PROBE_TRUTH[case.probe]:
            row = f"model {mid}: Probe. ({len(rules)} rules, {len(bads)} known-bad, 0 tests)"
            rows.append("  " + row)
            cases = "; " + KIT_CASES if case.probe == "kit" else ""
            details += ["  " + row, "    purpose: Probe.", "    rules: " + "; ".join(f"{n}: {d}" for n, d in rules) + cases,
                        "    known-bad: " + ", ".join(bads), "    code: -", "    tests: -"]
        text = ("## alpha [-]\n  Serve alpha\n  " + MODEL_LINE + "\n" + "\n".join(rows) + "\n## beta [-]\n  Serve beta\n\n"
                "## alpha [-] 1 files/1 loc, 0 rules\n  purpose: Serve alpha\n" + "\n".join(details))
        runtime = tuple((mid, tuple(n for n, _ in rules), bads) for mid, rules, bads, _keys in PROBE_TRUTH[case.probe])
        return ReadObservation(case, text, runtime=runtime)
    if case.sources:
        text = "# read fixture\n" + COVERAGE_LINE + "\n\n## alpha [-]\n  Serve alpha\n  " + MODEL_LINE + "\n## beta [-]\n  Serve beta"
        return ReadObservation(case, text)
    if case.relied or case.flowing:
        text = ("## beta [-] 1 files/2 loc, 0 rules\n  purpose: Serve beta\n  rules: -\n  known-bad: -\n"
                "  code: 1 files/2 loc\n  tests: -" + ("\n  uses alpha: run\n  " + RELIED_LINE if case.relied else "")
                + ("\n  " + FLOW_LINE if case.flowing else ""))
        return ReadObservation(case, text)
    if case.component:
        purpose = "(no summary yet)" if case.missing_summary else "Serve alpha"
        text = ("## alpha [-] 1 files/1 loc, 0 rules\n  purpose: " + purpose + "\n  rules: -\n  known-bad: -\n"
                "  code: 1 files/1 loc\n  tests: 1 files: tests/test_alpha.py; 300 functions, 300 bound\n  " + LARGE_MODEL_LINE)
    elif case.budget == 420:
        text = "# read fixture\n... truncated at 420 chars; not shown: alpha, beta; use read --component ID"
    else:
        purpose = "(no summary yet)" if case.missing_summary else "Serve alpha"
        alpha = f"## alpha [{'low' if case.layered else '-'}]\n  " + purpose + "\n  " + MODEL_LINE
        beta = f"## beta [{'top' if case.layered else '-'}]\n  Serve beta"
        text = "\n".join((beta, alpha) if case.layered and not file_order else (alpha, beta))
    return ReadObservation(case, text)


class Show:
    name = "Show"
    reads = ()
    writes = ("case", "text", "imported", "runtime")

    def __init__(self, fault=""):
        self.fault = fault

    def apply(self, case, state):
        observed = _abstract(case)
        if self.fault == "drop_component" and case.budget != 420:
            observed = replace(observed, text=observed.text.split("\n## beta [", 1)[0])
        elif self.fault == "import_model":
            observed = replace(observed, imported=True)
        elif self.fault == "overflow":
            observed = replace(observed, text=observed.text + "x" * (case.budget + 1))
        elif self.fault == "drop_model_contract" and case.budget != 420:
            observed = replace(observed, text=observed.text.replace(MODEL_LINE, "model read_probe: "))
        elif self.fault == "drop_summary_prompt" and case.missing_summary:
            observed = replace(observed, text=observed.text.replace("(no summary yet)", ""))
        elif self.fault == "tested_by_keys" and case.probe:
            text = observed.text
            for mid, rules, bads, keys in PROBE_TRUTH[case.probe]:
                if keys:
                    text = text.replace(f"({len(rules)} rules", f"({len(keys)} rules").replace(
                        "rules: " + "; ".join(f"{n}: {d}" for n, d in rules), "rules: " + ", ".join(keys) + " (from TESTED_BY)")
            observed = replace(observed, text=text)
        elif self.fault == "kit_hidden" and case.probe == "kit":
            observed = replace(observed, text=re.sub(r"\(4 rules, 3 known-bad", "(4 rules, ? known-bad", observed.text))
        elif self.fault == "hide_flows" and case.flowing:
            observed = replace(observed, text=observed.text.replace("\n  " + FLOW_LINE, ""))
        elif self.fault == "hide_relied" and case.relied:
            observed = replace(observed, text=observed.text.replace("\n  " + RELIED_LINE, ""))
        elif self.fault == "map_file_order" and case.layered:
            observed = _abstract(case, file_order=True)
        elif self.fault == "review_hides_error" and case.review:
            observed = replace(observed, text=re.sub(r"  1\. fix [^\n]*\n", "", observed.text))
        elif self.fault == "review_false_strength" and case.review:
            observed = replace(observed, text=observed.text.replace("strengths: ", "strengths: no dependency cycles; "))
        elif self.fault == "review_no_recipe" and case.review:
            observed = replace(observed, text=observed.text.replace("; references/map_format.md", ""))
        elif self.fault == "exact_words_only" and case.query:
            observed = replace(observed, text="")
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
            "hides_focused_component": _explorer("hide_focused"),
            "counts_tested_by_keys": _explorer("tested_by_keys"),
            "kit_known_bad_hidden": _explorer("kit_hidden"),
            "map_file_order": _explorer("map_file_order"),
            "hides_relied_rules": _explorer("hide_relied"),
            "hides_component_flows": _explorer("hide_flows"),
            "review_hides_error": _explorer("review_hides_error"),
            "review_claims_false_strength": _explorer("review_false_strength"),
            "review_step_without_recipe": _explorer("review_no_recipe"),
            "exact_words_only": _explorer("exact_words_only")}


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


def _runtime(root):
    """Import the probe models (after reading) to obtain their real names; then forget them."""
    models = root / ".flowguard/models"
    sys.path.insert(0, str(models))
    before = set(sys.modules)
    try:
        found = []
        for path in sorted(models.glob("probe_*.py")):
            spec = importlib.util.spec_from_file_location(f"_flowguard_read_truth_{path.stem}", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            found.append((module.MODEL_ID, tuple(sorted(rule.name for rule in module.build_explorer().invariants)),
                          tuple(sorted(module.broken_variants()))))
        return tuple(found)
    finally:
        sys.path.remove(str(models))
        for name in set(sys.modules) - before:
            sys.modules.pop(name, None)


def _review_components():
    def component(cid, **extra):
        return {**dict(id=cid, summary="Serve " + cid, responsibilities=[], files=[cid + ".py"], tests=[], models=[],
                       depends_on=[], status="draft", fingerprint="", layer=""), **extra}
    duties = [f"serve hub duty {word}" for word in ("one", "two", "three", "four", "five", "six", "seven")]
    return ([component("alpha", tests=["tests/test_alpha.py"]), component("beta"),
             component("app", depends_on=["store"]), component("store", depends_on=["app"]),
             dict(component(REVIEW_HUB, depends_on=["lib1", "lib2", "lib3"]), responsibilities=duties)]
            + [component(cid) for cid in ("lib1", "lib2", "lib3")]
            + [component(cid, depends_on=[REVIEW_HUB]) for cid in ("u1", "u2", "u3")])


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
        if case.layered:
            components[0]["layer"], components[1]["layer"] = "low", "top"
        if case.sources:
            _write(root, "alpha.py", "def run(): return True\ndef tested(): return True\n"
                                     "def skipped(): return True\ndef loose(): return True\n")
            _write(root, "tests/test_alpha.py", "from alpha import tested\ndef test_run(): pass\n"
                                                "def test_tested_function(): assert tested()\n")
            components[0]["entrypoints"] = ["alpha.py:run", "alpha.py:tested", "alpha.py:skipped", "alpha.py:loose"]
            model_source = model_source.replace(
                'IMPLEMENTED_BY = {"Run": "alpha.py:run"}\n',
                'IMPLEMENTED_BY = {"Run": "alpha.py:run"}\nNOT_MODELED = {"alpha.py:skipped": "a deliberate no-op"}\n')
            _write(root, ".flowguard/models/read_probe.py", model_source)
        if case.relied:
            _write(root, "beta.py", "import alpha\ndef run(): return alpha.run()\n")
            components[1]["depends_on"] = ["alpha"]       # with layers, beta ("top") may use alpha ("low")
        flows = [dict(id="chain", summary="beta then alpha", steps=["beta:run", "alpha:run"],
                      model=".flowguard/models/read_probe.py")] if case.flowing else []
        data = dict(project="read fixture", layers=["top", "low"] if case.layered else [], components=components, flows=flows)
        if case.review:
            for relative, source in REVIEW_FILES.items():
                _write(root, relative, source)
            data = dict(project="read fixture", layers=[], components=_review_components(),
                        flows=[dict(id="trip", summary="u1 calls the hub", steps=["u1:run", "hub:run"])])
        inv = build_inventory(root, DEFAULT_IGNORE, with_bodies=False, write_cache=False)
        for relative, source in PROBE_FILES.get(case.probe, {}).items():
            _write(root, relative, source)
        if case.query:
            from flowguard.map.views import find_owners
            data["components"][0]["responsibilities"] = [FIND_DUTY]
            text = "\n".join(cid for _, cid, _ in find_owners(data, inv, [case.query]))
        elif case.review:
            from flowguard.map.review import render_review
            text = render_review(root, data, inv, budget=case.budget)
        else:
            text = render_show(root, data, inv, component=case.component, detail=False, budget=case.budget)
        if case.probe:
            text += "\n\n" + render_show(root, data, inv, component="alpha", detail=False, budget=case.budget)
        models = (root / ".flowguard/models").resolve()
        imported = (root / "model_import.marker").exists() or any(
            isinstance((file := vars(module).get("__file__")), str) and Path(file).resolve().is_relative_to(models)
            for module in tuple(sys.modules.values()) if module is not None)
        observed = ReadObservation(case, text, imported, _runtime(root) if case.probe else ())
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
