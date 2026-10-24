"""First-map drafts cover each finite source once, honoring ignores and limits.

All input features are valid source layouts, including syntax errors.  The
feature kit enumerates tiny layouts; native new_map results feed the same
ownership predicates as the abstract model and its genuinely broken outputs.
"""
from collections import Counter
from dataclasses import dataclass, replace
from pathlib import Path
import shutil
import tempfile

from flowguard.core import FunctionResult, Invariant
from flowguard.explorer import Explorer
from flowguard.kit import Feature, feature_conformance, feature_explorer
from flowguard.map.common import DEFAULT_IGNORE
from flowguard.map.inventory import build_inventory
from flowguard.map.mapfile import component_files
from flowguard.map.scan import new_map
from flowguard.workflow import Workflow

MODEL_ID = "scan_coverage"
PARENT = "map-file"
IMPLEMENTED_BY = {"NewMap": "flowguard/map/scan.py:new_map"}
TESTED_BY = {
    "each_source_exactly_once": ["tests/test_flowguard_map.py:test_first_map_covers_finite_sources_once_within_budget"],
    "ignored_files_absent": ["tests/test_flowguard_map.py:test_first_map_covers_finite_sources_once_within_budget"],
    "bounded_component_count": ["tests/test_flowguard_map.py:test_first_map_covers_finite_sources_once_within_budget"],
    "draft_components": ["tests/test_flowguard_map.py:test_first_map_covers_finite_sources_once_within_budget"],
}


@dataclass(frozen=True)
class ScanCase:
    files: tuple[tuple[str, str], ...] = (("api.py", "def run(): return True\n"),
                                        ("service/core.py", "def save(): return True\n"))
    sources: tuple[str, ...] = ("api.py", "service/core.py")
    ignored: tuple[str, ...] = ()
    test_files: tuple[str, ...] = ()
    limit: int = 2


def _nested(case):
    extra = (("pkg/__init__.py", ""), ("pkg/nested/__init__.py", ""),
             ("pkg/nested/tool.py", "def tool(): return True\n"))
    return replace(case, files=case.files + extra, sources=case.sources + tuple(path for path, _ in extra))


def _ignored(case):
    return replace(case, files=case.files + (("skip/hidden.py", "raise RuntimeError('ignored')\n"),),
                   ignored=("skip/hidden.py",))


def _tests(case):
    return replace(case, files=case.files + (("tests/test_api.py", "def test_run(): pass\n"),),
                   test_files=("tests/test_api.py",))


def _syntax(case):
    return replace(case, files=case.files + (("broken/bad.py", "def broken(:\n"),),
                   sources=case.sources + ("broken/bad.py",))


FEATURES = (
    Feature("nested_packages", False, (), _nested),
    Feature("ignored_directory", False, (), _ignored),
    Feature("test_file", False, (), _tests),
    Feature("syntax_error", False, (), _syntax),
)


@dataclass(frozen=True)
class ScanObservation:
    case: ScanCase
    owned: tuple[str, ...]
    component_ids: tuple[str, ...]
    statuses: tuple[str, ...]


RULES = (
    Invariant("each_source_exactly_once", "every source is owned exactly once and tests are not source owners",
              lambda state, trace: Counter(state.owned) == Counter(state.case.sources)),
    Invariant("ignored_files_absent", "ignored files never enter a component",
              lambda state, trace: not set(state.owned) & set(state.case.ignored)),
    Invariant("bounded_component_count", "draft component count respects the requested maximum",
              lambda state, trace: len(state.component_ids) <= state.case.limit),
    Invariant("draft_components", "all first-map proposals remain drafts",
              lambda state, trace: len(state.statuses) == len(state.component_ids) and all(s == "draft" for s in state.statuses)),
)


def _cases():
    cases = [ScanCase()]
    for names in feature_explorer(FEATURES).external_inputs:
        case = ScanCase()
        for name in names:
            case = next(feature for feature in FEATURES if feature.name == name).apply(case)
        cases.append(case)
    return tuple(cases)


def _abstract(case):
    # A single bucket is a permissible allocation, not the production directory
    # grouping algorithm.  Native conformance never calls this function.
    return ScanObservation(case, case.sources, ("draft",), ("draft",))


class NewMap:
    name = "NewMap"
    reads = ()
    writes = ("case", "owned", "component_ids", "statuses")

    def __init__(self, fault=""):
        self.fault = fault

    def apply(self, case, state):
        observed = _abstract(case)
        if self.fault == "drop":
            observed = replace(observed, owned=observed.owned[1:])
        elif self.fault == "duplicate":
            observed = replace(observed, owned=observed.owned + observed.owned[:1])
        elif self.fault == "include_ignored" and case.ignored:
            observed = replace(observed, owned=observed.owned + case.ignored)
        elif self.fault == "too_many":
            ids = tuple(f"bucket{index}" for index in range(case.limit + 1))
            observed = replace(observed, component_ids=ids, statuses=("draft",) * len(ids))
        elif self.fault == "confirmed":
            observed = replace(observed, statuses=("confirmed",))
        return (FunctionResult(observed.component_ids, observed, label="drafted"),)


def _explorer(fault=""):
    return Explorer(Workflow((NewMap(fault),)), initial_states=(_abstract(ScanCase()),), external_inputs=_cases(),
                    invariants=RULES, max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {"loses_source": _explorer("drop"), "duplicates_source": _explorer("duplicate"),
            "includes_ignored": _explorer("include_ignored"), "exceeds_component_limit": _explorer("too_many"),
            "confirms_draft": _explorer("confirmed")}


def _write(root, relative, source):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _review(template, case):
    with tempfile.TemporaryDirectory(prefix="flowguard-scan-case-") as directory:
        root = Path(directory) / "project"
        shutil.copytree(template, root)
        for relative, source in case.files:
            _write(root, relative, source)
        ignore = [*DEFAULT_IGNORE, "skip/**"]
        inv = build_inventory(root, ignore, with_bodies=False, write_cache=False)
        if set(inv.source) - set(inv.tests) != set(case.sources) or set(inv.tests) != set(case.test_files):
            raise RuntimeError("native inventory does not match the finite source/test fixture")
        if "broken/bad.py" in case.sources and not inv.py["broken/bad.py"].parse_error:
            raise RuntimeError("the syntax-error fixture did not reach the real parser")
        actual = new_map(root, inv, max_components=case.limit)
        components = actual["components"]
        observed = ScanObservation(case, tuple(path for component in components for path in component_files(component, inv)),
                                   tuple(component["id"] for component in components),
                                   tuple(component["status"] for component in components))
        failed = [rule.name for rule in RULES if not rule.check(observed, None).ok]
        if failed:
            raise RuntimeError(f"native new_map violates {failed!r}: {actual!r}")
        return True


def conformance():
    with tempfile.TemporaryDirectory(prefix="flowguard-scan-template-") as directory:
        template = Path(directory)
        for relative, source in ScanCase().files:
            _write(template, relative, source)
        return feature_conformance(FEATURES, ScanCase, lambda case: _review(template, case))
