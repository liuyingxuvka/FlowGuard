"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Review the plan-detailing compiler rollout before production changes and final
confidence claims.

Guards against:
- treating vague plan prose as a complete FlowGuard plan;
- omitting validation, failure, rework, side-effect, or final evidence gates;
- overclaiming full confidence from scoped plan-detail evidence.

Use before editing:
plan-detailing compiler API, templates, routing, or installed skill surfaces.

Run:
python .flowguard/verification/owners/plan_detailing_compiler/run_checks.py
"""

from examples.plan_detailing_compiler.model import *  # noqa: F401,F403


def export_path_quality_source(model_instance_fingerprint: str):
    """Project explicitly selected source contracts; run no check or review."""
    from pathlib import Path
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint

    root = Path(__file__).resolve().parents[4]
    return compile_declared_path_quality_source(
        model_id='plan_detailing_compiler', model_instance_fingerprint=model_instance_fingerprint,
        graph_scope='native_check_contract',
        source_refs=tuple({"path": path, "source_fingerprint": functional_source_fingerprint(root, path)} for path in ('.flowguard/models/owners/plan_detailing_compiler/model.py', 'examples/plan_detailing_compiler/model.py')),
        contract_export=export_contract_model(),
    )
