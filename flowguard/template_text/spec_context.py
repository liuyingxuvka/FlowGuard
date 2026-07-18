"""Template text for read-only OpenSpec context."""

SPEC_CONTEXT_MODEL_TEMPLATE = r'''"""FlowGuard Risk Purpose Header.

Created with FlowGuard:
https://github.com/liuyingxuvka/FlowGuard

Purpose:
Read official OpenSpec authoring artifacts as external planning context.

Guards against:
- provider writes, sessions, caches, receipts, or execution-owner projection.

Use before editing:
plans or models that depend on an active OpenSpec change.

Run:
python .flowguard/spec_context/run_checks.py --change <change-id>

FlowGuard reads proposal, design, specs, tasks, and derived task status only.
OpenSpec keeps all write, validation, execution, receipt, and archive authority.
"""

from flowguard import read_openspec_context, review_spec_context


def run_model_checks(project_root=".", change_id="replace-with-change-id"):
    context = read_openspec_context(project_root, change_id)
    review = review_spec_context(context)
    return review.to_dict()
'''


SPEC_CONTEXT_RUN_CHECKS_TEMPLATE = r'''"""Run the read-only OpenSpec context review."""

import argparse
import json

from model import run_model_checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--change", required=True)
    args = parser.parse_args()
    report = run_model_checks(args.root, args.change)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


SPEC_CONTEXT_NOTES_TEMPLATE = """# FlowGuard OpenSpec context

FlowGuard may read the official OpenSpec proposal, design, specifications,
tasks, and task status as planning context. It does not write OpenSpec files,
run provider checks, create provider sessions/caches/receipts, or become the
owner of OpenSpec validation and archive actions.
"""


__all__ = (
    "SPEC_CONTEXT_MODEL_TEMPLATE",
    "SPEC_CONTEXT_NOTES_TEMPLATE",
    "SPEC_CONTEXT_RUN_CHECKS_TEMPLATE",
)
