"""Proof layer: run the executable models in .flowguard/models/.

A model file is a plain Python module:

    MODEL_ID = "order_placement"
    COMPONENTS = ["orders"]                                   # map components it protects
    IMPLEMENTED_BY = {"PlaceOrder": "shop/orders.py:OrderService.place"}
    def build_explorer(): ...     # required: flowguard.explorer.Explorer of the intended design; must pass
    def broken_variants(): ...    # required: {name: Explorer}; every variant must FAIL
    def conformance(): ...        # optional: replay model traces against the real code; .ok must be True

Each model runs in its own Python subprocess (fresh imports, no shared state).
Every requested model executes on every call: results are never cached, so a
PASS is always a statement about the current bytes, environment and interpreter.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from ..hazards import hazard_closures, model_hazards
from .check import PLACEHOLDER_ANCHOR, anchor_problems
from .common import parse_test_anchor
from .facts import AnchorWatch, PlaceholderAnchorError
from .mapfile import MapError, load_map, model_registry, read_model_contract, resolve_model_path, design_only_problem
from .tree import build_tree
from .runner import run_isolated_process

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
    rules: list[str] = field(default_factory=list)
    known_bad: list[str] = field(default_factory=list)
    code_gaps: list[str] = field(default_factory=list)
    hazards: list[str] = field(default_factory=list)              # open hazard hints
    closed_hazards: list[str] = field(default_factory=list)       # "<hint> (closed by known-bad X | invariant Y)"


def model_files(root: Path) -> list[Path]:
    return [root / e.path for e in model_registry(root).entries if e.kind == "contract"]


class _ViewModelLoader(importlib.machinery.SourceFileLoader):
    """Compile the selected bytes with their canonical project filename, without pyc."""
    def __init__(self, view, name: str, logical: str):
        self.view, self.logical = view, logical
        super().__init__(name, str(view.root / logical))

    def get_code(self, fullname):
        return self.source_to_code(self.get_data(self.path), self.path)

    def get_data(self, path):
        if Path(path) != Path(self.path):
            return super().get_data(path)
        physical = self.view.resolve(self.logical)
        if physical is None:
            raise ModuleNotFoundError(f"No model named {self.name!r} in the target view", name=self.name)
        return physical.read_bytes()


@contextmanager
def model_namespace(view):
    """One temporary namespace for direct model imports and every transitive helper."""
    if view is None:
        yield
        return
    names = view.model_names

    def belongs(name):
        # The engine package is not a user model module, even if a model's file
        # happens to use that basename; its direct anonymous load remains valid.
        return not (name == "flowguard" or name.startswith("flowguard.")) and (
            name.split(".")[0] in names or name in {"_flowguard_model_" + stem for stem in names})

    class Finder(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if "." in fullname or fullname not in names or fullname == "flowguard":
                return None
            logical = f".flowguard/models/{fullname}.py"
            if view.resolve(logical) is None:
                raise ModuleNotFoundError(f"No model named {fullname!r} in the target view", name=fullname)
            loader = _ViewModelLoader(view, fullname, logical)
            return importlib.util.spec_from_file_location(fullname, view.root / logical, loader=loader)

    before_modules = set(sys.modules)
    saved = {name: module for name, module in sys.modules.copy().items() if belongs(name)}
    saved_path, saved_finders, saved_bytecode = sys.path[:], sys.meta_path[:], sys.dont_write_bytecode
    for name in saved:
        sys.modules.pop(name, None)
    sys.meta_path.insert(0, Finder())
    sys.dont_write_bytecode = True
    try:
        yield
    finally:
        sys.path[:] = saved_path
        sys.meta_path[:] = saved_finders
        sys.dont_write_bytecode = saved_bytecode
        for name in list(sys.modules):
            module = sys.modules.get(name)
            filename = vars(module).get("__file__") if isinstance(module, type(sys)) else None
            new_project_module = (name not in before_modules and not (name == "flowguard" or name.startswith("flowguard."))
                                  and isinstance(filename, str) and Path(filename).resolve().is_relative_to(view.root))
            if belongs(name) or new_project_module:
                sys.modules.pop(name, None)
        sys.modules.update(saved)


@contextmanager
def _view_request(view):
    if view is None:
        yield []
        return
    with tempfile.TemporaryDirectory(prefix="flowguard-model-view-") as directory:
        path = Path(directory) / "view.json"
        path.write_text(json.dumps(view.to_payload()), encoding="utf-8")
        yield [str(path)]


def _load(root: Path, path: Path, *, view=None):
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    models_dir = str(root / ".flowguard/models")
    if models_dir not in sys.path:
        sys.path.append(models_dir)
    name = f"_flowguard_model_{path.stem}"
    loader = _ViewModelLoader(view, name, path.relative_to(root).as_posix()) if view is not None else None
    spec = importlib.util.spec_from_file_location(name, path, loader=loader)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module                    # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(module)
    return module


def run_model(root: Path, path: Path, timeout: int = DEFAULT_TIMEOUT, *, tests: bool = False, view=None) -> ModelResult:
    """Run one model in a fresh subprocess so imports and module state never leak between models."""
    package_parent = Path(__file__).resolve().parents[2]          # directory that contains 'flowguard/'
    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join([str(root), str(package_parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    rel = path.relative_to(root).as_posix()
    started = time.time()
    try:
        with _view_request(view) as extra:
            proc, timed_out, cleaned = run_isolated_process(
                [sys.executable, "-m", "flowguard.map.proof", str(root), str(path), *extra], cwd=root,
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
        result = ModelResult(**json.loads(lines[-1]))
    except (IndexError, ValueError, TypeError):
        tail = (proc.stderr or proc.stdout)[-2000:]
        return ModelResult(model=path.stem, file=rel, status="error", problems=[f"model process crashed:\n{tail}"],
                           seconds=round(time.time() - started, 3))
    if tests:
        run_bound_tests(root, path, result, timeout=timeout, view=view)
    return result


def run_bound_tests(root: Path, path: Path, result: ModelResult, *, timeout: int = DEFAULT_TIMEOUT, statuses: dict[str, str] | None = None, view=None) -> None:
    """Run a model's unique bound Python nodes once, then judge every actual item independently."""
    from .inventory import parse_python

    started = time.monotonic()
    try:
        physical = resolve_model_path(root, path.relative_to(root).as_posix(), view=view)
        if physical is None:
            raise FileNotFoundError(f"model {path} is absent from the target view")
        contract = read_model_contract(physical)
        retired = design_only_problem(contract, result.file)
        if retired:
            if retired not in result.problems:
                _fail(result, retired)
            return
        bindings = [(invariant, anchor) for invariant, anchors in contract.get("TESTED_BY", {}).items() for anchor in anchors]
        if statuses is not None:
            statuses.update({anchor: "not_run" for _, anchor in bindings})
        if not bindings:
            return
        anchors = list(contract.get("IMPLEMENTED_BY", {}).values())
        if not anchors:
            result.warnings.append("TESTED_BY reach not checked: no IMPLEMENTED_BY anchors")
            return
        nodes, parsed, exact_items = {}, {}, set()
        for invariant, anchor in bindings:
            rel, _, symbol = anchor.partition(":")
            if not rel.endswith(".py"):
                result.warnings.append(f"TESTED_BY {anchor} is not a Python test: reach not checked")
                continue
            try:
                rel, symbol, suffix = parse_test_anchor(anchor)
            except ValueError as exc:
                if statuses is not None:
                    statuses[anchor] = "failed"
                _fail(result, f"tested_by_failed {invariant} -> {anchor}: {exc}", code_gap=True)
                continue
            if rel not in parsed:
                parsed[rel] = parse_python(root, rel, rel[:-3].replace("/", "."), collect_bodies=False)
            info = parsed[rel]
            matches = [symbol] if symbol in info.symbols else sorted(s for s in info.symbols if s.endswith("." + symbol))
            if info.parse_error or len(matches) != 1:
                if statuses is not None:
                    statuses[anchor] = "failed"
                _fail(result, f"tested_by_failed {invariant} -> {anchor}: test symbol is missing, ambiguous or unreadable", code_gap=True)
                continue
            nodes[anchor] = rel + "::" + "::".join(matches[0].split(".")) + suffix
            if suffix:
                exact_items.add(anchor)
        if not nodes:
            return
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        package_parent = Path(__file__).resolve().parents[2]
        env["PYTHONPATH"] = os.pathsep.join([str(root), str(package_parent)] + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        with tempfile.TemporaryDirectory(prefix="flowguard-tested-by-") as folder:
            request, output = Path(folder) / "request.json", Path(folder) / "result.json"
            request.write_text(json.dumps({"anchors": anchors, "nodes": sorted(set(nodes.values())),
                                           **({"view": view.to_payload()} if view is not None else {})}), encoding="utf-8")
            proc, timed_out, cleaned = run_isolated_process(
                [sys.executable, "-m", "flowguard.map.testreach", str(root), str(request), str(output)],
                cwd=root, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
            if timed_out or not cleaned or not output.is_file():
                raise RuntimeError(f"TESTED_BY process exit={proc.returncode}; timeout={timed_out}; cleanup_confirmed={cleaned}; "
                                   + (proc.stderr or proc.stdout)[-1000:])
            payload = json.loads(output.read_text(encoding="utf-8"))
        diagnostic = ((proc.stdout or "") + "\n" + (proc.stderr or ""))[-2000:]
        if payload.get("error") or not payload.get("complete"):
            raise RuntimeError(payload.get("error") or "TESTED_BY result was incomplete")
        imports = payload.get("import_errors", [])
        external = [item for item in imports if item["type"] != "ModuleNotFoundError"
                    or not _project_missing(root, item.get("name"), view=view)]
        if external:
            raise RuntimeError("TESTED_BY dependency/import error: " + "; ".join(
                f"{item['type']} {item.get('name')!r} during {item['phase']} at {item['nodeid']}: {item['message']}"
                for item in external) + "\n" + diagnostic)
        known_failure = False
        for invariant, anchor in bindings:
            if anchor not in nodes:
                continue
            selector = nodes[anchor]
            items = [item for item in payload["items"] if item["nodeid"] == selector
                     or (anchor not in exact_items and item["nodeid"].startswith(selector + "["))]
            failed = [item["nodeid"] for item in items if item["failed"] or not item["entered"] or not item["call_passed"]]
            if not items or failed:
                if statuses is not None:
                    statuses[anchor] = "failed"
                _fail(result, f"tested_by_failed {invariant} -> {anchor}: {', '.join(failed) or 'test was not collected/executed'}", code_gap=True)
                known_failure = True
                continue
            missed = [item["nodeid"] for item in items if not (set(item["consulted"]) & set(anchors))]
            if statuses is not None:
                statuses[anchor] = "misses_anchor" if missed else "passed"
            if missed:
                _fail(result, f"tested_by_misses_anchor {invariant} -> {anchor}: the test ran but called or read none of IMPLEMENTED_BY; "
                              + ", ".join(missed), code_gap=True)
        if proc.returncode != 0:
            if known_failure:
                problem = "TESTED_BY pytest output: " + diagnostic
                result.problems.append(problem)
                result.code_gaps.append(problem)
            else:
                _fail(result, f"TESTED_BY pytest process exited {proc.returncode}: " + diagnostic)
    except Exception as exc:
        result.status = "error"
        result.problems.append(f"TESTED_BY environment/execution error: {exc}")
    finally:
        result.seconds = round(result.seconds + time.monotonic() - started, 3)


def _design_checks(explorer) -> set[str]:
    """Names of every property the intended design is judged by: invariants and declared reachability."""
    # same naming rule as flowguard.explorer.invariant_name, so violation names match
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


def _project_missing(root: Path, module: str | None, *, view=None) -> bool:
    """Only an actually inventoried project package can turn a missing import into work."""
    if not module or (view is not None and module.split(".")[0] in view.model_names):
        return False
    from .inventory import build_inventory
    from .mapfile import ignore_patterns

    try:
        data = view.data if view is not None else load_map(root)
        inv = build_inventory(root, ignore_patterns(data), with_bodies=False, write_cache=False)
    except (MapError, OSError):
        return False
    names = set()
    for info in inv.py.values():
        name = info.module.removeprefix("src.")
        names.add(name.split(".")[0])
    return module.split(".")[0] in names



def _fail(result: ModelResult, problem: str, *, code_gap: bool = False) -> None:
    if result.status != "error":
        result.status = "fail"
    result.problems.append(problem)
    if code_gap:
        result.code_gaps.append(problem)


def _anchor_verdict(result: ModelResult, root: Path, contract: dict, watch: AnchorWatch, where: str) -> None:
    """The one binding rule for contract models and runners: anchors are declared, resolve and are consulted."""
    anchors = contract.get("IMPLEMENTED_BY", {})
    if not anchors:
        _fail(result, "declares no IMPLEMENTED_BY anchors; name the real code this model is about ('path:Symbol'), "
                      "or plan it as a target model (python -m flowguard target start)")
    problems = anchor_problems(root, anchors.values())
    for name, anchor in sorted(anchors.items()):
        if anchor in problems:
            _fail(result, f"IMPLEMENTED_BY {name} -> {problems[anchor]}", code_gap=True)
    for anchor in watch.missing():
        if anchor not in problems:
            _fail(result, f"IMPLEMENTED_BY anchor {anchor} never ran and its file was never read {where}; "
                          "call that code or read it as code facts", code_gap=True)
    for anchor in watch.unobserved():
        if anchor not in problems:
            result.warnings.append(f"IMPLEMENTED_BY anchor {anchor} is not Python and its file was not read: "
                                   "execution not verified")


def _child_start_check(root: Path, path: Path, contract: dict, module, design, result: ModelResult, *, view=None) -> None:
    """Warn about the actual model-parent port, without lending its calls to the child proof."""
    if "project_parent_state" not in contract["functions"]:
        return
    parent_id = contract.get("PARENT", "?")
    try:
        from .inventory import build_inventory
        from .mapfile import ignore_patterns
        from flowguard.kit import reachable_states
        from types import ModuleType

        try:
            data = view.data if view is not None else load_map(root)
        except MapError:
            data = {"components": []}
        tree = build_tree(root, data, build_inventory(root, ignore_patterns(data), write_cache=(view is None)), view=view)
        node = tree.nodes.get(result.model)
        if node is None or node.parent_kind != "model" or tree.nodes[node.parent].kind != "contract":
            return
        parent_id = node.parent
        parent_path = (root / tree.nodes[parent_id].path).resolve()
        # Reuse only this check's already-imported same-file parent module. _load
        # itself still executes fresh, and no Explorer or reachable set is cached.
        state_module = sys.modules.get(type(design.initial_states[0]).__module__) if design.initial_states else None
        candidates = [state_module, *vars(module).values(), *list(sys.modules.values())]
        parent = next((m for m in candidates if isinstance(m, ModuleType)
                       and isinstance(filename := getattr(m, "__file__", None), str)
                       and Path(filename).resolve() == parent_path), None)
        if parent is None:
            parent = _load(root, parent_path, view=view)
        parent_design = parent.build_explorer()
        project = module.project_parent_state
        if not callable(project):
            raise TypeError("project_parent_state must be callable")
        states = reachable_states(parent_design, project)
        missing = [state for state in states if state not in design.initial_states]
        if missing:
            result.warnings.append(f"child_start_gap: {len(missing)} of {len(states)} states the parent '{parent_id}' reaches "
                "are not start states of this child; start it from "
                "flowguard.kit.reachable_states(<parent>.build_explorer(), project_parent_state)")
    except Exception as exc:
        detail = str(exc).splitlines()[0] if str(exc).splitlines() else type(exc).__name__
        result.warnings.append(f"child_start_gap not checked: parent '{parent_id}' could not be explored ({detail})")


def run_model_in_process(root: Path, path: Path, *, view=None) -> ModelResult:
    with model_namespace(view):
        physical = resolve_model_path(root, path.relative_to(root).as_posix(), view=view)
        if physical is None:
            return ModelResult(path.stem, path.relative_to(root).as_posix(), status="error", problems=["model is absent from the target view"])
        contract = read_model_contract(physical)
        result = ModelResult(model=contract.get("MODEL_ID", path.stem), file=path.relative_to(root).as_posix())
        retired = design_only_problem(contract, result.file)
        if retired:
            _fail(result, retired)
            return result
        if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
            result.status = "error"
            result.problems.append("a model file needs MODEL_ID and def build_explorer()")
            return result
        started = time.time()
        try:
            from flowguard.explorer import Explorer, invariant_name
            for anchor in contract.get("IMPLEMENTED_BY", {}).values():
                if PLACEHOLDER_ANCHOR in anchor:
                    raise PlaceholderAnchorError(anchor_problems(root, [anchor])[anchor])
            module = _load(root, path, view=view)
            anchors = contract.get("IMPLEMENTED_BY", {})
            calls = AnchorWatch(root, anchors.values())
            design = module.build_explorer()
            if not isinstance(design, Explorer):
                raise TypeError("build_explorer() must return flowguard.explorer.Explorer; no exploration executed")
            design_checks = _design_checks(design)
            if not design_checks:
                result.status = "fail"
                result.problems.append("build_explorer() declares no invariants or reachability checks")
            invariant_names = {invariant_name(i) for i in design.invariants}
            result.rules = sorted(invariant_names)
            for name in sorted(set(contract.get("TESTED_BY", {})) - invariant_names):
                result.status = "fail"
                result.problems.append(f"TESTED_BY names {name!r}, which is not an invariant of build_explorer()")
            with calls:
                report = design.explore()
            try:
                result.hazards = model_hazards(design)
            except Exception as exc:
                result.hazards = [f"inference failed: {exc}"]
            caught_variants: dict = {}
            untested = sorted(invariant_names - contract.get("TESTED_BY", {}).keys())
            if untested:
                result.warnings.append("invariant_untested: " + ", ".join(untested)
                                       + " have no TESTED_BY test; bind a test that fails when the rule is broken")
            if not report.explored_sequence_count or not report.transition_count:
                result.status = "fail"
                result.problems.append("build_explorer() explored no input transitions; the design proves nothing")
            for branch in report.exception_branches:
                if branch.error_type == "PlaceholderAnchorError":
                    raise PlaceholderAnchorError(branch.message)
            if not report.ok:
                result.status = "fail"
                result.problems.append("the intended design violates its invariants:\n" + report.format_text(max_examples=1))
            _child_start_check(root, path, contract, module, design, result, view=view)
            if "broken_variants" in contract["functions"]:
                variants = module.broken_variants()
                if not isinstance(variants, dict) or not variants:
                    raise ValueError("broken_variants() must return a nonempty dictionary; no known-bad proof executed")
                result.known_bad = sorted(str(name) for name in variants)
                covered: set[str] = set()
                for name, explorer in variants.items():
                    if not isinstance(explorer, Explorer):
                        raise TypeError(f"broken variant {name!r} must be a flowguard.explorer.Explorer")
                    bad = explorer.explore()
                    for branch in bad.exception_branches:
                        if branch.error_type == "PlaceholderAnchorError":
                            raise PlaceholderAnchorError(branch.message)
                    if bad.ok:
                        result.status = "fail"
                        result.problems.append(f"known-bad variant {name!r} passed: the invariants do not catch it")
                    else:
                        from flowguard.explorer import check_invariant
                        invariant_checks = {invariant_name(i): i for i in design.invariants}
                        caught = {v.invariant_name for v in bad.violations
                                  if v.invariant_name in invariant_checks and not v.message.startswith("invariant raised ")
                                  and not (oracle := check_invariant(invariant_checks[v.invariant_name], v.state, v.trace)).ok
                                  and not oracle.message.startswith("invariant raised ")}
                        invariant_hits = caught.copy()
                        caught |= _failed_checks(bad) - {v.invariant_name for v in bad.violations}
                        if bad.exploration_status != "budget_exhausted" and (caught & design_checks):
                            covered |= invariant_hits & invariant_names
                            caught_variants[name] = explorer
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
            if result.hazards and not result.hazards[0].startswith("inference failed: "):
                try:     # hints never change the verdict; a model closes them, nothing is recorded
                    closures = hazard_closures(design, caught_variants)
                except Exception:
                    closures = {}
                result.closed_hazards = [f"{hint} (closed by {closures[hint]})" for hint in result.hazards if hint in closures]
                result.hazards = [hint for hint in result.hazards if hint not in closures]
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
                        problem = f"model environment/interpreter error: {environment[0].message}; interpreter={sys.executable}"
                        result.problems.append(problem)
                        missing = re.search(r"No module named [\'\"]([^\'\"]+)", environment[0].message)
                        if missing and _project_missing(root, missing.group(1), view=view):
                            result.code_gaps.append(problem)
                    else:
                        result.status = "fail"
                        problem = "the real code does not conform to the model:\n" + conf.format_text(max_examples=1)
                        result.problems.append(problem)
                        result.code_gaps.append(problem)
            else:
                _fail(result, "abstract boundary only: no conformance(); replay the real code or compare it as code facts, "
                              "or plan it as a target model (python -m flowguard target start)")
            _anchor_verdict(result, root, contract, calls, "during build_explorer().explore() or conformance()")
        except PlaceholderAnchorError as exc:
            _fail(result, str(exc))
        except (ImportError, ModuleNotFoundError) as exc:
            result.status = "error"
            problem = f"model environment/interpreter error: {exc}; interpreter={sys.executable}"
            result.problems.append(problem)
            if isinstance(exc, ModuleNotFoundError) and _project_missing(root, exc.name, view=view):
                result.code_gaps.append(problem)
        except Exception:  # noqa: BLE001 - a crashing model is a reported error, not a crash of the runner
            result.status = "error"
            result.problems.append(traceback.format_exc(limit=4))
        result.seconds = round(time.time() - started, 3)
        return result


def model_id_of(path: str | Path) -> str:
    path = Path(path)
    return read_model_contract(path).get("MODEL_ID", path.stem)


def run_models(root: Path, ids: list[str], *, timeout: int = DEFAULT_TIMEOUT, tests: bool = False, view=None, inv=None) -> list[ModelResult]:
    has_map = True
    try:
        data = view.data if view is not None else load_map(root)
    except MapError:
        has_map = False
        data = {"components": []}
    registry = model_registry(root, data, view=view)
    from .inventory import build_inventory
    from .mapfile import ignore_patterns
    if inv is None:
        inv = build_inventory(root, ignore_patterns(data), write_cache=(view is None))
    tree = build_tree(root, data, inv, view=view)
    issues = [ModelResult(model="registry", file=issue.path, status="error",
                          problems=[f"{issue.code} {issue.path}: {issue.message}"])
              for issue in registry.issues]
    errors = []
    available = {entry.id for entry in registry.entries}
    if has_map:
        available.add("system")
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
    for entry in registry.entries:
        if ids and entry.id not in ids:
            continue
        path = root / entry.path
        results.append(run_model(root, path, timeout, tests=tests, view=view))
    if has_map and (not ids or "system" in ids):
        from .system_model import run_system_model
        results.append(run_system_model(root, data, inv, view=view))
    return results + issues


HAZARDS_SHOWN = 3


def render_results(results: list[ModelResult], *, all_hazards: bool = False) -> str:
    if not results:
        return "models: 0 declared, 0 executed; no model proof"
    def names(values):
        return ", ".join(values[:8]) + (f" +{len(values) - 8} more" if len(values) > 8 else "")

    lines = []
    for r in results:
        lines.append(f"{r.status.upper():5} {r.model:32} {r.seconds:>7}s")
        if r.rules or r.known_bad:
            lines.append(f"      rules: {names(r.rules)}; known-bad: {names(r.known_bad)}")
        shown = r.hazards if all_hazards else r.hazards[:HAZARDS_SHOWN]
        lines += [f"      hazard: {hazard}" for hazard in shown]
        if all_hazards:
            lines += [f"      hazard closed: {hazard}" for hazard in r.closed_hazards]
        if r.hazards or r.closed_hazards:
            lines.append(f"      hazards: {len(r.hazards)} open ({len(shown)} shown), {len(r.closed_hazards)} closed "
                         "by known-bad variants or invariants")
        lines += ["      " + p.replace("\n", "\n      ") for p in r.problems]
        lines += [f"      warning: {w}" for w in r.warnings]
    failed = sum(r.status != "pass" for r in results)
    lines.append(f"models: {len(results) - failed} passed, {failed} failed")
    return "\n".join(lines)


if __name__ == "__main__":          # child process entry used by run_model()
    _root, _path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    _view = None
    if len(sys.argv) > 3:
        from .targetfile import ModelView
        _view = ModelView.from_payload(json.loads(Path(sys.argv[3]).read_text(encoding="utf-8")))
    print(json.dumps(run_model_in_process(_root, _path, view=_view).__dict__))
