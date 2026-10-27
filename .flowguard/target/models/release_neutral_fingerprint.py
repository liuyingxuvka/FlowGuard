OUTPUTS = {'fingerprint': ('current', 'migrate', 'stale')}
"""Version declarations are neutral; all other bytes and format migration matter."""
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory

from flowguard import FunctionResult, Invariant, InvariantResult, Workflow
from flowguard.explorer import Explorer
from flowguard.map.facts import CodeFactsReport, Fact

MODEL_ID = "release_neutral_fingerprint"
PARENT = "map-file"
IMPLEMENTED_BY = {'ReleaseNeutral': 'flowguard/map/mapfile.py:_release_neutral', 'ComponentState': 'flowguard/map/mapfile.py:component_state', 'Fingerprint': 'flowguard/map/mapfile.py:fingerprint', 'FormatGuard': 'flowguard/map/mapfile.py:format_guard'}
USES = {
    'BuildInventory': 'flowguard/map/inventory.py:build_inventory',
}
TESTED_BY = {'version_only_change_is_current': ['tests/test_release_neutral_fingerprint.py:test_version_only_bump_keeps_components_current'], 'other_edit_is_stale': ['tests/test_release_neutral_fingerprint.py:test_non_version_edit_in_version_file_is_stale'], 'format_one_map_migrates_once': ['tests/test_release_neutral_fingerprint.py:test_format1_map_migrates_once', 'tests/test_release_neutral_fingerprint.py:test_format2_map_with_format1_value_is_stale'], 'formula_change_names_format': ['tests/test_release_neutral_fingerprint.py:test_formula_change_without_format_bump_warns']}
CASES = ("version_py", "version_toml", "version_file", "docstring", "other_py", "other_name", "other_tool",
         "legacy_format1", "legacy_format2", "formula_edit_same_format", "formula_edit_bumped", "other_function_edit")
EXPECTED = {case: "current" if case.startswith("version_") or case == "docstring" else "stale" for case in CASES}
EXPECTED["legacy_format1"] = "migrate"
EXPECTED.update(formula_edit_same_format="warn", formula_edit_bumped="none", other_function_edit="none")


@dataclass(frozen=True)
class State:
    case: str = ""
    fingerprint: str = ""
    format_notice: str = ""
    @property
    def status(self): return self.format_notice or self.fingerprint


class Step:
    name = "Fingerprint"
    reads = ()
    writes = ("case", "fingerprint", "format_notice")

    def __init__(self, defect=""):
        self.defect = defect

    def apply(self, event, state):
        status = EXPECTED[event]
        if self.defect == "stale_on_version_bump" and event.startswith("version_"):
            status = "stale"
        if self.defect == "blanks_every_version_line" and event == "other_tool":
            status = "current"
        if self.defect == "migrates_forever" and event == "legacy_format2":
            status = "migrate"
        if event in {"formula_edit_same_format", "formula_edit_bumped", "other_function_edit"}:
            if self.defect == "silent_formula_change" and event == "formula_edit_same_format":
                status = "none"
            return (FunctionResult(status, State(event, "", status), label=event),)
        return (FunctionResult(status, State(event, status), label=event),)


def _holds(state, cases):
    return InvariantResult.fail(f"{state.case}: {state.status}") if state.case in cases and state.status != EXPECTED[state.case] else InvariantResult.pass_()


INVARIANTS = (
    Invariant("version_only_change_is_current", "only version values may change without staleness",
              lambda s, t: _holds(s, ("version_py", "version_toml", "version_file", "docstring"))),
    Invariant("other_edit_is_stale", "other source and TOML fields retain byte identity",
              lambda s, t: _holds(s, ("other_py", "other_name", "other_tool"))),
    Invariant("format_one_map_migrates_once", "legacy pointers migrate only in format one",
              lambda s, t: _holds(s, ("legacy_format1", "legacy_format2"))),
    Invariant("formula_change_names_format", "a change to fingerprint or _release_neutral without a FINGERPRINT_FORMAT change is warned",
              lambda s, t: _holds(s, ("formula_edit_same_format", "formula_edit_bumped", "other_function_edit"))),
)


def _explorer(defect=""):
    return Explorer(Workflow((Step(defect),)), (State(),), CASES, invariants=INVARIANTS,
                    max_sequence_length=1, progress_steps=0)


def build_explorer():
    return _explorer()


def broken_variants():
    return {name: _explorer(name) for name in ("stale_on_version_bump", "blanks_every_version_line", "migrates_forever", "silent_formula_change")}


def conformance():
    from flowguard.map import mapfile
    from flowguard.map.common import content_digest
    from flowguard.map.inventory import build_inventory
    native = getattr(mapfile, "component_state", None)
    neutral = getattr(mapfile, "_release_neutral", None)
    if native is None or neutral is None:
        return CodeFactsReport((Fact("native_fingerprint_api", False, "release-neutral API has not been written"),))
    facts = []
    for case in CASES:
        if case in {"formula_edit_same_format", "formula_edit_bumped", "other_function_edit"}:
            before = "FINGERPRINT_FORMAT = 2\ndef fingerprint(root, files): return 1\ndef _release_neutral(path, content): return content\ndef owner_index(): return {}\n"
            after = before.replace("return content", "return content.strip()")
            if case == "formula_edit_bumped":
                after = after.replace("FINGERPRINT_FORMAT = 2", "FINGERPRINT_FORMAT = 3")
            elif case == "other_function_edit":
                after = before.replace("return {}", "return dict()")
            message = mapfile.format_guard(before, after)
            observed = "warn" if message else "none"
            facts.append(Fact(case, observed == EXPECTED[case] and (not message or "_release_neutral" in message and "stays 2" in message), repr(message)))
            continue
        with TemporaryDirectory(prefix="fg-neutral-") as directory:
            root = Path(directory)
            files = {"pkg/__init__.py": '\"\"\"__version__ = "inside documentation" note.\"\"\"\n__version__ = "1.0.0"\nX = 1\n',
                     "pyproject.toml": '[project]\nname = "app"\nversion = "1.0.0"\n[tool.x]\nversion = "stable"\n',
                     "VERSION": "1.0.0\n"}
            for path, text in files.items():
                p = root / path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text, encoding="utf-8")
            comp = {"id": "app", "files": list(files), "status": "confirmed"}
            comp["fingerprint"] = mapfile.fingerprint(root, list(files))
            if case.startswith("legacy_"):
                legacy = sha256()
                for path in sorted(files):
                    legacy.update(f"{path}\0{content_digest(root / path)}\n".encode())
                comp["fingerprint"] = "sha256:" + legacy.hexdigest()
            else:
                path, old, new = {
                    "version_py": ("pkg/__init__.py", '"1.0.0"', '"1.0.1"'),
                    "version_toml": ("pyproject.toml", '"1.0.0"', '"1.0.1"'),
                    "version_file": ("VERSION", "1.0.0", "1.0.1"),
                    "docstring": ("pkg/__init__.py", '"1.0.0"', '"1.0.1"'),
                    "other_py": ("pkg/__init__.py", "X = 1", "X = 2"),
                    "other_name": ("pyproject.toml", '"app"', '"other"'),
                    "other_tool": ("pyproject.toml", '"stable"', '"changed"'),
                }[case]
                (root / path).write_text(files[path].replace(old, new), encoding="utf-8")
            data = {"fingerprint_format": 1 if case == "legacy_format1" else 2}
            observed = native(root, comp, build_inventory(root, []), data)
            facts.append(Fact(case, observed == EXPECTED[case], f"expected {EXPECTED[case]}, got {observed}"))
    return CodeFactsReport(tuple(facts))
