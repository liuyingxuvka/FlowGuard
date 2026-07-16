"""Canonical FlowGuard agent-skill suite inventory and reconciliation.

Canonical membership comes from the suite map and is reconciled against every
``SKILL.md`` directory.  A valid installer ownership manifest may identify
unrelated skills that merely share the root; undeclared FlowGuard-reserved
names, missing canonical members, and member control files remain strict.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .distribution_sync import OWNERSHIP_MANIFEST_NAME, OWNERSHIP_SCHEMA


FLOWGUARD_SUITE_MAP = ".skillguard/flowguard-suite/suite-map.json"
FLOWGUARD_SKILL_ROOT = ".agents/skills"
FLOWGUARD_SUITE_SCHEMA = "skillguard.suite_map.v1"
FLOWGUARD_SUITE_NAME = "flowguard-agent-skill-suite"
FLOWGUARD_KERNEL_ROLE = "kernel_router"
FLOWGUARD_SATELLITE_ROLE = "public_satellite"
FLOWGUARD_EXPECTED_MEMBER_COUNT = 17
FLOWGUARD_EXPECTED_SATELLITE_COUNT = 16
MODEL_PURPOSE_SKILL_MARKERS = (
    "Model-purpose gate",
    "task-specific failure(s)",
    "native good/bad-per-failure/oracle/current evidence",
    "Reusable types are not fixed-purpose",
    "no mode/fallback",
    "SkillGuard only supervises FlowGuard-declared checks",
)
MODEL_PURPOSE_PROMPT_MARKERS = (
    "one-or-many protected failures",
    "reusable model types are not permanently single-purpose",
    "SkillGuard only supervises declared checks",
)
FLOWGUARD_REQUIRED_MEMBER_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    ".skillguard/contract-source.json",
    ".skillguard/compiled-contract.json",
    ".skillguard/check-manifest.json",
)
FLOWGUARD_CONTROL_ROOT = ".skillguard"

SUITE_STATUS_PASS = "pass"
SUITE_STATUS_BLOCKED = "blocked"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def _relative(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


@dataclass(frozen=True)
class SkillSuiteFinding:
    """One deterministic suite inventory failure."""

    code: str
    message: str
    member_id: str = ""
    file_path: str = ""
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "member_id": self.member_id,
            "file_path": self.file_path,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SkillSuiteMemberReport:
    """Declared member plus its current filesystem state."""

    skill_id: str
    role: str
    owner: str
    declared_path: str
    discovered: bool
    control_root_present: bool
    required_files: Mapping[str, bool]
    source_hash: str = ""

    @property
    def ok(self) -> bool:
        return self.discovered and self.control_root_present and all(self.required_files.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "role": self.role,
            "owner": self.owner,
            "declared_path": self.declared_path,
            "discovered": self.discovered,
            "control_root_present": self.control_root_present,
            "required_files": dict(self.required_files),
            "source_hash": self.source_hash,
            "ok": self.ok,
        }


@dataclass(frozen=True)
class SkillSuiteReport:
    """Canonical inventory validation report."""

    root: str
    schema_version: str
    suite_name: str
    inventory_hash: str
    semantic_hash: str
    declared_member_ids: tuple[str, ...]
    discovered_member_ids: tuple[str, ...]
    members: tuple[SkillSuiteMemberReport, ...]
    findings: tuple[SkillSuiteFinding, ...]
    co_located_skill_ids: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.findings

    @property
    def status(self) -> str:
        return SUITE_STATUS_PASS if self.ok else SUITE_STATUS_BLOCKED

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_skill_suite_report",
            "ok": self.ok,
            "status": self.status,
            "root": self.root,
            "schema_version": self.schema_version,
            "suite_name": self.suite_name,
            "inventory_hash": self.inventory_hash,
            "semantic_hash": self.semantic_hash,
            "declared_member_count": len(self.declared_member_ids),
            "discovered_member_count": len(self.discovered_member_ids),
            "co_located_skill_count": len(self.co_located_skill_ids),
            "declared_member_ids": list(self.declared_member_ids),
            "discovered_member_ids": list(self.discovered_member_ids),
            "co_located_skill_ids": list(self.co_located_skill_ids),
            "members": [member.to_dict() for member in self.members],
            "findings": [finding.to_dict() for finding in self.findings],
            "claim_boundary": (
                "This report validates current suite membership and required-file presence only; "
                "co-located skill ids are reported but are not validated as part of FlowGuard; "
                "it does not replace deep contract checks, native command execution, receipt "
                "freshness, distribution parity, or release evidence."
            ),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent, sort_keys=True)

    def format_text(self) -> str:
        lines = [
            "=== flowguard skill suite inventory ===",
            f"status: {self.status}",
            f"members: {len(self.declared_member_ids)} declared / {len(self.discovered_member_ids)} discovered",
            f"inventory_hash: {self.inventory_hash}",
            f"semantic_hash: {self.semantic_hash}",
        ]
        if self.co_located_skill_ids:
            lines.append(f"co-located skills (not validated): {', '.join(self.co_located_skill_ids)}")
        for finding in self.findings:
            subject = f" member={finding.member_id}" if finding.member_id else ""
            lines.append(f"- {finding.code}:{subject} {finding.message}")
        return "\n".join(lines)


def load_suite_map(path: str | Path) -> dict[str, Any]:
    """Load one suite map without silently repairing malformed content."""

    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("suite map root must be an object")
    return value


def discover_skill_ids(skill_root: str | Path) -> tuple[str, ...]:
    """Discover immediate skill directories from ``SKILL.md`` presence."""

    root = Path(skill_root)
    if not root.is_dir():
        return ()
    return tuple(sorted(path.name for path in root.iterdir() if path.is_dir() and (path / "SKILL.md").is_file()))


def _distribution_owned_member_ids(skill_root: Path) -> tuple[str, ...]:
    """Return the exact member boundary from one valid installer manifest."""

    path = skill_root / OWNERSHIP_MANIFEST_NAME
    if not path.is_file():
        return ()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(payload, Mapping):
        return ()
    if payload.get("artifact_type") != "flowguard_skill_distribution_ownership":
        return ()
    if payload.get("schema_version") != OWNERSHIP_SCHEMA:
        return ()

    raw_member_ids = payload.get("member_ids")
    raw_files = payload.get("files")
    if not isinstance(raw_member_ids, list) or not isinstance(raw_files, list):
        return ()
    if not all(isinstance(item, str) and item for item in raw_member_ids):
        return ()
    member_ids = tuple(raw_member_ids)
    if len(member_ids) != len(set(member_ids)):
        return ()

    owned_paths = {
        str(row.get("relative_path", "")).replace("\\", "/")
        for row in raw_files
        if isinstance(row, Mapping)
    }
    if any(f"{member_id}/SKILL.md" not in owned_paths for member_id in member_ids):
        return ()
    return member_ids


def _uses_flowguard_reserved_skill_id(skill_id: str) -> bool:
    normalized = skill_id.casefold()
    return (
        normalized == "flowguard"
        or normalized.startswith("flowguard-")
        or normalized.startswith("model-first-function-flow")
    )


def _member_source_hash(skill_dir: Path) -> str:
    skill_file = skill_dir / "SKILL.md"
    return hashlib.sha256(skill_file.read_bytes()).hexdigest().upper() if skill_file.is_file() else ""


def _member_required_files(skill_dir: Path) -> tuple[str, ...]:
    """Return the one current required member surface."""

    del skill_dir
    return FLOWGUARD_REQUIRED_MEMBER_FILES


def _semantic_inventory(map_data: Mapping[str, Any]) -> dict[str, Any]:
    members = []
    for raw in map_data.get("included_skills", ()):
        if not isinstance(raw, Mapping):
            continue
        members.append(
            {
                "name": str(raw.get("name", "")),
                "path": str(raw.get("path", "")),
                "role": str(raw.get("role", "")),
                "owner": str(raw.get("owner", "")),
                "required": bool(raw.get("required", False)),
                "control_root": str(raw.get("evidence_location", "")),
                "required_files": list(FLOWGUARD_REQUIRED_MEMBER_FILES),
            }
        )
    return {
        "schema_version": str(map_data.get("schema_version", "")),
        "suite_name": str(map_data.get("suite_name", "")),
        "target_path": str(map_data.get("target_path", "")),
        "members": members,
    }


def detect_private_suite_inventories(
    root: str | Path,
    member_ids: Sequence[str],
    *,
    allowed_paths: Iterable[str] = (),
) -> tuple[SkillSuiteFinding, ...]:
    """Find a second substantial literal member list in executable sources."""

    root_path = Path(root).resolve()
    allowed = {Path(value).as_posix() for value in allowed_paths}
    findings: list[SkillSuiteFinding] = []
    quoted = {
        member_id: re.compile(rf"(?P<quote>['\"]){re.escape(member_id)}(?P=quote)")
        for member_id in member_ids
    }
    for parent in (root_path / "flowguard", root_path / "scripts"):
        if not parent.is_dir():
            continue
        for path in sorted(parent.rglob("*.py")):
            rel = _relative(path, root_path)
            if rel in allowed or "__pycache__" in path.parts:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            matches = sorted(member_id for member_id, pattern in quoted.items() if pattern.search(text))
            if len(matches) < 4:
                continue
            findings.append(
                SkillSuiteFinding(
                    "private_suite_inventory_detected",
                    "executable source contains a second substantial literal FlowGuard skill list",
                    file_path=rel,
                    metadata={"member_ids": matches},
                )
            )
    return tuple(findings)


def validate_skill_suite(
    root: str | Path = ".",
    *,
    suite_map_path: str | Path | None = None,
    skill_root: str | Path | None = None,
    check_private_inventories: bool = True,
) -> SkillSuiteReport:
    """Reconcile canonical members and report any safely scoped co-location."""

    root_path = Path(root).resolve()
    map_path = Path(suite_map_path) if suite_map_path is not None else root_path / FLOWGUARD_SUITE_MAP
    if not map_path.is_absolute():
        map_path = root_path / map_path
    external_skill_root = skill_root is not None
    skills_path = Path(skill_root) if external_skill_root else root_path / FLOWGUARD_SKILL_ROOT
    if not skills_path.is_absolute():
        skills_path = root_path / skills_path

    findings: list[SkillSuiteFinding] = []
    if not map_path.is_file():
        findings.append(
            SkillSuiteFinding(
                "suite_map_missing",
                "canonical FlowGuard suite map is missing",
                file_path=_relative(map_path, root_path),
            )
        )
        return SkillSuiteReport(str(root_path), "", "", "", "", (), discover_skill_ids(skills_path), (), tuple(findings))

    try:
        map_data = load_suite_map(map_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append(
            SkillSuiteFinding(
                "suite_map_invalid",
                str(exc),
                file_path=_relative(map_path, root_path),
            )
        )
        return SkillSuiteReport(str(root_path), "", "", "", "", (), discover_skill_ids(skills_path), (), tuple(findings))

    schema_version = str(map_data.get("schema_version", ""))
    suite_name = str(map_data.get("suite_name", ""))
    if schema_version != FLOWGUARD_SUITE_SCHEMA:
        findings.append(SkillSuiteFinding("suite_schema_invalid", "suite map schema version is not supported", metadata={"actual": schema_version, "expected": FLOWGUARD_SUITE_SCHEMA}))
    if suite_name != FLOWGUARD_SUITE_NAME:
        findings.append(SkillSuiteFinding("suite_name_invalid", "suite map name is not the FlowGuard canonical suite", metadata={"actual": suite_name, "expected": FLOWGUARD_SUITE_NAME}))

    raw_members = map_data.get("included_skills", ())
    if not isinstance(raw_members, list):
        raw_members = []
        findings.append(SkillSuiteFinding("suite_members_invalid", "included_skills must be an array"))

    declared_ids: list[str] = []
    member_rows: list[Mapping[str, Any]] = []
    for index, raw in enumerate(raw_members):
        if not isinstance(raw, Mapping):
            findings.append(SkillSuiteFinding("suite_member_invalid", "suite member must be an object", metadata={"index": index}))
            continue
        skill_id = str(raw.get("name", ""))
        if not skill_id:
            findings.append(SkillSuiteFinding("suite_member_missing_id", "suite member is missing name", metadata={"index": index}))
            continue
        if skill_id in declared_ids:
            findings.append(SkillSuiteFinding("duplicate_member", "suite member id is declared more than once", member_id=skill_id))
        declared_ids.append(skill_id)
        member_rows.append(raw)

    if len(declared_ids) != FLOWGUARD_EXPECTED_MEMBER_COUNT:
        findings.append(SkillSuiteFinding("invalid_suite_cardinality", "current FlowGuard suite must declare seventeen members", metadata={"actual": len(declared_ids), "expected": FLOWGUARD_EXPECTED_MEMBER_COUNT}))
    kernel_ids = [str(raw.get("name", "")) for raw in member_rows if raw.get("role") == FLOWGUARD_KERNEL_ROLE]
    satellite_ids = [str(raw.get("name", "")) for raw in member_rows if raw.get("role") == FLOWGUARD_SATELLITE_ROLE]
    if len(kernel_ids) != 1:
        findings.append(SkillSuiteFinding("invalid_kernel_cardinality", "suite must declare exactly one kernel", metadata={"kernel_ids": kernel_ids}))
    if len(satellite_ids) != FLOWGUARD_EXPECTED_SATELLITE_COUNT:
        findings.append(SkillSuiteFinding("invalid_satellite_cardinality", "suite must declare sixteen satellites", metadata={"satellite_ids": satellite_ids}))

    all_discovered_ids = discover_skill_ids(skills_path)
    declared_set = set(declared_ids)
    discovered_set = set(all_discovered_ids)
    for skill_id in sorted(declared_set - discovered_set):
        findings.append(SkillSuiteFinding("missing_declared_member", "declared suite member has no SKILL.md directory", member_id=skill_id))
    extra_ids = discovered_set - declared_set
    co_located_ids: set[str] = set()
    owned_member_ids = _distribution_owned_member_ids(skills_path)
    ownership_matches_declaration = (
        len(declared_ids) == len(declared_set)
        and len(owned_member_ids) == len(declared_ids)
        and set(owned_member_ids) == declared_set
    )
    for skill_id in sorted(extra_ids):
        if ownership_matches_declaration and not _uses_flowguard_reserved_skill_id(skill_id):
            co_located_ids.add(skill_id)
            continue
        findings.append(SkillSuiteFinding("extra_discovered_member", "SKILL.md directory is absent from the canonical suite map", member_id=skill_id))
    suite_discovered_ids = tuple(sorted(discovered_set - co_located_ids))

    member_reports: list[SkillSuiteMemberReport] = []
    for raw in member_rows:
        skill_id = str(raw.get("name", ""))
        declared_path = str(raw.get("path", f"{FLOWGUARD_SKILL_ROOT}/{skill_id}"))
        skill_dir = skills_path / skill_id if external_skill_root else root_path / declared_path
        required_files = {relative: (skill_dir / relative).is_file() for relative in _member_required_files(skill_dir)}
        control_root_present = (skill_dir / FLOWGUARD_CONTROL_ROOT).is_dir()
        member_reports.append(
            SkillSuiteMemberReport(
                skill_id=skill_id,
                role=str(raw.get("role", "")),
                owner=str(raw.get("owner", "")),
                declared_path=declared_path,
                discovered=skill_id in discovered_set and (skill_dir / "SKILL.md").is_file(),
                control_root_present=control_root_present,
                required_files=required_files,
                source_hash=_member_source_hash(skill_dir),
            )
        )
        if not control_root_present:
            findings.append(SkillSuiteFinding("missing_control_root", "declared member is missing its required .skillguard control root", member_id=skill_id, file_path=f"{declared_path}/{FLOWGUARD_CONTROL_ROOT}"))
        for relative, present in required_files.items():
            if not present:
                findings.append(SkillSuiteFinding("missing_required_file", "declared suite member is missing a required entry or control file", member_id=skill_id, file_path=f"{declared_path}/{relative}", metadata={"required_file": relative}))
        skill_file = skill_dir / "SKILL.md"
        prompt_file = skill_dir / "agents/openai.yaml"
        if skill_file.is_file():
            skill_text = skill_file.read_text(encoding="utf-8")
            missing = tuple(marker for marker in MODEL_PURPOSE_SKILL_MARKERS if marker not in skill_text)
            if missing:
                findings.append(SkillSuiteFinding(
                    "model_purpose_gate_missing",
                    "FlowGuard skill is missing the current mandatory instance-purpose gate",
                    member_id=skill_id,
                    file_path=f"{declared_path}/SKILL.md",
                    metadata={"missing_markers": missing},
                ))
            lowered = skill_text.casefold()
            forbidden = tuple(value for value in ("optional purpose mode", "skip purpose declaration", "skillguard owns purpose semantics") if value in lowered)
            if forbidden:
                findings.append(SkillSuiteFinding(
                    "model_purpose_gate_weakened",
                    "FlowGuard skill exposes a weaker or wrongly owned purpose route",
                    member_id=skill_id,
                    file_path=f"{declared_path}/SKILL.md",
                    metadata={"forbidden_markers": forbidden},
                ))
        if prompt_file.is_file():
            prompt_text = prompt_file.read_text(encoding="utf-8")
            missing = tuple(marker for marker in MODEL_PURPOSE_PROMPT_MARKERS if marker not in prompt_text)
            if missing:
                findings.append(SkillSuiteFinding(
                    "model_purpose_prompt_missing",
                    "FlowGuard installed prompt projection is missing current instance-purpose guidance",
                    member_id=skill_id,
                    file_path=f"{declared_path}/agents/openai.yaml",
                    metadata={"missing_markers": missing},
                ))

    inventory_hash = _sha256_text(_canonical_json(map_data))
    semantic_hash = _sha256_text(_canonical_json(_semantic_inventory(map_data)))
    if check_private_inventories:
        findings.extend(
            detect_private_suite_inventories(
                root_path,
                declared_ids,
                allowed_paths=("flowguard/skill_suite.py", "flowguard/self_maintenance.py"),
            )
        )

    return SkillSuiteReport(
        root=str(root_path),
        schema_version=schema_version,
        suite_name=suite_name,
        inventory_hash=inventory_hash,
        semantic_hash=semantic_hash,
        declared_member_ids=tuple(declared_ids),
        discovered_member_ids=suite_discovered_ids,
        members=tuple(member_reports),
        findings=tuple(findings),
        co_located_skill_ids=tuple(sorted(co_located_ids)),
    )


__all__ = [
    "FLOWGUARD_CONTROL_ROOT",
    "FLOWGUARD_EXPECTED_MEMBER_COUNT",
    "FLOWGUARD_EXPECTED_SATELLITE_COUNT",
    "FLOWGUARD_KERNEL_ROLE",
    "MODEL_PURPOSE_PROMPT_MARKERS",
    "MODEL_PURPOSE_SKILL_MARKERS",
    "FLOWGUARD_REQUIRED_MEMBER_FILES",
    "FLOWGUARD_SATELLITE_ROLE",
    "FLOWGUARD_SKILL_ROOT",
    "FLOWGUARD_SUITE_MAP",
    "FLOWGUARD_SUITE_NAME",
    "FLOWGUARD_SUITE_SCHEMA",
    "SkillSuiteFinding",
    "SkillSuiteMemberReport",
    "SkillSuiteReport",
    "detect_private_suite_inventories",
    "discover_skill_ids",
    "load_suite_map",
    "validate_skill_suite",
]
