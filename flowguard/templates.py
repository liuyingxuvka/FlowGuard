"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from .template_text.core import (
    ADOPTION_LOG_TEMPLATE,
    MODEL_NOTES_TEMPLATE,
)
from .template_text.contract_exhaustion import (
    CONTRACT_EXHAUSTION_MODEL_TEMPLATE,
)
from .template_text.ui_journey import (
    UI_JOURNEY_MODEL_TEMPLATE,
)


@dataclass(frozen=True)
class TemplateFile:
    path: str
    content: str


def adoption_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile("docs/flowguard_agents_rules.md", """# FlowGuard rules for the project agent

Copy these six rules into the project's AGENTS.md or CLAUDE.md:

1. Start each session with `python -m flowguard read` before opening source.
2. Before adding behavior, use `python -m flowguard read --find WORDS`; extend its existing owner.
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change`, fix errors, and run the affected tests and models it selects.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.
"""),
    )




def ui_journey_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/ui_journey.py", UI_JOURNEY_MODEL_TEMPLATE),
    )


def contract_exhaustion_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/contract_exhaustion.py", CONTRACT_EXHAUSTION_MODEL_TEMPLATE),
    )


def write_template_files(
    root: str | Path,
    files: tuple[TemplateFile, ...],
    *,
    overwrite: bool = False,
) -> tuple[Path, ...]:
    target_root = Path(root)
    written: list[Path] = []
    for file in files:
        target = target_root / file.path
        if target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        written.append(target)
    return tuple(written)


__all__ = [
    "ADOPTION_LOG_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "TemplateFile",
    "adoption_template_files",
    "contract_exhaustion_template_files",
    "ui_journey_template_files",
    "write_template_files",
]
