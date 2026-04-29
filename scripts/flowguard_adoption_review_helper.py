"""Discover and summarize local FlowGuard adoption evidence.

This is an internal maintenance helper for the three-day adoption review. It is
read-only: it scans project folders, classifies evidence quality, and prints a
small JSON or Markdown report.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard.adoption_audit import audit_flowguard_adoption


SKIP_DIRS = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "site-packages",
}


@dataclass(frozen=True)
class AdoptionEntrySummary:
    task_id: str = ""
    project: str = ""
    task_summary: str = ""
    status: str = ""
    ok: bool | None = None
    command_count: int = 0
    has_commands: bool = False
    has_command_failure: bool = False
    strongest_finding: str = ""
    skipped_or_blocked_reason: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AdoptionEntrySummary":
        commands = tuple(data.get("commands") or ())
        command_failures = tuple(
            command
            for command in commands
            if isinstance(command, dict) and command.get("ok") is False
        )
        skipped = tuple(str(item) for item in data.get("skipped_steps") or ())
        findings = tuple(str(item) for item in data.get("findings") or ())
        friction = tuple(str(item) for item in data.get("friction_points") or ())
        blocked_reason = ""
        if data.get("status") in {"blocked", "failed", "skipped_with_reason"}:
            blocked_reason = "; ".join(skipped or friction or (str(data.get("trigger_reason") or ""),))
        elif skipped:
            blocked_reason = "; ".join(skipped)
        ok_value = data.get("ok")
        return cls(
            task_id=str(data.get("task_id") or ""),
            project=str(data.get("project") or ""),
            task_summary=str(data.get("task_summary") or ""),
            status=str(data.get("status") or "legacy_unknown"),
            ok=ok_value if isinstance(ok_value, bool) else None,
            command_count=len(commands) or int(data.get("command_count") or 0),
            has_commands=bool(commands) or bool(data.get("has_commands")),
            has_command_failure=bool(command_failures) or data.get("ok") is False,
            strongest_finding=findings[0] if findings else "",
            skipped_or_blocked_reason=blocked_reason,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "project": self.project,
            "task_summary": self.task_summary,
            "status": self.status,
            "ok": self.ok,
            "command_count": self.command_count,
            "has_commands": self.has_commands,
            "has_command_failure": self.has_command_failure,
            "strongest_finding": self.strongest_finding,
            "skipped_or_blocked_reason": self.skipped_or_blocked_reason,
        }


@dataclass(frozen=True)
class ProjectEvidenceSummary:
    root: Path
    project: str
    classification: str
    has_jsonl: bool
    has_markdown: bool
    model_file_count: int
    entry_count: int
    latest_entry: AdoptionEntrySummary | None = None
    flags: tuple[str, ...] = ()
    evidence_files: tuple[str, ...] = field(default_factory=tuple)
    adoption_audit_status: str = ""
    adoption_audit_findings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": str(self.root),
            "project": self.project,
            "classification": self.classification,
            "has_jsonl": self.has_jsonl,
            "has_markdown": self.has_markdown,
            "model_file_count": self.model_file_count,
            "entry_count": self.entry_count,
            "latest_entry": self.latest_entry.to_dict() if self.latest_entry else None,
            "flags": list(self.flags),
            "evidence_files": list(self.evidence_files),
            "adoption_audit_status": self.adoption_audit_status,
            "adoption_audit_findings": list(self.adoption_audit_findings),
        }


def discover_project_roots(roots: Iterable[Path], *, max_depth: int = 5) -> tuple[Path, ...]:
    candidates: set[Path] = set()
    for root in roots:
        root = root.resolve()
        if not root.exists():
            continue
        for current, dirs, files in os.walk(root):
            current_path = Path(current)
            depth = len(current_path.relative_to(root).parts)
            dirs[:] = [item for item in dirs if item not in SKIP_DIRS and depth < max_depth]
            file_set = set(files)
            if "adoption_log.jsonl" in file_set and current_path.name == ".flowguard":
                candidates.add(current_path.parent)
            if "flowguard_adoption_log.md" in file_set and current_path.name == "docs":
                candidates.add(current_path.parent)
            if current_path.name == ".flowguard" and _contains_python_model(current_path):
                candidates.add(current_path.parent)
    return tuple(sorted(candidates, key=lambda path: str(path).lower()))


def analyze_project(root: Path) -> ProjectEvidenceSummary:
    root = root.resolve()
    jsonl_path = root / ".flowguard" / "adoption_log.jsonl"
    markdown_path = root / "docs" / "flowguard_adoption_log.md"
    model_files = _model_files(root)
    entries = _read_jsonl_entries(jsonl_path)
    latest = AdoptionEntrySummary.from_dict(entries[-1]) if entries else None
    text_sample = _combined_text_sample(jsonl_path, markdown_path)
    adoption_audit = audit_flowguard_adoption(root)
    adoption_audit_flags = tuple(finding.category for finding in adoption_audit.findings)
    flags = tuple(dict.fromkeys(_flags(jsonl_path, markdown_path, latest, text_sample) + adoption_audit_flags))
    classification = _classify(
        has_jsonl=jsonl_path.exists(),
        has_markdown=markdown_path.exists(),
        model_count=len(model_files),
        latest=latest,
        flags=flags,
    )
    project = latest.project if latest and latest.project else root.name
    evidence_files = []
    if jsonl_path.exists():
        evidence_files.append(str(jsonl_path))
    if markdown_path.exists():
        evidence_files.append(str(markdown_path))
    evidence_files.extend(str(path) for path in model_files[:10])
    return ProjectEvidenceSummary(
        root=root,
        project=project,
        classification=classification,
        has_jsonl=jsonl_path.exists(),
        has_markdown=markdown_path.exists(),
        model_file_count=len(model_files),
        entry_count=len(entries),
        latest_entry=latest,
        flags=flags,
        evidence_files=tuple(evidence_files),
        adoption_audit_status=adoption_audit.status,
        adoption_audit_findings=tuple(
            f"{finding.severity}: {finding.category}: {finding.message}"
            for finding in adoption_audit.findings
        ),
    )


def build_report(roots: Iterable[Path], *, max_depth: int = 5) -> dict[str, Any]:
    project_roots = discover_project_roots(roots, max_depth=max_depth)
    projects = tuple(analyze_project(root) for root in project_roots)
    counts: dict[str, int] = {}
    for project in projects:
        counts[project.classification] = counts.get(project.classification, 0) + 1
    return {
        "artifact_type": "flowguard_adoption_review_helper_report",
        "project_count": len(projects),
        "classification_counts": counts,
        "projects": [project.to_dict() for project in projects],
    }


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# FlowGuard Adoption Evidence Scan",
        "",
        f"- Projects: {report['project_count']}",
        f"- Classification counts: {json.dumps(report['classification_counts'], sort_keys=True)}",
    ]
    for project in report["projects"]:
        latest = project.get("latest_entry") or {}
        lines.extend(
            [
                "",
                f"## {project['project']}",
                "",
                f"- Root: `{project['root']}`",
                f"- Classification: `{project['classification']}`",
                f"- Evidence: JSONL={project['has_jsonl']}, Markdown={project['has_markdown']}, models={project['model_file_count']}",
                f"- Entries: {project['entry_count']}",
                f"- Flags: {', '.join(project['flags']) if project['flags'] else 'none'}",
                f"- Adoption audit: {project.get('adoption_audit_status') or 'not_run'}",
                f"- Task: {latest.get('task_summary') or 'none recorded'}",
                f"- Strongest finding: {latest.get('strongest_finding') or 'none recorded'}",
                f"- Skipped/blocked reason: {latest.get('skipped_or_blocked_reason') or 'none recorded'}",
            ]
        )
    return "\n".join(lines)


def _contains_python_model(path: Path) -> bool:
    try:
        return any("__pycache__" not in item.parts for item in path.rglob("*.py"))
    except OSError:
        return False


def _model_files(root: Path) -> tuple[Path, ...]:
    fg = root / ".flowguard"
    if not fg.exists():
        return ()
    try:
        return tuple(
            sorted(
                (
                    path
                    for path in fg.rglob("*.py")
                    if "__pycache__" not in path.parts
                ),
                key=lambda path: str(path).lower(),
            )
        )
    except OSError:
        return ()


def _read_jsonl_entries(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.exists():
        return ()
    entries = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                entries.append(value)
    except OSError:
        return ()
    return tuple(entries)


def _combined_text_sample(*paths: Path) -> str:
    chunks = []
    for path in paths:
        if not path.exists():
            continue
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace")[:20000])
        except OSError:
            continue
    return "\n".join(chunks).lower()


def _flags(
    jsonl_path: Path,
    markdown_path: Path,
    latest: AdoptionEntrySummary | None,
    text_sample: str,
) -> tuple[str, ...]:
    flags = []
    if not jsonl_path.exists():
        flags.append("missing_jsonl")
    if not markdown_path.exists():
        flags.append("missing_markdown")
    if latest is None:
        flags.append("no_jsonl_entries")
    elif latest.status == "legacy_unknown":
        flags.append("legacy_status")
    if latest and latest.has_command_failure:
        flags.append("command_failure_evidence")
    if latest and latest.skipped_or_blocked_reason:
        flags.append("skipped_or_blocked_step")
    if latest and _mentions_fallback(
        " ".join(
            (
                latest.task_summary,
                latest.strongest_finding,
                latest.skipped_or_blocked_reason,
            )
        )
    ):
        flags.append("current_historical_fallback")
    if _mentions_fallback(text_sample):
        flags.append("historical_fallback")
    return tuple(dict.fromkeys(flags))


def _classify(
    *,
    has_jsonl: bool,
    has_markdown: bool,
    model_count: int,
    latest: AdoptionEntrySummary | None,
    flags: tuple[str, ...],
) -> str:
    if "current_historical_fallback" in flags:
        return "historical_fallback"
    if latest and latest.status in {"blocked", "failed"}:
        return "blocked_or_failed"
    if latest and latest.status == "in_progress":
        return "in_progress"
    if latest and latest.status == "completed":
        if latest.has_commands and not latest.has_command_failure and latest.skipped_or_blocked_reason:
            return "complete_with_skips"
        if latest.has_commands and not latest.has_command_failure:
            return "complete"
        return "useful_but_incomplete"
    if latest and (latest.has_commands or latest.strongest_finding):
        return "useful_but_incomplete"
    if has_jsonl or has_markdown or model_count:
        return "in_progress"
    return "no_evidence"


def _mentions_fallback(text: str) -> bool:
    value = text.lower()
    return any(
        term in value
        for term in (
            "fallback",
            "temporary mini-framework",
            "pythonpath",
            "pypath",
            "project-local fallback",
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", action="append", default=None, help="Root to scan. Can be repeated.")
    parser.add_argument("--max-depth", type=int, default=5, help="Maximum directory depth below each root.")
    parser.add_argument("--markdown", action="store_true", help="Print Markdown instead of JSON.")
    parser.add_argument("--output", help="Optional output file.")
    args = parser.parse_args(argv)

    roots = tuple(Path(item) for item in (args.root or [Path.cwd()]))
    report = build_report(roots, max_depth=args.max_depth)
    text = format_markdown(report) if args.markdown else json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
