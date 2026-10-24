"""Every removed path, literal, command-line flag, project marker and public name in one table.

Callers ask this module whether something they see is retired; the codes and messages live here only.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Retired:
    kind: str        # path, literal, flag, project_marker or public_name
    match: tuple[str, ...]
    code: str        # finding code, or the fixed message head a caller prints
    message: str


LEDGER = ".flowguard/behavior/inventory/ledger.json"
DESIGN_MARKER = "DESIGN_ONLY"
PROJECT_MARKER = ".flowguard/project.toml"

RETIRED = (
    Retired("path", (LEDGER,), "retired_file",
            f"{LEDGER} is no longer read; move each promise to its component's entrypoints "
            "and a model, then delete the file (see references/upgrade.md)"),
    Retired("path", (".flowguard/verification/owners/*/run_checks.py", ".flowguard/models/owners/*"), "runner_model",
            "runner models are no longer run; rewrite it as a contract model in .flowguard/models/ "
            "and delete this file (references/upgrade.md)"),
    Retired("literal", (DESIGN_MARKER,), "design_only_model",
            '{path}: DESIGN_ONLY is retired; a model of code that does not exist yet is a target model: '
            'move this file to .flowguard/target/models/ (python -m flowguard target start "<goal>")'),
    Retired("literal", (DESIGN_MARKER,), "target_design_only",
            "{path}: a target is already a future design; remove DESIGN_ONLY"),
    Retired("flag", ("--request", "--contract", "--owner-current"), "0.69 workflow interface retired in 0.70.0",
            "This 0.69 workflow interface retired in 0.70.0; see references/upgrade.md"),
    Retired("project_marker", (PROJECT_MARKER,), "0.69 project detected",
            "FlowGuard 0.69 project detected; upgrade instructions: references/upgrade.md"),
    Retired("public_name", ("ModelAuthoritySnapshot", "ModelRevisionSet", "ModelAuthority", "ModelAuthorityStore",
                            "model_authority_snapshot", "RuntimeGateway"), "retired in 0.70.0",
            "{name} retired in 0.70.0; see references/upgrade.md"),
)


def _entry(code: str) -> Retired:
    return next(entry for entry in RETIRED if entry.code == code)


def retired_file_message(root: Path) -> str | None:
    """The retired_file warning when the old behavior ledger is still present."""
    return _entry("retired_file").message if (root / LEDGER).is_file() else None


def runner_model_paths(root: Path, referenced: set[str], logical_sources: set[str]) -> set[str]:
    """Locations of retired runner models: owner runner scripts, owner model folders and referenced run_checks.py."""
    found = {p.relative_to(root).as_posix()
             for p in (root / ".flowguard/verification/owners").glob("*/run_checks.py") if p.is_file()}
    found.update(directory.relative_to(root).as_posix()
                 for directory in (root / ".flowguard/models/owners").glob("*")
                 if directory.is_dir() and any(p.is_file() for p in directory.rglob("*.py")))
    for logical in referenced | logical_sources:
        path = Path(logical)
        if path.is_absolute() or ".." in path.parts:
            continue             # the ordinary path validation owns this diagnostic
        if len(path.parts) >= 5 and path.parts[:3] == (".flowguard", "models", "owners") and path.suffix == ".py":
            found.add(Path(*path.parts[:4]).as_posix())
        elif logical in referenced and path.name == "run_checks.py":
            found.add(path.as_posix())
    return found


def runner_model_message() -> str:
    return _entry("runner_model").message


def has_design_marker(contract: dict) -> bool:
    return DESIGN_MARKER in contract


def design_only_problem(contract: dict, path: str) -> str | None:
    """The design_only_model problem of a current model that still declares the design marker."""
    return _entry("design_only_model").message.format(path=path) if has_design_marker(contract) else None


def target_design_only_message(path: str) -> str:
    return _entry("target_design_only").message.format(path=path)


def retired_flag_message(args: list[str]) -> str | None:
    entry = _entry("0.69 workflow interface retired in 0.70.0")
    return entry.message if any(flag in args for flag in entry.match) else None


def legacy_project_message(project: Path) -> str | None:
    """The upgrade pointer for a 0.69 project (its marker without a current map)."""
    if (project / PROJECT_MARKER).is_file() and not (project / ".flowguard/map.json").is_file():
        return _entry("0.69 project detected").message
    return None


def retired_public_name_message(name: str) -> str | None:
    entry = _entry("retired in 0.70.0")
    return entry.message.format(name=name) if name in entry.match else None
