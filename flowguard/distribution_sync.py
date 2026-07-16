"""Declarative install, uninstall, and parity checks for FlowGuard skills.

The distribution surface is deliberately file based.  Every managed file is
identified by its path and hashes, while volatile evidence is omitted only by
named exclusion rules that remain visible in every inventory and report.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence


DISTRIBUTION_SCHEMA = "flowguard.skill_distribution.v1"
OWNERSHIP_SCHEMA = "flowguard.skill_distribution_ownership.v1"
OWNERSHIP_MANIFEST_NAME = ".flowguard-skill-suite-ownership.json"
CANONICAL_SKILL_ROOT = ".agents/skills"
CANONICAL_SUITE_MAP = ".skillguard/flowguard-suite/suite-map.json"
FLOWGUARD_EXPECTED_MEMBER_COUNT = 17


@dataclass(frozen=True)
class ExclusionRule:
    rule_id: str
    pattern: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"rule_id": self.rule_id, "pattern": self.pattern, "reason": self.reason}


DEFAULT_EXCLUSION_RULES = (
    ExclusionRule("python_bytecode", "*/__pycache__/*", "generated Python bytecode is not a release-owned skill artifact"),
    ExclusionRule("python_bytecode", "*.pyc", "generated Python bytecode is not a release-owned skill artifact"),
    ExclusionRule("current_evidence", "*/.skillguard/evidence/*", "current-run evidence is environment-local and is re-created by validation"),
    ExclusionRule("current_report", "*/.skillguard/reports/current_*.json", "current-run reports are receipts, not installed skill source"),
    ExclusionRule("current_ai_judgment", "*/.skillguard/ai_judgments/current_*.json", "current AI judgments are run receipts, not installed skill source"),
    ExclusionRule("progress_ledger", "*/.skillguard/skillguard_progress_ledger.jsonl", "the append-only local run ledger is not distributed"),
    ExclusionRule("run_receipt", "*/.skillguard/*run*receipt*.json", "current-run receipt files are not distributed"),
    ExclusionRule("run_record", "*/.skillguard/*run*record*.json", "current-run record files are not distributed"),
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def semantic_hash_bytes(value: bytes, *, relative_path: str = "") -> str:
    """Hash semantic text content while preserving raw equality as a separate gate."""

    try:
        text = value.decode("utf-8-sig")
    except UnicodeDecodeError:
        return _sha256(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if relative_path.lower().endswith(".json"):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            pass
        else:
            text = _canonical_json(parsed)
    return _sha256(text.encode("utf-8"))


def _safe_relative(value: str) -> str:
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
        or (path.parts and re.fullmatch(r"[A-Za-z]:", path.parts[0]) is not None)
    ):
        raise ValueError(f"unsafe relative skill path: {value!r}")
    return path.as_posix()


def _contained_path(root: Path, relative: str) -> Path:
    relative = _safe_relative(relative)
    root_resolved = root.expanduser().resolve()
    candidate = (root_resolved / Path(*PurePosixPath(relative).parts)).resolve(strict=False)
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ValueError(f"skill path escapes target root: {relative!r}")
    return candidate


def resolve_source_skill_root(root: str | Path) -> Path:
    """Accept either a repository/workspace root or its ``.agents/skills`` root."""

    candidate = Path(root).expanduser().resolve()
    nested = candidate / CANONICAL_SKILL_ROOT
    if nested.is_dir():
        return nested.resolve()
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"skill source root does not exist: {candidate}")


def resolve_target_skill_root(
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
) -> Path:
    """Resolve an explicit skills root or ``CODEX_HOME/skills`` without creating it."""

    if target is not None and codex_home is not None:
        raise ValueError("target and codex_home are mutually exclusive")
    if target is not None:
        return Path(target).expanduser().resolve()
    home_value = codex_home if codex_home is not None else os.environ.get("CODEX_HOME")
    home = Path(home_value).expanduser() if home_value else Path.home() / ".codex"
    return (home / "skills").resolve()


def _assert_disjoint(source: Path, target: Path) -> None:
    source = source.resolve()
    target = target.resolve(strict=False)
    if source == target or source in target.parents or target in source.parents:
        raise ValueError("source and target skill roots must not overlap")


def _find_rule(relative: str, rules: Sequence[ExclusionRule]) -> ExclusionRule | None:
    return next((rule for rule in rules if fnmatch.fnmatchcase(relative, rule.pattern)), None)


@dataclass(frozen=True)
class FileFingerprint:
    relative_path: str
    raw_hash: str
    semantic_hash: str
    size: int

    @classmethod
    def from_path(cls, path: Path, relative_path: str) -> "FileFingerprint":
        content = path.read_bytes()
        return cls(
            relative_path=_safe_relative(relative_path),
            raw_hash=_sha256(content),
            semantic_hash=semantic_hash_bytes(content, relative_path=relative_path),
            size=len(content),
        )

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FileFingerprint":
        return cls(
            relative_path=_safe_relative(str(value.get("relative_path", ""))),
            raw_hash=str(value.get("raw_hash", "")),
            semantic_hash=str(value.get("semantic_hash", "")),
            size=int(value.get("size", 0)),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "raw_hash": self.raw_hash,
            "semantic_hash": self.semantic_hash,
            "size": self.size,
        }


@dataclass(frozen=True)
class ExcludedFile:
    relative_path: str
    rule_id: str
    pattern: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "relative_path": self.relative_path,
            "rule_id": self.rule_id,
            "pattern": self.pattern,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SkillTreeInventory:
    root: str
    member_ids: tuple[str, ...]
    missing_member_ids: tuple[str, ...]
    files: tuple[FileFingerprint, ...]
    excluded_files: tuple[ExcludedFile, ...]
    unsafe_paths: tuple[str, ...]
    raw_tree_hash: str
    semantic_tree_hash: str

    @property
    def ok(self) -> bool:
        return not self.missing_member_ids and not self.unsafe_paths

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "member_ids": list(self.member_ids),
            "member_count": len(self.member_ids),
            "missing_member_ids": list(self.missing_member_ids),
            "files": [item.to_dict() for item in self.files],
            "file_count": len(self.files),
            "excluded_files": [item.to_dict() for item in self.excluded_files],
            "excluded_file_count": len(self.excluded_files),
            "unsafe_paths": list(self.unsafe_paths),
            "raw_tree_hash": self.raw_tree_hash,
            "semantic_tree_hash": self.semantic_tree_hash,
            "ok": self.ok,
        }


def discover_member_ids(source: str | Path) -> tuple[str, ...]:
    source_path = Path(source).expanduser().resolve()
    repository_root = source_path if (source_path / CANONICAL_SKILL_ROOT).is_dir() else None
    if repository_root is not None:
        map_path = repository_root / CANONICAL_SUITE_MAP
        if map_path.is_file():
            payload = json.loads(map_path.read_text(encoding="utf-8"))
            rows = payload.get("included_skills", ())
            ids = tuple(str(row.get("name", "")) for row in rows if isinstance(row, Mapping))
            if ids and all(ids):
                return ids
    skill_root = resolve_source_skill_root(source_path)
    return tuple(sorted(path.name for path in skill_root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()))


def inventory_skill_tree(
    root: str | Path,
    *,
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
    allow_missing_root: bool = False,
) -> SkillTreeInventory:
    """Inventory every file beneath declared skill members in deterministic order."""

    root_path = Path(root).expanduser().resolve()
    nested = root_path / CANONICAL_SKILL_ROOT
    skill_root = nested.resolve() if nested.is_dir() else root_path
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(root_path)
    ids = tuple(_safe_relative(item) for item in ids)
    if len(set(ids)) != len(ids):
        raise ValueError("member ids must be unique")
    if not skill_root.is_dir() and not allow_missing_root:
        raise FileNotFoundError(f"skill tree does not exist: {skill_root}")

    files: list[FileFingerprint] = []
    excluded: list[ExcludedFile] = []
    unsafe: list[str] = []
    missing: list[str] = []
    for member_id in ids:
        member_dir = _contained_path(skill_root, member_id)
        if not member_dir.is_dir():
            missing.append(member_id)
            continue
        for file_path in sorted(member_dir.rglob("*")):
            if file_path.is_symlink():
                unsafe.append(file_path.relative_to(skill_root).as_posix())
                continue
            if not file_path.is_file():
                continue
            relative = file_path.relative_to(skill_root).as_posix()
            try:
                _contained_path(skill_root, relative)
            except ValueError:
                unsafe.append(relative)
                continue
            rule = _find_rule(relative, exclusion_rules)
            if rule is not None:
                excluded.append(ExcludedFile(relative, rule.rule_id, rule.pattern, rule.reason))
                continue
            files.append(FileFingerprint.from_path(file_path, relative))

    files.sort(key=lambda item: item.relative_path)
    excluded.sort(key=lambda item: item.relative_path)
    raw_tree_hash = _sha256(
        _canonical_json([[item.relative_path, item.raw_hash] for item in files]).encode("utf-8")
    )
    semantic_tree_hash = _sha256(
        _canonical_json([[item.relative_path, item.semantic_hash] for item in files]).encode("utf-8")
    )
    return SkillTreeInventory(
        root=str(skill_root),
        member_ids=ids,
        missing_member_ids=tuple(missing),
        files=tuple(files),
        excluded_files=tuple(excluded),
        unsafe_paths=tuple(sorted(unsafe)),
        raw_tree_hash=raw_tree_hash,
        semantic_tree_hash=semantic_tree_hash,
    )


@dataclass(frozen=True)
class TreeParity:
    reference: str
    candidate: str
    missing_files: tuple[str, ...]
    extra_files: tuple[str, ...]
    raw_mismatches: tuple[str, ...]
    semantic_mismatches: tuple[str, ...]
    missing_members: tuple[str, ...]
    unsafe_paths: tuple[str, ...]
    reference_exclusions: tuple[ExcludedFile, ...] = ()
    candidate_exclusions: tuple[ExcludedFile, ...] = ()

    @property
    def ok(self) -> bool:
        return not (
            self.missing_files
            or self.extra_files
            or self.raw_mismatches
            or self.missing_members
            or self.unsafe_paths
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference,
            "candidate": self.candidate,
            "ok": self.ok,
            "missing_files": list(self.missing_files),
            "extra_files": list(self.extra_files),
            "raw_mismatches": list(self.raw_mismatches),
            "semantic_mismatches": list(self.semantic_mismatches),
            "missing_members": list(self.missing_members),
            "unsafe_paths": list(self.unsafe_paths),
            "reference_exclusions": [item.to_dict() for item in self.reference_exclusions],
            "candidate_exclusions": [item.to_dict() for item in self.candidate_exclusions],
            "claim_boundary": "Raw equality is required; semantic equality is reported and never masks a raw mismatch.",
        }


def compare_tree_inventories(reference: SkillTreeInventory, candidate: SkillTreeInventory) -> TreeParity:
    reference_files = {item.relative_path: item for item in reference.files}
    candidate_files = {item.relative_path: item for item in candidate.files}
    common = sorted(reference_files.keys() & candidate_files.keys())
    raw = tuple(path for path in common if reference_files[path].raw_hash != candidate_files[path].raw_hash)
    semantic = tuple(
        path for path in common if reference_files[path].semantic_hash != candidate_files[path].semantic_hash
    )
    return TreeParity(
        reference=reference.root,
        candidate=candidate.root,
        missing_files=tuple(sorted(reference_files.keys() - candidate_files.keys())),
        extra_files=tuple(sorted(candidate_files.keys() - reference_files.keys())),
        raw_mismatches=raw,
        semantic_mismatches=semantic,
        missing_members=tuple(sorted(set(reference.missing_member_ids) | set(candidate.missing_member_ids))),
        unsafe_paths=tuple(sorted(set(reference.unsafe_paths) | set(candidate.unsafe_paths))),
        reference_exclusions=reference.excluded_files,
        candidate_exclusions=candidate.excluded_files,
    )


@dataclass(frozen=True)
class ConfiguredParityReport:
    reference_name: str
    inventories: Mapping[str, SkillTreeInventory]
    comparisons: Mapping[str, TreeParity]

    @property
    def ok(self) -> bool:
        return bool(self.comparisons) and all(item.ok for item in self.comparisons.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_skill_tree_parity",
            "schema_version": DISTRIBUTION_SCHEMA,
            "reference_name": self.reference_name,
            "ok": self.ok,
            "inventories": {name: value.to_dict() for name, value in self.inventories.items()},
            "comparisons": {name: value.to_dict() for name, value in self.comparisons.items()},
            "claim_boundary": "Parity covers the complete declared member trees except paths itemized by exclusion rule.",
        }


def compare_configured_skill_trees(
    roots: Mapping[str, str | Path],
    *,
    reference_name: str = "source",
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
) -> ConfiguredParityReport:
    if reference_name not in roots:
        raise ValueError(f"reference root {reference_name!r} is not configured")
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(roots[reference_name])
    inventories = {
        name: inventory_skill_tree(
            root,
            member_ids=ids,
            exclusion_rules=exclusion_rules,
            allow_missing_root=name != reference_name,
        )
        for name, root in roots.items()
    }
    reference = inventories[reference_name]
    comparisons = {
        name: compare_tree_inventories(reference, inventory)
        for name, inventory in inventories.items()
        if name != reference_name
    }
    return ConfiguredParityReport(reference_name, inventories, comparisons)


@dataclass(frozen=True)
class DistributionFinding:
    code: str
    message: str
    relative_path: str = ""
    blocking: bool = True
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "relative_path": self.relative_path,
            "blocking": self.blocking,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class DistributionReport:
    action: str
    source: str
    target: str
    dry_run: bool
    copied_files: tuple[str, ...] = ()
    removed_files: tuple[str, ...] = ()
    unchanged_files: tuple[str, ...] = ()
    adopted_files: tuple[str, ...] = ()
    conflict_files: tuple[str, ...] = ()
    extra_files: tuple[str, ...] = ()
    excluded_files: tuple[ExcludedFile, ...] = ()
    findings: tuple[DistributionFinding, ...] = ()
    ownership_manifest: str = ""
    parity: TreeParity | None = None

    @property
    def ok(self) -> bool:
        return not any(finding.blocking for finding in self.findings)

    @property
    def status(self) -> str:
        if not self.ok:
            return "blocked"
        if self.findings or self.extra_files:
            return "pass_with_gaps"
        return "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_skill_distribution_report",
            "schema_version": DISTRIBUTION_SCHEMA,
            "action": self.action,
            "ok": self.ok,
            "status": self.status,
            "source": self.source,
            "target": self.target,
            "dry_run": self.dry_run,
            "copied_files": list(self.copied_files),
            "removed_files": list(self.removed_files),
            "unchanged_files": list(self.unchanged_files),
            "adopted_files": list(self.adopted_files),
            "conflict_files": list(self.conflict_files),
            "extra_files": list(self.extra_files),
            "excluded_files": [item.to_dict() for item in self.excluded_files],
            "findings": [item.to_dict() for item in self.findings],
            "ownership_manifest": self.ownership_manifest,
            "parity": self.parity.to_dict() if self.parity is not None else None,
            "claim_boundary": "Only manifest-owned files whose installed raw hash is unchanged may be removed automatically.",
        }


def _manifest_path(target: Path) -> Path:
    return target / OWNERSHIP_MANIFEST_NAME


def _ownership_payload(
    source: Path,
    target: Path,
    inventory: SkillTreeInventory,
    files: Iterable[FileFingerprint],
    rules: Sequence[ExclusionRule],
) -> dict[str, Any]:
    return {
        "artifact_type": "flowguard_skill_distribution_ownership",
        "schema_version": OWNERSHIP_SCHEMA,
        "source_root": str(source),
        "target_root": str(target),
        "member_ids": list(inventory.member_ids),
        "source_raw_tree_hash": inventory.raw_tree_hash,
        "source_semantic_tree_hash": inventory.semantic_tree_hash,
        "files": [item.to_dict() for item in sorted(files, key=lambda item: item.relative_path)],
        "exclusion_policy": [rule.to_dict() for rule in rules],
        "source_excluded_files": [item.to_dict() for item in inventory.excluded_files],
    }


def _read_manifest(target: Path) -> tuple[dict[str, Any] | None, str]:
    path = _manifest_path(target)
    if not path.is_file():
        return None, ""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(payload, dict) or payload.get("schema_version") != OWNERSHIP_SCHEMA:
        return None, "ownership manifest schema is missing or unsupported"
    try:
        rows = payload.get("files", ())
        if not isinstance(rows, list):
            raise ValueError("ownership manifest files must be an array")
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("ownership manifest file row must be an object")
            _safe_relative(str(row.get("relative_path", "")))
    except ValueError as exc:
        return None, str(exc)
    return payload, ""


def _write_manifest(path: Path, payload: Mapping[str, Any]) -> bool:
    content = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)
    return True


def _fingerprint_if_file(path: Path, relative: str) -> FileFingerprint | None:
    if path.is_symlink():
        raise ValueError(f"target path is a symlink: {relative}")
    return FileFingerprint.from_path(path, relative) if path.is_file() else None


def install_skill_suite(
    source: str | Path,
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
    dry_run: bool = False,
    adopt_existing: bool = False,
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
) -> DistributionReport:
    source_root = resolve_source_skill_root(source)
    target_root = resolve_target_skill_root(target, codex_home=codex_home)
    _assert_disjoint(source_root, target_root)
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(source)
    source_inventory = inventory_skill_tree(source_root, member_ids=ids, exclusion_rules=exclusion_rules)
    findings: list[DistributionFinding] = []
    if member_ids is None and len(ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        findings.append(
            DistributionFinding(
                "invalid_suite_cardinality",
                "a complete FlowGuard distribution must contain exactly seventeen skills",
                metadata={"actual": len(ids), "expected": FLOWGUARD_EXPECTED_MEMBER_COUNT},
            )
        )
    for member in source_inventory.missing_member_ids:
        findings.append(DistributionFinding("source_member_missing", "declared source member is missing", member))
    for relative in source_inventory.unsafe_paths:
        findings.append(DistributionFinding("unsafe_source_path", "source contains a symlink or escaping path", relative))
    if findings:
        return DistributionReport("install", str(source_root), str(target_root), dry_run, excluded_files=source_inventory.excluded_files, findings=tuple(findings), ownership_manifest=str(_manifest_path(target_root)))

    old_manifest, manifest_error = _read_manifest(target_root)
    if manifest_error:
        findings.append(DistributionFinding("ownership_manifest_invalid", manifest_error, OWNERSHIP_MANIFEST_NAME))
        return DistributionReport("install", str(source_root), str(target_root), dry_run, excluded_files=source_inventory.excluded_files, findings=tuple(findings), ownership_manifest=str(_manifest_path(target_root)))
    old_rows = {
        item.relative_path: item
        for item in (FileFingerprint.from_dict(row) for row in (old_manifest or {}).get("files", ()))
    }
    source_rows = {item.relative_path: item for item in source_inventory.files}
    copied: list[str] = []
    removed: list[str] = []
    unchanged: list[str] = []
    adopted: list[str] = []
    conflicts: list[str] = []
    owned: dict[str, FileFingerprint] = {}

    for relative, source_file in source_rows.items():
        destination = _contained_path(target_root, relative)
        if destination.exists() and not destination.is_file():
            findings.append(
                DistributionFinding(
                    "non_file_target_conflict",
                    "a source-owned file path is occupied by a directory or special file",
                    relative,
                )
            )
            conflicts.append(relative)
            continue
        try:
            actual = _fingerprint_if_file(destination, relative)
        except ValueError as exc:
            findings.append(DistributionFinding("unsafe_target_path", str(exc), relative))
            conflicts.append(relative)
            continue
        if actual is None:
            copied.append(relative)
            owned[relative] = source_file
        elif actual.raw_hash == source_file.raw_hash:
            unchanged.append(relative)
            owned[relative] = source_file
        elif relative in old_rows and actual.raw_hash == old_rows[relative].raw_hash:
            copied.append(relative)
            owned[relative] = source_file
        elif adopt_existing:
            copied.append(relative)
            adopted.append(relative)
            owned[relative] = source_file
            findings.append(
                DistributionFinding(
                    "existing_file_adopted",
                    "explicit adoption replaces an existing canonical source-owned path and records its new ownership hash",
                    relative,
                    blocking=False,
                    metadata={
                        "previous_raw_hash": actual.raw_hash,
                        "source_raw_hash": source_file.raw_hash,
                        "disposition": "replace_and_adopt",
                    },
                )
            )
        else:
            conflicts.append(relative)
            if relative in old_rows:
                owned[relative] = old_rows[relative]
            findings.append(DistributionFinding("modified_target_conflict", "target file differs from both source and its last installer-owned hash", relative))

    for relative, old_file in old_rows.items():
        if relative in source_rows:
            continue
        destination = _contained_path(target_root, relative)
        actual = _fingerprint_if_file(destination, relative)
        if actual is None:
            continue
        if actual.raw_hash == old_file.raw_hash:
            removed.append(relative)
        else:
            conflicts.append(relative)
            owned[relative] = old_file
            findings.append(DistributionFinding("obsolete_modified_conflict", "obsolete installer-owned file was modified and is preserved", relative))

    target_inventory = inventory_skill_tree(
        target_root,
        member_ids=ids,
        exclusion_rules=exclusion_rules,
        allow_missing_root=True,
    )
    extras = sorted(
        item.relative_path
        for item in target_inventory.files
        if item.relative_path not in source_rows and item.relative_path not in old_rows
    )
    for relative in extras:
        findings.append(DistributionFinding("extra_unowned_file", "target member tree contains a file not owned by this distribution", relative))
    reported_exclusions = tuple(
        sorted(
            {
                (item.relative_path, item.rule_id, item.pattern): item
                for item in source_inventory.excluded_files + target_inventory.excluded_files
            }.values(),
            key=lambda item: (item.relative_path, item.rule_id),
        )
    )

    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)
        for relative in copied:
            source_file = _contained_path(source_root, relative)
            destination = _contained_path(target_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_file, destination)
        for relative in removed:
            destination = _contained_path(target_root, relative)
            if destination.is_file() and not destination.is_symlink():
                destination.unlink()
        payload = _ownership_payload(source_root, target_root, source_inventory, owned.values(), exclusion_rules)
        _write_manifest(_manifest_path(target_root), payload)

    parity = None
    if not dry_run:
        final_inventory = inventory_skill_tree(target_root, member_ids=ids, exclusion_rules=exclusion_rules)
        parity = compare_tree_inventories(source_inventory, final_inventory)
    return DistributionReport(
        action="install",
        source=str(source_root),
        target=str(target_root),
        dry_run=dry_run,
        copied_files=tuple(copied),
        removed_files=tuple(removed),
        unchanged_files=tuple(unchanged),
        adopted_files=tuple(adopted),
        conflict_files=tuple(sorted(set(conflicts))),
        extra_files=tuple(extras),
        excluded_files=reported_exclusions,
        findings=tuple(findings),
        ownership_manifest=str(_manifest_path(target_root)),
        parity=parity,
    )


def check_skill_suite(
    source: str | Path,
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
) -> DistributionReport:
    source_root = resolve_source_skill_root(source)
    target_root = resolve_target_skill_root(target, codex_home=codex_home)
    _assert_disjoint(source_root, target_root)
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(source)
    source_inventory = inventory_skill_tree(source_root, member_ids=ids, exclusion_rules=exclusion_rules)
    target_inventory = inventory_skill_tree(target_root, member_ids=ids, exclusion_rules=exclusion_rules, allow_missing_root=True)
    parity = compare_tree_inventories(source_inventory, target_inventory)
    findings: list[DistributionFinding] = []
    if member_ids is None and len(ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        findings.append(
            DistributionFinding(
                "invalid_suite_cardinality",
                "a complete FlowGuard distribution must contain exactly seventeen skills",
                metadata={"actual": len(ids), "expected": FLOWGUARD_EXPECTED_MEMBER_COUNT},
            )
        )
    manifest, manifest_error = _read_manifest(target_root)
    if manifest_error:
        findings.append(DistributionFinding("ownership_manifest_invalid", manifest_error, OWNERSHIP_MANIFEST_NAME))
    elif manifest is None:
        findings.append(DistributionFinding("ownership_manifest_missing", "installed skill tree has no ownership manifest", OWNERSHIP_MANIFEST_NAME))
    else:
        manifest_rows = {item.relative_path: item for item in (FileFingerprint.from_dict(row) for row in manifest.get("files", ()))}
        source_rows = {item.relative_path: item for item in source_inventory.files}
        for relative, source_file in source_rows.items():
            owned = manifest_rows.get(relative)
            if owned is None:
                findings.append(DistributionFinding("file_not_owned", "source file is not recorded in the ownership manifest", relative))
            elif owned.raw_hash != source_file.raw_hash:
                findings.append(DistributionFinding("ownership_source_hash_mismatch", "ownership manifest does not describe the current source hash", relative))
        for relative in sorted(manifest_rows.keys() - source_rows.keys()):
            findings.append(DistributionFinding("obsolete_manifest_entry", "ownership manifest records a path absent from the current source", relative))
    for relative in parity.missing_files:
        findings.append(DistributionFinding("installed_file_missing", "installed tree is missing a source file", relative))
    for relative in parity.extra_files:
        findings.append(DistributionFinding("extra_unowned_file", "installed member tree contains an extra file", relative))
    for relative in parity.raw_mismatches:
        findings.append(DistributionFinding("installed_raw_hash_mismatch", "installed file raw hash differs from source", relative))
    for relative in parity.missing_members:
        findings.append(DistributionFinding("installed_member_missing", "installed tree is missing a declared skill member", relative))
    for relative in parity.unsafe_paths:
        findings.append(DistributionFinding("unsafe_distribution_path", "source or installed tree contains a symlink or escaping path", relative))
    return DistributionReport(
        action="check",
        source=str(source_root),
        target=str(target_root),
        dry_run=False,
        unchanged_files=tuple(sorted(set(item.relative_path for item in source_inventory.files) - set(parity.missing_files) - set(parity.raw_mismatches))),
        extra_files=parity.extra_files,
        excluded_files=source_inventory.excluded_files + target_inventory.excluded_files,
        findings=tuple(findings),
        ownership_manifest=str(_manifest_path(target_root)),
        parity=parity,
    )


def _remove_empty_member_directories(target: Path, member_ids: Sequence[str]) -> None:
    for member_id in member_ids:
        member = _contained_path(target, member_id)
        if not member.is_dir() or member.is_symlink():
            continue
        for directory in sorted((path for path in member.rglob("*") if path.is_dir()), key=lambda path: len(path.parts), reverse=True):
            try:
                directory.rmdir()
            except OSError:
                pass
        try:
            member.rmdir()
        except OSError:
            pass


def uninstall_skill_suite(
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
    dry_run: bool = False,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
) -> DistributionReport:
    target_root = resolve_target_skill_root(target, codex_home=codex_home)
    manifest, manifest_error = _read_manifest(target_root)
    if manifest_error or manifest is None:
        message = manifest_error or "ownership manifest is missing; no files can be proven installer-owned"
        return DistributionReport(
            "uninstall",
            "",
            str(target_root),
            dry_run,
            findings=(DistributionFinding("ownership_manifest_unavailable", message, OWNERSHIP_MANIFEST_NAME),),
            ownership_manifest=str(_manifest_path(target_root)),
        )
    rows = [FileFingerprint.from_dict(row) for row in manifest.get("files", ())]
    removed: list[str] = []
    conflicts: list[str] = []
    absent: list[str] = []
    retained: list[FileFingerprint] = []
    findings: list[DistributionFinding] = []
    for row in rows:
        path = _contained_path(target_root, row.relative_path)
        try:
            actual = _fingerprint_if_file(path, row.relative_path)
        except ValueError as exc:
            conflicts.append(row.relative_path)
            retained.append(row)
            findings.append(DistributionFinding("unsafe_target_path", str(exc), row.relative_path))
            continue
        if actual is None:
            absent.append(row.relative_path)
        elif actual.raw_hash == row.raw_hash:
            removed.append(row.relative_path)
        else:
            conflicts.append(row.relative_path)
            retained.append(row)
            findings.append(DistributionFinding("modified_owned_file_preserved", "installer-owned path changed after install and is preserved", row.relative_path))

    member_ids = tuple(str(item) for item in manifest.get("member_ids", ()))
    target_inventory = inventory_skill_tree(target_root, member_ids=member_ids, exclusion_rules=exclusion_rules, allow_missing_root=True)
    owned_paths = {row.relative_path for row in rows}
    extras = tuple(sorted(item.relative_path for item in target_inventory.files if item.relative_path not in owned_paths))
    for relative in extras:
        findings.append(DistributionFinding("unowned_file_preserved", "uninstall does not delete an unowned file", relative, blocking=False))

    if not dry_run:
        for relative in removed:
            path = _contained_path(target_root, relative)
            if path.is_file() and not path.is_symlink():
                path.unlink()
        _remove_empty_member_directories(target_root, member_ids)
        manifest_path = _manifest_path(target_root)
        if retained:
            payload = dict(manifest)
            payload["files"] = [item.to_dict() for item in retained]
            _write_manifest(manifest_path, payload)
        elif manifest_path.is_file():
            manifest_path.unlink()

    return DistributionReport(
        action="uninstall",
        source=str(manifest.get("source_root", "")),
        target=str(target_root),
        dry_run=dry_run,
        removed_files=tuple(removed),
        unchanged_files=tuple(absent),
        conflict_files=tuple(conflicts),
        extra_files=extras,
        excluded_files=target_inventory.excluded_files,
        findings=tuple(findings),
        ownership_manifest=str(_manifest_path(target_root)),
    )


__all__ = [
    "CANONICAL_SKILL_ROOT",
    "CANONICAL_SUITE_MAP",
    "DEFAULT_EXCLUSION_RULES",
    "DISTRIBUTION_SCHEMA",
    "FLOWGUARD_EXPECTED_MEMBER_COUNT",
    "OWNERSHIP_MANIFEST_NAME",
    "OWNERSHIP_SCHEMA",
    "ConfiguredParityReport",
    "DistributionFinding",
    "DistributionReport",
    "ExcludedFile",
    "ExclusionRule",
    "FileFingerprint",
    "SkillTreeInventory",
    "TreeParity",
    "check_skill_suite",
    "compare_configured_skill_trees",
    "compare_tree_inventories",
    "discover_member_ids",
    "install_skill_suite",
    "inventory_skill_tree",
    "resolve_source_skill_root",
    "resolve_target_skill_root",
    "semantic_hash_bytes",
    "uninstall_skill_suite",
]
