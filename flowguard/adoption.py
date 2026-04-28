"""Adoption logging helpers for real project flowguard pilots."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

from .core import FrozenMetadata, freeze_metadata
from .export import to_jsonable


ADOPTION_STATUSES = (
    "in_progress",
    "completed",
    "blocked",
    "skipped_with_reason",
    "failed",
)

_STATUS_ALIASES = {
    "": "auto",
    "auto": "auto",
    "complete": "completed",
    "ok": "completed",
    "pass": "completed",
    "passed": "completed",
    "partial": "blocked",
    "blocked_or_partial": "blocked",
    "skip": "skipped_with_reason",
    "skipped": "skipped_with_reason",
}


def utc_now_text() -> str:
    """Return a stable UTC timestamp for adoption logs."""

    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _as_tuple(values: Iterable[Any] | None) -> tuple[Any, ...]:
    if values is None:
        return ()
    return tuple(values)


def _normalize_status(status: str | None) -> str:
    value = str(status or "auto").strip().lower()
    value = _STATUS_ALIASES.get(value, value)
    if value == "auto":
        return value
    if value not in ADOPTION_STATUSES:
        raise ValueError(
            "adoption status must be one of "
            f"{', '.join(ADOPTION_STATUSES)}; got {status!r}"
        )
    return value


@dataclass(frozen=True)
class AdoptionCommandResult:
    """One command or check run during a flowguard adoption session."""

    command: str
    ok: bool
    duration_seconds: float = 0.0
    summary: str = ""
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "command", str(self.command))
        object.__setattr__(self, "ok", bool(self.ok))
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
        object.__setattr__(self, "summary", str(self.summary or ""))
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "ok": self.ok,
            "duration_seconds": round(self.duration_seconds, 6),
            "summary": self.summary,
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class AdoptionLogEntry:
    """Structured record of using flowguard on a real project task."""

    task_id: str
    project: str
    task_summary: str
    trigger_reason: str
    started_at: str
    ended_at: str
    duration_seconds: float
    status: str = "auto"
    skill_decision: str = "used_flowguard"
    model_files: tuple[str, ...] = ()
    commands: tuple[AdoptionCommandResult, ...] = ()
    findings: tuple[str, ...] = ()
    counterexamples: tuple[str, ...] = ()
    friction_points: tuple[str, ...] = ()
    skipped_steps: tuple[str, ...] = ()
    next_actions: tuple[str, ...] = ()
    metadata: FrozenMetadata = field(default_factory=tuple, compare=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", str(self.task_id))
        object.__setattr__(self, "project", str(self.project))
        object.__setattr__(self, "task_summary", str(self.task_summary))
        object.__setattr__(self, "trigger_reason", str(self.trigger_reason))
        object.__setattr__(self, "started_at", str(self.started_at))
        object.__setattr__(self, "ended_at", str(self.ended_at))
        object.__setattr__(self, "duration_seconds", float(self.duration_seconds))
        object.__setattr__(
            self,
            "commands",
            tuple(
                item
                if isinstance(item, AdoptionCommandResult)
                else AdoptionCommandResult(**item)
                for item in self.commands
            ),
        )
        status = _normalize_status(self.status)
        if status == "auto":
            status = "failed" if self.commands and not self.ok else "completed"
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "skill_decision", str(self.skill_decision))
        object.__setattr__(self, "model_files", tuple(str(item) for item in self.model_files))
        object.__setattr__(self, "findings", tuple(str(item) for item in self.findings))
        object.__setattr__(
            self,
            "counterexamples",
            tuple(str(item) for item in self.counterexamples),
        )
        object.__setattr__(
            self,
            "friction_points",
            tuple(str(item) for item in self.friction_points),
        )
        object.__setattr__(
            self,
            "skipped_steps",
            tuple(str(item) for item in self.skipped_steps),
        )
        object.__setattr__(
            self,
            "next_actions",
            tuple(str(item) for item in self.next_actions),
        )
        object.__setattr__(self, "metadata", freeze_metadata(self.metadata))

    @property
    def ok(self) -> bool:
        """Return whether all recorded commands completed successfully."""

        return all(command.ok for command in self.commands)

    @property
    def has_commands(self) -> bool:
        """Return whether the entry contains at least one executable check."""

        return bool(self.commands)

    @property
    def complete(self) -> bool:
        """Return whether the adoption session is final and successful."""

        return self.status == "completed" and self.ok

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "flowguard_adoption_log_entry",
            "task_id": self.task_id,
            "project": self.project,
            "task_summary": self.task_summary,
            "trigger_reason": self.trigger_reason,
            "status": self.status,
            "skill_decision": self.skill_decision,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "duration_seconds": round(self.duration_seconds, 6),
            "ok": self.ok,
            "complete": self.complete,
            "has_commands": self.has_commands,
            "command_count": len(self.commands),
            "model_files": list(self.model_files),
            "commands": [command.to_dict() for command in self.commands],
            "findings": list(self.findings),
            "counterexamples": list(self.counterexamples),
            "friction_points": list(self.friction_points),
            "skipped_steps": list(self.skipped_steps),
            "next_actions": list(self.next_actions),
            "metadata": to_jsonable(self.metadata),
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    def to_json_line(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def format_markdown(self) -> str:
        lines = [
            f"## {self.task_id} - {self.task_summary}",
            "",
            f"- Project: {self.project}",
            f"- Trigger reason: {self.trigger_reason}",
            f"- Status: {self.status}",
            f"- Skill decision: {self.skill_decision}",
            f"- Started: {self.started_at}",
            f"- Ended: {self.ended_at}",
            f"- Duration seconds: {self.duration_seconds:.3f}",
            f"- Commands OK: {self.ok}",
            "",
            "### Model Files",
        ]
        lines.extend(_bullet_lines(self.model_files, empty="none recorded"))
        lines.append("")
        lines.append("### Commands")
        if self.commands:
            for command in self.commands:
                status = "OK" if command.ok else "FAIL"
                summary = f" - {command.summary}" if command.summary else ""
                lines.append(
                    f"- {status} ({command.duration_seconds:.3f}s): "
                    f"`{command.command}`{summary}"
                )
        else:
            lines.append("- none recorded")
        _append_section(lines, "Findings", self.findings)
        _append_section(lines, "Counterexamples", self.counterexamples)
        _append_section(lines, "Friction Points", self.friction_points)
        _append_section(lines, "Skipped Steps", self.skipped_steps)
        _append_section(lines, "Next Actions", self.next_actions)
        return "\n".join(lines)


class AdoptionTimer:
    """Small timer for constructing adoption log entries."""

    def __init__(
        self,
        *,
        task_id: str,
        project: str,
        task_summary: str,
        trigger_reason: str,
        status: str = "auto",
        skill_decision: str = "used_flowguard",
        started_at: str | None = None,
    ) -> None:
        self.task_id = task_id
        self.project = project
        self.task_summary = task_summary
        self.trigger_reason = trigger_reason
        self.status = status
        self.skill_decision = skill_decision
        self.started_at = started_at or utc_now_text()
        self._start = time.perf_counter()

    def __enter__(self) -> "AdoptionTimer":
        return self

    def __exit__(self, _exc_type: Any, _exc: Any, _tb: Any) -> None:
        return None

    def finish(
        self,
        *,
        ended_at: str | None = None,
        status: str | None = None,
        model_files: Iterable[str] | None = None,
        commands: Iterable[AdoptionCommandResult | Mapping[str, Any]] | None = None,
        findings: Iterable[str] | None = None,
        counterexamples: Iterable[str] | None = None,
        friction_points: Iterable[str] | None = None,
        skipped_steps: Iterable[str] | None = None,
        next_actions: Iterable[str] | None = None,
        metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
    ) -> AdoptionLogEntry:
        return make_adoption_log_entry(
            task_id=self.task_id,
            project=self.project,
            task_summary=self.task_summary,
            trigger_reason=self.trigger_reason,
            skill_decision=self.skill_decision,
            started_at=self.started_at,
            ended_at=ended_at or utc_now_text(),
            duration_seconds=time.perf_counter() - self._start,
            status=status or self.status,
            model_files=model_files,
            commands=commands,
            findings=findings,
            counterexamples=counterexamples,
            friction_points=friction_points,
            skipped_steps=skipped_steps,
            next_actions=next_actions,
            metadata=metadata,
        )


def make_adoption_log_entry(
    *,
    task_id: str,
    project: str,
    task_summary: str,
    trigger_reason: str,
    skill_decision: str = "used_flowguard",
    started_at: str | None = None,
    ended_at: str | None = None,
    duration_seconds: float = 0.0,
    status: str = "auto",
    model_files: Iterable[str] | None = None,
    commands: Iterable[AdoptionCommandResult | Mapping[str, Any]] | None = None,
    findings: Iterable[str] | None = None,
    counterexamples: Iterable[str] | None = None,
    friction_points: Iterable[str] | None = None,
    skipped_steps: Iterable[str] | None = None,
    next_actions: Iterable[str] | None = None,
    metadata: Mapping[str, Any] | Iterable[tuple[str, Any]] | None = None,
) -> AdoptionLogEntry:
    return AdoptionLogEntry(
        task_id=task_id,
        project=project,
        task_summary=task_summary,
        trigger_reason=trigger_reason,
        skill_decision=skill_decision,
        started_at=started_at or utc_now_text(),
        ended_at=ended_at or utc_now_text(),
        duration_seconds=duration_seconds,
        status=status,
        model_files=tuple(str(item) for item in _as_tuple(model_files)),
        commands=tuple(commands or ()),
        findings=tuple(str(item) for item in _as_tuple(findings)),
        counterexamples=tuple(str(item) for item in _as_tuple(counterexamples)),
        friction_points=tuple(str(item) for item in _as_tuple(friction_points)),
        skipped_steps=tuple(str(item) for item in _as_tuple(skipped_steps)),
        next_actions=tuple(str(item) for item in _as_tuple(next_actions)),
        metadata=metadata,
    )


def append_jsonl(path: str | Path, entry: AdoptionLogEntry) -> None:
    """Append one adoption log entry to a JSONL file."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("a", encoding="utf-8") as handle:
        handle.write(entry.to_json_line())
        handle.write("\n")


def append_markdown_log(path: str | Path, entry: AdoptionLogEntry) -> None:
    """Append one adoption log entry to a Markdown log file."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    prefix = "\n\n" if target.exists() and target.stat().st_size else ""
    with target.open("a", encoding="utf-8") as handle:
        handle.write(prefix)
        handle.write(entry.format_markdown())
        handle.write("\n")


def _append_section(lines: list[str], title: str, values: tuple[str, ...]) -> None:
    lines.append("")
    lines.append(f"### {title}")
    lines.extend(_bullet_lines(values, empty="none recorded"))


def _bullet_lines(values: Iterable[str], *, empty: str) -> list[str]:
    items = tuple(values)
    if not items:
        return [f"- {empty}"]
    return [f"- {item}" for item in items]


__all__ = [
    "ADOPTION_STATUSES",
    "AdoptionCommandResult",
    "AdoptionLogEntry",
    "AdoptionTimer",
    "append_jsonl",
    "append_markdown_log",
    "make_adoption_log_entry",
    "utc_now_text",
]
