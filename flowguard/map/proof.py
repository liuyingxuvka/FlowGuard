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
Results are cached only when existing COMPONENTS and dependency ownership close
the input boundary. Keys include mapped source bytes, direct anchors, the model,
map and Python/engine identity. Unknown helper/config/dynamic inputs rerun.
Only passes are reused; ``--force`` ignores the cache. The cache is never authority.
"""

from __future__ import annotations

import ast
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

from .common import CACHE_RELDIR, content_digest, read_source
from .inventory import build_inventory, parse_python, resolve_import
from .mapfile import (MapError, component_files, component_graph, ignore_patterns, load_map,
                      model_registry, read_model_contract)

CACHE_SCHEMA = "flowguard.map.model_cache.v2"
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
    return [root / e.path for e in model_registry(root).entries if e.kind == "contract"]


def _engine_digest() -> str:
    """Calculated once per model run, never during map reads or impact analysis."""
    package = Path(__file__).resolve().parents[1]
    h = hashlib.sha256(sys.version.encode())
    for source in sorted(package.rglob("*.py")):
        h.update(source.relative_to(package).as_posix().encode() + content_digest(source).encode())
    return h.hexdigest()


def _cache_inputs(root: Path, path: Path, contract: dict, data: dict, inv) -> tuple[list[str], str]:
    """Use existing ownership/dependency declarations; unknown inputs mean rerun.

    This is deliberately a conservative boundary check, not a new dependency
    resolver or input-manifest schema. Dynamic file/environment/import access
    cannot be proven complete by the map and therefore disables PASS reuse.
    """
    components = contract.get("COMPONENTS", [])
    if not data or not components:
        return [], "map and nonempty COMPONENTS bindings are required"
    by_id = {c["id"]: c for c in data["components"]}
    graph = component_graph(data, inv)
    pending, selected = list(components), set()
    inputs = {path.relative_to(root).as_posix()}
    while pending:
        cid = pending.pop()
        if cid in selected:
            continue
        if cid not in by_id:
            return [], f"unknown component {cid!r}"
        selected.add(cid)
        comp = by_id[cid]
        owned = component_files(comp, inv)
        if not owned:
            return [], f"component {cid!r} has no known source inputs"
        inputs.update(owned)
        pending.extend(set(comp.get("depends_on", [])) | graph.get(cid, set()))
    inputs.update(anchor.split(":", 1)[0] for anchor in contract.get("IMPLEMENTED_BY", {}).values())
    modules = {info.module: rel for rel, info in inv.py.items()}
    # Imported local helpers must already belong to the mapped input boundary.
    for rel in sorted(inputs):
        source = root / rel
        if not source.is_file():
            return [], f"missing input {rel}"
        if source.suffix != ".py":
            return [], f"non-Python input boundary not verified: {rel}"
        info = inv.py.get(rel) or parse_python(root, rel, "_flowguard_model")
        if info.parse_error:
            return [], f"unparseable input {rel}"
        for imp in info.imports:
            target = resolve_import(imp, modules)
            top = imp.split(":", 1)[0].split(".", 1)[0]
            if top in {"random", "time", "datetime", "subprocess", "socket", "urllib", "http", "secrets"}:
                return [], f"external/runtime input import {imp!r} in {rel}"
            if imp.rsplit(":", 1)[-1] in {"open", "getenv", "import_module", "__import__", "eval", "exec"}:
                return [], f"dynamic input import {imp!r} in {rel}"
            if target and target not in inputs and top != "flowguard":
                return [], f"helper {target} is outside the mapped input boundary"
            if not target and top not in sys.stdlib_module_names and top != "flowguard":
                return [], f"unresolved import {imp!r} in {rel}"
        tree = ast.parse(read_source(source))
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr == "environ":
                return [], f"environment input in {rel}"
            if isinstance(node, ast.Call):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
                if name in {"open", "read_text", "read_bytes", "read", "load", "getenv", "import_module",
                            "__import__", "exec", "eval", "getattr", "get_data", "get_resource_reader"}:
                    return [], f"dynamic/helper/config input ({name}) in {rel}"
    return sorted(inputs), ""


def _input_key(root: Path, path: Path, contract: dict, *, engine_digest: str | None = None,
               inputs: list[str] | None = None) -> str:
    if inputs is None:
        try:
            data = load_map(root)
        except MapError:
            data = {}
        inputs, _ = _cache_inputs(root, path, contract, data, build_inventory(root, ignore_patterns(data)))
    h = hashlib.sha256((engine_digest if engine_digest is not None else _engine_digest()).encode())
    for rel in inputs or [path.relative_to(root).as_posix()]:
        target = root / rel
        h.update(rel.encode() + (content_digest(target).encode() if target.is_file() else b"<missing>"))
    # A dependency/ownership edit changes the meaning of the same source bytes.
    mapping = root / ".flowguard/map.json"
    h.update(content_digest(mapping).encode() if mapping.is_file() else b"<no-map>")
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


def run_models(root: Path, ids: list[str], *, force: bool = False, timeout: int = DEFAULT_TIMEOUT) -> list[ModelResult]:
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
    selected = [entry for entry in registry.entries if not ids or entry.id in ids]
    inv = build_inventory(root, ignore_patterns(data)) if any(e.kind == "contract" for e in selected) else None
    engine_digest = _engine_digest() if inv is not None else ""
    cache_path = root / CACHE_RELDIR / "models.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        cache = cache["models"] if cache.get("schema") == CACHE_SCHEMA else {}
        if not isinstance(cache, dict):
            cache = {}
    except (OSError, ValueError, KeyError):
        cache = {}
    results = []
    for entry in selected:
        path = root / entry.path
        if entry.kind == "runner":
            results.append(run_runner(root, path, timeout))
            continue
        contract = read_model_contract(path)
        inputs, reason = _cache_inputs(root, path, contract, data, inv)
        key = _input_key(root, path, contract, inputs=inputs, engine_digest=engine_digest)
        hit = cache.get(path.name)
        cached_result = None
        if not reason and isinstance(hit, dict) and hit.get("key") == key and not force:
            try:
                candidate = ModelResult(**hit["result"])
                if candidate.model == entry.id and candidate.file == entry.path and candidate.status == "pass":
                    cached_result = candidate
            except (KeyError, TypeError):
                pass                      # corrupt cache entries are never proof
        if cached_result is not None:
            result = cached_result
            result.cached = True
        else:
            result = run_model(root, path, timeout)
            if reason:
                result.warnings.append(f"cache not reused: {reason}")
            if result.status == "pass" and not reason:
                cache[path.name] = {"key": key, "result": {k: v for k, v in result.__dict__.items() if k != "cached"}}
            else:
                cache.pop(path.name, None)
        results.append(result)
    try:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"schema": CACHE_SCHEMA, "models": cache}, indent=1), encoding="utf-8")
    except OSError:
        pass
    return results


def render_results(results: list[ModelResult]) -> str:
    if not results:
        return "models: 0 declared, 0 executed; no model proof"
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
