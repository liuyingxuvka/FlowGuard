"""Read-only OpenSpec delta projection and history-disposition checks.

The checker deliberately does not invoke OpenSpec, archive a change, or write
provider artifacts.  It can either project normal spec application in memory
or freeze the explicit ``--skip-specs`` contract where current specs must stay
byte-for-byte unchanged while the archived delta identity is still verified.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable, Mapping, Sequence


SCHEMA_VERSION = "flowguard.openspec_semantic_sync.v1"
LEDGER_SCHEMA_VERSION = "flowguard.openspec_history_disposition.v1"
TERMINAL_DISPOSITIONS = {
    "current_replacement",
    "retired",
    "restore_current",
    "external_owner",
}
REQUIRED_DISPOSITION_COUNTS = {
    "current_replacement": 24,
    "retired": 30,
    "restore_current": 12,
    "external_owner": 11,
}

_REQUIREMENT_RE = re.compile(r"^###\s*Requirement:\s*(.+?)\s*$", re.IGNORECASE)
_SCENARIO_RE = re.compile(r"^####\s*Scenario:\s*(.+?)\s*$")
_MAIN_REQUIREMENTS_RE = re.compile(r"^##\s+Requirements\s*$", re.IGNORECASE)
_DELTA_SECTION_RE = re.compile(
    r"^##\s+(ADDED|MODIFIED|REMOVED|RENAMED)\s+Requirements\s*$",
    re.IGNORECASE,
)
_ANY_SECOND_LEVEL_RE = re.compile(r"^##\s+")
_RENAME_FROM_RE = re.compile(r"^\s*-\s*FROM:\s*`?(.+?)`?\s*$", re.IGNORECASE)
_RENAME_TO_RE = re.compile(r"^\s*-\s*TO:\s*`?(.+?)`?\s*$", re.IGNORECASE)


class SemanticSyncError(ValueError):
    """A deterministic semantic-sync validation failure."""


@dataclass(frozen=True)
class RequirementBlock:
    name: str
    raw: str

    @property
    def scenarios(self) -> tuple[str, ...]:
        return tuple(
            match.group(1).strip()
            for line in _normalize_newlines(self.raw).splitlines()
            if (match := _SCENARIO_RE.match(line))
        )


@dataclass(frozen=True)
class MainSpec:
    before: str
    header: str
    preamble: str
    blocks: tuple[RequirementBlock, ...]
    after: str


@dataclass(frozen=True)
class DeltaPlan:
    added: tuple[RequirementBlock, ...]
    modified: tuple[RequirementBlock, ...]
    removed: tuple[str, ...]
    renamed: tuple[tuple[str, str], ...]

    @property
    def operation_count(self) -> int:
        return (
            len(self.added)
            + len(self.modified)
            + len(self.removed)
            + len(self.renamed)
        )


def _normalize_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def normalize_requirement_name(value: str) -> str:
    """Match the provider's current exact normalization: trim only."""

    return value.strip()


def _normalized_block(value: str) -> str:
    return _normalize_newlines(value).strip()


def _sha256_bytes(value: bytes) -> str:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def _sha256_text(value: str) -> str:
    return _sha256_bytes(_normalize_newlines(value).encode("utf-8"))


def _json_hash(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return _sha256_bytes(encoded)


def _fence_mask(lines: Sequence[str]) -> list[bool]:
    mask: list[bool] = []
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        marker = None
        if stripped.startswith("```"):
            marker = "```"
        elif stripped.startswith("~~~"):
            marker = "~~~"
        mask.append(fence is not None)
        if marker is not None:
            if fence is None:
                fence = marker
                mask[-1] = True
            elif fence == marker:
                fence = None
                mask[-1] = True
    return mask


def _requirement_blocks(
    lines: Sequence[str],
    start: int,
    end: int,
    mask: Sequence[bool],
) -> tuple[str, tuple[RequirementBlock, ...]]:
    header_indexes = [
        index
        for index in range(start, end)
        if not mask[index] and _REQUIREMENT_RE.match(lines[index])
    ]
    preamble_end = header_indexes[0] if header_indexes else end
    preamble = "\n".join(lines[start:preamble_end]).rstrip()
    blocks: list[RequirementBlock] = []
    for position, index in enumerate(header_indexes):
        block_end = header_indexes[position + 1] if position + 1 < len(header_indexes) else end
        match = _REQUIREMENT_RE.match(lines[index])
        assert match is not None
        blocks.append(
            RequirementBlock(
                name=normalize_requirement_name(match.group(1)),
                raw="\n".join(lines[index:block_end]).rstrip(),
            )
        )
    return preamble, tuple(blocks)


def parse_main_spec(content: str) -> MainSpec:
    normalized = _normalize_newlines(content)
    lines = normalized.split("\n")
    mask = _fence_mask(lines)
    headers = [
        index
        for index, line in enumerate(lines)
        if not mask[index] and _MAIN_REQUIREMENTS_RE.match(line)
    ]
    if len(headers) != 1:
        raise SemanticSyncError(
            f"main spec must contain exactly one Requirements section; found {len(headers)}"
        )
    header_index = headers[0]
    end = len(lines)
    for index in range(header_index + 1, len(lines)):
        if not mask[index] and _ANY_SECOND_LEVEL_RE.match(lines[index]):
            end = index
            break
    preamble, blocks = _requirement_blocks(
        lines,
        header_index + 1,
        end,
        mask,
    )
    duplicate_names = [
        name for name, count in Counter(block.name for block in blocks).items() if count > 1
    ]
    if duplicate_names:
        raise SemanticSyncError(
            "ambiguous current requirement source(s): " + ", ".join(sorted(duplicate_names))
        )
    return MainSpec(
        before="\n".join(lines[:header_index]).rstrip(),
        header=lines[header_index],
        preamble=preamble,
        blocks=blocks,
        after="\n".join(lines[end:]).strip("\n"),
    )


def _section_ranges(lines: Sequence[str], mask: Sequence[bool]) -> list[tuple[str, int, int]]:
    headers: list[tuple[str, int]] = []
    for index, line in enumerate(lines):
        if mask[index]:
            continue
        match = _DELTA_SECTION_RE.match(line)
        if match:
            headers.append((match.group(1).upper(), index))
    ranges: list[tuple[str, int, int]] = []
    for position, (operation, index) in enumerate(headers):
        end = len(lines)
        for candidate in range(index + 1, len(lines)):
            if not mask[candidate] and _ANY_SECOND_LEVEL_RE.match(lines[candidate]):
                end = candidate
                break
        ranges.append((operation, index + 1, end))
    return ranges


def _parse_renames(lines: Sequence[str], start: int, end: int) -> tuple[tuple[str, str], ...]:
    renames: list[tuple[str, str]] = []
    pending_from: str | None = None
    for line in lines[start:end]:
        if match := _RENAME_FROM_RE.match(line):
            if pending_from is not None:
                raise SemanticSyncError("RENAMED has a FROM without a matching TO")
            pending_from = normalize_requirement_name(match.group(1))
            continue
        if match := _RENAME_TO_RE.match(line):
            if pending_from is None:
                raise SemanticSyncError("RENAMED has a TO without a preceding FROM")
            renames.append(
                (pending_from, normalize_requirement_name(match.group(1)))
            )
            pending_from = None
    if pending_from is not None:
        raise SemanticSyncError("RENAMED has a FROM without a matching TO")
    return tuple(renames)


def parse_delta_spec(content: str) -> DeltaPlan:
    normalized = _normalize_newlines(content)
    lines = normalized.split("\n")
    mask = _fence_mask(lines)
    ranges = _section_ranges(lines, mask)
    if not ranges:
        raise SemanticSyncError(
            "delta parsing found no ADDED/MODIFIED/REMOVED/RENAMED operations"
        )

    added: list[RequirementBlock] = []
    modified: list[RequirementBlock] = []
    removed: list[str] = []
    renamed: list[tuple[str, str]] = []
    for operation, start, end in ranges:
        if operation == "RENAMED":
            renamed.extend(_parse_renames(lines, start, end))
            continue
        _, blocks = _requirement_blocks(lines, start, end, mask)
        if operation == "ADDED":
            added.extend(blocks)
        elif operation == "MODIFIED":
            modified.extend(blocks)
        elif operation == "REMOVED":
            removed.extend(block.name for block in blocks)

    plan = DeltaPlan(
        added=tuple(added),
        modified=tuple(modified),
        removed=tuple(removed),
        renamed=tuple(renamed),
    )
    if plan.operation_count == 0:
        raise SemanticSyncError("delta sections contain no operations")
    _validate_delta_plan(plan)
    return plan


def _duplicates(values: Iterable[str]) -> list[str]:
    counts = Counter(values)
    return sorted(name for name, count in counts.items() if count > 1)


def _validate_delta_plan(plan: DeltaPlan) -> None:
    added = [block.name for block in plan.added]
    modified = [block.name for block in plan.modified]
    removed = list(plan.removed)
    renamed_from = [source for source, _ in plan.renamed]
    renamed_to = [target for _, target in plan.renamed]
    for label, names in (
        ("ADDED", added),
        ("MODIFIED", modified),
        ("REMOVED", removed),
        ("RENAMED FROM", renamed_from),
        ("RENAMED TO", renamed_to),
    ):
        duplicate_names = _duplicates(names)
        if duplicate_names:
            raise SemanticSyncError(
                f"duplicate requirement in {label}: {', '.join(duplicate_names)}"
            )
    conflicts: list[str] = []
    for name in set(modified) & set(removed):
        conflicts.append(f"{name} in MODIFIED and REMOVED")
    for name in set(modified) & set(added):
        conflicts.append(f"{name} in MODIFIED and ADDED")
    for name in set(added) & set(removed):
        conflicts.append(f"{name} in ADDED and REMOVED")
    for source, target in plan.renamed:
        if source in modified:
            conflicts.append(
                f"MODIFIED must use renamed target {target!r}, not source {source!r}"
            )
        if target in added:
            conflicts.append(f"RENAMED target {target!r} collides with ADDED")
    if conflicts:
        raise SemanticSyncError("; ".join(sorted(conflicts)))


def _build_skeleton(capability: str, change_id: str) -> str:
    return (
        f"# {capability} Specification\n\n"
        "## Purpose\n"
        f"TBD - created by archiving change {change_id}. Update Purpose after archive.\n\n"
        "## Requirements\n"
    )


def _render_main_spec(spec: MainSpec, blocks: Sequence[RequirementBlock]) -> str:
    body_parts = []
    if spec.preamble.strip():
        body_parts.append(spec.preamble.rstrip())
    body_parts.extend(block.raw.rstrip() for block in blocks)
    body = "\n\n".join(body_parts).rstrip()
    sections = [spec.before.rstrip(), spec.header, body, spec.after]
    sections = [
        section
        for index, section in enumerate(sections)
        if not (index == 0 and not section)
    ]
    rebuilt = "\n".join(sections)
    rebuilt = re.sub(r"\n{3,}", "\n\n", rebuilt)
    return rebuilt


def apply_delta_projection(
    current_content: str | None,
    delta_content: str,
    *,
    capability: str,
    change_id: str,
) -> tuple[str, dict[str, int]]:
    """Apply provider-compatible operations in memory and perform stricter ambiguity checks."""

    plan = parse_delta_spec(delta_content)
    if current_content is None:
        if plan.modified or plan.renamed or plan.removed:
            raise SemanticSyncError(
                f"{capability}: target spec does not exist; only ADDED is valid"
            )
        current_content = _build_skeleton(capability, change_id)
    spec = parse_main_spec(current_content)
    by_name = {block.name: block for block in spec.blocks}

    renamed_targets: dict[str, str] = {}
    for source, target in plan.renamed:
        if source not in by_name:
            raise SemanticSyncError(
                f'{capability} RENAMED source not found: "### Requirement: {source}"'
            )
        if target in by_name:
            raise SemanticSyncError(
                f'{capability} RENAMED target already exists: "### Requirement: {target}"'
            )
        block = by_name.pop(source)
        lines = block.raw.splitlines()
        lines[0] = f"### Requirement: {target}"
        by_name[target] = RequirementBlock(target, "\n".join(lines))
        renamed_targets[source] = target

    for name in plan.removed:
        if name not in by_name:
            raise SemanticSyncError(
                f'{capability} REMOVED source not found: "### Requirement: {name}"'
            )
        del by_name[name]

    for incoming in plan.modified:
        current = by_name.get(incoming.name)
        if current is None:
            raise SemanticSyncError(
                f'{capability} MODIFIED source not found: "### Requirement: {incoming.name}"'
            )
        missing_scenarios = sorted(set(current.scenarios) - set(incoming.scenarios))
        if missing_scenarios:
            raise SemanticSyncError(
                f"{capability} MODIFIED would drop current scenario(s): "
                + ", ".join(missing_scenarios)
            )
        by_name[incoming.name] = incoming

    for incoming in plan.added:
        current = by_name.get(incoming.name)
        if current is not None:
            raise SemanticSyncError(
                f'{capability} ADDED target already exists: "### Requirement: {incoming.name}"'
            )
        by_name[incoming.name] = incoming

    order: list[RequirementBlock] = []
    seen: set[str] = set()
    for block in spec.blocks:
        current_name = renamed_targets.get(block.name, block.name)
        replacement = by_name.get(current_name)
        if replacement is not None:
            order.append(replacement)
            seen.add(current_name)
    for name, block in by_name.items():
        if name not in seen:
            order.append(block)
    return (
        _render_main_spec(spec, order),
        {
            "added": len(plan.added),
            "modified": len(plan.modified),
            "removed": len(plan.removed),
            "renamed": len(plan.renamed),
        },
    )


def _semantic_spec_projection(content: str) -> dict[str, Any]:
    spec = parse_main_spec(content)
    return {
        "requirements": [
            {
                "name": block.name,
                "raw": _normalized_block(block.raw),
                "scenarios": list(block.scenarios),
            }
            for block in spec.blocks
        ]
    }


def _plan_projection(plan: DeltaPlan) -> dict[str, Any]:
    return {
        "renamed": [
            {"from": source, "to": target} for source, target in plan.renamed
        ],
        "removed": list(plan.removed),
        "modified": [
            {"name": block.name, "raw_sha256": _sha256_text(block.raw)}
            for block in plan.modified
        ],
        "added": [
            {"name": block.name, "raw_sha256": _sha256_text(block.raw)}
            for block in plan.added
        ],
    }


def _safe_change_dir(root: Path, change_id: str) -> Path:
    if (
        not change_id
        or change_id in {".", ".."}
        or "/" in change_id
        or "\\" in change_id
    ):
        raise SemanticSyncError("change id must be one safe directory name")
    path = root / "openspec" / "changes" / change_id
    if not path.is_dir():
        raise SemanticSyncError(f"current change directory not found: {change_id}")
    return path


def build_pre_archive_projection(
    root: Path,
    change_id: str,
    *,
    skip_specs: bool = False,
    ledger_path: Path | None = None,
) -> dict[str, Any]:
    """Freeze expected post-state without invoking or writing through the provider."""

    root = root.resolve()
    change_dir = _safe_change_dir(root, change_id)
    delta_root = change_dir / "specs"
    delta_paths = sorted(delta_root.glob("**/spec.md")) if delta_root.is_dir() else []
    findings: list[dict[str, Any]] = []
    capabilities: list[dict[str, Any]] = []
    delta_files: list[dict[str, Any]] = []

    for delta_path in delta_paths:
        relative_delta = delta_path.relative_to(change_dir).as_posix()
        capability = delta_path.parent.relative_to(delta_root).as_posix()
        delta_bytes = delta_path.read_bytes()
        delta_content = delta_bytes.decode("utf-8")
        try:
            plan = parse_delta_spec(delta_content)
        except (UnicodeDecodeError, SemanticSyncError) as exc:
            findings.append(
                {
                    "code": "delta_invalid",
                    "capability": capability,
                    "detail": str(exc),
                }
            )
            continue
        delta_files.append(
            {
                "path": relative_delta,
                "raw_sha256": _sha256_bytes(delta_bytes),
                "operations": _plan_projection(plan),
            }
        )
        current_path = root / "openspec" / "specs" / Path(*capability.split("/")) / "spec.md"
        current_exists = current_path.is_file()
        current_bytes = current_path.read_bytes() if current_exists else None
        current_content = (
            current_bytes.decode("utf-8") if current_bytes is not None else None
        )
        try:
            if skip_specs:
                expected_content = current_content
                counts = {
                    "added": 0,
                    "modified": 0,
                    "removed": 0,
                    "renamed": 0,
                }
            else:
                expected_content, counts = apply_delta_projection(
                    current_content,
                    delta_content,
                    capability=capability,
                    change_id=change_id,
                )
            capabilities.append(
                {
                    "capability": capability,
                    "current_path": current_path.relative_to(root).as_posix(),
                    "pre_exists": current_exists,
                    "pre_raw_sha256": (
                        _sha256_bytes(current_bytes)
                        if current_bytes is not None
                        else None
                    ),
                    "expected_exists": expected_content is not None,
                    "expected_raw_sha256": (
                        _sha256_bytes(current_bytes)
                        if skip_specs and current_bytes is not None
                        else (
                            _sha256_bytes(expected_content.encode("utf-8"))
                            if expected_content is not None
                            else None
                        )
                    ),
                    "expected_semantic_sha256": (
                        _json_hash(_semantic_spec_projection(expected_content))
                        if expected_content is not None
                        else None
                    ),
                    "expected_semantic": (
                        _semantic_spec_projection(expected_content)
                        if expected_content is not None
                        else None
                    ),
                    "applied_counts": counts,
                }
            )
        except SemanticSyncError as exc:
            findings.append(
                {
                    "code": "projection_invalid",
                    "capability": capability,
                    "detail": str(exc),
                }
            )

    ledger_result = None
    if ledger_path is not None:
        try:
            ledger_result = validate_history_ledger(root, ledger_path)
            if ledger_result["status"] != "pass":
                findings.extend(ledger_result["findings"])
        except (OSError, json.JSONDecodeError, SemanticSyncError) as exc:
            findings.append({"code": "ledger_invalid", "detail": str(exc)})

    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": root.as_posix(),
        "provider_identity": {
            "id": "openspec",
            "lifecycle_owner": "external",
            "operation_invoked": False,
        },
        "change_id": change_id,
        "provider_mode": "skip_specs" if skip_specs else "apply_specs",
        "operation_order": ["RENAMED", "REMOVED", "MODIFIED", "ADDED"],
        "claim_boundary": (
            "Read-only expectation only. The checker did not invoke archive, "
            "write OpenSpec artifacts, or prove provider transaction atomicity."
        ),
        "skip_specs_contract": (
            "Current specs are expected to remain byte-for-byte unchanged; "
            "delta identity and archived placement remain mandatory."
            if skip_specs
            else None
        ),
        "change_path": change_dir.relative_to(root).as_posix(),
        "delta_files": delta_files,
        "capabilities": capabilities,
        "ledger": ledger_result,
        "status": "pass" if not findings else "blocked",
        "findings": findings,
    }


def _find_archived_change(root: Path, change_id: str) -> Path:
    archive_root = root / "openspec" / "changes" / "archive"
    candidates = sorted(
        path
        for path in archive_root.iterdir()
        if path.is_dir() and (path.name == change_id or path.name.endswith(f"-{change_id}"))
    )
    if len(candidates) != 1:
        raise SemanticSyncError(
            f"expected exactly one archived change for {change_id}; found {len(candidates)}"
        )
    return candidates[0]


def compare_post_archive(
    root: Path,
    projection: Mapping[str, Any],
    *,
    archive_dir: Path | None = None,
) -> dict[str, Any]:
    """Compare actual provider post-state with a frozen pre-archive projection."""

    root = root.resolve()
    change_id = str(projection.get("change_id", ""))
    findings: list[dict[str, Any]] = []
    try:
        archived = (
            archive_dir.resolve()
            if archive_dir is not None
            else _find_archived_change(root, change_id)
        )
    except (OSError, SemanticSyncError) as exc:
        archived = None
        findings.append({"code": "archived_change_identity_missing", "detail": str(exc)})

    expected_delta_paths = {
        str(row["path"]): str(row["raw_sha256"])
        for row in projection.get("delta_files", [])
    }
    if archived is not None:
        actual_delta_paths = {
            path.relative_to(archived).as_posix(): _sha256_bytes(path.read_bytes())
            for path in sorted((archived / "specs").glob("**/spec.md"))
        }
        for path in sorted(set(expected_delta_paths) | set(actual_delta_paths)):
            if expected_delta_paths.get(path) != actual_delta_paths.get(path):
                findings.append(
                    {
                        "code": "archived_delta_mismatch",
                        "path": path,
                        "expected": expected_delta_paths.get(path),
                        "actual": actual_delta_paths.get(path),
                    }
                )

    for row in projection.get("capabilities", []):
        current_path = root / str(row["current_path"])
        expected_exists = bool(row["expected_exists"])
        actual_exists = current_path.is_file()
        if actual_exists != expected_exists:
            findings.append(
                {
                    "code": "post_archive_existence_mismatch",
                    "capability": row["capability"],
                    "expected_exists": expected_exists,
                    "actual_exists": actual_exists,
                }
            )
            continue
        if not actual_exists:
            continue
        content_bytes = current_path.read_bytes()
        content = content_bytes.decode("utf-8")
        actual_raw = _sha256_bytes(content_bytes)
        actual_semantic = _json_hash(_semantic_spec_projection(content))
        if actual_raw != row["expected_raw_sha256"]:
            findings.append(
                {
                    "code": "post_archive_raw_mismatch",
                    "capability": row["capability"],
                    "expected": row["expected_raw_sha256"],
                    "actual": actual_raw,
                }
            )
        if actual_semantic != row["expected_semantic_sha256"]:
            expected_names = {
                item["name"]
                for item in (row.get("expected_semantic") or {}).get("requirements", [])
            }
            actual_names = {
                item["name"]
                for item in _semantic_spec_projection(content)["requirements"]
            }
            findings.append(
                {
                    "code": "post_archive_semantic_mismatch",
                    "capability": row["capability"],
                    "missing_requirements": sorted(expected_names - actual_names),
                    "extra_requirements": sorted(actual_names - expected_names),
                }
            )
    return {
        "schema_version": SCHEMA_VERSION,
        "project_root": root.as_posix(),
        "provider_identity": projection.get("provider_identity"),
        "change_id": change_id,
        "provider_mode": projection.get("provider_mode"),
        "claim_boundary": (
            "Read-only post-observation. Equality does not prove provider "
            "transaction atomicity and mismatch is not repaired automatically."
        ),
        "status": "pass" if not findings else "blocked",
        "findings": findings,
    }


def _history_key(row: Mapping[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("source_change", "")),
        str(row.get("capability", "")),
        str(row.get("operation", "")),
        str(row.get("requirement", "")),
    )


def _git_text(root: Path, revision: str, relative_path: str) -> str | None:
    completed = subprocess.run(
        ["git", "show", f"{revision}:{relative_path}"],
        cwd=root,
        text=True,
        encoding="utf-8",
        errors="strict",
        capture_output=True,
        check=False,
    )
    if completed.returncode == 0:
        return completed.stdout
    return None


def derive_historical_gap_keys(
    root: Path,
    *,
    baseline_revision: str,
    audited_changes: Sequence[str],
) -> set[tuple[str, str, str, str]]:
    """Recompute the frozen historical gap set from Git and archive bytes."""

    root = root.resolve()
    current_titles: dict[str, set[str]] = {}
    for capability_dir in (root / "openspec" / "specs").iterdir():
        if not capability_dir.is_dir():
            continue
        relative = f"openspec/specs/{capability_dir.name}/spec.md"
        content = _git_text(root, baseline_revision, relative)
        if content is None:
            current_titles[capability_dir.name] = set()
            continue
        current_titles[capability_dir.name] = {
            block.name for block in parse_main_spec(content).blocks
        }

    gaps: set[tuple[str, str, str, str]] = set()
    archive_root = root / "openspec" / "changes" / "archive"
    for change in audited_changes:
        change_dir = archive_root / change
        if not change_dir.is_dir():
            raise SemanticSyncError(f"audited archived change is missing: {change}")
        for path in sorted((change_dir / "specs").glob("**/spec.md")):
            capability = path.parent.relative_to(change_dir / "specs").as_posix()
            plan = parse_delta_spec(path.read_text(encoding="utf-8"))
            for operation, blocks in (
                ("ADDED", plan.added),
                ("MODIFIED", plan.modified),
            ):
                for block in blocks:
                    if block.name not in current_titles.get(capability, set()):
                        gaps.add((change, capability, operation, block.name))
    return gaps


def _require_resolved_target(
    root: Path,
    row: Mapping[str, Any],
    findings: list[dict[str, Any]],
) -> None:
    target = row.get("target")
    if not isinstance(target, Mapping):
        findings.append(
            {"code": "ledger_target_missing", "key": list(_history_key(row))}
        )
        return
    capability = str(target.get("capability", ""))
    requirement = str(target.get("requirement", ""))
    path = root / "openspec" / "specs" / capability / "spec.md"
    if not path.is_file():
        findings.append(
            {
                "code": "ledger_target_capability_missing",
                "key": list(_history_key(row)),
                "capability": capability,
            }
        )
        return
    names = {block.name for block in parse_main_spec(path.read_text(encoding="utf-8")).blocks}
    if requirement not in names:
        findings.append(
            {
                "code": "ledger_target_requirement_missing",
                "key": list(_history_key(row)),
                "target": [capability, requirement],
            }
        )


def _owner_delta_titles(root: Path, owner_change: str, capability: str) -> set[str]:
    path = (
        root
        / "openspec"
        / "changes"
        / owner_change
        / "specs"
        / capability
        / "spec.md"
    )
    if not path.is_file():
        return set()
    plan = parse_delta_spec(path.read_text(encoding="utf-8"))
    return (
        {block.name for block in plan.added}
        | {block.name for block in plan.modified}
        | {target for _, target in plan.renamed}
    )


def validate_history_ledger_data(
    root: Path,
    data: Mapping[str, Any],
    *,
    expected_keys: set[tuple[str, str, str, str]] | None = None,
    required_counts: Mapping[str, int] | None = REQUIRED_DISPOSITION_COUNTS,
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    if data.get("schema_version") != LEDGER_SCHEMA_VERSION:
        findings.append(
            {
                "code": "ledger_schema_invalid",
                "actual": data.get("schema_version"),
            }
        )
    rows = data.get("rows")
    if not isinstance(rows, list):
        raise SemanticSyncError("ledger rows must be a list")
    keys = [_history_key(row) for row in rows if isinstance(row, Mapping)]
    duplicate_keys = [key for key, count in Counter(keys).items() if count > 1]
    for key in duplicate_keys:
        findings.append({"code": "ledger_duplicate_key", "key": list(key)})
    if len(rows) != len(keys):
        findings.append({"code": "ledger_row_invalid"})

    audit = data.get("audit", {})
    if expected_keys is None:
        if not isinstance(audit, Mapping):
            raise SemanticSyncError("ledger audit metadata is missing")
        expected_keys = derive_historical_gap_keys(
            root,
            baseline_revision=str(audit.get("baseline_revision", "")),
            audited_changes=tuple(str(value) for value in audit.get("changes", [])),
        )
    actual_keys = set(keys)
    for key in sorted(expected_keys - actual_keys):
        findings.append({"code": "ledger_history_key_missing", "key": list(key)})
    for key in sorted(actual_keys - expected_keys):
        findings.append({"code": "ledger_history_key_unexpected", "key": list(key)})

    counts = Counter(
        str(row.get("disposition", ""))
        for row in rows
        if isinstance(row, Mapping)
    )
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        disposition = str(row.get("disposition", ""))
        key = list(_history_key(row))
        if disposition not in TERMINAL_DISPOSITIONS:
            findings.append(
                {
                    "code": "ledger_pending_or_unknown_disposition",
                    "key": key,
                    "disposition": disposition,
                }
            )
            continue
        archive_path = (
            root
            / "openspec"
            / "changes"
            / "archive"
            / str(row["source_change"])
            / "specs"
            / str(row["capability"])
            / "spec.md"
        )
        if not archive_path.is_file():
            findings.append({"code": "ledger_archive_source_missing", "key": key})
        else:
            plan = parse_delta_spec(archive_path.read_text(encoding="utf-8"))
            source_names = {
                ("ADDED", block.name) for block in plan.added
            } | {
                ("MODIFIED", block.name) for block in plan.modified
            }
            if (str(row["operation"]), str(row["requirement"])) not in source_names:
                findings.append({"code": "ledger_archive_row_unmatched", "key": key})

        if disposition in {"current_replacement", "restore_current"}:
            _require_resolved_target(root, row, findings)
        elif disposition == "retired":
            if not str(row.get("reason", "")).strip():
                findings.append({"code": "ledger_retirement_reason_missing", "key": key})
            evidence = row.get("retirement_evidence")
            if not isinstance(evidence, Mapping) or not str(evidence.get("path", "")).strip():
                findings.append({"code": "ledger_retirement_evidence_missing", "key": key})
            elif not (root / str(evidence["path"])).is_file():
                findings.append(
                    {
                        "code": "ledger_retirement_evidence_path_missing",
                        "key": key,
                        "path": evidence["path"],
                    }
                )
        elif disposition == "external_owner":
            owner_change = str(row.get("owner_change", ""))
            owner_status = str(row.get("owner_status", ""))
            target = row.get("target")
            if owner_status != "merged":
                findings.append(
                    {
                        "code": "ledger_external_owner_nonterminal",
                        "key": key,
                        "owner_status": owner_status,
                    }
                )
            if not isinstance(target, Mapping):
                findings.append({"code": "ledger_target_missing", "key": key})
            else:
                capability = str(target.get("capability", ""))
                requirement = str(target.get("requirement", ""))
                if requirement not in _owner_delta_titles(root, owner_change, capability):
                    findings.append(
                        {
                            "code": "ledger_owner_delta_requirement_missing",
                            "key": key,
                            "owner_change": owner_change,
                            "target": [capability, requirement],
                        }
                    )

    if required_counts is not None:
        for disposition, expected in required_counts.items():
            actual = counts.get(disposition, 0)
            if actual != expected:
                findings.append(
                    {
                        "code": "ledger_disposition_count_mismatch",
                        "disposition": disposition,
                        "expected": expected,
                        "actual": actual,
                    }
                )
        if len(rows) != sum(required_counts.values()):
            findings.append(
                {
                    "code": "ledger_row_count_mismatch",
                    "expected": sum(required_counts.values()),
                    "actual": len(rows),
                }
            )
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "status": "pass" if not findings else "blocked",
        "row_count": len(rows),
        "disposition_counts": dict(sorted(counts.items())),
        "findings": findings,
    }


def validate_history_ledger(root: Path, ledger_path: Path) -> dict[str, Any]:
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    result = validate_history_ledger_data(root.resolve(), data)
    result["path"] = ledger_path.resolve().relative_to(root.resolve()).as_posix()
    result["raw_sha256"] = _sha256_bytes(ledger_path.read_bytes())
    return result


def _format_text(result: Mapping[str, Any]) -> str:
    lines = [
        f"OpenSpec semantic sync: {result.get('status', 'unknown')}",
        f"change: {result.get('change_id', 'n/a')}",
        f"provider mode: {result.get('provider_mode', 'n/a')}",
    ]
    for finding in result.get("findings", []):
        lines.append(
            f"- {finding.get('code', 'finding')}: "
            f"{finding.get('detail', json.dumps(finding, ensure_ascii=False, sort_keys=True))}"
        )
    lines.append(str(result.get("claim_boundary", "")))
    return "\n".join(lines).rstrip() + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Read-only OpenSpec semantic projection and history audit"
    )
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--change")
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--skip-specs", action="store_true")
    parser.add_argument(
        "--post-archive",
        type=Path,
        metavar="PROJECTION_JSON",
        help="compare current/archive state with a previously frozen JSON projection",
    )
    parser.add_argument("--archive-dir", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    try:
        root = args.root.resolve()
        if args.post_archive is not None:
            projection = json.loads(args.post_archive.read_text(encoding="utf-8"))
            result = compare_post_archive(
                root,
                projection,
                archive_dir=args.archive_dir,
            )
        else:
            if not args.change:
                parser.error("--change is required unless --post-archive is used")
            ledger = args.ledger
            if ledger is not None and not ledger.is_absolute():
                ledger = root / ledger
            result = build_pre_archive_projection(
                root,
                args.change,
                skip_specs=args.skip_specs,
                ledger_path=ledger,
            )
    except (OSError, UnicodeError, json.JSONDecodeError, SemanticSyncError) as exc:
        result = {
            "schema_version": SCHEMA_VERSION,
            "status": "blocked",
            "findings": [{"code": "semantic_sync_error", "detail": str(exc)}],
            "claim_boundary": "No provider write or archive command was attempted.",
        }

    if args.json:
        sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(_format_text(result))
    return 0 if result.get("status") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
