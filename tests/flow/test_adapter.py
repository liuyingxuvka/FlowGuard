"""The flow bridge uses the one native producer and existing conformance owner."""
from __future__ import annotations

import json
from pathlib import Path
import textwrap

import pytest

from flowguard.flow import Model, need
from flowguard.flow.adapter import check_trace, fields, trace_calls, walk, witness_trace
from flowguard.flow.explore import Bounds, explore
from flowguard.native import session
from flowguard.replay import ReplayInput


def bound(tmp_path, methods, *, output="ok", model_step=None, parameters=None, initial=0, extra=""):
    source = "class Refusal(Exception):\n    pass\nclass Program:\n    def __init__(self):\n        self.n = 0\n"
    source += textwrap.indent(textwrap.dedent(methods).strip() + "\n", "    ")
    source += extra
    (tmp_path / "app.py").write_text(source)
    model = Model("bound")
    model.root = tmp_path
    model.field("n", [0, 1, 2], initial)
    if model_step is None:
        @model.action()
        def step(s):
            need(s["n"] < 2, "at the limit")
            s["n"] += 1
            return output
    else:
        model.action(**(parameters or {}))(model_step)
    binding = model.bind_adapter(
        {"root": str(tmp_path), "system": "app:Program", "classes": ["app:Program"], "refusal": ["app:Refusal"]},
        state=lambda snapshot: {"n": fields(snapshot, names=("n",))["n"]},
        operations={a.name: a.name for a in model.actions},
    )
    return explore(model), binding


def test_model_code_output_only_drift_has_the_actual_input_path(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "code"
        ''', output="model")
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "drift"
    assert result.conformance.violations[0].rule_name == "projected_output_matches"
    assert result.conformance.violations[0].expected_step.function_output == "model"
    assert result.inputs == (ReplayInput(None, "step", {}),)
    assert result.native["steps"][0]["outcome"] == "success"


def test_unknown_real_state_is_drift_instead_of_a_partial_projection(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n = 9
            return "ok"
        ''')
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "drift" and "outside the model domain" in result.conformance.violations[0].message


def test_code_operation_omitted_from_model_is_reported(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "ok"
        def reset(self):
            self.n = 0
        ''')
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "drift"
    assert "system.reset" in result.conformance.violations[0].message


def test_refused_final_step_is_compared_and_captured(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            if self.n >= 2:
                raise Refusal("at the limit")
            self.n += 1
            return "ok"
        ''')
    end = next(i for i, state in enumerate(graph.states) if state == (2,))
    trace = witness_trace(graph, end, last=0)
    assert [s.label for s in trace.steps] == ["success", "success", "refusal"]
    result = check_trace(graph, trace)
    assert result.status == "conformant"
    assert result.native["steps"][-1]["outcome"] == "refusal"
    assert result.native["steps"][-1]["before"] == result.native["steps"][-1]["after"]


def test_native_crash_is_visible_and_engine_fault_is_not_a_sut_crash(tmp_path, monkeypatch):
    graph, _ = bound(tmp_path, '''
        def step(self):
            raise ValueError("actual SUT crash")
        ''')
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "drift" and result.native["steps"][0]["outcome"] == "crash"
    original = session.run_isolated_process

    def injected(command, **kwargs):
        command = list(command)
        command[2] = "raise RuntimeError('injected native failure')\n" + command[2]
        return original(command, **kwargs)

    monkeypatch.setattr(session, "run_isolated_process", injected)
    with pytest.raises(session.NativeEngineError, match="injected native failure"):
        check_trace(graph, trace_calls(graph, [0]))


def test_expected_values_never_enter_production_recipe(tmp_path):
    secret = "model-only-oracle-4385"
    graph, binding = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "actual"
        ''', output=secret)
    seen = []

    def dispatch(value):
        assert isinstance(value, ReplayInput)
        assert not hasattr(value, "new_state") and not hasattr(value, "function_output")
        seen.append(value)
        return {"name": "step", "kwargs": value.function_input}

    binding.dispatch = dispatch
    result = check_trace(graph, trace_calls(graph, [0]))
    assert seen == [ReplayInput(None, "step", {})]
    assert secret not in json.dumps(result.native)


def test_snapshot_restore_and_stale_source_use_native_owner(tmp_path):
    graph, binding = bound(tmp_path, '''
        def step(self):
            if self.n >= 2:
                raise Refusal("at the limit")
            self.n += 1
            return "ok"
        ''')
    result = check_trace(graph, trace_calls(graph, [0]))
    checkpoint = binding.snapshot(result)
    restored = binding.restore(checkpoint, tail=(ReplayInput(None, "step", {}),))
    assert fields(restored["final"], names=("n",)) == {"n": 2}
    source = tmp_path / "app.py"
    source.write_text(source.read_text() + "\n# changed actual source\n")
    with pytest.raises(session.UnsupportedWorld, match="checkpoint.*stale"):
        binding.restore(checkpoint)


def test_walk_has_a_finite_seeded_step_budget_and_ignores_disjoint_code(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            if self.n >= 2:
                raise Refusal("at the limit")
            self.n += 1
            return "ok"
        ''')
    (tmp_path / "unrelated.py").write_text('raise AssertionError("disjoint module must not execute")\n')
    result = walk(graph, steps=4, seed=17)
    assert result.status == "conformant"
    assert len(result.native["steps"]) == 4
    assert result.seed == 17 and result.step_budget == 4
    assert result.to_dict()["scope"] == "finite native calls; no original-conflict closure proof"


def test_dynamic_public_lookup_is_explicit_unknown_inventory(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "ok"
        def __getattr__(self, name):
            raise AttributeError(name)
        ''')
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "unknown" and "dynamic attribute lookup" in result.reason


def test_branch_repair_permit_refuse_only_drift_keeps_its_actual_arguments(tmp_path):
    def repair(s, place):
        return None
    graph, _ = bound(tmp_path, '''
        def repair(self, place):
            if place == "branch":
                raise Refusal("repairs only at main")
        ''', model_step=repair, parameters={"place": ("main", "branch")})
    result = check_trace(graph, trace_calls(graph, [1]))
    assert result.status == "drift"
    assert result.conformance.violations[0].rule_name == "label_matches"
    assert result.inputs[0].function_input == {"place": "branch"}
    assert result.native["steps"][0]["outcome"] == "refusal"


def test_concrete_symmetry_witness_keeps_each_objects_output_and_state(tmp_path):
    (tmp_path / "app.py").write_text('''class Program:
    def __init__(self):
        self.items = {"T1": 0, "T2": 0}
    def mark(self, t):
        self.items[t] = 1
        return t
''')
    model = Model("objects")
    model.root = tmp_path
    ids = model.objects("tool", "T1", "T2")
    model.field("n", [0, 1], 0, over=ids)
    @model.action(t=ids)
    def mark(s, t):
        need(s["n", t] == 0, "already marked")
        s["n", t] = 1
        return t
    model.bind_adapter({"root": str(tmp_path), "system": "app:Program", "classes": ["app:Program"]},
                       state=lambda snapshot: {("n", t): value for t, value in fields(snapshot)["items"].items()},
                       operations={"mark": "mark"})
    graph = explore(model)
    assert graph.sym is not None
    target = next(i for i, state in enumerate(graph.states) if state == (1, 1))
    trace = witness_trace(graph, target)
    assert [step.function_output for step in trace.steps] == ["T1", "T2"]
    assert trace.steps[0].new_state == {("n", "T1"): 1, ("n", "T2"): 0}
    assert check_trace(graph, trace).status == "conformant"


def test_initial_state_and_old_saved_prefix_are_compared_without_oracle_seeding(tmp_path):
    import base64
    graph, binding = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "ok"
        @classmethod
        def load(cls, path):
            import json
            result = cls()
            with open(path) as source:
                result.n = json.load(source)["n"]
            return result
        ''', initial=1)
    binding.start = {"files": {"old.json": base64.b64encode(b'{"n":1}').decode()}}
    binding.prefix = ({"name": "load", "args": [{"$file": "old.json"}], "replace": True},)
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "conformant"
    assert fields(result.native["initial"], names=("n",)) == {"n": 0}
    assert fields(result.native["steps"][0]["after"], names=("n",)) == {"n": 1}
    other = tmp_path / "wrong_initial"
    other.mkdir()
    initial_graph, _ = bound(other, '''
        def step(self):
            self.n += 1
            return "ok"
        ''', initial=1)
    failed = check_trace(initial_graph, trace_calls(initial_graph, []))
    assert failed.status == "drift"
    assert failed.conformance.violations[0].rule_name == "projected_state_matches"


def test_missing_native_capture_is_unknown_even_after_real_calls(tmp_path, monkeypatch):
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "ok"
        ''')
    original = session.replay
    def without_evidence(*args, **kwargs):
        actual = original(*args, **kwargs)
        actual.pop("rule_captures")
        return actual
    monkeypatch.setattr(session, "replay", without_evidence)
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "unknown" and result.conformance is None
    assert len(result.native["steps"]) == 1


def test_a_loaded_model_binds_its_project_root_without_importing_the_sut(tmp_path):
    from flowguard.flow.model import load_model
    (tmp_path / "app.py").write_text('''class Program:
    def __init__(self):
        self.n = 0
    def step(self):
        self.n = 1
        return "ok"
''')
    model_path = tmp_path / ".flowguard/flow/bound.py"
    model_path.parent.mkdir(parents=True)
    model_path.write_text('''from flowguard.flow import Model
from flowguard.flow.adapter import fields
m = Model("loaded", covers=["app.py:Program"])
m.field("n", [0, 1], 0)
@m.action()
def step(s):
    s["n"] = 1
    return "ok"
m.bind_adapter({"system": "app:Program", "classes": ["app:Program"]},
               state=lambda snapshot: fields(snapshot, names=("n",)),
               operations={"step": "step"})
MODEL = m
''')
    loaded = load_model(model_path, tmp_path)
    assert set(loaded.reads) == {".flowguard/flow/bound.py", "app.py"}
    graph = explore(loaded.model)
    assert check_trace(graph, trace_calls(graph, [0])).status == "conformant"


def test_actual_constructor_crash_keeps_failure_facts_without_an_initial_state(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            return "ok"
        ''')
    source = tmp_path / "app.py"
    source.write_text(source.read_text().replace("self.n = 0", 'raise ValueError("constructor failed")'))
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "unknown"
    assert result.native["evidence_error"]["outcome"] == "crash"
    assert result.native["evidence_error"]["exception"]["type"] == "builtins:ValueError"
    assert "initial" not in result.native


def test_real_native_calls_do_not_hide_a_conformance_judgment_fault(tmp_path, monkeypatch):
    import flowguard.flow.adapter as bridge
    from flowguard.conformance import ConformanceRule
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "ok"
        ''')
    def fail(expected, observed):
        raise RuntimeError("injected comparison failure")
    monkeypatch.setattr(bridge, "default_conformance_rules",
                        lambda: (ConformanceRule("fault", "fault control", fail),))
    with pytest.raises(session.NativeEngineError, match="injected comparison failure") as failed:
        check_trace(graph, trace_calls(graph, [0]))
    assert failed.value.phase == "judgment"


def test_a_capped_model_does_not_fabricate_a_native_walk_or_turn_unknown_into_error(tmp_path):
    graph, _ = bound(tmp_path, '''
        def step(self):
            self.n += 1
            return "ok"
        ''')
    capped = explore(graph.model, Bounds(1))
    assert not capped.complete
    result = walk(capped, steps=3, seed=17)
    assert result.status == "unknown" and result.native == {} and result.conformance is None
    assert result.step_budget == 3 and "incomplete" in result.reason


def test_declared_constant_dispatch_arguments_are_real_inputs(tmp_path):
    graph, binding = bound(tmp_path, '''
        def step(self, amount):
            self.n += amount
            return "ok"
        ''')
    binding.operations["step"] = {"name": "step", "kwargs": {"amount": 1}}
    result = check_trace(graph, trace_calls(graph, [0]))
    assert result.status == "conformant"
    assert result.native["steps"][0]["call"]["kwargs"] == {"amount": 1}
