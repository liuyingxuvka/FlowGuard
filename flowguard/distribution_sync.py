"""Declarative install, uninstall, and parity checks for FlowGuard skills.

The distribution surface is deliberately file based.  Every managed file is
identified by its path and hashes, while volatile evidence is omitted only by
named exclusion rules that remain visible in every inventory and report.
"""

from __future__ import annotations

import fnmatch
import hashlib
import importlib.metadata
import importlib.resources
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from .suite_contract import FLOWGUARD_EXPECTED_MEMBER_COUNT


DISTRIBUTION_SCHEMA = "flowguard.skill_distribution.v1"
OWNERSHIP_SCHEMA = "flowguard.skill_distribution_ownership.v1"
OWNERSHIP_MANIFEST_NAME = ".flowguard-skill-suite-ownership.json"
CONSUMER_RELEASE_SCHEMA = "consumer.skill_distribution.current"
CONSUMER_RELEASE_MANIFEST = "consumer-release.json"
CONSUMER_RELEASE_CLAIM = (
    "This manifest identifies target-owned consumer files only. It carries no "
    "author contract, receipt, router, session, cache, or execution authority."
)
CONSUMER_SUITE_AUTHORITY_SCHEMA = "flowguard.consumer_suite_authority.v1"
CONSUMER_SUITE_AUTHORITY_ARTIFACT = "flowguard_consumer_suite_authority"
CONSUMER_SUITE_AUTHORITY_MANIFEST = "consumer-suite-authority.json"
CONSUMER_SUITE_AUTHORITY_PROJECTION = "projection:consumer-distribution"
CONSUMER_SUITE_AUTHORITY_CLAIM = (
    "This package-owned authority identifies the exact clean FlowGuard consumer "
    "projection. It contains no author path, contract, receipt, router, cache, "
    "session, or execution authority."
)
CANONICAL_SKILL_ROOT = ".agents/skills"
CANONICAL_SUITE_MAP = ".skillguard/flowguard-suite/suite-map.json"
PARITY_ROLE_AUTHOR_SOURCE = "author_source"
PARITY_ROLE_CONSUMER_DISTRIBUTION = "consumer_distribution"
PARITY_ROLES = frozenset(
    {PARITY_ROLE_AUTHOR_SOURCE, PARITY_ROLE_CONSUMER_DISTRIBUTION}
)


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
    ExclusionRule(
        "author_control",
        "*/.skillguard/*",
        "SkillGuard contracts, checks, receipts, and runtime state are author-side maintenance artifacts and never consumer files",
    ),
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
        return cls.from_bytes(content, relative_path)

    @classmethod
    def from_bytes(cls, content: bytes, relative_path: str) -> "FileFingerprint":
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


def _strict_file_fingerprint(
    value: Mapping[str, Any],
    *,
    context: str,
) -> FileFingerprint:
    expected_keys = {"relative_path", "raw_hash", "semantic_hash", "size"}
    if set(value) != expected_keys:
        raise ValueError(f"{context} fields do not match the current schema")
    relative = value.get("relative_path")
    raw_hash = value.get("raw_hash")
    semantic_hash = value.get("semantic_hash")
    size = value.get("size")
    if not isinstance(relative, str):
        raise ValueError(f"{context} relative_path must be a string")
    if not isinstance(raw_hash, str) or re.fullmatch(r"[0-9A-F]{64}", raw_hash) is None:
        raise ValueError(f"{context} raw_hash must be an uppercase SHA-256 digest")
    if (
        not isinstance(semantic_hash, str)
        or re.fullmatch(r"[0-9A-F]{64}", semantic_hash) is None
    ):
        raise ValueError(
            f"{context} semantic_hash must be an uppercase SHA-256 digest"
        )
    if isinstance(size, bool) or not isinstance(size, int) or size < 0:
        raise ValueError(f"{context} size must be a non-negative integer")
    return FileFingerprint(_safe_relative(relative), raw_hash, semantic_hash, size)


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


@dataclass(frozen=True)
class ConsumerSuiteAuthority:
    source: str
    flowguard_version: str
    member_ids: tuple[str, ...]
    files: tuple[FileFingerprint, ...]
    raw_tree_hash: str
    semantic_tree_hash: str
    authority_hash: str

    def as_inventory(self) -> SkillTreeInventory:
        return SkillTreeInventory(
            root=self.source,
            member_ids=self.member_ids,
            missing_member_ids=(),
            files=self.files,
            excluded_files=(),
            unsafe_paths=(),
            raw_tree_hash=self.raw_tree_hash,
            semantic_tree_hash=self.semantic_tree_hash,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": CONSUMER_SUITE_AUTHORITY_ARTIFACT,
            "schema_version": CONSUMER_SUITE_AUTHORITY_SCHEMA,
            "flowguard_version": self.flowguard_version,
            "projection_id": CONSUMER_SUITE_AUTHORITY_PROJECTION,
            "member_ids": list(self.member_ids),
            "files": [item.to_dict() for item in self.files],
            "raw_tree_hash": self.raw_tree_hash,
            "semantic_tree_hash": self.semantic_tree_hash,
            "authority_hash": self.authority_hash,
            "claim_boundary": CONSUMER_SUITE_AUTHORITY_CLAIM,
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
        lexical_member = skill_root / Path(*PurePosixPath(member_id).parts)
        if lexical_member.is_symlink():
            unsafe.append(member_id)
            continue
        try:
            member_dir = _contained_path(skill_root, member_id)
        except ValueError:
            unsafe.append(member_id)
            continue
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


def _wire_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _consumer_release_bytes(
    member_id: str,
    files: Sequence[FileFingerprint],
) -> bytes:
    prefix = f"{member_id}/"
    member_files = [
        {
            "path": item.relative_path.removeprefix(prefix),
            "content_hash": "sha256:" + item.raw_hash.casefold(),
        }
        for item in files
        if item.relative_path.startswith(prefix)
        and item.relative_path != f"{member_id}/{CONSUMER_RELEASE_MANIFEST}"
    ]
    member_files.sort(key=lambda row: row["path"])
    identity = {
        "schema_version": CONSUMER_RELEASE_SCHEMA,
        "skill_id": member_id,
        "projection_id": "projection:consumer-distribution",
        "files": member_files,
        "author_control_excluded": True,
    }
    release_id = _wire_hash(_canonical_json(identity).encode("utf-8"))
    manifest = {
        **identity,
        "release_id": release_id,
        "claim_boundary": CONSUMER_RELEASE_CLAIM,
    }
    manifest["manifest_hash"] = _wire_hash(_canonical_json(manifest).encode("utf-8"))
    return (_canonical_json(manifest) + "\n").encode("utf-8")


def _consumer_source_inventory(
    root: str | Path,
    *,
    member_ids: Sequence[str],
    exclusion_rules: Sequence[ExclusionRule],
) -> tuple[SkillTreeInventory, dict[str, bytes]]:
    """Project an author tree into the exact clean consumer file inventory."""

    base = inventory_skill_tree(
        root,
        member_ids=member_ids,
        exclusion_rules=exclusion_rules,
    )
    generated: dict[str, bytes] = {}
    files = list(base.files)
    base_paths = {item.relative_path for item in base.files}
    for member_id in base.member_ids:
        relative = f"{member_id}/{CONSUMER_RELEASE_MANIFEST}"
        if relative in base_paths:
            raise ValueError(
                "author source contains compiler-owned consumer release manifest: "
                f"{relative}"
            )
        payload = _consumer_release_bytes(member_id, base.files)
        generated[relative] = payload
        files.append(FileFingerprint.from_bytes(payload, relative))
    files.sort(key=lambda item: item.relative_path)
    raw_tree_hash = _sha256(
        _canonical_json([[item.relative_path, item.raw_hash] for item in files]).encode("utf-8")
    )
    semantic_tree_hash = _sha256(
        _canonical_json([[item.relative_path, item.semantic_hash] for item in files]).encode("utf-8")
    )
    return (
        SkillTreeInventory(
            root=base.root,
            member_ids=base.member_ids,
            missing_member_ids=base.missing_member_ids,
            files=tuple(files),
            excluded_files=base.excluded_files,
            unsafe_paths=base.unsafe_paths,
            raw_tree_hash=raw_tree_hash,
            semantic_tree_hash=semantic_tree_hash,
        ),
        generated,
    )


def build_consumer_suite_authority_bytes(
    root: str | Path,
    *,
    member_ids: Sequence[str],
    flowguard_version: str,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
) -> bytes:
    """Compile one deterministic package-owned clean-consumer authority."""

    version = str(flowguard_version).strip()
    if not version:
        raise ValueError("flowguard_version is required")
    inventory, _generated = _consumer_source_inventory(
        root,
        member_ids=member_ids,
        exclusion_rules=exclusion_rules,
    )
    if len(inventory.member_ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        raise ValueError(
            "consumer authority requires exactly "
            f"{FLOWGUARD_EXPECTED_MEMBER_COUNT} members"
        )
    if inventory.missing_member_ids or inventory.unsafe_paths:
        raise ValueError("consumer authority source inventory is incomplete or unsafe")
    identity: dict[str, Any] = {
        "artifact_type": CONSUMER_SUITE_AUTHORITY_ARTIFACT,
        "schema_version": CONSUMER_SUITE_AUTHORITY_SCHEMA,
        "flowguard_version": version,
        "projection_id": CONSUMER_SUITE_AUTHORITY_PROJECTION,
        "member_ids": list(inventory.member_ids),
        "files": [item.to_dict() for item in inventory.files],
        "raw_tree_hash": inventory.raw_tree_hash,
        "semantic_tree_hash": inventory.semantic_tree_hash,
        "claim_boundary": CONSUMER_SUITE_AUTHORITY_CLAIM,
    }
    identity["authority_hash"] = _wire_hash(
        _canonical_json(identity).encode("utf-8")
    )
    return (_canonical_json(identity) + "\n").encode("utf-8")


def _packaged_authority_text() -> tuple[str, str]:
    resource = importlib.resources.files("flowguard").joinpath(
        CONSUMER_SUITE_AUTHORITY_MANIFEST
    )
    return resource.read_text(encoding="utf-8"), str(resource)


def _parse_consumer_suite_authority_text(
    text: str,
    *,
    source: str,
    expected_version: str,
) -> ConsumerSuiteAuthority:
    """Parse authority bytes for the fixed package loader and isolated tests."""

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"consumer authority JSON is invalid: {exc}") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("consumer authority root must be an object")
    allowed_keys = {
        "artifact_type",
        "schema_version",
        "flowguard_version",
        "projection_id",
        "member_ids",
        "files",
        "raw_tree_hash",
        "semantic_tree_hash",
        "authority_hash",
        "claim_boundary",
    }
    if set(payload) != allowed_keys:
        raise ValueError("consumer authority fields do not match the current schema")
    if payload.get("artifact_type") != CONSUMER_SUITE_AUTHORITY_ARTIFACT:
        raise ValueError("consumer authority artifact type is invalid")
    if payload.get("schema_version") != CONSUMER_SUITE_AUTHORITY_SCHEMA:
        raise ValueError("consumer authority schema is unsupported")
    if payload.get("projection_id") != CONSUMER_SUITE_AUTHORITY_PROJECTION:
        raise ValueError("consumer authority projection is invalid")
    if payload.get("claim_boundary") != CONSUMER_SUITE_AUTHORITY_CLAIM:
        raise ValueError("consumer authority claim boundary is invalid")

    version_value = payload.get("flowguard_version")
    if not isinstance(version_value, str) or not version_value:
        raise ValueError("consumer authority FlowGuard version is missing")
    version = version_value
    if version != expected_version:
        raise ValueError(
            "consumer authority version does not match the installed FlowGuard "
            f"package: authority={version} installed={expected_version}"
        )

    raw_member_ids = payload.get("member_ids")
    if not isinstance(raw_member_ids, list):
        raise ValueError("consumer authority member_ids must be an array")
    if any(not isinstance(item, str) for item in raw_member_ids):
        raise ValueError("consumer authority member ids must be strings")
    member_ids = tuple(_safe_relative(item) for item in raw_member_ids)
    if len(member_ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        raise ValueError(
            "consumer authority must declare exactly "
            f"{FLOWGUARD_EXPECTED_MEMBER_COUNT} members"
        )
    if len(set(member_ids)) != len(member_ids):
        raise ValueError("consumer authority member ids must be unique")
    if any(len(PurePosixPath(member_id).parts) != 1 for member_id in member_ids):
        raise ValueError("consumer authority member ids must be single directory names")
    if any(
        member_id != "flowguard" and not member_id.startswith("flowguard-")
        for member_id in member_ids
    ):
        raise ValueError("consumer authority contains a non-FlowGuard member id")
    if "flowguard" not in member_ids:
        raise ValueError("consumer authority is missing the FlowGuard kernel")

    raw_files = payload.get("files")
    if not isinstance(raw_files, list):
        raise ValueError("consumer authority files must be an array")
    try:
        files = tuple(
            _strict_file_fingerprint(row, context="consumer authority file row")
            for row in raw_files
            if isinstance(row, Mapping)
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"consumer authority file inventory is invalid: {exc}") from exc
    if len(files) != len(raw_files):
        raise ValueError("consumer authority file row must be an object")
    relative_paths = tuple(item.relative_path for item in files)
    if len(set(relative_paths)) != len(relative_paths):
        raise ValueError("consumer authority file paths must be unique")
    if relative_paths != tuple(sorted(relative_paths)):
        raise ValueError("consumer authority file paths must be sorted")
    allowed_prefixes = tuple(f"{member_id}/" for member_id in member_ids)
    if any(not relative.startswith(allowed_prefixes) for relative in relative_paths):
        raise ValueError("consumer authority file is outside the declared member boundary")
    if any(".skillguard" in PurePosixPath(relative).parts for relative in relative_paths):
        raise ValueError("consumer authority contains author-control material")
    for member_id in member_ids:
        required = {
            f"{member_id}/SKILL.md",
            f"{member_id}/agents/openai.yaml",
            f"{member_id}/{CONSUMER_RELEASE_MANIFEST}",
        }
        if not required.issubset(relative_paths):
            raise ValueError(
                f"consumer authority is missing required files for {member_id}"
            )

    sorted_files = tuple(sorted(files, key=lambda item: item.relative_path))
    raw_tree_hash = _sha256(
        _canonical_json(
            [[item.relative_path, item.raw_hash] for item in sorted_files]
        ).encode("utf-8")
    )
    semantic_tree_hash = _sha256(
        _canonical_json(
            [[item.relative_path, item.semantic_hash] for item in sorted_files]
        ).encode("utf-8")
    )
    declared_raw_tree_hash = payload.get("raw_tree_hash")
    declared_semantic_tree_hash = payload.get("semantic_tree_hash")
    if (
        not isinstance(declared_raw_tree_hash, str)
        or re.fullmatch(r"[0-9A-F]{64}", declared_raw_tree_hash) is None
        or raw_tree_hash != declared_raw_tree_hash
    ):
        raise ValueError("consumer authority raw tree hash is invalid")
    if (
        not isinstance(declared_semantic_tree_hash, str)
        or re.fullmatch(r"[0-9A-F]{64}", declared_semantic_tree_hash) is None
        or semantic_tree_hash != declared_semantic_tree_hash
    ):
        raise ValueError("consumer authority semantic tree hash is invalid")
    authority_payload = dict(payload)
    authority_hash_value = authority_payload.pop("authority_hash", "")
    if (
        not isinstance(authority_hash_value, str)
        or re.fullmatch(r"sha256:[0-9a-f]{64}", authority_hash_value) is None
    ):
        raise ValueError("consumer authority hash is invalid")
    authority_hash = authority_hash_value
    expected_authority_hash = _wire_hash(
        _canonical_json(authority_payload).encode("utf-8")
    )
    if authority_hash != expected_authority_hash:
        raise ValueError("consumer authority hash is invalid")

    return ConsumerSuiteAuthority(
        source=source,
        flowguard_version=version,
        member_ids=member_ids,
        files=sorted_files,
        raw_tree_hash=raw_tree_hash,
        semantic_tree_hash=semantic_tree_hash,
        authority_hash=authority_hash,
    )


def _load_packaged_consumer_suite_authority_snapshot(
) -> tuple[ConsumerSuiteAuthority, str]:
    try:
        text, source = _packaged_authority_text()
    except (FileNotFoundError, ModuleNotFoundError, OSError) as exc:
        raise ValueError(f"packaged consumer authority is unavailable: {exc}") from exc
    try:
        expected_version = importlib.metadata.version("flowguard")
    except importlib.metadata.PackageNotFoundError as exc:
        raise ValueError("installed FlowGuard package metadata is unavailable") from exc
    return (
        _parse_consumer_suite_authority_text(
            text,
            source=source,
            expected_version=expected_version,
        ),
        text,
    )


def load_consumer_suite_authority() -> ConsumerSuiteAuthority:
    """Load the sole package resource bound to installed package metadata."""

    authority, _text = _load_packaged_consumer_suite_authority_snapshot()
    return authority


def _source_authority_findings(
    source_inventory: SkillTreeInventory,
) -> tuple[DistributionFinding, ...]:
    try:
        authority = load_consumer_suite_authority()
    except ValueError as exc:
        return (
            DistributionFinding(
                "consumer_authority_invalid",
                str(exc),
                CONSUMER_SUITE_AUTHORITY_MANIFEST,
            ),
        )
    findings: list[DistributionFinding] = []
    if tuple(source_inventory.member_ids) != authority.member_ids:
        findings.append(
            DistributionFinding(
                "consumer_authority_member_mismatch",
                "packaged authority member ids differ from the current author projection",
                CONSUMER_SUITE_AUTHORITY_MANIFEST,
                metadata={
                    "authority_member_ids": authority.member_ids,
                    "source_member_ids": source_inventory.member_ids,
                },
            )
        )
    parity = compare_tree_inventories(
        authority.as_inventory(),
        source_inventory,
    )
    for relative in parity.missing_files:
        findings.append(
            DistributionFinding(
                "consumer_authority_source_file_missing",
                "current author projection is missing a packaged-authority file",
                relative,
            )
        )
    for relative in parity.extra_files:
        findings.append(
            DistributionFinding(
                "consumer_authority_source_file_extra",
                "current author projection contains a file absent from packaged authority",
                relative,
            )
        )
    for relative in parity.raw_mismatches:
        findings.append(
            DistributionFinding(
                "consumer_authority_source_hash_mismatch",
                "current author projection raw hash differs from packaged authority",
                relative,
            )
        )
    for relative in parity.missing_members:
        findings.append(
            DistributionFinding(
                "consumer_authority_source_member_missing",
                "current author projection is missing a packaged-authority member",
                relative,
            )
        )
    for relative in parity.unsafe_paths:
        findings.append(
            DistributionFinding(
                "consumer_authority_source_path_unsafe",
                "current author projection contains an unsafe path",
                relative,
            )
        )
    return tuple(findings)


def _consumer_author_control_files(
    root: Path,
    member_ids: Sequence[str],
) -> tuple[str, ...]:
    residuals: list[str] = []
    for member_id in member_ids:
        relative_root = f"{member_id}/.skillguard"
        try:
            control_root = _contained_path(root, relative_root)
        except ValueError:
            residuals.append(relative_root)
            continue
        if not control_root.exists() and not control_root.is_symlink():
            continue
        residuals.append(relative_root)
        if not control_root.is_dir() or control_root.is_symlink():
            continue
        residuals.extend(
            path.relative_to(root).as_posix()
            for path in sorted(control_root.rglob("*"))
            if path.is_file() or path.is_symlink()
        )
    return tuple(dict.fromkeys(residuals))


def _consumer_text_findings(
    root: Path,
    files: Sequence[FileFingerprint],
) -> tuple[DistributionFinding, ...]:
    findings: list[DistributionFinding] = []
    text_suffixes = {
        ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml",
        ".py", ".ps1", ".sh", ".js", ".ts", ".tsx", ".jsx", ".html",
        ".css", ".xml", ".ini", ".cfg",
    }
    patterns = (
        ("consumer_skillguard_reference", re.compile(r"(?i)\bskillguard\b|\.skillguard")),
        (
            "consumer_portfolio_authority_reference",
            re.compile(r"(?i)\bportfolio[_ -](?:receipt|reuse|evidence|graduation)\b"),
        ),
    )
    for item in files:
        if item.relative_path.endswith(f"/{CONSUMER_RELEASE_MANIFEST}"):
            continue
        path = _contained_path(root, item.relative_path)
        if path.suffix.casefold() not in text_suffixes and path.name != "SKILL.md":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for code, pattern in patterns:
            if pattern.search(text):
                findings.append(
                    DistributionFinding(
                        code,
                        "consumer files must not require or instruct use of author-side SkillGuard state",
                        item.relative_path,
                    )
                )
    return tuple(findings)


def _consumer_release_findings(
    root: Path,
    authority: ConsumerSuiteAuthority,
) -> tuple[DistributionFinding, ...]:
    findings: list[DistributionFinding] = []
    expected_keys = {
        "schema_version",
        "skill_id",
        "projection_id",
        "files",
        "author_control_excluded",
        "release_id",
        "claim_boundary",
        "manifest_hash",
    }
    for member_id in authority.member_ids:
        relative = f"{member_id}/{CONSUMER_RELEASE_MANIFEST}"
        path = root / Path(*PurePosixPath(relative).parts)
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            findings.append(
                DistributionFinding(
                    "consumer_release_invalid",
                    f"consumer release manifest cannot be read: {exc}",
                    relative,
                )
            )
            continue
        if not isinstance(payload, dict) or set(payload) != expected_keys:
            findings.append(
                DistributionFinding(
                    "consumer_release_invalid",
                    "consumer release manifest fields do not match the current schema",
                    relative,
                )
            )
            continue
        expected_files = [
            {
                "path": item.relative_path.removeprefix(f"{member_id}/"),
                "content_hash": "sha256:" + item.raw_hash.casefold(),
            }
            for item in authority.files
            if item.relative_path.startswith(f"{member_id}/")
            and item.relative_path != relative
        ]
        expected_files.sort(key=lambda row: row["path"])
        identity = {
            "schema_version": CONSUMER_RELEASE_SCHEMA,
            "skill_id": member_id,
            "projection_id": CONSUMER_SUITE_AUTHORITY_PROJECTION,
            "files": expected_files,
            "author_control_excluded": True,
        }
        expected_release_id = _wire_hash(
            _canonical_json(identity).encode("utf-8")
        )
        expected_payload = {
            **identity,
            "release_id": expected_release_id,
            "claim_boundary": CONSUMER_RELEASE_CLAIM,
        }
        expected_manifest_hash = _wire_hash(
            _canonical_json(expected_payload).encode("utf-8")
        )
        expected_payload["manifest_hash"] = expected_manifest_hash
        if payload != expected_payload:
            findings.append(
                DistributionFinding(
                    "consumer_release_identity_mismatch",
                    "consumer release manifest does not match its package-authority member projection",
                    relative,
                )
            )
    return tuple(findings)


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
    root_roles: Mapping[str, str]
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
            "root_roles": dict(self.root_roles),
            "ok": self.ok,
            "inventories": {name: value.to_dict() for name, value in self.inventories.items()},
            "comparisons": {name: value.to_dict() for name, value in self.comparisons.items()},
            "claim_boundary": (
                "Author roots are compared to the canonical author projection and consumer roots "
                "to the generated clean consumer projection; roles are explicit and never inferred."
            ),
        }


def compare_configured_skill_trees(
    roots: Mapping[str, str | Path],
    *,
    root_roles: Mapping[str, str],
    reference_name: str = "source",
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
) -> ConfiguredParityReport:
    if reference_name not in roots:
        raise ValueError(f"reference root {reference_name!r} is not configured")
    if set(root_roles) != set(roots):
        raise ValueError("root_roles must declare exactly one role for every configured root")
    invalid_roles = sorted(
        f"{name}:{role}" for name, role in root_roles.items() if role not in PARITY_ROLES
    )
    if invalid_roles:
        raise ValueError(f"unsupported parity root roles: {', '.join(invalid_roles)}")
    if root_roles[reference_name] != PARITY_ROLE_AUTHOR_SOURCE:
        raise ValueError("the canonical parity reference must be an explicit author_source root")
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(roots[reference_name])
    reference_author = inventory_skill_tree(
        roots[reference_name],
        member_ids=ids,
        exclusion_rules=exclusion_rules,
    )
    reference_consumer, _ = _consumer_source_inventory(
        roots[reference_name],
        member_ids=ids,
        exclusion_rules=exclusion_rules,
    )
    inventories: dict[str, SkillTreeInventory] = {reference_name: reference_author}
    comparisons: dict[str, TreeParity] = {}
    for name, root in roots.items():
        if name == reference_name:
            continue
        inventory = inventory_skill_tree(
            root,
            member_ids=ids,
            exclusion_rules=exclusion_rules,
            allow_missing_root=True,
        )
        inventories[name] = inventory
        reference = (
            reference_consumer
            if root_roles[name] == PARITY_ROLE_CONSUMER_DISTRIBUTION
            else reference_author
        )
        comparisons[name] = compare_tree_inventories(reference, inventory)
    return ConfiguredParityReport(reference_name, dict(root_roles), inventories, comparisons)


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
    authority_hash: str = ""
    authority_raw_tree_hash: str = ""
    authority_semantic_tree_hash: str = ""
    authority_member_ids: tuple[str, ...] = ()

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
            "authority_hash": self.authority_hash,
            "authority_raw_tree_hash": self.authority_raw_tree_hash,
            "authority_semantic_tree_hash": self.authority_semantic_tree_hash,
            "authority_member_ids": list(self.authority_member_ids),
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
    payload, error, _raw = _read_manifest_snapshot(target)
    return payload, error


def _read_manifest_snapshot(
    target: Path,
) -> tuple[dict[str, Any] | None, str, bytes | None]:
    path = _manifest_path(target)
    if not path.is_file():
        return None, "", None
    try:
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc), None
    expected_keys = {
        "artifact_type",
        "schema_version",
        "source_root",
        "target_root",
        "member_ids",
        "source_raw_tree_hash",
        "source_semantic_tree_hash",
        "files",
        "exclusion_policy",
        "source_excluded_files",
    }
    if not isinstance(payload, dict) or set(payload) != expected_keys:
        return None, "ownership manifest fields do not match the current schema", raw
    if payload.get("artifact_type") != "flowguard_skill_distribution_ownership":
        return None, "ownership manifest artifact type is invalid", raw
    if payload.get("schema_version") != OWNERSHIP_SCHEMA:
        return None, "ownership manifest schema is missing or unsupported", raw
    try:
        for field_name in ("source_root", "target_root"):
            value = payload.get(field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"ownership manifest {field_name} must be a non-empty string"
                )
        members = payload.get("member_ids")
        if not isinstance(members, list) or any(
            not isinstance(item, str) for item in members
        ):
            raise ValueError("ownership manifest member_ids must be a string array")
        normalized_members = tuple(_safe_relative(item) for item in members)
        if len(set(normalized_members)) != len(normalized_members):
            raise ValueError("ownership manifest member ids must be unique")
        for field_name in ("source_raw_tree_hash", "source_semantic_tree_hash"):
            value = payload.get(field_name)
            if not isinstance(value, str) or re.fullmatch(
                r"[0-9A-F]{64}", value
            ) is None:
                raise ValueError(
                    f"ownership manifest {field_name} must be an uppercase SHA-256 digest"
                )
        rows = payload.get("files")
        if not isinstance(rows, list):
            raise ValueError("ownership manifest files must be an array")
        fingerprints = []
        for row in rows:
            if not isinstance(row, Mapping):
                raise ValueError("ownership manifest file row must be an object")
            fingerprints.append(
                _strict_file_fingerprint(
                    row,
                    context="ownership manifest file row",
                )
            )
        paths = tuple(item.relative_path for item in fingerprints)
        if len(set(paths)) != len(paths) or paths != tuple(sorted(paths)):
            raise ValueError(
                "ownership manifest file paths must be unique and sorted"
            )
        expected_policy = [rule.to_dict() for rule in DEFAULT_EXCLUSION_RULES]
        if payload.get("exclusion_policy") != expected_policy:
            raise ValueError(
                "ownership manifest exclusion policy differs from the current fixed policy"
            )
        excluded_rows = payload.get("source_excluded_files")
        if not isinstance(excluded_rows, list):
            raise ValueError(
                "ownership manifest source_excluded_files must be an array"
            )
        excluded_keys = {"relative_path", "rule_id", "pattern", "reason"}
        for row in excluded_rows:
            if (
                not isinstance(row, Mapping)
                or set(row) != excluded_keys
                or any(not isinstance(row.get(key), str) for key in excluded_keys)
            ):
                raise ValueError(
                    "ownership manifest excluded-file row is invalid"
                )
            _safe_relative(row["relative_path"])
    except (TypeError, ValueError) as exc:
        return None, str(exc), raw
    return payload, "", raw


def validate_installed_consumer_suite(
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
) -> DistributionReport:
    """Validate the installed FlowGuard suite from package-owned authority only.

    This runtime path deliberately has no author-checkout input.  It consumes
    the immutable authority shipped in the installed package and compares that
    authority to the global consumer projection plus its ownership manifest.
    """

    target_root = resolve_target_skill_root(target, codex_home=codex_home)
    try:
        authority, authority_text_before = (
            _load_packaged_consumer_suite_authority_snapshot()
        )
    except ValueError as exc:
        return DistributionReport(
            action="consumer-authority-check",
            source=CONSUMER_SUITE_AUTHORITY_MANIFEST,
            target=str(target_root),
            dry_run=False,
            findings=(
                DistributionFinding(
                    "consumer_authority_invalid",
                    str(exc),
                    CONSUMER_SUITE_AUTHORITY_MANIFEST,
                ),
            ),
            ownership_manifest=str(_manifest_path(target_root)),
        )

    manifest, manifest_error, manifest_bytes_before = _read_manifest_snapshot(
        target_root
    )
    authority_inventory = authority.as_inventory()
    try:
        target_inventory = inventory_skill_tree(
            target_root,
            member_ids=authority.member_ids,
            exclusion_rules=DEFAULT_EXCLUSION_RULES,
            allow_missing_root=True,
        )
    except (OSError, ValueError) as exc:
        return DistributionReport(
            action="consumer-authority-check",
            source=authority.source,
            target=str(target_root),
            dry_run=False,
            findings=(
                DistributionFinding(
                    "consumer_projection_inventory_error",
                    f"{type(exc).__name__}: {exc}",
                ),
            ),
            ownership_manifest=str(_manifest_path(target_root)),
            authority_hash=authority.authority_hash,
            authority_raw_tree_hash=authority.raw_tree_hash,
            authority_semantic_tree_hash=authority.semantic_tree_hash,
            authority_member_ids=authority.member_ids,
        )
    parity = compare_tree_inventories(authority_inventory, target_inventory)
    findings: list[DistributionFinding] = []
    for relative in parity.missing_files:
        findings.append(
            DistributionFinding(
                "installed_file_missing",
                "installed tree is missing a package-authority file",
                relative,
            )
        )
    for relative in parity.extra_files:
        findings.append(
            DistributionFinding(
                "extra_unowned_file",
                "installed FlowGuard member tree contains a file absent from package authority",
                relative,
            )
        )
    for relative in parity.raw_mismatches:
        findings.append(
            DistributionFinding(
                "installed_raw_hash_mismatch",
                "installed file raw hash differs from package authority",
                relative,
            )
        )
    for relative in parity.missing_members:
        findings.append(
            DistributionFinding(
                "installed_member_missing",
                "installed tree is missing a package-authority member",
                relative,
            )
        )
    for relative in parity.unsafe_paths:
        findings.append(
            DistributionFinding(
                "unsafe_distribution_path",
                "installed tree contains a symlink or escaping path",
                relative,
            )
        )

    if manifest_error:
        findings.append(
            DistributionFinding(
                "ownership_manifest_invalid",
                manifest_error,
                OWNERSHIP_MANIFEST_NAME,
            )
        )
    elif manifest is None:
        findings.append(
            DistributionFinding(
                "ownership_manifest_missing",
                "installed skill tree has no ownership manifest",
                OWNERSHIP_MANIFEST_NAME,
            )
        )
    else:
        if manifest.get("artifact_type") != "flowguard_skill_distribution_ownership":
            findings.append(
                DistributionFinding(
                    "ownership_manifest_artifact_invalid",
                    "ownership manifest artifact type is invalid",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )
        manifest_members = tuple(str(item) for item in manifest.get("member_ids", ()))
        if manifest_members != authority.member_ids:
            findings.append(
                DistributionFinding(
                    "ownership_member_mismatch",
                    "ownership manifest members differ from package authority",
                    OWNERSHIP_MANIFEST_NAME,
                    metadata={
                        "authority_member_ids": authority.member_ids,
                        "ownership_member_ids": manifest_members,
                    },
                )
            )
        if manifest.get("source_raw_tree_hash") != authority.raw_tree_hash:
            findings.append(
                DistributionFinding(
                    "ownership_raw_tree_hash_mismatch",
                    "ownership manifest raw tree hash differs from package authority",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )
        if manifest.get("source_semantic_tree_hash") != authority.semantic_tree_hash:
            findings.append(
                DistributionFinding(
                    "ownership_semantic_tree_hash_mismatch",
                    "ownership manifest semantic tree hash differs from package authority",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )
        if str(manifest.get("target_root", "")) != str(target_root):
            findings.append(
                DistributionFinding(
                    "ownership_target_mismatch",
                    "ownership manifest target root differs from the active global skills root",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )
        try:
            manifest_files = tuple(
                _strict_file_fingerprint(
                    row,
                    context="ownership manifest file row",
                )
                for row in manifest.get("files", ())
                if isinstance(row, Mapping)
            )
        except (TypeError, ValueError) as exc:
            manifest_files = ()
            findings.append(
                DistributionFinding(
                    "ownership_file_inventory_invalid",
                    f"ownership manifest file inventory is invalid: {exc}",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )
        raw_manifest_rows = manifest.get("files", ())
        if (
            not isinstance(raw_manifest_rows, list)
            or len(manifest_files) != len(raw_manifest_rows)
        ):
            findings.append(
                DistributionFinding(
                    "ownership_file_inventory_invalid",
                    "ownership manifest file rows must all be objects",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )
        elif manifest_files != authority.files:
            findings.append(
                DistributionFinding(
                    "ownership_file_inventory_mismatch",
                    "ownership manifest files differ from package authority",
                    OWNERSHIP_MANIFEST_NAME,
                )
            )

    for relative in _consumer_author_control_files(
        target_root,
        authority.member_ids,
    ):
        findings.append(
            DistributionFinding(
                "consumer_author_control_residual",
                "installed consumer skill still contains author-side .skillguard state",
                relative,
            )
        )

    if target_root.is_dir():
        for child in sorted(target_root.iterdir(), key=lambda path: path.name):
            child_id = child.name.casefold()
            if child_id in authority.member_ids:
                continue
            if child_id == "flowguard" or child_id.startswith("flowguard-"):
                findings.append(
                    DistributionFinding(
                        "reserved_flowguard_member_extra",
                        "global skills root contains an undeclared reserved FlowGuard path",
                        child.name,
                        metadata={
                            "path_kind": (
                                "symlink"
                                if child.is_symlink()
                                else "directory"
                                if child.is_dir()
                                else "file"
                            )
                        },
                    )
                )

    findings.extend(_consumer_release_findings(target_root, authority))
    findings.extend(_consumer_text_findings(target_root, authority.files))
    try:
        authority_text_after, _authority_source_after = _packaged_authority_text()
        installed_version_after = importlib.metadata.version("flowguard")
    except (
        FileNotFoundError,
        ModuleNotFoundError,
        OSError,
        importlib.metadata.PackageNotFoundError,
    ) as exc:
        findings.append(
            DistributionFinding(
                "consumer_authority_snapshot_changed",
                f"package authority became unavailable during validation: {exc}",
                CONSUMER_SUITE_AUTHORITY_MANIFEST,
            )
        )
    else:
        if (
            authority_text_after != authority_text_before
            or installed_version_after != authority.flowguard_version
        ):
            findings.append(
                DistributionFinding(
                    "consumer_authority_snapshot_changed",
                    "package authority or installed package metadata changed during validation",
                    CONSUMER_SUITE_AUTHORITY_MANIFEST,
                )
            )
    _manifest_after, _manifest_error_after, manifest_bytes_after = (
        _read_manifest_snapshot(target_root)
    )
    if manifest_bytes_after != manifest_bytes_before:
        findings.append(
            DistributionFinding(
                "ownership_snapshot_changed",
                "ownership manifest changed during consumer validation",
                OWNERSHIP_MANIFEST_NAME,
            )
        )
    try:
        target_inventory_after = inventory_skill_tree(
            target_root,
            member_ids=authority.member_ids,
            exclusion_rules=DEFAULT_EXCLUSION_RULES,
            allow_missing_root=True,
        )
    except (OSError, ValueError) as exc:
        findings.append(
            DistributionFinding(
                "consumer_projection_snapshot_changed",
                f"consumer projection became unreadable during validation: {exc}",
            )
        )
    else:
        if target_inventory_after != target_inventory:
            findings.append(
                DistributionFinding(
                    "consumer_projection_snapshot_changed",
                    "consumer projection changed during validation",
                )
            )
    unchanged = tuple(
        sorted(
            set(item.relative_path for item in authority.files)
            - set(parity.missing_files)
            - set(parity.raw_mismatches)
        )
    )
    return DistributionReport(
        action="consumer-authority-check",
        source=authority.source,
        target=str(target_root),
        dry_run=False,
        unchanged_files=unchanged,
        extra_files=parity.extra_files,
        excluded_files=target_inventory.excluded_files,
        findings=tuple(findings),
        ownership_manifest=str(_manifest_path(target_root)),
        parity=parity,
        authority_hash=authority.authority_hash,
        authority_raw_tree_hash=authority.raw_tree_hash,
        authority_semantic_tree_hash=authority.semantic_tree_hash,
        authority_member_ids=authority.member_ids,
    )


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


def _install_skill_tree(
    source: str | Path,
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
    dry_run: bool = False,
    adopt_existing: bool = False,
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
    enforce_consumer_authority: bool = False,
) -> DistributionReport:
    source_root = resolve_source_skill_root(source)
    target_root = resolve_target_skill_root(target, codex_home=codex_home)
    _assert_disjoint(source_root, target_root)
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(source)
    source_inventory, generated_files = _consumer_source_inventory(
        source_root,
        member_ids=ids,
        exclusion_rules=exclusion_rules,
    )
    findings: list[DistributionFinding] = []
    if enforce_consumer_authority and len(ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        findings.append(
            DistributionFinding(
                "invalid_suite_cardinality",
                "a complete FlowGuard distribution must contain exactly fifteen skills",
                metadata={"actual": len(ids), "expected": FLOWGUARD_EXPECTED_MEMBER_COUNT},
            )
        )
    if enforce_consumer_authority:
        findings.extend(_source_authority_findings(source_inventory))
    for member in source_inventory.missing_member_ids:
        findings.append(DistributionFinding("source_member_missing", "declared source member is missing", member))
    for relative in source_inventory.unsafe_paths:
        findings.append(DistributionFinding("unsafe_source_path", "source contains a symlink or escaping path", relative))
    findings.extend(_consumer_text_findings(source_root, source_inventory.files))
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

    author_residuals = _consumer_author_control_files(target_root, ids)
    planned_removals = set(removed)
    for relative in author_residuals:
        if relative not in planned_removals:
            findings.append(
                DistributionFinding(
                    "consumer_author_control_residual",
                    "installed consumer skill still contains author-side .skillguard state",
                    relative,
                )
            )

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
            destination = _contained_path(target_root, relative)
            destination.parent.mkdir(parents=True, exist_ok=True)
            generated = generated_files.get(relative)
            if generated is not None:
                with tempfile.NamedTemporaryFile("wb", dir=destination.parent, delete=False) as handle:
                    handle.write(generated)
                    temporary = Path(handle.name)
                temporary.replace(destination)
            else:
                source_file = _contained_path(source_root, relative)
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


def install_skill_suite(
    source: str | Path,
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
    dry_run: bool = False,
    adopt_existing: bool = False,
) -> DistributionReport:
    """Install the exact package-authorized FlowGuard consumer suite."""

    try:
        return _install_skill_tree(
            source,
            target,
            codex_home=codex_home,
            dry_run=dry_run,
            adopt_existing=adopt_existing,
            member_ids=None,
            exclusion_rules=DEFAULT_EXCLUSION_RULES,
            enforce_consumer_authority=True,
        )
    except (OSError, ValueError) as exc:
        target_root = resolve_target_skill_root(target, codex_home=codex_home)
        return DistributionReport(
            action="install",
            source=str(Path(source).expanduser()),
            target=str(target_root),
            dry_run=dry_run,
            findings=(
                DistributionFinding(
                    "consumer_source_projection_invalid",
                    f"{type(exc).__name__}: {exc}",
                ),
            ),
            ownership_manifest=str(_manifest_path(target_root)),
        )


def _check_skill_tree(
    source: str | Path,
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
    member_ids: Sequence[str] | None = None,
    exclusion_rules: Sequence[ExclusionRule] = DEFAULT_EXCLUSION_RULES,
    enforce_consumer_authority: bool = False,
) -> DistributionReport:
    source_root = resolve_source_skill_root(source)
    target_root = resolve_target_skill_root(target, codex_home=codex_home)
    _assert_disjoint(source_root, target_root)
    ids = tuple(member_ids) if member_ids is not None else discover_member_ids(source)
    source_inventory, _generated_files = _consumer_source_inventory(
        source_root,
        member_ids=ids,
        exclusion_rules=exclusion_rules,
    )
    target_inventory = inventory_skill_tree(target_root, member_ids=ids, exclusion_rules=exclusion_rules, allow_missing_root=True)
    parity = compare_tree_inventories(source_inventory, target_inventory)
    findings: list[DistributionFinding] = []
    if enforce_consumer_authority and len(ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        findings.append(
            DistributionFinding(
                "invalid_suite_cardinality",
                "a complete FlowGuard distribution must contain exactly fifteen skills",
                metadata={"actual": len(ids), "expected": FLOWGUARD_EXPECTED_MEMBER_COUNT},
            )
        )
    if enforce_consumer_authority:
        findings.extend(_source_authority_findings(source_inventory))
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
    for relative in _consumer_author_control_files(target_root, ids):
        findings.append(
            DistributionFinding(
                "consumer_author_control_residual",
                "installed consumer skill still contains author-side .skillguard state",
                relative,
            )
        )
    findings.extend(_consumer_text_findings(source_root, source_inventory.files))
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


def check_skill_suite(
    source: str | Path,
    target: str | Path | None = None,
    *,
    codex_home: str | Path | None = None,
) -> DistributionReport:
    """Check exact package-authorized FlowGuard source/install parity."""

    try:
        return _check_skill_tree(
            source,
            target,
            codex_home=codex_home,
            member_ids=None,
            exclusion_rules=DEFAULT_EXCLUSION_RULES,
            enforce_consumer_authority=True,
        )
    except (OSError, ValueError) as exc:
        target_root = resolve_target_skill_root(target, codex_home=codex_home)
        return DistributionReport(
            action="check",
            source=str(Path(source).expanduser()),
            target=str(target_root),
            dry_run=False,
            findings=(
                DistributionFinding(
                    "consumer_source_projection_invalid",
                    f"{type(exc).__name__}: {exc}",
                ),
            ),
            ownership_manifest=str(_manifest_path(target_root)),
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
    target_inventory = inventory_skill_tree(
        target_root,
        member_ids=member_ids,
        exclusion_rules=DEFAULT_EXCLUSION_RULES,
        allow_missing_root=True,
    )
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
    "CONSUMER_SUITE_AUTHORITY_ARTIFACT",
    "CONSUMER_SUITE_AUTHORITY_CLAIM",
    "CONSUMER_SUITE_AUTHORITY_MANIFEST",
    "CONSUMER_SUITE_AUTHORITY_PROJECTION",
    "CONSUMER_SUITE_AUTHORITY_SCHEMA",
    "DEFAULT_EXCLUSION_RULES",
    "DISTRIBUTION_SCHEMA",
    "FLOWGUARD_EXPECTED_MEMBER_COUNT",
    "PARITY_ROLE_AUTHOR_SOURCE",
    "PARITY_ROLE_CONSUMER_DISTRIBUTION",
    "PARITY_ROLES",
    "OWNERSHIP_MANIFEST_NAME",
    "OWNERSHIP_SCHEMA",
    "ConfiguredParityReport",
    "ConsumerSuiteAuthority",
    "DistributionFinding",
    "DistributionReport",
    "ExcludedFile",
    "ExclusionRule",
    "FileFingerprint",
    "SkillTreeInventory",
    "TreeParity",
    "build_consumer_suite_authority_bytes",
    "check_skill_suite",
    "compare_configured_skill_trees",
    "compare_tree_inventories",
    "discover_member_ids",
    "install_skill_suite",
    "inventory_skill_tree",
    "load_consumer_suite_authority",
    "resolve_source_skill_root",
    "resolve_target_skill_root",
    "semantic_hash_bytes",
    "uninstall_skill_suite",
    "validate_installed_consumer_suite",
]
