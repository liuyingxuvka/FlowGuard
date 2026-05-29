"""Template text for FlowGuard structure mesh route."""

from __future__ import annotations

STRUCTURE_MESH_MODEL_TEMPLATE = '''"""FlowGuard Risk Purpose Header

Created with FlowGuard: https://github.com/liuyingxuvka/FlowGuard
Purpose: Review whether a large script or module can be split into owned child modules while preserving public behavior.
Guards against: missing child ownership, removed public entrypoints, missing facades, duplicate state or side-effect owners, unsafe dependency cycles, config drift, and overclaimed parity evidence.
Use before editing: Update this StructureMesh before splitting large scripts, moving module boundaries, extracting services, or changing public imports and CLI/API surfaces.
Run: python .flowguard/structure_mesh/run_checks.py
"""

from __future__ import annotations

from flowguard import (
    CodeStructureRecommendation,
    EVIDENCE_ABSTRACT_GREEN,
    EVIDENCE_CONFORMANCE_GREEN,
    ModuleStructureEvidence,
    PublicEntrypointEvidence,
    StructureMeshPlan,
    StructurePartitionItem,
    TargetModuleRecommendation,
    review_structure_mesh,
)


def target_structure_recommendation() -> CodeStructureRecommendation:
    return CodeStructureRecommendation(
        "legacy-reporter-target-structure",
        source_model_id="legacy-reporter-functional-model",
        source_model_path=".flowguard/legacy_reporter/model.py",
        parent_module_id="legacy_reporter",
        target_modules=(
            TargetModuleRecommendation(
                "cli",
                path="reporter/cli.py",
                owns_function_blocks=("parse_args",),
                public_entrypoints=("python -m reporter",),
                validation_boundaries=("cli parity test",),
                rationale="CLI parsing and the public entrypoint stay together behind the facade.",
            ),
            TargetModuleRecommendation(
                "config",
                path="reporter/config.py",
                owns_function_blocks=("load_config",),
                owns_config=("report_defaults",),
                validation_boundaries=("config default parity test",),
                rationale="Configuration defaults have one owner to avoid drift.",
            ),
            TargetModuleRecommendation(
                "renderer",
                path="reporter/renderer.py",
                owns_function_blocks=("render_report",),
                owns_state=("render_cache",),
                owns_side_effects=("write_report",),
                validation_boundaries=("render replay",),
                rationale="Rendering owns cached render state and report writing side effects.",
            ),
        ),
        function_block_map=(
            ("parse_args", "cli"),
            ("load_config", "config"),
            ("render_report", "renderer"),
        ),
        state_owner_map=(("render_cache", "renderer"),),
        side_effect_owner_map=(("write_report", "renderer"),),
        config_owner_map=(("report_defaults", "config"),),
        public_entrypoint_map=(("python -m reporter", "cli"),),
        facade_module_id="cli",
        validation_boundaries=("cli parity test", "config default parity test", "render replay"),
        rationale="The FlowGuard functional model separates CLI intake, config loading, and rendering side effects.",
    )


def routine_plan() -> StructureMeshPlan:
    return StructureMeshPlan(
        parent_module_id="legacy_reporter",
        target_structure=target_structure_recommendation(),
        decision_scope="routine",
        required_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
        partition_items=(
            StructurePartitionItem("parse_args", owner_module_id="cli"),
            StructurePartitionItem("load_config", owner_module_id="config"),
            StructurePartitionItem("render_report", owner_module_id="renderer"),
        ),
        child_modules=(
            ModuleStructureEvidence(
                "cli",
                path="reporter/cli.py",
                owns_functions=("parse_args",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "config",
                path="reporter/config.py",
                owns_functions=("load_config",),
                owns_config=("report_defaults",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "renderer",
                path="reporter/renderer.py",
                owns_functions=("render_report",),
                owns_state=("render_cache",),
                owns_side_effects=("write_report",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "release_packaging",
                path="reporter/release.py",
                layer="release",
                release_required=True,
                behavior_parity_current=False,
                behavior_parity_tier=EVIDENCE_CONFORMANCE_GREEN,
                not_ready_reason="release packaging check is deferred during routine refactor work",
            ),
        ),
        public_entrypoints=(
            PublicEntrypointEvidence(
                "python -m reporter",
                entrypoint_type="cli",
                old_path="reporter.py",
                new_path="reporter/__main__.py",
                parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
        ),
    )


def broken_plan() -> StructureMeshPlan:
    return StructureMeshPlan(
        parent_module_id="legacy_reporter",
        decision_scope="release",
        required_evidence_tier=EVIDENCE_CONFORMANCE_GREEN,
        partition_items=(
            StructurePartitionItem("parse_args", owner_module_id="cli"),
            StructurePartitionItem("load_config", owner_module_id="config"),
            StructurePartitionItem("render_report", owner_module_id="renderer"),
        ),
        child_modules=(
            ModuleStructureEvidence(
                "cli",
                path="reporter/cli.py",
                owns_functions=("parse_args",),
                owns_state=("shared_context",),
                dependency_cycles=("cli->renderer->cli",),
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
            ModuleStructureEvidence(
                "renderer",
                path="reporter/renderer.py",
                owns_functions=("render_report",),
                owns_state=("shared_context",),
                owns_side_effects=("write_report",),
                facade_retained=False,
                config_defaults_changed=True,
                behavior_parity_current=False,
                behavior_parity_tier=EVIDENCE_ABSTRACT_GREEN,
            ),
        ),
        public_entrypoints=(
            PublicEntrypointEvidence(
                "python -m reporter",
                entrypoint_type="cli",
                compatibility_preserved=False,
                facade_available=False,
                parity_evidence_current=False,
                parity_evidence_tier=EVIDENCE_ABSTRACT_GREEN,
                release_required=True,
            ),
        ),
    )


def run_checks():
    return review_structure_mesh(routine_plan()), review_structure_mesh(broken_plan())
'''

STRUCTURE_MESH_RUN_CHECKS_TEMPLATE = '''"""Run the StructureMesh template checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    routine, broken = run_checks()
    print(routine.format_text())
    print()
    print(broken.format_text(max_findings=5))
    return 0 if routine.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''

STRUCTURE_MESH_NOTES_TEMPLATE = """# FlowGuard StructureMesh Notes

Use this scaffold to keep a module or script split explicit before code moves.

## What StructureMesh Reviews

- which child module owns each function, state item, config key, side effect,
  public entrypoint, or behavior contract;
- which FlowGuard functional model derived the target child-module structure
  before the existing script or module is split;
- whether old public imports, CLI commands, API routes, and data shapes remain
  available through a facade or compatibility layer;
- whether duplicated state, duplicated side effects, unsafe dependency cycles,
  config drift, or stale parity evidence make the split unsafe;
- whether routine work can proceed while release-only checks remain visible as
  deferred obligations.

StructureMesh does not refactor code. Project adapters or agents should collect
source inventory, model-derived target structure, ownership, dependency, and
parity evidence, then feed that evidence into the StructureMesh model.
"""

__all__ = [
    'STRUCTURE_MESH_MODEL_TEMPLATE',
    'STRUCTURE_MESH_RUN_CHECKS_TEMPLATE',
    'STRUCTURE_MESH_NOTES_TEMPLATE',
]
