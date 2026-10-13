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
the script exits with 0; its id is its directory name.  Runner models are never
cached because their inputs are not declared.

Each model runs in its own Python subprocess (fresh imports, no shared state).
Results are cached in .flowguard/cache/models.json keyed by the bytes of the
model file and of the files named in IMPLEMENTED_BY.  Only passes are reused;
``--force`` ignores the cache.  The cache is never authority.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path

from .common import CACHE_RELDIR, MODELS_RELDIR, content_digest
from .mapfile import read_model_contract

CACHE_SCHEMA = "flowguard.map.model_cache.v1"
DEFAULT_TIMEOUT = 300          # seconds per model


@dataclass
class ModelResult:
    model: str
    file: str
    status: str = "pass"                      # pass | fail | error
    problems: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    seconds: float = 0.0
    cached: bool = False


def model_files(root: Path) -> list[Path]:
    base = root / MODELS_RELDIR
    return sorted(p for p in base.glob("*.py") if not p.name.startswith("_")) if base.is_dir() else []


def _input_key(root: Path, path: Path, contract: dict) -> str:
    h = hashlib.sha256(content_digest(path).encode())
    for anchor in sorted(contract.get("IMPLEMENTED_BY", {}).values()):
        target = root / anchor.split(":", 1)[0]
        h.update(anchor.encode() + (content_digest(target).encode() if target.is_file() else b"<missing>"))
    return h.hexdigest()


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
    rel = path.relative_to(root).as_posix()
    started = time.time()
    try:
        proc = subprocess.run([sys.executable, "-m", "flowguard.map.proof", str(root), str(path)], cwd=root,
                              env=env, capture_output=True, text=True, timeout=timeout)
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
            for name, explorer in module.broken_variants().items():
                if explorer.explore().ok:
                    result.status = "fail"
                    result.problems.append(f"known-bad variant {name!r} passed: the invariants do not catch it")
        else:
            result.warnings.append("no broken_variants(): nothing proves the invariants can fail")
        if "conformance" in contract["functions"]:
            conf = module.conformance()
            if conf is not None and not conf.ok:
                result.status = "fail"
                result.problems.append("the real code does not conform to the model:\n" + conf.format_text(max_examples=1))
        else:
            result.warnings.append("no conformance(): the model is not replayed against the real code")
    except Exception:  # noqa: BLE001 - a crashing model is a reported error, not a crash of the runner
        result.status = "error"
        result.problems.append(traceback.format_exc(limit=4))
    result.seconds = round(time.time() - started, 3)
    return result


def model_id_of(path: str | Path) -> str:
    path = Path(path)
    return path.parent.name if path.name == "run_checks.py" else path.stem


def runner_files(root: Path) -> list[Path]:
    """run_checks.py scripts listed in map components' ``models`` (if a map exists)."""
    try:
        data = json.loads((root / ".flowguard" / "map.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    found = {m for c in data.get("components", []) for m in c.get("models", []) if m.endswith("run_checks.py")}
    return sorted(root / m for m in found if (root / m).is_file())


def run_runner(root: Path, path: Path, timeout: int = DEFAULT_TIMEOUT) -> ModelResult:
    package_parent = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), str(package_parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = ModelResult(model=model_id_of(path), file=path.relative_to(root).as_posix())
    started = time.time()
    try:
        proc = subprocess.run([sys.executable, str(path)], cwd=root, env=env, capture_output=True, text=True,
                              timeout=timeout)
        if proc.returncode != 0:
            result.status = "fail"
            tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-15:])
            result.problems.append(f"runner exited with {proc.returncode}:\n{tail}")
    except subprocess.TimeoutExpired:
        result.status = "error"
        result.problems.append(f"timed out after {timeout}s")
    result.seconds = round(time.time() - started, 3)
    return result


def run_models(root: Path, ids: list[str], *, force: bool = False, timeout: int = DEFAULT_TIMEOUT) -> list[ModelResult]:
    cache_path = root / CACHE_RELDIR / "models.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cache = cache["models"] if cache.get("schema") == CACHE_SCHEMA else {}
    except (OSError, ValueError, KeyError):
        cache = {}
    results = []
    for path in model_files(root):
        contract = read_model_contract(path)
        if ids and contract.get("MODEL_ID", path.stem) not in ids and path.stem not in ids:
            continue
        key = _input_key(root, path, contract)
        hit = cache.get(path.name)
        if hit and hit["key"] == key and not force:
            result = ModelResult(**hit["result"])
            result.cached = True
        else:
            result = run_model(root, path, timeout)
            if result.status == "pass":
                cache[path.name] = {"key": key, "result": {k: v for k, v in result.__dict__.items() if k != "cached"}}
            else:
                cache.pop(path.name, None)
        results.append(result)
    for path in runner_files(root):
        if ids and model_id_of(path) not in ids:
            continue
        results.append(run_runner(root, path, timeout))
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"schema": CACHE_SCHEMA, "models": cache}, indent=1), encoding="utf-8")
    except OSError:
        pass
    return results


def render_results(results: list[ModelResult]) -> str:
    if not results:
        return "no models found in .flowguard/models/ or in map components' models (or none matched the given ids)"
    lines = []
    for r in results:
        lines.append(f"{r.status.upper():5} {r.model:32} {r.seconds:>7}s" + ("  (cached)" if r.cached else ""))
        lines += ["      " + p.replace("\n", "\n      ") for p in r.problems]
        lines += [f"      warning: {w}" for w in r.warnings]
    failed = sum(r.status != "pass" for r in results)
    lines.append(f"models: {len(results) - failed} passed, {failed} failed")
    return "\n".join(lines)


if __name__ == "__main__":          # child process entry used by run_model()
    _root, _path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    print(json.dumps(run_model_in_process(_root, _path).__dict__))
