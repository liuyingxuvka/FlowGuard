"""Fresh, small native inputs for the gap classifier; no saved proof results."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard.map.facts import Fact


def regular_source(name="one", *, expected=1, positive=False, primary=True, stronger=False, missing=False, broad=False):
    declarations = []
    if primary:
        declarations.append('Invariant("answer", "native answer matches the declared table", lambda s,t: InvariantResult.pass_() if s in (0, EXPECTED["answer"]) else InvariantResult.fail("answer"))')
    if positive:
        declarations.append('Invariant("positive", "the answer is nonnegative", lambda s,t: InvariantResult.pass_() if _positive(s) else InvariantResult.fail("negative"))')
    return '''from pathlib import Path
from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact, load_anchor
MODEL_ID = {name!r}
PARENT = "app"
IMPLEMENTED_BY = {{"Value": "native.py:{anchor}"}}
TESTED_BY = {tests}
EXPECTED = {{"answer": {expected}}}
def _positive(s): return {positive_expression}
INVARIANTS = ({rules},)
class Value:
    name = "Value"
    def __init__(self, value): self.value = value
    def apply(self, event, state): return (FunctionResult(self.value, self.value),)
def make(value): return Explorer(Workflow((Value(value),)), (0,), ("value",), invariants=INVARIANTS, max_sequence_length=1, progress_steps=0)
def build_explorer(): return make(EXPECTED["answer"])
def broken_variants(): return {variants}
def conformance():
    actual = load_anchor(IMPLEMENTED_BY["Value"], root=Path.cwd())()
    return CodeFactsReport((Fact("native_answer", {comparison}, repr(actual)),))
'''.format(name=name, anchor="value" if name == "one" else "other_value" if name == "moved" else "third_value",
           tests='{"positive": ["tests/missing.py:test_value"]}' if missing else '{}', expected=expected,
           positive_expression='s >= 0 and s <= EXPECTED["answer"]' if stronger else 's >= 0',
           rules=', '.join(declarations),
           variants='{"wrong": make(EXPECTED["answer"] + 1), "negative": make(-1)}' if primary else '{"negative": make(-1)}',
           comparison='actual >= 0' if broad else 'actual == EXPECTED["answer"]')


KIT_SOURCE = '''from pathlib import Path
from flowguard.kit import Feature, feature_explorer, feature_variants, feature_conformance
from flowguard.map.facts import load_anchor
MODEL_ID = "one"
COMPONENTS = ["app"]
IMPLEMENTED_BY = {"Accept": "native.py:accept"}
FEATURES = (Feature("bad", True, ("bad",), lambda value: 1),)
def build_explorer(): return feature_explorer(FEATURES, codes="first")
def broken_variants(): return feature_variants(FEATURES, codes="first")
def conformance():
    accept = load_anchor(IMPLEMENTED_BY["Accept"], root=Path.cwd())
    return feature_conformance(FEATURES, lambda: 0, lambda value: (accept(value), ("bad",) if value else ()), codes="first")
'''


def make_project(root, source):
    (root / ".flowguard/models").mkdir(parents=True)
    (root / "native.py").write_text('def value(): return 1\ndef other_value(): return 1\ndef third_value(): return 1\ndef accept(value): return value == 0\n')
    (root / ".flowguard/models/one.py").write_text(source)
    data = {"schema": "flowguard.map.v1", "components": [{"id": "app", "summary": "Native values",
            "responsibilities": ["Compute native values"], "files": ["native.py"], "tests": [],
            "models": [".flowguard/models/one.py"], "status": "draft"}]}
    (root / ".flowguard/map.json").write_text(json.dumps(data))


def native_case(case):
    from flowguard.map import target as native
    from flowguard.map.facets import target_goal_rules
    from flowguard.map.mapfile import load_map
    from flowguard.map.targetfile import load_target, build_target_view
    with TemporaryDirectory(prefix="fg-gap-case-") as directory:
        root = Path(directory)
        source = regular_source(positive=case.startswith("move") or case.startswith("remove") or case.startswith("changed_"),
                                expected=2 if case == "remove_gap" else 1, broad=case == "remove_gap")
        if case == "kit_binding":
            source = KIT_SOURCE
        if case == "shared_tuple":
            first = source.index("INVARIANTS = (")
            last = source.index("\nclass Value:", first)
            source = source[:first] + 'RULE_DATA = (("answer matches", lambda s,t: InvariantResult.pass_() if s in (0, 1) else InvariantResult.fail("answer")),\n             ("answer nonnegative", lambda s,t: InvariantResult.pass_() if s >= 0 else InvariantResult.fail("negative")))\nINVARIANTS = (Invariant("answer", RULE_DATA[0][0], RULE_DATA[0][1]),\n              Invariant("positive", RULE_DATA[1][0], RULE_DATA[1][1]),)' + source[last:]
        if case == "shared_tuple":
            source = source.replace('def broken_variants(): return {"wrong": make(EXPECTED["answer"] + 1), "negative": make(-1)}',
                                    'BAD_DATA = (("wrong", 2), ("negative", -1))\ndef broken_variants(): return {name: make(value) for name, value in BAD_DATA}')
        make_project(root, source)
        if case == "anchor_exception":
            path = root / "native.py"
            path.write_text(path.read_text().replace('def value(): return 1', 'def value(): raise RuntimeError("native failure")'))
        with redirect_stdout(StringIO()):
            native.start_target(root, "classify the native change")
            native.add_to_target(root, "one")
        model = root / ".flowguard/target/models/one.py"
        if case in {"native", "table", "anchor_exception", "engine_exception", "adapter_exception", "anchor_only", "closed", "open"}:
            model.write_text(regular_source(expected=2))
        elif case == "shared_tuple":
            model.write_text(source.replace('"answer matches"', '"answer equals the declared native value"'))
        elif case.startswith("changed_"):
            model.write_text(source.replace("def _positive(s): return s >= 0", "def _positive(s): return s >= -1").replace('"negative": make(-1)', '"negative": make(-2)'))
            if case == "changed_with_line":
                (root / ".flowguard/target/PLAN.txt").write_text('changes: one.positive because "The revised lower bound is intentional."\n')
        elif case in {"recorded", "missing_test"}:
            model.write_text(regular_source(positive=True, missing=case == "missing_test"))
        elif case.startswith("move"):
            model.write_text(regular_source())
            with redirect_stdout(StringIO()):
                native.add_to_target(root, "app")
            target_path = root / ".flowguard/target/map.json"
            data = json.loads(target_path.read_text())
            component = data["components"][0]
            component["models"].append(".flowguard/models/moved.py")
            (model.parent / "moved.py").write_text(regular_source("moved", positive=True, primary=False))
            if case == "move_twice":
                component["models"].append(".flowguard/models/second.py")
                (model.parent / "second.py").write_text(regular_source("second", positive=True, primary=False, stronger=True))
            target_path.write_text(json.dumps(data))
        elif case.startswith("remove"):
            model.write_text(regular_source(expected=2 if case == "remove_gap" else 1))
        elif case == "kit_binding":
            model.write_text(KIT_SOURCE.replace('COMPONENTS = ["app"]', 'COMPONENTS = ["app"]\nPARENT = "app"'))
        else:
            raise ValueError(case)
        if case == "anchor_only":
            model.write_text(model.read_text().replace("native.py:value", "native.py:future_value"))
        if case in {"closed", "open"}:
            path = root / "native.py"
            value = 2 if case == "closed" else 3
            path.write_text(path.read_text().replace("def value(): return 1", f"def value(): return {value}"))
        if case == "engine_exception":
            (root / "engine.py").write_text('def broken(): raise RuntimeError("unanchored engine failure")\n')
            path = root / ".flowguard/map.json"
            data = json.loads(path.read_text());data["components"][0]["files"].append("engine.py");path.write_text(json.dumps(data))
            model.write_text(model.read_text().replace('actual = load_anchor(IMPLEMENTED_BY["Value"], root=Path.cwd())()',
                             'from engine import broken\n    actual = broken()'))
        if case == "adapter_exception":
            model.write_text(model.read_text().replace('actual = load_anchor(IMPLEMENTED_BY["Value"], root=Path.cwd())()',
                             'actual = load_anchor(IMPLEMENTED_BY["Value"], root=Path.cwd())().missing_property'))
        current, target = load_map(root), load_target(root)
        view = build_target_view(root, current, target)
        goal = target_goal_rules(root, target, view)
        report = native.check_target(root)
        text = native.render_target_report(report)
        return {"text": text, "goal": goal, "errors": [str(f) for f in report.errors],
                "todos": [str(f) for f in report.todos], "todo_codes": [f.code for f in report.todos]}


def native_cases():
    for case in ("native", "table", "missing_test", "recorded", "move", "move_twice", "anchor_exception",
                 "engine_exception", "adapter_exception", "kit_binding", "remove_clean", "remove_gap",
                 "anchor_only", "closed", "open", "shared_tuple", "changed_without_line", "changed_with_line"):
        result = native_case(case)
        text, goal = result["text"], "\n".join(result["goal"])
        if case == "anchor_only":
            ok = "only the missing anchor symbol 'future_value' in native.py" in text and "conformance did not run" in text
        elif case in {"closed", "open"}:
            prefix = "GAP CLOSED" if case == "closed" else "GAP OPEN"
            ok = prefix + " one:" in text and "native.py" in text and "NO GAP one:" not in text
        elif case == "shared_tuple":
            ok = result["goal"] == ["model one: ~answer"]
        elif case in {"native", "table", "anchor_exception"}:
            ok = "EXPECTED GAP one:" in text
            if case == "table":
                ok = ok and "~answer" in goal
        elif case.startswith("changed_"):
            blocked = "rule_changed_without_line" in result["todo_codes"]
            ok = "NO GAP one:" in text and not result["errors"] and blocked == (case == "changed_without_line")
        elif case in {"missing_test", "recorded"}:
            ok = "NO GAP one:" in text and "EXPECTED GAP one:" not in text
        elif case.startswith("move"):
            ok = "moved rules only: moved" in text and ">positive (from one)" in goal
            if case == "move_twice":
                ok = ok and "model second: +positive" in goal
        elif case in {"engine_exception", "adapter_exception"}:
            ok = bool(result["errors"]) and "EXPECTED GAP one:" not in text
        elif case in {"kit_binding", "remove_clean"}:
            ok = "no rule change: one" in text and "code gap(s) are TO-DO" not in text
        else:
            ok = "no rule change: one" in text and "code gap(s) are TO-DO" in text
        yield Fact(case, ok, json.dumps(result, sort_keys=True))
