"""Template text for provider-neutral read-only WorkContext."""

WORK_CONTEXT_MODEL_TEMPLATE = r'''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Read one declared external planning/work source as content-addressed context.

Guards against:
- provider writes, execution, sessions, caches, receipts, or test-owner projection;
- missing adapter roles, stale artifacts, and project-root escape.

Use before editing: Read declared planning, specification, Spike, changelog,
Superpowers, or other provider artifacts before non-trivial modeled work.

Run:
python .flowguard/work_context/run_checks.py --adapter <adapter-id> --work-id <id>

The native provider keeps all authoring, execution, validation, status, and
lifecycle authority. Provider status is planning context, never FlowGuard proof.
"""

from flowguard import read_work_context, review_work_context


def run_model_checks(
    project_root=".",
    adapter_id="declared-files",
    native_work_id="replace-with-work-id",
    declaration=None,
):
    context = read_work_context(
        project_root,
        native_work_id,
        adapter_id=adapter_id,
        declaration=declaration or {},
    )
    return review_work_context(context).to_dict()
'''


WORK_CONTEXT_RUN_CHECKS_TEMPLATE = r'''"""Run the provider-neutral WorkContext review."""

import argparse
import json

from model import run_model_checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--adapter", required=True)
    parser.add_argument("--work-id", required=True)
    parser.add_argument("--declaration-json", default="")
    args = parser.parse_args()
    declaration = (
        json.loads(args.declaration_json)
        if args.declaration_json
        else {}
    )
    report = run_model_checks(
        args.root,
        args.adapter,
        args.work_id,
        declaration,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


WORK_CONTEXT_NOTES_TEMPLATE = """# FlowGuard WorkContext

FlowGuard reads explicitly declared provider artifacts through a registered,
read-only adapter. OpenSpec, Spec Kit, Superpowers, declared files, and future
providers retain their native authoring, execution, validation, and lifecycle.
No provider status, checkbox, session, cache, or receipt becomes FlowGuard
model or test evidence.
"""


__all__ = (
    "WORK_CONTEXT_MODEL_TEMPLATE",
    "WORK_CONTEXT_NOTES_TEMPLATE",
    "WORK_CONTEXT_RUN_CHECKS_TEMPLATE",
)
