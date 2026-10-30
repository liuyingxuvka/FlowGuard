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

from concurrent.futures import ThreadPoolExecutor

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

from .check import PLACEHOLDER_ANCHOR, anchor_problems
from .common import parse_test_anchor, child_pytest_environment, child_import_path
from .facts import AnchorWatch, PlaceholderAnchorError
from .mapfile import MapError, load_map, model_registry, read_model_contract, resolve_model_path
from .tree import build_tree
from .runner import run_isolated_process

from .proof_request import (
    _view_request,
    _port_request,
)

DEFAULT_JOBS = min(4, os.cpu_count() or 1)

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
    test_seconds: float | None = None
    process_reason: str = ""
    sequences: int = 0
    size_observed: bool = False
    size_debts_used: list[int] = field(default_factory=list)
    advice_limit: float = 10.0


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


def run_model(
    root: Path,
    path: Path,
    timeout: int = DEFAULT_TIMEOUT,
    *,
    tests: bool = False,
    view=None,
    port_request=None,
) -> ModelResult:
    """Run one model in a fresh subprocess so imports and module state never leak between models."""
    try:
        data = view.data if view is not None else load_map(root)
    except MapError:
        data = {}
    env = child_pytest_environment(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(child_import_path(root, data))
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    rel = path.relative_to(root).as_posix()
    started = time.time()
    try:
        with _view_request(view, port_request) as extra:
            proc, timed_out, cleaned = run_isolated_process(
                [sys.executable, "-m", "flowguard.map.proof", str(root), str(path), *extra],
                cwd=root,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
            )
        if timed_out or not cleaned or proc.returncode != 0:
            return ModelResult(
                model=path.stem,
                file=rel,
                status="error",
                problems=[
                    f"model process exit={proc.returncode}; timeout={timed_out}; cleanup_confirmed={cleaned}"
                ],
                seconds=round(time.time() - started, 3),
            )
    except subprocess.TimeoutExpired:
        return ModelResult(
            model=path.stem,
            file=rel,
            status="error",
            problems=[f"timed out after {timeout}s"],
            seconds=round(time.time() - started, 3),
        )
    lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
    try:
        result = ModelResult(**json.loads(lines[-1]))
    except (IndexError, ValueError, TypeError):
        tail = (proc.stderr or proc.stdout)[-2000:]
        return ModelResult(
            model=path.stem,
            file=rel,
            status="error",
            problems=[f"model process crashed:\n{tail}"],
            seconds=round(time.time() - started, 3),
        )
    if tests:
        run_bound_tests(root, path, result, timeout=timeout, view=view)
    return result





def run_bound_tests(
    root: Path,
    path: Path,
    result: ModelResult,
    *,
    timeout: int = DEFAULT_TIMEOUT,
    statuses: dict[str, str] | None = None,
    view=None
) -> None:
    """Check each model's bound test items once through the test-reach owner."""
    from .proof_tests import _run_bound_tests

    return _run_bound_tests(
        root,
        path,
        result,
        timeout=timeout,
        statuses=statuses,
        view=view,
        _fail=_fail,
        _project_missing=_project_missing,
        run_isolated_process=run_isolated_process,
    )


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
        inv = build_inventory(root, ignore_patterns(data), with_bodies=False, write_cache=False, import_roots=tuple(data.get("import_roots", ())))
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


def _import_origin(root, anchor):
    path = anchor.partition(":")[0]
    expected = os.path.realpath(root / path)
    dotted = path.removesuffix(".py").replace("/", ".").removesuffix(".__init__")
    for name in dict.fromkeys((dotted, dotted.removeprefix("src."))):
        module = sys.modules.get(name)
        actual = getattr(module, "__file__", None)
        if isinstance(actual, str) and os.path.realpath(actual) != expected:
            return f" (imported {name} from {actual})"
    return ""


def _anchor_verdict(result: ModelResult, root: Path, contract: dict, watch: AnchorWatch, where: str) -> None:
    """The one binding rule for contract models and runners: anchors are declared, resolve and are consulted."""
    anchors = contract.get("IMPLEMENTED_BY", {})
    if not anchors:
        _fail(result, "declares no IMPLEMENTED_BY anchors; name the real code this model is about ('path:Symbol'), "
                      "or plan it as a target model (python -m flowguard target start)")
    uses = contract.get("USES", {})
    problems = anchor_problems(root, [*anchors.values(), *uses.values()])
    for name, anchor in sorted(anchors.items()):
        if anchor in problems:
            _fail(result, f"IMPLEMENTED_BY {name} -> {problems[anchor]}", code_gap=True)
    for name, anchor in sorted(uses.items()):
        if anchor in problems:
            _fail(result, f"USES {name} -> {problems[anchor]}", code_gap=True)
    if problems:  # native replay is deferred until every declared entry exists
        return
    for anchor in watch.missing():
        if anchor not in problems and anchor in anchors.values():
            _fail(result, f"IMPLEMENTED_BY anchor {anchor} never ran and its file was never read {where}; "
                          "call that code in conformance() or read it as code facts" + _import_origin(root, anchor))
    for anchor in sorted(set(uses.values()) - watch.called):
        _fail(result, f"USES anchor {anchor} never ran during conformance(); call it there or remove it")
    for anchor in watch.unobserved():
        if anchor not in problems:
            result.warnings.append(f"IMPLEMENTED_BY anchor {anchor} is not Python and its file was not read: "
                                   "execution not verified")


def child_start_hits(root, view, parent_logical, child_logical, field, values):
    """Count new-value starts; a batch of siblings shares one fresh parent exploration.

    A single child returns (hits, total, smallest value). An internal sibling batch
    returns those tuples keyed by logical child path; no states or verdicts persist.
    """
    from flowguard.kit import reachable_states

    batch = isinstance(child_logical, (list, tuple))
    children = list(child_logical) if batch else [child_logical]
    with model_namespace(view):
        parent = _load(root, root / parent_logical, view=view)
        sys.modules[Path(parent_logical).stem] = parent
        states = reachable_states(parent.build_explorer())
        result = {}
        for logical in children:
            child = _load(root, root / logical, view=view)
            hits = [state for state in states if getattr(state, field) in values
                    and child.project_parent_state(state) is not None]
            value = min((getattr(state, field) for state in hits), key=str) if hits else None
            result[logical] = len(hits), len(states), value
    return result if batch else result[child_logical]


def _child_start_check(
    root: Path,
    path: Path,
    contract: dict,
    module,
    design,
    result: ModelResult,
    *,
    view=None,
    tree=None,
) -> None:
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
        if tree is None:
            tree = build_tree(
                root,
                data,
                build_inventory(
                    root,
                    ignore_patterns(data),
                    write_cache=(view is None),
                    import_roots=tuple(data.get("import_roots", ())),
                ),
                view=view,
            )
        node = tree.nodes.get(result.model)
        if (
            node is None
            or node.parent_kind != "model"
            or tree.nodes[node.parent].kind != "contract"
        ):
            return
        parent_id = node.parent
        parent_path = (root / tree.nodes[parent_id].path).resolve()
        # Reuse only this check's already-imported same-file parent module. _load
        # itself still executes fresh, and no Explorer or reachable set is cached.
        state_module = (
            sys.modules.get(type(design.initial_states[0]).__module__)
            if design.initial_states
            else None
        )
        candidates = [state_module, *vars(module).values(), *list(sys.modules.values())]
        parent = next(
            (
                m
                for m in candidates
                if isinstance(m, ModuleType)
                and isinstance(filename := getattr(m, "__file__", None), str)
                and Path(filename).resolve() == parent_path
            ),
            None,
        )
        if parent is None:
            parent = _load(root, parent_path, view=view)
        parent_design = parent.build_explorer()
        project = module.project_parent_state
        if not callable(project):
            raise TypeError("project_parent_state must be callable")
        states = reachable_states(parent_design, project)
        missing = [state for state in states if state not in design.initial_states]
        if missing:
            result.warnings.append(
                f"child_start_gap: {len(missing)} of {len(states)} states the parent '{parent_id}' reaches "
                "are not start states of this child; start it from "
                "flowguard.kit.reachable_states(<parent>.build_explorer(), project_parent_state)"
            )
    except Exception as exc:
        detail = str(exc).splitlines()[0] if str(exc).splitlines() else type(exc).__name__
        result.warnings.append(
            f"child_start_gap not checked: parent '{parent_id}' could not be explored ({detail})"
        )


def uncovered_message(name: str) -> str:
    """One wording for an invariant no known-bad variant breaks (map models, release and target check)."""
    return (f"uncovered_invariant: invariant {name!r} is violated by no known-bad variant; add a known-bad variant "
            "that breaks it, or remove it from this model's invariants if this model cannot break it "
            "(a shared rule belongs to the model whose inputs can break it)")


def _exception_through_anchor(root, contract, error):
    """Match actual traceback code objects with the same symbol rules as AnchorWatch."""
    anchors = [*contract.get("IMPLEMENTED_BY", {}).values(), *contract.get("USES", {}).values()]
    watch = AnchorWatch(root, anchors)
    trace = error.__traceback__
    while trace is not None:
        watch._record_call(trace.tb_frame)
        trace = trace.tb_next
    return bool(watch.called)


def run_model_in_process(root: Path, path: Path, *, view=None, port_request=None) -> ModelResult:
    with model_namespace(view):
        physical = resolve_model_path(root, path.relative_to(root).as_posix(), view=view)
        if physical is None:
            return ModelResult(
                path.stem,
                path.relative_to(root).as_posix(),
                status="error",
                problems=["model is absent from the target view"],
            )
        contract = read_model_contract(physical)
        result = ModelResult(
            model=contract.get("MODEL_ID", path.stem), file=path.relative_to(root).as_posix()
        )
        if "MODEL_ID" not in contract or "build_explorer" not in contract["functions"]:
            result.status = "error"
            result.problems.append("a model file needs MODEL_ID and def build_explorer()")
            return result
        from .mapfile import process_model_reason

        try:
            data = view.data if view is not None else load_map(root)
        except MapError:
            data = {}
        result.process_reason = process_model_reason(data, contract, root=root)
        result.advice_limit = data.get("large_model_seconds", 10)
        started = time.time()
        phase = "design"
        try:
            from flowguard.explorer import Explorer, invariant_name

            for anchor in [
                *contract.get("IMPLEMENTED_BY", {}).values(),
                *contract.get("USES", {}).values(),
            ]:
                if PLACEHOLDER_ANCHOR in anchor:
                    raise PlaceholderAnchorError(anchor_problems(root, [anchor])[anchor])
            module = _load(root, path, view=view)
            anchors = [
                *contract.get("IMPLEMENTED_BY", {}).values(),
                *contract.get("USES", {}).values(),
            ]
            calls = AnchorWatch(root, anchors)
            design = module.build_explorer()
            if not isinstance(design, Explorer):
                raise TypeError(
                    "build_explorer() must return flowguard.explorer.Explorer; no exploration executed"
                )
            design_checks = _design_checks(design)
            if not design_checks:
                result.status = "fail"
                result.problems.append(
                    "build_explorer() declares no invariants or reachability checks"
                )
            invariant_names = {invariant_name(i) for i in design.invariants}
            result.rules = sorted(invariant_names)
            for name in sorted(set(contract.get("TESTED_BY", {})) - invariant_names):
                result.status = "fail"
                result.problems.append(
                    f"TESTED_BY names {name!r}, which is not an invariant of build_explorer()"
                )
            report = design.explore()
            result.sequences = report.explored_sequence_count
            result.size_observed = report.exploration_complete
            from .lint import apply_accepted_debts
            from .lint_models import size_finding

            finding = size_finding(result.model, "sequences", result.sequences)
            if finding:
                findings, used = apply_accepted_debts([finding], data.get("accepted_debts", []), root=root)
                result.size_debts_used = sorted(used)
                finding = findings[0]
                if finding.level == "error":
                    _fail(result, "large_model: " + finding.message)
                elif finding.level == "warn":
                    result.warnings.append("large_model: " + finding.message)
            from .port import Port, run_findings
            from .inventory import build_inventory
            from .mapfile import ignore_patterns

            if port_request is not None:
                from .port import port_from_payload
                from .tree import ModelNode, ModelTree

                ports = {
                    mid: port_from_payload(value) for mid, value in port_request["ports"].items()
                }
                nodes = {
                    mid: ModelNode(id=mid, source="", **metadata)
                    for mid, metadata in port_request["nodes"].items()
                }
                tree = ModelTree(nodes, {})
            else:
                inv = build_inventory(
                    root,
                    ignore_patterns(data),
                    with_bodies=False,
                    write_cache=False,
                    import_roots=tuple(data.get("import_roots", ())),
                )
                tree = (
                    build_tree(root, data, inv, view=view)
                    if data.get("components") is not None
                    else None
                )
                ports = (
                    {mid: node.contract.get("port", Port()) for mid, node in tree.nodes.items()}
                    if tree is not None
                    else {}
                )
            if tree is not None and result.model in tree.nodes:
                for finding in run_findings(
                    result.model, design, report, ports[result.model], tree, ports
                ):
                    if finding.level == "warn":
                        result.warnings.append(finding.message)
                    else:
                        _fail(result, finding.message)
            untested = sorted(invariant_names - contract.get("TESTED_BY", {}).keys())
            if untested and contract.get("TESTED_BY") and not result.process_reason:
                result.warnings.append(
                    "invariant_untested: "
                    + ", ".join(untested)
                    + " have no TESTED_BY test; bind a test that fails when the rule is broken"
                )
            if not report.explored_sequence_count or not report.transition_count:
                result.status = "fail"
                result.problems.append(
                    "build_explorer() explored no input transitions; the design proves nothing"
                )
            for branch in report.exception_branches:
                if branch.error_type == "PlaceholderAnchorError":
                    raise PlaceholderAnchorError(branch.message)
            if not report.ok:
                result.status = "fail"
                result.problems.append(
                    "the intended design violates its invariants:\n"
                    + report.format_text(max_examples=1)
                )
            _child_start_check(root, path, contract, module, design, result, view=view, tree=tree)
            if "broken_variants" in contract["functions"]:
                variants = module.broken_variants()
                if not isinstance(variants, dict) or not variants:
                    raise ValueError(
                        "broken_variants() must return a nonempty dictionary; no known-bad proof executed"
                    )
                result.known_bad = sorted(str(name) for name in variants)
                covered: set[str] = set()
                for name, explorer in variants.items():
                    if not isinstance(explorer, Explorer):
                        raise TypeError(
                            f"broken variant {name!r} must be a flowguard.explorer.Explorer"
                        )
                    bad = explorer.explore()
                    for branch in bad.exception_branches:
                        if branch.error_type == "PlaceholderAnchorError":
                            raise PlaceholderAnchorError(branch.message)
                    if bad.ok:
                        result.status = "fail"
                        result.problems.append(
                            f"known-bad variant {name!r} passed: the invariants do not catch it"
                        )
                    else:
                        from flowguard.explorer import check_invariant

                        invariant_checks = {invariant_name(i): i for i in design.invariants}
                        caught = {
                            v.invariant_name
                            for v in bad.violations
                            if v.invariant_name in invariant_checks
                            and not v.message.startswith("invariant raised ")
                            and not (
                                oracle := check_invariant(
                                    invariant_checks[v.invariant_name], v.state, v.trace
                                )
                            ).ok
                            and not oracle.message.startswith("invariant raised ")
                        }
                        invariant_hits = caught.copy()
                        caught |= _failed_checks(bad) - {v.invariant_name for v in bad.violations}
                        if bad.exploration_status != "budget_exhausted" and (
                            caught & design_checks
                        ):
                            covered |= invariant_hits & invariant_names
                            continue
                        result.status = "fail"
                        result.problems.append(
                            f"known-bad variant {name!r} fails without violating a design property; "
                            "crashes, unrelated rules and budget exhaustion prove nothing"
                        )
                for name in sorted(invariant_names - covered):
                    result.uncovered_invariants.append(name)
                    result.status = "fail"
                    result.problems.append(uncovered_message(name))
            else:
                raise ValueError(
                    "no broken_variants(): define at least one known-bad Explorer; no known-bad proof executed"
                )
            missing_anchors = anchor_problems(root, anchors)
            if result.process_reason:
                result.seconds = round(time.time() - started, 3)
                return result
            if "conformance" in contract["functions"] and not missing_anchors:
                phase = "conformance"
                calls.called.difference_update(contract.get("USES", {}).values())
                with calls:
                    conf = module.conformance()
                if (
                    conf is None
                    or not isinstance(getattr(conf, "ok", None), bool)
                    or not callable(getattr(conf, "format_text", None))
                ):
                    raise ValueError(
                        "conformance() must return a report with boolean .ok and format_text(); no real-code proof executed"
                    )
                if not conf.ok:
                    adapter_errors = [
                        v
                        for v in getattr(conf, "violations", ())
                        if getattr(v, "rule_name", "") in {"adapter_exception", "adapter_reset"}
                    ]
                    native_errors = bool(adapter_errors) and all(
                        getattr(v, "exception", None) is not None
                        and _exception_through_anchor(root, contract, v.exception)
                        for v in adapter_errors
                    )
                    design_error = bool(adapter_errors) and not native_errors
                    environment = next(
                        (
                            v
                            for v in adapter_errors
                            if "ImportError:" in v.message or "ModuleNotFoundError:" in v.message
                        ),
                        None,
                    )
                    result.status = "error" if design_error or environment else "fail"
                    problem = (
                        "conformance adapter failed:\n"
                        if design_error
                        else "the real code does not conform to the model:\n"
                    ) + conf.format_text(max_examples=1)
                    if environment:
                        problem = f"model environment/interpreter error: {environment.message}; interpreter={sys.executable}"
                    if design_error:
                        problem += '; observe new behaviour defensively, e.g. getattr(report, "blocked", None)'
                    result.problems.append(problem)
                    if not design_error:
                        result.code_gaps.append(problem)
            elif "conformance" not in contract["functions"]:
                _fail(
                    result,
                    "abstract boundary only: no conformance(); replay the real code or compare it as code facts, "
                    "or plan it as a target model (python -m flowguard target start)",
                )
            _anchor_verdict(result, root, contract, calls, "during conformance()")
        except PlaceholderAnchorError as exc:
            _fail(result, str(exc))
        except (ImportError, ModuleNotFoundError) as exc:
            result.status = "error"
            native = phase == "conformance" and _exception_through_anchor(root, contract, exc)
            problem = f"model environment/interpreter error: {exc}; interpreter={sys.executable}"
            if not native:
                problem += (
                    '; observe new behaviour defensively, e.g. getattr(report, "blocked", None)'
                )
            result.problems.append(problem)
            if native:
                result.code_gaps.append(problem)
        except (
            Exception
        ) as exc:  # a broken model is a design error unless native conformance raised
            result.status = "error"
            native = phase == "conformance" and _exception_through_anchor(root, contract, exc)
            problem = traceback.format_exc(limit=4)
            if not native:
                problem += (
                    '; observe new behaviour defensively, e.g. getattr(report, "blocked", None)'
                )
            result.problems.append(problem)
            if native:
                result.code_gaps.append(problem)
        result.seconds = round(time.time() - started, 3)
        return result





def run_models(
    root: Path,
    ids: list[str],
    *,
    timeout: int = DEFAULT_TIMEOUT,
    tests: bool = False,
    view=None,
    inv=None,
    jobs: int = 1,
) -> list[ModelResult]:
    if type(jobs) is not int or not 1 <= jobs <= 32:
        raise ValueError("jobs must be between 1 and 32")
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
        inv = build_inventory(
            root,
            ignore_patterns(data),
            write_cache=(view is None),
            import_roots=tuple(data.get("import_roots", ())),
        )
    tree = build_tree(root, data, inv, view=view)
    issues = [
        ModelResult(
            model="registry",
            file=issue.path,
            status="error",
            problems=[f"{issue.code} {issue.path}: {issue.message}"],
        )
        for issue in registry.issues
    ]
    errors = []
    available = {entry.id for entry in registry.entries}
    if has_map:
        available.add("system")
    for mid in sorted(set(ids) - available):
        message = f"unknown model id {mid!r}"
        component = next((c for c in data.get("components", []) if c["id"] == mid), None)
        if component:
            bound = [n.id for n in tree.models_for_component(mid)]
            message += (
                f"; {mid!r} is a component id; registered model ids: {', '.join(bound) or '(none)'}"
            )
        errors.append(ModelResult(model=mid, file="", status="error", problems=[message]))
    if errors:
        return errors + issues
    selected = [entry for entry in registry.entries if not ids or entry.id in ids]
    shared = _port_request(tree, selected[0].id) if selected else None

    def execute(entry):
        request = _port_request(tree, entry.id, shared=shared)
        return run_model(
            root, root / entry.path, timeout, tests=tests, view=view, port_request=request
        )

    if jobs == 1:
        results = [execute(entry) for entry in selected]
    else:
        with ThreadPoolExecutor(max_workers=jobs) as pool:
            results = list(pool.map(execute, selected))
    if has_map and (not ids or "system" in ids):
        from .system_model import run_system_model

        results.append(run_system_model(root, data, inv, view=view))
    _size_debt_warnings(root, data, inv, tree, registry, results, view=view)
    return results + issues


def _size_debt_warnings(root, data, inv, tree, registry, results, *, view=None):
    """Judge only active size debts whose actual model scope was fully observed."""
    from .debts import evaluate_debts
    from .lint import apply_accepted_debts
    from .lint_models import model_size_findings

    evaluation = evaluate_debts(root, data)
    debts = data.get("accepted_debts", [])
    pending = [index for index in evaluation.active_indices if debts[index].get("code") == "large_model"]
    if not pending:
        return
    static = model_size_findings(root, data, inv, view=view, tree=tree)
    _, used = apply_accepted_debts(static, debts, evaluation=evaluation)
    for result in results:
        used.update(result.size_debts_used)
    observed = {result.model: result for result in results if result.size_observed}
    complete = not registry.issues and {entry.id for entry in registry.entries} <= set(observed)
    for index in pending:
        debt = debts[index]
        if index in used:
            continue
        if "component" in debt:
            receiver = observed.get(debt["component"])
        else:
            receiver = next(iter(results), None) if complete else None
        if receiver is not None:
            receiver.warnings.append(f"debt_stale {debt.get('component', '*')}: accepted debt matches no finding: {debt['reason']}")




def render_results(results: list[ModelResult]) -> str:
    if not results:
        return "models: 0 declared, 0 executed; no model proof"
    def names(values):
        return ", ".join(values[:8]) + (f" +{len(values) - 8} more" if len(values) > 8 else "")

    lines = []
    for r in results:
        suffix = f"  tests {r.test_seconds}s" if r.test_seconds is not None else ""
        if r.process_reason:
            suffix += "  (process model: no code yet)"
        lines.append(f"{r.status.upper():5} {r.model:32} {r.seconds}s{suffix}")
        if r.status != "pass" and (r.rules or r.known_bad):
            lines.append(f"      rules: {names(r.rules)}; known-bad: {names(r.known_bad)}")
        lines += ["      " + p.replace("\n", "\n      ") for p in r.problems]
        lines += [f"      warning: {w}" for w in r.warnings]
    groups = {}
    for result in results:
        seconds = result.seconds + (result.test_seconds or 0)
        if seconds > result.advice_limit:
            groups.setdefault(result.advice_limit, []).append((result.model, seconds))
    for limit, models in sorted(groups.items()):
        models.sort(key=lambda item: (-item[1], item[0]))
        values = ", ".join(f"{name} {seconds:.1f}s" for name, seconds in models)
        lines.append(f"INFO large_model x{len(models)}: {values} (model + bound tests over the {limit:g}s advice); "
                     "a split usually helps: references/routes.md#Split a model")
    failed = sum(r.status != "pass" for r in results)
    lines.append(f"models: {len(results) - failed} passed, {failed} failed")
    return "\n".join(lines)


if __name__ == "__main__":          # child process entry used by run_model()
    _root, _path = Path(sys.argv[1]).resolve(), Path(sys.argv[2]).resolve()
    _view, _ports = None, None
    if len(sys.argv) > 3:
        from .targetfile import ModelView
        _payload = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
        if "port_request" in _payload:
            _ports = _payload["port_request"]
            _view = ModelView.from_payload(_payload["view"]) if _payload["view"] is not None else None
        else:
            _view = ModelView.from_payload(_payload)
    print(json.dumps(run_model_in_process(_root, _path, view=_view, port_request=_ports).__dict__))
