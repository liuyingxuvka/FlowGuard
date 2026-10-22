"""Proof layer: run the executable models in .flowguard/models/.

A model file is a plain Python module:

    MODEL_ID = "order_placement"
    COMPONENTS = ["orders"]                                   # map components it protects
    IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}
    def build_explorer(): ...     # required: flowguard.explorer.Explorer of the intended design; must pass
    def broken_variants(): ...    # required: {name: Explorer}; every variant must FAIL
    def conformance(): ...        # optional: replay model traces against the real code; .ok must be True

A second kind, *runner models*, is any ``run_checks.py`` listed in a map
component's ``models`` (for example ``.flowguard/verification/owners/<id>/run_checks.py``
next to ``.flowguard/models/owners/<id>/model.py``).  A runner model passes when
the script completes a nonempty check via run_owner and exits with 0; its id is its directory name.

Each model runs in its own Python subprocess (fresh imports, no shared state).
Every requested model executes on every call: results are never cached, so a
PASS is always a statement about the current bytes, environment and interpreter.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .check import anchor_problems
from .facts import AnchorWatch
from .mapfile import MapError, load_map, model_registry, read_model_contract, component_files
from .tree import build_tree
from .runner import COMPLETION_LINE, CONSULTED_LINE, LOADED_LINE, run_isolated_process

DEFAULT_TIMEOUT = 300          # seconds per model


@dataclass
class ModelResult:
    model: str
    file: str
    status: str = "pass"                      # pass | fail | error
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0
    uncovered_invariants: list[str] = field(default_factory=list)


def model_files(root: Path) -> list[Path]:
    return [root / e.path for e in model_registry(root).entries if e.kind == "contract"]


def _load(root: Path, path: Path):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    models_dir = str(root / ".flowguard/models")
    if models_dir not in sys.path:
        sys.path.append(models_dir)
    name = f"_flowguard_model_{path.stem}"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module                    # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def run_model(root: Path, path: Path, timeout: int = DEFAULT_TIMEOUT) -> ModelResult:
    """Run one model in a fresh subprocess so imports and module state never leak between models."""
    package_parent = Path(__file__).resolve().parents[2]          # directory that contains 'flowguard/'
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), str(package_parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    rel = path.relative_to(root).as_posix()
    started = time.time()
    try:
        proc, timed_out, cleaned = run_isolated_process(
            [sys.executable, "-m", "flowguard.map.proof", str(root), str(path)], cwd=root,
            env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if timed_out or not cleaned or proc.returncode != 0:
            return ModelResult(model=path.stem, file=rel, status="error",
                               problems=[f"model process exit={proc.returncode}; timeout={timed_out}; cleanup_confirmed={cleaned}"],
                               seconds=round(time.time() - started, 3))
    except subprocess.TimeoutExpired:
        return ModelResult(model=path.stem, file=rel, status="error", problems=[f"timed out after {timeout}s"],
                           seconds=round(time.time() - started, 3))
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    try:
        return ModelResult(**json.loads(lines[-1]))
    except (IndexError, ValueError, TypeError):
        tail = (proc.stderr or proc.stdout)[-2000:]
        return ModelResult(model=path.stem, file=rel, status="error", problems=[f"model process crashed:\n{tail}"],
                           seconds=round(time.time() - started, 3))


def _design_checks(explorer) -> set[str]:
    """Names of every property the intended design is judged by: invariants and declared reachability."""
    # same naming rule as flowguard.explorer._invariant_name, so violation names match
    names = {str(getattr(i, "name", getattr(i, "__name__", type(i).__name__))) for i in getattr(explorer, "invariants", ())}
    names |= {f"label:{label}" for label in getattr(explorer, "required_labels", ())}
    names |= {getattr(c, "name", "") for c in getattr(explorer, "required_reachable", ())}
    if getattr(explorer, "success_predicate", None) is not None:
        names.add("success_predicate")
    return names - {""}


def _failed_checks(report) -> set[str]:
    return ({v.invariant_name for v in getattr(report, "violations", ()) if not v.message.startswith("invariant raised ")}
            | {f.name for f in getattr(report, "reachability_failures", ())
               if not f.message.startswith("reachability predicate raised ") and f.description != "success predicate raised"})



def _fail(result: ModelResult, problem: str) -> None:
    if result.status != "error":
        result.status = "fail"
    result.problems.append(problem)


def _anchor_verdict(result: ModelResult, root: Path, contract: dict, watch: AnchorWatch, where: str) -> None:
    """The one binding rule for contract models and runners: anchors are declared, resolve and are consulted."""
    anchors = contract.get("IMPLEMENTED_BY", {})
    if contract.get("DESIGN_ONLY"):
        if not anchors:
            return
    elif not anchors:
        _fail(result, "declares no IMPLEMENTED_BY anchors; name the real code this model is about ('path:Symbol'), "
                      "or mark DESIGN_ONLY = '<reason>' while that code does not exist")
    problems = anchor_problems(root, anchors.values())
    for name, anchor in sorted(anchors.items()):
        if anchor in problems:
            _fail(result, f"IMPLEMENTED_BY {name} -> {problems[anchor]}")
    for anchor in watch.missing():
        if anchor not in problems:
            _fail(result, f"IMPLEMENTED_BY anchor {anchor} never ran and its file was never read {where}; "
                          "call that code or read it as code facts")
    for anchor in watch.unobserved():
        if anchor not in problems:
            result.warnings.append(f"IMPLEMENTED_BY anchor {anchor} is not Python and its file was not read: "
                                   "execution not verified")


def run_model_in_process(root: Path, path: Path) -> ModelResult:
    contract = read_model_contract(path)
    result = ModelResult(model=contract.get("MODEL_ID", path.stem), file=path.relative_to(root).as_posix())
    if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
        result.status = "error"
        result.problems.append("a model file needs MODEL_ID and def build_explorer()")
        return result
    started = time.time()
    try:
        from flowguard.explorer import Explorer, _invariant_name
        module = _load(root, path)
        anchors = contract.get("IMPLEMENTED_BY", {})
        calls = AnchorWatch(root, anchors.values())
        design = module.build_explorer()
        if not isinstance(design, Explorer):
            raise TypeError("build_explorer() must return flowguard.explorer.Explorer; no exploration executed")
        design_checks = _design_checks(design)
        if not design_checks:
            result.status = "fail"
            result.problems.append("build_explorer() declares no invariants or reachability checks")
        invariant_names = {_invariant_name(i) for i in design.invariants}
        for name in sorted(set(contract.get("TESTED_BY", {})) - invariant_names):
            result.status = "fail"
            result.problems.append(f"TESTED_BY names {name!r}, which is not an invariant of build_explorer()")
        with calls:
            report = design.explore()
        if not report.explored_sequence_count or not report.transition_count:
            result.status = "fail"
            result.problems.append("build_explorer() explored no input transitions; the design proves nothing")
        if not report.ok:
            result.status = "fail"
            result.problems.append("the intended design violates its invariants:\n" + report.format_text(max_examples=1))
        if "broken_variants" in contract["functions"]:
            variants = module.broken_variants()
            if not isinstance(variants, dict) or not variants:
                raise ValueError("broken_variants() must return a nonempty dictionary; no known-bad proof executed")
            covered: set[str] = set()
            for name, explorer in variants.items():
                if not isinstance(explorer, Explorer):
                    raise TypeError(f"broken variant {name!r} must be a flowguard.explorer.Explorer")
                bad = explorer.explore()
                if bad.ok:
                    result.status = "fail"
                    result.problems.append(f"known-bad variant {name!r} passed: the invariants do not catch it")
                else:
                    from flowguard.explorer import _check_invariant
                    invariant_checks = {_invariant_name(i): i for i in design.invariants}
                    caught = {v.invariant_name for v in bad.violations
                              if v.invariant_name in invariant_checks and not v.message.startswith("invariant raised ")
                              and not (oracle := _check_invariant(invariant_checks[v.invariant_name], v.state, v.trace)).ok
                              and not oracle.message.startswith("invariant raised ")}
                    invariant_hits = caught.copy()
                    caught |= _failed_checks(bad) - {v.invariant_name for v in bad.violations}
                    if bad.exploration_status != "budget_exhausted" and (caught & design_checks):
                        covered |= invariant_hits & invariant_names
                        continue
                    result.status = "fail"
                    result.problems.append(f"known-bad variant {name!r} fails without violating a design property; "
                                           "crashes, unrelated rules and budget exhaustion prove nothing")
            for name in sorted(invariant_names - covered):
                result.uncovered_invariants.append(name)
                result.warnings.append(f"invariant {name!r} is violated by no known-bad variant; "
                                       "add a variant that breaks it, or say why it cannot be broken")
        else:
            raise ValueError("no broken_variants(): define at least one known-bad Explorer; no known-bad proof executed")
        if "conformance" in contract["functions"]:
            with calls:
                conf = module.conformance()
            if conf is None or not isinstance(getattr(conf, "ok", None), bool) or not callable(getattr(conf, "format_text", None)):
                raise ValueError("conformance() must return a report with boolean .ok and format_text(); no real-code proof executed")
            if not conf.ok:
                environment = [v for v in getattr(conf, "violations", ())
                               if getattr(v, "rule_name", "") in {"adapter_exception", "adapter_reset"}
                               and ("ModuleNotFoundError:" in v.message or "ImportError:" in v.message)]
                if environment:
                    result.status = "error"
                    result.problems.append(f"model environment/interpreter error: {environment[0].message}; "
                                           f"interpreter={sys.executable}")
                else:
                    result.status = "fail"
                    result.problems.append("the real code does not conform to the model:\n" + conf.format_text(max_examples=1))
        elif contract.get("DESIGN_ONLY"):
            result.warnings.append(f"design only ({contract['DESIGN_ONLY']}): no conformance(); bind it once the code exists")
        else:
            _fail(result, "abstract boundary only: no conformance(); replay the real code or compare it as code facts, "
                          "or mark DESIGN_ONLY = '<reason>'")
        _anchor_verdict(result, root, contract, calls, "during build_explorer().explore() or conformance()")
    except (ImportError, ModuleNotFoundError) as exc:
        result.status = "error"
        result.problems.append(f"model environment/interpreter error: {exc}; interpreter={sys.executable}")
    except Exception:  # noqa: BLE001 - a crashing model is a reported error, not a crash of the runner
        result.status = "error"
        result.problems.append(traceback.format_exc(limit=4))
    result.seconds = round(time.time() - started, 3)
    return result


def model_id_of(path: str | Path) -> str:
    path = Path(path)
    return path.parent.name if path.name == "run_checks.py" else read_model_contract(path).get("MODEL_ID", path.stem)


def runner_files(root: Path) -> list[Path]:
    """run_checks.py scripts listed in map components' ``models`` (if a map exists)."""
    return [root / e.path for e in model_registry(root).entries if e.kind == "runner"]


def run_runner(root: Path, path: Path, timeout: int = DEFAULT_TIMEOUT, own_files: set[str] | None = None) -> ModelResult:
    package_parent = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), str(package_parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = ModelResult(model=model_id_of(path), file=path.relative_to(root).as_posix())
    started = time.time()
    try:
        contract = read_model_contract(path)
    except (OSError, SyntaxError, ValueError) as exc:
        result.status = "error"
        result.problems.append(f"cannot read the runner's IMPLEMENTED_BY / TESTED_BY literals: {exc}")
        return result
    try:
        proc, timed_out, cleaned = run_isolated_process(
            [sys.executable, "-c", "from flowguard.map.runner import _probe_main; raise SystemExit(_probe_main())", str(path)],
            cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
        if timed_out or not cleaned:
            result.status = "error"
            result.problems.append(f"timed out={timed_out} after {timeout}s; cleanup_confirmed={cleaned}")
            result.seconds = round(time.time() - started, 3)
            return result
        loaded, consulted = set(), {"anchors": [], "read": []}
        stderr = []
        for line in proc.stderr.splitlines():
            if line.startswith(LOADED_LINE):
                loaded.update(json.loads(line[len(LOADED_LINE):]))
            elif line.startswith(CONSULTED_LINE):
                consulted = json.loads(line[len(CONSULTED_LINE):])
            else:
                stderr.append(line)
        if proc.returncode != 0:
            result.status = "error" if proc.returncode == 3 and "no checks completed" in proc.stderr else "fail"
            tail = "\n".join((proc.stdout + "\n" + "\n".join(stderr)).strip().splitlines()[-15:])
            result.problems.append(f"runner exited with {proc.returncode}:\n{tail}")
        else:
            lines = proc.stdout.strip().splitlines()
            if not (lines and lines[-1].startswith(COMPLETION_LINE)):
                result.warnings.append("runner does not end with raise SystemExit(run_owner(main)); "
                                       "its exit code 0 is taken as the result")
        watch = AnchorWatch(root, contract.get("IMPLEMENTED_BY", {}).values())
        watch.called = set(consulted["anchors"])
        watch.read_files = {os.path.realpath(root / rel) for rel in consulted["read"]}
        if contract.get("DESIGN_ONLY"):
            result.warnings.append(f"design only ({contract['DESIGN_ONLY']}): bind it once the code exists")
        elif own_files is not None and not ((loaded | set(consulted["read"])) & own_files):
            _fail(result, "abstract boundary only: runner loaded no code of its bound components")
        _anchor_verdict(result, root, contract, watch, "by the runner")
    except subprocess.TimeoutExpired:
        result.status = "error"
        result.problems.append(f"timed out after {timeout}s")
    result.seconds = round(time.time() - started, 3)
    return result


def run_models(root: Path, ids: list[str], *, timeout: int = DEFAULT_TIMEOUT) -> list[ModelResult]:
    try:
        data = load_map(root)
    except MapError:
        data = {"components": []}
    registry = model_registry(root, data)
    from .inventory import build_inventory
    from .mapfile import ignore_patterns
    inv = build_inventory(root, ignore_patterns(data))
    tree = build_tree(root, data, inv)
    issues = [ModelResult(model="registry", file=issue.path, status="error",
                          problems=[f"{issue.code} {issue.path}: {issue.message}"])
              for issue in registry.issues]
    errors = []
    available = {entry.id for entry in registry.entries}
    for mid in sorted(set(ids) - available):
        message = f"unknown model id {mid!r}"
        component = next((c for c in data.get("components", []) if c["id"] == mid), None)
        if component:
            bound = [n.id for n in tree.models_for_component(mid)]
            message += f"; {mid!r} is a component id; registered model ids: {', '.join(bound) or '(none)'}"
        errors.append(ModelResult(model=mid, file="", status="error", problems=[message]))
    if errors:
        return errors + issues
    results = []
    own_files = {}
    for entry in registry.entries:
        if entry.kind == "runner":
            own_files[entry.path] = {f for c in data.get("components", [])
                                    if c["id"] in tree.nodes[entry.id].components for f in component_files(c, inv)}
    for entry in registry.entries:
        if ids and entry.id not in ids:
            continue
        path = root / entry.path
        results.append(run_runner(root, path, timeout, own_files.get(entry.path)) if entry.kind == "runner" else run_model(root, path, timeout))
    return results + issues


def render_results(results: list[ModelResult]) -> str:
    if not results:
        return "models: 0 declared, 0 executed; no model proof"
    lines = []
    for r in results:
        lines.append(f"{r.status.upper():5} {r.model:32} {r.seconds:>7}s")
        lines += ["      " + p.replace("\n", "\n      ") for p in r.problems]
        lines += [f"      warning: {w}" for w in r.warnings]
    failed = sum(r.status != "pass" for r in results)
    lines.append(f"models: {len(results) - failed} passed, {failed} failed")
    return "\n".join(lines)


if __name__ == "__main__":          # child process entry used by run_model()
    _root, _path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    print(json.dumps(run_model_in_process(_root, _path).__dict__))
