"""Read-only checks for FlowGuard adoption evidence."""

from __future__ import annotations

import importlib.util
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


ADOPTION_AUDIT_SEVERITIES = ("warning", "suggestion")
ADOPTION_AUDIT_STATUSES = ("pass", "pass_with_gaps")

FALLBACK_TERMS = (
    "fallback explorer",
    "fallback_explorer",
    "temporary mini-framework",
    "project-local fallback",
    "mini-framework fallback",
)
FLOWGUARD_UNAVAILABLE_RE = re.compile(
    r"flowguard_package_available\s*[:=]\s*false",
    re.IGNORECASE,
)
LOCAL_EXPLORER_RE = re.compile(r"\bclass\s+Explorer\b")
LOCAL_WORKFLOW_RE = re.compile(r"\bclass\s+Workflow\b")


@dataclass(frozen=True)
class AdoptionAuditFinding:
    """One read-only adoption evidence finding."""

    severity: str
    category: str
    message: str
    recommendation: str = ""
    file_path: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        severity = str(self.severity).lower()
        if severity not in ADOPTION_AUDIT_SEVERITIES:
            raise ValueError(f"severity must be one of {ADOPTION_AUDIT_SEVERITIES!r}")
        object.__setattr__(self, "severity", severity)
        object.__setattr__(self, "category", str(self.category))
        object.__setattr__(self, "message", str(self.message))
        object.__setattr__(self, "recommendation", str(self.recommendation or ""))
        object.__setattr__(self, "file_path", str(self.file_path or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "severity": self.severity,
            "category": self.category,
            "message": self.message,
            "recommendation": self.recommendation,
            "file_path": self.file_path,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class AdoptionAuditReport:
    """Read-only report for adoption evidence freshness."""

    root: str
    flowguard_available: bool
    findings: tuple[AdoptionAuditFinding, ...] = ()
    scanned_files: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return True

    @property
    def status(self) -> str:
        return "pass_with_gaps" if self.findings else "pass"

    def format_text(self) -> str:
        lines = [
            "=== flowguard adoption audit ===",
            f"status: {self.status}",
            f"flowguard_available: {str(self.flowguard_available).lower()}",
            f"scanned_files: {len(self.scanned_files)}",
        ]
        for finding in self.findings:
            lines.extend(
                [
                    "",
                    f"{finding.severity.upper()}: {finding.category}",
                    f"message: {finding.message}",
                ]
            )
            if finding.file_path:
                lines.append(f"file: {finding.file_path}")
            if finding.recommendation:
                lines.append(f"recommendation: {finding.recommendation}")
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_adoption_audit_report",
            "root": self.root,
            "ok": self.ok,
            "status": self.status,
            "flowguard_available": self.flowguard_available,
            "scanned_files": list(self.scanned_files),
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def audit_flowguard_adoption(
    root: str | Path = ".",
    *,
    flowguard_available: bool | None = None,
) -> AdoptionAuditReport:
    """Scan `.flowguard` adoption files for stale fallback evidence.

    This is a read-only helper. Findings are warnings or suggestions; they do
    not replace executable model checks or make adoption fail by themselves.
    """

    root_path = Path(root).resolve()
    if flowguard_available is None:
        flowguard_available = _detect_flowguard_available()

    findings: list[AdoptionAuditFinding] = []
    model_files = _flowguard_python_files(root_path)
    current_fallback_count = 0
    for path in model_files:
        text = _read_text(path)
        if not text:
            continue
        markers = _current_fallback_markers(text)
        if not markers:
            continue
        current_fallback_count += 1
        if flowguard_available:
            findings.append(
                AdoptionAuditFinding(
                    "warning",
                    "stale_fallback_model",
                    "real flowguard is importable, but this current .flowguard model still appears to use fallback evidence",
                    "Migrate the current model to the real FlowGuard Workflow/Explorer API, or mark the fallback as historical.",
                    str(path),
                    {"markers": markers},
                )
            )
        else:
            findings.append(
                AdoptionAuditFinding(
                    "warning",
                    "current_fallback_model",
                    "this current .flowguard model appears to use fallback evidence because real flowguard is not importable",
                    "Connect the real FlowGuard package or record the fallback as a skipped/blocked adoption gap.",
                    str(path),
                    {"markers": markers},
                )
            )

    if current_fallback_count == 0 and _historical_fallback_mentioned(root_path):
        findings.append(
            AdoptionAuditFinding(
                "suggestion",
                "historical_fallback_evidence",
                "historical adoption notes mention fallback evidence, but no current .flowguard Python model appears stale",
                "Keep historical fallback visible, but do not report it as current FlowGuard execution.",
            )
        )

    return AdoptionAuditReport(
        root=str(root_path),
        flowguard_available=bool(flowguard_available),
        findings=tuple(findings),
        scanned_files=tuple(str(path) for path in model_files),
    )


def _detect_flowguard_available() -> bool:
    return importlib.util.find_spec("flowguard") is not None


def _flowguard_python_files(root: Path) -> tuple[Path, ...]:
    flowguard_dir = root / ".flowguard"
    if not flowguard_dir.exists():
        return ()
    try:
        return tuple(
            sorted(
                (
                    path
                    for path in flowguard_dir.rglob("*.py")
                    if "__pycache__" not in path.parts
                ),
                key=lambda path: str(path).lower(),
            )
        )
    except OSError:
        return ()


def _read_text(path: Path, *, limit: int = 200_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _current_fallback_markers(text: str) -> tuple[str, ...]:
    lowered = text.lower()
    markers: list[str] = []
    if FLOWGUARD_UNAVAILABLE_RE.search(text):
        markers.append("flowguard_package_available=false")
    markers.extend(term for term in FALLBACK_TERMS if term in lowered)
    if LOCAL_EXPLORER_RE.search(text) and "from flowguard" not in lowered:
        markers.append("local Explorer class")
    if LOCAL_WORKFLOW_RE.search(text) and "from flowguard" not in lowered:
        markers.append("local Workflow class")
    return tuple(dict.fromkeys(markers))


def _historical_fallback_mentioned(root: Path) -> bool:
    for path in (
        root / ".flowguard" / "adoption_log.jsonl",
        root / "docs" / "flowguard_adoption_log.md",
    ):
        text = _read_text(path)
        if not text:
            continue
        lowered = text.lower()
        if any(term in lowered for term in FALLBACK_TERMS) or "fallback" in lowered:
            return True
    return False


__all__ = [
    "ADOPTION_AUDIT_SEVERITIES",
    "ADOPTION_AUDIT_STATUSES",
    "AdoptionAuditFinding",
    "AdoptionAuditReport",
    "audit_flowguard_adoption",
]
