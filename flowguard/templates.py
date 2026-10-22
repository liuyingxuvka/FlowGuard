"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from .template_text.architecture_reduction import (
    ARCHITECTURE_REDUCTION_MODEL_TEMPLATE,
)
from .template_text.behavior_commitment import (
    BEHAVIOR_COMMITMENT_LEDGER_TEMPLATE,
    BEHAVIOR_COMMITMENT_MODEL_TEMPLATE,
)
from .template_text.code_structure import (
    CODE_STRUCTURE_MODEL_TEMPLATE,
)
from .template_text.core import (
    ADOPTION_LOG_TEMPLATE,
    MODEL_NOTES_TEMPLATE,
)
from .template_text.field_lifecycle import (
    FIELD_LIFECYCLE_MODEL_TEMPLATE,
)
from .template_text.model_test_alignment import MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE
from .template_text.model_mesh import (
    MODEL_MESH_MODEL_TEMPLATE,
)
from .template_text.contract_exhaustion import (
    CONTRACT_EXHAUSTION_MODEL_TEMPLATE,
)
from .template_text.topology_hazard import (
    TOPOLOGY_HAZARD_MODEL_TEMPLATE,
)
from .template_text.ui_flow_structure import (
    UI_FLOW_STRUCTURE_MODEL_TEMPLATE,
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


def model_test_alignment_template_files() -> tuple[TemplateFile, ...]:
    return (TemplateFile(".flowguard/models/model_test_alignment.py", MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE),)


def architecture_reduction_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/architecture_reduction.py", ARCHITECTURE_REDUCTION_MODEL_TEMPLATE),
    )


def behavior_commitment_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/behavior_commitment.py", BEHAVIOR_COMMITMENT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/behavior/inventory/ledger.json", BEHAVIOR_COMMITMENT_LEDGER_TEMPLATE),
    )


def code_structure_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/code_structure.py", CODE_STRUCTURE_MODEL_TEMPLATE),
    )


def field_lifecycle_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/field_lifecycle.py", FIELD_LIFECYCLE_MODEL_TEMPLATE),
    )


def ui_flow_structure_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/ui_flow_structure.py", UI_FLOW_STRUCTURE_MODEL_TEMPLATE),
    )


def topology_hazard_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/topology_hazard.py", TOPOLOGY_HAZARD_MODEL_TEMPLATE),
    )


def model_mesh_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/model_mesh.py", MODEL_MESH_MODEL_TEMPLATE),
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
    "ARCHITECTURE_REDUCTION_MODEL_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_TEMPLATE",
    "BEHAVIOR_COMMITMENT_MODEL_TEMPLATE",
    "CODE_STRUCTURE_MODEL_TEMPLATE",
    "FIELD_LIFECYCLE_MODEL_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "TOPOLOGY_HAZARD_MODEL_TEMPLATE",
    "TemplateFile",
    "adoption_template_files",
    "architecture_reduction_template_files",
    "behavior_commitment_template_files",
    "code_structure_template_files",
    "contract_exhaustion_template_files",
    "field_lifecycle_template_files",
    "model_mesh_template_files",
    "model_test_alignment_template_files",
    "topology_hazard_template_files",
    "ui_flow_structure_template_files",
    "write_template_files",
]
