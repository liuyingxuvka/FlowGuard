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
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .mapfile import MapError, load_map, model_registry, read_model_contract, component_files
from .runner import COMPLETION_LINE, LOADED_LINE

DEFAULT_TIMEOUT = 300          # seconds per model


@dataclass
class ModelResult:
    model: str
    file: str
    status: str = "pass"                      # pass | fail | error
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0


def model_files(root: Path) -> list[Path]:
    return [root / e.path for e in model_registry(root).entries if e.kind == "contract"]


def _load(root: Path, path: Path):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
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
        proc = subprocess.run([sys.executable, "-m", "flowguard.map.proof", str(root), str(path)], cwd=root,
                              env=env, capture_output=True, encoding="utf-8", errors="replace", timeout=timeout)
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


class _AnchorCalls:
    """Record which IMPLEMENTED_BY anchors run during the model run (global sys.settrace call events only)."""

    def __init__(self, root: Path, anchors: dict) -> None:
        self.by_path: dict[str, dict[str, str]] = {}
        self.not_python: list[str] = []
        for anchor in anchors.values():
            rel, _, symbol = anchor.partition(":")
            if not rel.endswith(".py"):
                self.not_python.append(anchor)       # JS/TS etc.: execution cannot be observed in-process
                continue
            self.by_path.setdefault(os.path.realpath(root / rel), {})[symbol] = anchor
        self.seen: set[str] = set()
        self._files: dict[str, dict[str, str]] = {}

    def _hook(self, frame, event, arg):
        if event != "call":
            return None
        code = frame.f_code
        symbols = self._files.get(code.co_filename)
        if symbols is None:
            symbols = self._files[code.co_filename] = self.by_path.get(os.path.realpath(code.co_filename), {})
        if symbols:
            qualname = code.co_qualname
            for symbol, anchor in symbols.items():
                if qualname == symbol or ("." not in symbol and qualname.startswith(symbol + ".")):
                    self.seen.add(anchor)
        return None                       # never trace lines

    def __enter__(self):
        if self.by_path:
            self._previous = sys.gettrace()
            self._previous_thread = threading.gettrace()
            sys.settrace(self._hook)
            threading.settrace(self._hook)
        return self

    def __exit__(self, *exc) -> None:
        if self.by_path:
            sys.settrace(self._previous)
            threading.settrace(self._previous_thread)

    def missing(self) -> set[str]:
        return {a for symbols in self.by_path.values() for a in symbols.values()} - self.seen


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
        calls = _AnchorCalls(root, anchors)
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
                    caught |= _failed_checks(bad) - {v.invariant_name for v in bad.violations}
                    if bad.exploration_status != "budget_exhausted" and (caught & design_checks):
                        continue
                    result.status = "fail"
                    result.problems.append(f"known-bad variant {name!r} fails without violating a design property; "
                                           "crashes, unrelated rules and budget exhaustion prove nothing")
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
        else:
            result.warnings.append("abstract boundary only: no conformance(); real implementation not verified")
        for anchor in sorted(calls.missing()):
            if result.status != "error":
                result.status = "fail"
            result.problems.append(f"IMPLEMENTED_BY anchor {anchor} never ran during build_explorer().explore() "
                                   "or conformance(); call that code or declare an abstract model with IMPLEMENTED_BY = {}")
        for anchor in calls.not_python:
            result.warnings.append(f"IMPLEMENTED_BY anchor {anchor} is not Python: execution not verified")
        if not anchors and "conformance" in contract["functions"]:
            result.warnings.append("abstract boundary only: conformance is not tied to IMPLEMENTED_BY code")
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
        proc = subprocess.run([sys.executable, "-c", "from flowguard.map.runner import _probe_main; raise SystemExit(_probe_main())", str(path)], cwd=root, env=env, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        loaded = set()
        stderr = []
        for line in proc.stderr.splitlines():
            if line.startswith(LOADED_LINE):
                loaded.update(json.loads(line[len(LOADED_LINE):]))
            else:
                stderr.append(line)
        if proc.returncode != 0:
            result.status = "error" if proc.returncode == 3 and "no FlowGuard checks completed" in proc.stderr else "fail"
            tail = "\n".join((proc.stdout + "\n" + "\n".join(stderr)).strip().splitlines()[-15:])
            result.problems.append(f"runner exited with {proc.returncode}:\n{tail}")
        else:
            lines = proc.stdout.strip().splitlines()
            completion = None
            if lines and lines[-1].startswith(COMPLETION_LINE):
                try:
                    completion = json.loads(lines[-1][len(COMPLETION_LINE):])
                except ValueError:
                    pass
            if not isinstance(completion, dict) or completion.get("exit_code") != 0 or type(completion.get("checked")) is not int or completion["checked"] <= 0:
                result.status = "error"
                result.problems.append("runner exited 0 without completed checks; end with:\n"
                                       "from flowguard.map.runner import run_owner\n"
                                       "raise SystemExit(run_owner(main))")
        if own_files is not None and not (loaded & own_files):
            result.warnings.append("abstract boundary only: runner loaded no code of its bound components")
    except subprocess.TimeoutExpired:
        result.status = "error"
        result.problems.append(f"timed out after {timeout}s")
    result.seconds = round(time.time() - started, 3)
    return result


def run_models(root: Path, ids: list[str], *, timeout: int = DEFAULT_TIMEOUT) -> list[ModelResult]:
    try:
        data = load_map(root)
    except MapError:
        data = {}
    registry = model_registry(root, data)
    errors = [ModelResult(model=issue.code, file=issue.path, status="error", problems=[issue.message])
              for issue in registry.issues]
    available = {entry.id for entry in registry.entries}
    for mid in sorted(set(ids) - available):
        message = f"unknown model id {mid!r}"
        component = next((c for c in data.get("components", []) if c["id"] == mid), None)
        if component:
            bound = sorted(entry.id for entry in registry.entries if entry.path in component.get("models", []))
            message += f"; {mid!r} is a component id; registered model ids: {', '.join(bound) or '(none)'}"
        errors.append(ModelResult(model=mid, file="", status="error", problems=[message]))
    if errors:
        return errors
    results = []
    own_files = {}
    if any(entry.kind == "runner" for entry in registry.entries):
        from .common import DEFAULT_IGNORE
        from .inventory import build_inventory
        from .mapfile import ignore_patterns
        inv = build_inventory(root, ignore_patterns(data))
        inv.set_explicit_sources([pattern for comp in data.get("components", []) for pattern in comp.get("files", [])])
        for entry in registry.entries:
            if entry.kind == "runner":
                own_files[entry.path] = {f for c in data.get("components", [])
                                        if entry.path in c.get("models", []) for f in component_files(c, inv)}
    for entry in registry.entries:
        if ids and entry.id not in ids:
            continue
        path = root / entry.path
        results.append(run_runner(root, path, timeout, own_files.get(entry.path)) if entry.kind == "runner" else run_model(root, path, timeout))
    return results


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
