"""Read-only identities for explicitly named completion objectives.

An objective is deliberately resolved from a reviewed OpenSpec change rather
than from a caller-supplied hash or an execution directory.  The resolver is
used by both readiness and full validation so the two routes cannot silently
choose different cycle identities.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import stat
from typing import Any

from .evidence_receipts import fingerprint_value


COMPLETION_OBJECTIVE_SCHEMA = "flowguard.completion_objective.v1"
_OBJECTIVE_METADATA = ".openspec.yaml"
_OBJECTIVE_ROOT_FILES = frozenset({"proposal.md", "design.md", _OBJECTIVE_METADATA})
_OBJECTIVE_EXCLUDED_FILES = frozenset({"tasks.md"})
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x0400)


class CompletionObjectiveError(ValueError):
    """A named completion objective cannot be independently resolved."""

    def __init__(self, code: str, message: str) -> None:
        self.code = str(code).strip() or "completion_objective_invalid"
        super().__init__(f"{self.code}: {message}")


@dataclass(frozen=True)
class CompletionObjective:
    """The bounded, content-addressed identity of one reviewed objective."""

    change_name: str
    fingerprint: str
    artifact_paths: tuple[str, ...]

    @property
    def artifact_count(self) -> int:
        return len(self.artifact_paths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": COMPLETION_OBJECTIVE_SCHEMA,
            "change_name": self.change_name,
            "fingerprint": self.fingerprint,
            "artifact_paths": list(self.artifact_paths),
            "artifact_count": self.artifact_count,
        }


def _is_reparse_point(path: Path) -> bool:
    """Return whether *path* is a symlink or Windows reparse point."""

    try:
        if path.is_symlink():
            return True
        attributes = getattr(os.stat(path, follow_symlinks=False), "st_file_attributes", 0)
        return bool(int(attributes) & _REPARSE_POINT)
    except OSError as exc:
        raise CompletionObjectiveError(
            "completion_objective_unreadable",
            f"cannot inspect {path}: {type(exc).__name__}: {exc}",
        ) from exc


def _safe_change_name(value: str) -> str:
    name = str(value or "").strip()
    if not name:
        raise CompletionObjectiveError(
            "completion_objective_missing",
            "an explicit OpenSpec change name is required",
        )
    if name in {".", ".."} or any(separator in name for separator in ("/", "\\")):
        raise CompletionObjectiveError(
            "completion_objective_unsafe_name",
            "the change name must be one repository-local directory name",
        )
    if Path(name).name != name:
        raise CompletionObjectiveError(
            "completion_objective_unsafe_name",
            "the change name must not contain path components",
        )
    return name


def _relative_artifact_paths(change_root: Path) -> tuple[str, ...]:
    """Enumerate only the immutable planning artifacts used for identity."""

    if not change_root.is_dir() or _is_reparse_point(change_root):
        raise CompletionObjectiveError(
            "completion_objective_invalid_root",
            f"objective directory is not a real directory: {change_root}",
        )

    discovered: list[str] = []
    for candidate in sorted(change_root.rglob("*"), key=lambda item: item.as_posix().lower()):
        relative = candidate.relative_to(change_root)
        relative_text = relative.as_posix()
        if _is_reparse_point(candidate):
            raise CompletionObjectiveError(
                "completion_objective_reparse_point",
                f"objective contains a symlink/reparse point: {relative_text}",
            )
        if candidate.is_dir():
            continue
        if not candidate.is_file():
            raise CompletionObjectiveError(
                "completion_objective_non_file",
                f"objective contains a non-regular artifact: {relative_text}",
            )
        if relative_text == "tasks.md":
            # Task checkbox progress is implementation state, not a new
            # product objective.  It must never buy another completion cycle.
            continue
        if relative_text in _OBJECTIVE_ROOT_FILES or relative.parts[:1] == ("specs",) and candidate.suffix.lower() == ".md":
            discovered.append(relative_text)
            continue
        raise CompletionObjectiveError(
            "completion_objective_unregistered_artifact",
            f"objective contains an unregistered artifact: {relative_text}",
        )

    required = set(_OBJECTIVE_ROOT_FILES)
    missing = sorted(required.difference(discovered))
    if missing:
        raise CompletionObjectiveError(
            "completion_objective_missing_artifact",
            "objective is missing required artifacts: " + ", ".join(missing),
        )
    if not any(path.startswith("specs/") and path.endswith(".md") for path in discovered):
        raise CompletionObjectiveError(
            "completion_objective_missing_specs",
            "objective must contain at least one specs/**/*.md artifact",
        )
    return tuple(discovered)


def resolve_completion_objective(
    repository_root: str | Path,
    change_name: str,
) -> CompletionObjective:
    """Resolve one explicit, current OpenSpec objective without writing files."""

    root = Path(repository_root).expanduser().resolve()
    if not root.is_dir() or _is_reparse_point(root):
        raise CompletionObjectiveError(
            "completion_objective_repository_invalid",
            f"repository root is not a real directory: {root}",
        )
    safe_name = _safe_change_name(change_name)
    changes_root = root / "openspec" / "changes"
    if not changes_root.is_dir():
        raise CompletionObjectiveError(
            "completion_objective_changes_root_invalid",
            f"OpenSpec changes root is unavailable: {changes_root}",
        )
    if _is_reparse_point(changes_root):
        raise CompletionObjectiveError(
            "completion_objective_changes_root_invalid",
            f"OpenSpec changes root is a symlink/reparse point: {changes_root}",
        )
    change_root = changes_root / safe_name
    try:
        change_root.relative_to(changes_root)
    except ValueError as exc:  # pragma: no cover - defensive after name check
        raise CompletionObjectiveError(
            "completion_objective_unsafe_name",
            "objective escapes the OpenSpec changes root",
        ) from exc
    if not change_root.exists():
        raise CompletionObjectiveError(
            "completion_objective_unknown",
            f"OpenSpec change does not exist: {safe_name}",
        )

    artifact_paths = _relative_artifact_paths(change_root)
    artifacts: list[dict[str, Any]] = []
    for relative_text in artifact_paths:
        artifact = change_root / Path(*relative_text.split("/"))
        try:
            raw = artifact.read_bytes()
        except (OSError, UnicodeError) as exc:
            raise CompletionObjectiveError(
                "completion_objective_unreadable",
                f"cannot read {relative_text}: {type(exc).__name__}: {exc}",
            ) from exc
        artifacts.append(
            {
                "path": relative_text,
                "size": len(raw),
                "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
            }
        )
    payload = {
        "schema_version": COMPLETION_OBJECTIVE_SCHEMA,
        "change_name": safe_name,
        "artifacts": artifacts,
    }
    return CompletionObjective(
        change_name=safe_name,
        fingerprint=fingerprint_value(payload),
        artifact_paths=artifact_paths,
    )


__all__ = [
    "COMPLETION_OBJECTIVE_SCHEMA",
    "CompletionObjective",
    "CompletionObjectiveError",
    "resolve_completion_objective",
]
