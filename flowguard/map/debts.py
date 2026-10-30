"""One evaluation of explicit accepted-debt reasons and project deadlines."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
import re
import tomllib

from .common import Finding

DATE = re.compile(r"\d{4}-\d{2}-\d{2}\Z")
VERSION = re.compile(r"(\d+)\.(\d+)\.(\d+)\Z")


@dataclass(frozen=True)
class DebtState:
    index: int
    code: str
    component: str
    expires: object
    status: str
    detail: str = ""


@dataclass(frozen=True)
class DebtEvaluation:
    states: tuple[DebtState, ...]

    @property
    def active_indices(self) -> frozenset[int]:
        return frozenset(state.index for state in self.states if state.status == "active")

    def diagnostics(self, *, strict: bool = False) -> list[Finding]:
        """Return fresh findings so severity never leaks between command modes."""
        out = []
        for state in self.states:
            subject = f"{state.code} {state.component}".rstrip()
            if state.status == "invalid":
                out.append(Finding("error", "debt_without_expiry", state.component,
                                   f"debt_without_expiry: accepted debt {subject} needs reason and expires{state.detail}"))
            elif state.status == "expired":
                out.append(Finding("error" if strict else "warn", "debt_expired", state.component,
                                   f"debt_expired: {subject} expired at {state.expires}"))
        return out


def _project_version(root: Path | None) -> tuple[int, ...] | None:
    if root is None:
        return None
    try:
        with (Path(root) / "pyproject.toml").open("rb") as stream:
            project = tomllib.load(stream).get("project", {})
    except (OSError, ValueError, TypeError):
        return None
    value = project.get("version", "") if isinstance(project, dict) else ""
    match = VERSION.fullmatch(value) if isinstance(value, str) else None
    return tuple(map(int, match.groups())) if match else None


def evaluate_debts(root: Path | None, data: dict, *, today: date | None = None) -> DebtEvaluation:
    """Classify raw records without changing or persisting them; equality expires."""
    today = date.today() if today is None else today
    states = []
    version_read = False
    version = None
    for index, debt in enumerate(data.get("accepted_debts", [])):
        code = debt.get("code", "")
        component = debt.get("component", "*")
        reason = debt.get("reason")
        expires = debt.get("expires")
        status, detail = "invalid", ""
        if isinstance(expires, str):
            if DATE.fullmatch(expires):
                try:
                    deadline = date.fromisoformat(expires)
                except ValueError:
                    pass
                else:
                    status = "expired" if today >= deadline else "active"
            elif expires.startswith("v") and (match := VERSION.fullmatch(expires[1:])):
                if not version_read:
                    version = _project_version(root)
                    version_read = True
                if version is None:
                    detail = " (this project has no version in pyproject.toml: use a date)"
                else:
                    status = "expired" if version >= tuple(map(int, match.groups())) else "active"
        if not isinstance(reason, str) or not reason.strip():
            status = "invalid"
        states.append(DebtState(index, code, component, expires, status, detail))
    return DebtEvaluation(tuple(states))


def active_debts(data: dict, *, root: Path | None = None,
                 evaluation: DebtEvaluation | None = None) -> list[dict]:
    evaluation = evaluation if evaluation is not None else evaluate_debts(root, data)
    eligible = evaluation.active_indices
    return [debt for index, debt in enumerate(data.get("accepted_debts", []))
            if index in eligible]
