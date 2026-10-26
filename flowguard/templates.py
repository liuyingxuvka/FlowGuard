"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from .template_text.behaviour import BEHAVIOUR_MODEL_TEMPLATE
from .template_text.validator import (
    VALIDATOR_MODEL_TEMPLATE,
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
2. Before changing behaviour or structure: `python -m flowguard target start "<goal>"`, edit the target, `python -m flowguard target check`, then `python -m flowguard target promote`; extend the existing owner (`python -m flowguard read --find WORDS`).
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change`, fix errors, and run the affected tests and models it selects.
5. Re-read each REVIEW component, update its description if behavior changed, then `python -m flowguard map confirm ID`.
6. At final release, freeze the source and run the full suite and `python -m flowguard release` once on that revision (same-SHA CI may provide this); report failures and unrun checks honestly.
"""),
    )




def behaviour_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/order_placement.py", BEHAVIOUR_MODEL_TEMPLATE),
    )


def ui_journey_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/ui_journey.py", UI_JOURNEY_MODEL_TEMPLATE),
    )


def validator_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/validator.py", VALIDATOR_MODEL_TEMPLATE),
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
        staged = (target_root / ".flowguard/target").is_dir() and file.path.startswith(".flowguard/models/")
        relative = file.path.replace(".flowguard/models/", ".flowguard/target/models/", 1) if staged else file.path
        target = target_root / relative
        if target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(file.content, encoding="utf-8")
        written.append(target)
    if any(p.parent == target_root / ".flowguard/models" for p in written) and (target_root / ".flowguard/map.json").is_file():
        from .map.mapfile import load_map, model_digests, save_map
        data = load_map(target_root)
        data["model_digests"] = model_digests(target_root)
        save_map(target_root, data)
    return tuple(written)


__all__ = [
    "TemplateFile",
    "adoption_template_files",
    "behaviour_template_files",
    "validator_template_files",
    "ui_journey_template_files",
    "write_template_files",
]
