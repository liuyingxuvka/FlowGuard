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
2. Before changing behaviour or structure: locate the owner model with `python -m flowguard read --find WORDS` (or a path:function) and extend it (a separate aspect gets its own model), run `python -m flowguard target start "<goal>"` and `python -m flowguard target add <model>`, edit the copy in .flowguard/target/, run `python -m flowguard target check` until it shows EXPECTED GAP and no ERROR, change the code, then run `python -m flowguard target promote` and the map confirm it prints.
3. Open only the affected component's files (`python -m flowguard read --component ID`).
4. After editing, run `python -m flowguard change` and fix errors; for `port changed ... -> verify X`, run `python -m flowguard target add X` and make X receive the value; open each place a `consumes`, `produces`, `mentions` or `nothing produces` line names; restore what a `promises: -...` line lists or give the reason in the commit message; then run the affected tests and models it selects. Models, tests and code grow together: split a model or a test file that grows too big (map check warns at the soft limit and refuses at the hard one), keep them in correspondence where it makes functional sense, and give a reason where a model has no test or no code yet.
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
