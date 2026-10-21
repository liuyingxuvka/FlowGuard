"""Reusable project template content for model-first flowguard adoption."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


from .template_text.code_structure_recommendation import (
    CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE,
    CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE,
    CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE,
)
from .template_text.core import (
    ADOPTION_LOG_TEMPLATE,
    MODEL_NOTES_TEMPLATE,
)
from .template_text.behavior_commitment_ledger import (
    BEHAVIOR_COMMITMENT_LEDGER_LEDGER_TEMPLATE,
    BEHAVIOR_COMMITMENT_LEDGER_MODEL_TEMPLATE,
    BEHAVIOR_COMMITMENT_LEDGER_RUN_CHECKS_TEMPLATE,
    BEHAVIOR_COMMITMENT_LEDGER_NOTES_TEMPLATE,
)
from .template_text.field_lifecycle import (
    FIELD_LIFECYCLE_MODEL_TEMPLATE,
)
from .template_text.model_test_alignment import (
    MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE,
    MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE,
    MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE,
    MODEL_TEST_ALIGNMENT_FULL_MODEL_TEMPLATE,
    MODEL_TEST_ALIGNMENT_FULL_RUN_CHECKS_TEMPLATE,
    MODEL_TEST_ALIGNMENT_FULL_NOTES_TEMPLATE,
)
from .template_text.primary_path_authority import (
    PRIMARY_PATH_AUTHORITY_MODEL_TEMPLATE,
    PRIMARY_PATH_AUTHORITY_RUN_CHECKS_TEMPLATE,
    PRIMARY_PATH_AUTHORITY_NOTES_TEMPLATE,
)
from .template_text.model_mesh import (
    MODEL_MESH_MODEL_TEMPLATE,
    MODEL_MESH_RUN_CHECKS_TEMPLATE,
    MODEL_MESH_NOTES_TEMPLATE,
)
from .template_text.contract_exhaustion import (
    CONTRACT_EXHAUSTION_MODEL_TEMPLATE,
)
from .template_text.topology_hazard import (
    TOPOLOGY_HAZARD_MODEL_TEMPLATE,
    TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE,
    TOPOLOGY_HAZARD_NOTES_TEMPLATE,
)
from .template_text.ui_flow_structure import (
    UI_FLOW_STRUCTURE_MODEL_TEMPLATE,
    UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE,
    UI_FLOW_STRUCTURE_NOTES_TEMPLATE,
    UI_FLOW_STRUCTURE_FULL_MODEL_TEMPLATE,
    UI_FLOW_STRUCTURE_FULL_RUN_CHECKS_TEMPLATE,
    UI_FLOW_STRUCTURE_FULL_NOTES_TEMPLATE,
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


def behavior_commitment_ledger_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/behavior/inventory/ledger.json", BEHAVIOR_COMMITMENT_LEDGER_LEDGER_TEMPLATE),
        TemplateFile(".flowguard/models/owners/behavior_commitment_ledger/model.py", BEHAVIOR_COMMITMENT_LEDGER_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/behavior_commitment_ledger/run_checks.py", BEHAVIOR_COMMITMENT_LEDGER_RUN_CHECKS_TEMPLATE),
    )


def primary_path_authority_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/primary_path_authority/model.py", PRIMARY_PATH_AUTHORITY_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/primary_path_authority/run_checks.py", PRIMARY_PATH_AUTHORITY_RUN_CHECKS_TEMPLATE),
    )


def model_test_alignment_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/model_test_alignment/model.py", MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/model_test_alignment/run_checks.py", MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE),
    )


def model_test_alignment_full_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/model_test_alignment/model.py", MODEL_TEST_ALIGNMENT_FULL_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/model_test_alignment/run_checks.py", MODEL_TEST_ALIGNMENT_FULL_RUN_CHECKS_TEMPLATE),
    )


def code_structure_recommendation_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(
            ".flowguard/models/owners/code_structure_recommendation/model.py",
            CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE,
        ),
        TemplateFile(
            ".flowguard/verification/owners/code_structure_recommendation/run_checks.py",
            CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE,
        ),
    )


def field_lifecycle_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/field_lifecycle.py", FIELD_LIFECYCLE_MODEL_TEMPLATE),
    )


def ui_flow_structure_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/ui_flow_structure/model.py", UI_FLOW_STRUCTURE_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/ui_flow_structure/run_checks.py", UI_FLOW_STRUCTURE_RUN_CHECKS_TEMPLATE),
    )


def ui_flow_structure_full_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/ui_flow_structure/model.py", UI_FLOW_STRUCTURE_FULL_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/ui_flow_structure/run_checks.py", UI_FLOW_STRUCTURE_FULL_RUN_CHECKS_TEMPLATE),
    )


def topology_hazard_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/model_topology_hazard_review/model.py", TOPOLOGY_HAZARD_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/model_topology_hazard_review/run_checks.py", TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE),
    )


def model_mesh_template_files() -> tuple[TemplateFile, ...]:
    return (
        TemplateFile(".flowguard/models/owners/model_mesh/model.py", MODEL_MESH_MODEL_TEMPLATE),
        TemplateFile(".flowguard/verification/owners/model_mesh/run_checks.py", MODEL_MESH_RUN_CHECKS_TEMPLATE),
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
    def prepare_current_runner(file: TemplateFile) -> str:
        """Make a v2 verification runner import its paired current model.

        v2 deliberately keeps model authority and executable verification in
        separate role roots.  Public templates are still authored as compact
        ``from model import ...`` or ``import model`` snippets, so the writer
        adds one explicit current model root to ``sys.path`` at materialization
        time.  It never searches legacy locations or accepts an alternate copy.
        """

        parts = Path(file.path).parts
        import_marker = (
            "from model import"
            if "from model import" in file.content
            else "import model"
            if "import model" in file.content
            else None
        )
        if (
            len(parts) == 5
            and parts[:3] == (".flowguard", "verification", "owners")
            and parts[-1] == "run_checks.py"
            and import_marker is not None
            and "_FLOWGUARD_MODEL_ROOT" not in file.content
            and "_MODEL_DIR" not in file.content
        ):
            owner = parts[3]
            preamble = (
                "from pathlib import Path\n"
                "import sys\n\n"
                f"_MODEL_DIR = Path(__file__).resolve().parents[4] / \".flowguard\" / \"models\" / \"owners\" / \"{owner}\"\n"
                "if str(_MODEL_DIR) not in sys.path:\n"
                "    sys.path.insert(0, str(_MODEL_DIR))\n\n"
            )
            return file.content.replace(import_marker, preamble + import_marker, 1)
        return file.content

    target_root = Path(root)
    written: list[Path] = []
    for file in files:
        target = target_root / file.path
        if target.exists() and not overwrite:
            raise FileExistsError(f"template target already exists: {target}")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(prepare_current_runner(file), encoding="utf-8")
        written.append(target)
    return tuple(written)


__all__ = [
    "ADOPTION_LOG_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_LEDGER_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_MODEL_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_NOTES_TEMPLATE",
    "BEHAVIOR_COMMITMENT_LEDGER_RUN_CHECKS_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_MODEL_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_NOTES_TEMPLATE",
    "CODE_STRUCTURE_RECOMMENDATION_RUN_CHECKS_TEMPLATE",
    "FIELD_LIFECYCLE_MODEL_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_MODEL_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_NOTES_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_RUN_CHECKS_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_FULL_MODEL_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_FULL_NOTES_TEMPLATE",
    "MODEL_TEST_ALIGNMENT_FULL_RUN_CHECKS_TEMPLATE",
    "MODEL_NOTES_TEMPLATE",
    "PRIMARY_PATH_AUTHORITY_MODEL_TEMPLATE",
    "PRIMARY_PATH_AUTHORITY_NOTES_TEMPLATE",
    "PRIMARY_PATH_AUTHORITY_RUN_CHECKS_TEMPLATE",
    "TOPOLOGY_HAZARD_MODEL_TEMPLATE",
    "TOPOLOGY_HAZARD_NOTES_TEMPLATE",
    "TOPOLOGY_HAZARD_RUN_CHECKS_TEMPLATE",
    "TemplateFile",
    "UI_FLOW_STRUCTURE_FULL_MODEL_TEMPLATE",
    "UI_FLOW_STRUCTURE_FULL_NOTES_TEMPLATE",
    "UI_FLOW_STRUCTURE_FULL_RUN_CHECKS_TEMPLATE",
    "adoption_template_files",
    "behavior_commitment_ledger_template_files",
    "code_structure_recommendation_template_files",
    "contract_exhaustion_template_files",
    "field_lifecycle_template_files",
    "model_mesh_template_files",
    "model_test_alignment_full_template_files",
    "model_test_alignment_template_files",
    "primary_path_authority_template_files",
    "topology_hazard_template_files",
    "ui_flow_structure_full_template_files",
    "ui_flow_structure_template_files",
    "write_template_files",
]
