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
python .flowguard/plan_detailing_compiler/run_checks.py
"""

from examples.plan_detailing_compiler.model import *  # noqa: F401,F403
