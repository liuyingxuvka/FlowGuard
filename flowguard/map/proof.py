"""Proof layer: run the executable models in .flowguard/models/.

A model file is a plain Python module:

    MODEL_ID = "order_placement"
    COMPONENTS = ["orders"]                                   # map components it protects
    IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}
    def build_explorer(): ...     # required: flowguard.explorer.Explorer of the intended design; must pass
    def broken_variants(): ...    # recommended: {name: Explorer}; every variant must FAIL
    def conformance(): ...        # optional: replay model traces against the real code; .ok must be True

A second kind, *runner models*, is any ``run_checks.py`` listed in a map
component's ``models`` (for example ``.flowguard/verification/owners/<id>/run_checks.py``
next to ``.flowguard/models/owners/<id>/model.py``).  A runner model passes when
the script exits with 0; its id is its directory name.

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

from .mapfile import MapError, load_map, model_registry, read_model_contract

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


def run_model_in_process(root: Path, path: Path) -> ModelResult:
    contract = read_model_contract(path)
    result = ModelResult(model=contract.get("MODEL_ID", path.stem), file=path.relative_to(root).as_posix())
    if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
        result.status = "error"
        result.problems.append("a model file needs MODEL_ID and def build_explorer()")
        return result
    started = time.time()
    try:
        module = _load(root, path)
        report = module.build_explorer().explore()
        if not report.ok:
            result.status = "fail"
            result.problems.append("the intended design violates its invariants:\n" + report.format_text(max_examples=1))
        if "broken_variants" in contract["functions"]:
            variants = module.broken_variants()
            if not isinstance(variants, dict) or not variants:
                raise ValueError("broken_variants() must return a nonempty dictionary; no known-bad proof executed")
            for name, explorer in variants.items():
                if explorer.explore().ok:
                    result.status = "fail"
                    result.problems.append(f"known-bad variant {name!r} passed: the invariants do not catch it")
        else:
            result.warnings.append("no broken_variants(): nothing proves the invariants can fail")
        if "conformance" in contract["functions"]:
            conf = module.conformance()
            if conf is None or not isinstance(getattr(conf, "ok", None), bool) or not callable(getattr(conf, "format_text", None)):
                raise ValueError("conformance() must return a report with boolean .ok and format_text(); no real-code proof executed")
            if not conf.ok:
                result.status = "fail"
                result.problems.append("the real code does not conform to the model:\n" + conf.format_text(max_examples=1))
        else:
            result.warnings.append("abstract boundary only: no conformance(); real implementation not verified")
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


def run_runner(root: Path, path: Path, timeout: int = DEFAULT_TIMEOUT) -> ModelResult:
    package_parent = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), str(package_parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    result = ModelResult(model=model_id_of(path), file=path.relative_to(root).as_posix())
    started = time.time()
    try:
        proc = subprocess.run([sys.executable, str(path)], cwd=root, env=env, capture_output=True,
                              encoding="utf-8", errors="replace", timeout=timeout)
        if proc.returncode != 0:
            result.status = "fail"
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
            result.problems.append(f"runner exited with {proc.returncode}:\n{tail}")
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
    for entry in registry.entries:
        if ids and entry.id not in ids:
            continue
        path = root / entry.path
        results.append(run_runner(root, path, timeout) if entry.kind == "runner" else run_model(root, path, timeout))
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
