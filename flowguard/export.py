"""Deterministic JSON-compatible export helpers."""

from __future__ import annotations

import json
from dataclasses import fields, is_dataclass
from typing import Any, Mapping


JsonDict = dict[str, Any]


def type_name(value: Any) -> str:
    cls = type(value)
    return f"{cls.__module__}.{cls.__qualname__}"


def to_jsonable(value: Any) -> Any:
    """Convert arbitrary model values into deterministic JSON-compatible data."""

    if value is None or isinstance(value, (bool, int, float, str)):
        return value

    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]

    if isinstance(value, list):
        return [to_jsonable(item) for item in value]

    if isinstance(value, (set, frozenset)):
        return [to_jsonable(item) for item in sorted(value, key=repr)]

    if isinstance(value, Mapping):
        return {
            str(key): to_jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: repr(pair[0]))
        }

    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__type__": type_name(value),
            "repr": repr(value),
            "fields": {
                field.name: to_jsonable(getattr(value, field.name))
                for field in fields(value)
            },
        }

    to_dict = getattr(value, "to_dict", None)
    if to_dict is not None and callable(to_dict):
        try:
            return to_jsonable(to_dict())
        except TypeError:
            pass

    return {
        "__type__": type_name(value),
        "repr": repr(value),
    }


def trace_step_to_dict(step: Any) -> JsonDict:
    return {
        "external_input": to_jsonable(step.external_input),
        "function_name": step.function_name,
        "function_input": to_jsonable(step.function_input),
        "function_output": to_jsonable(step.function_output),
        "old_state": to_jsonable(step.old_state),
        "new_state": to_jsonable(step.new_state),
        "label": step.label,
        "reason": step.reason,
        "metadata": to_jsonable(step.metadata),
    }


def trace_to_dict(trace: Any) -> JsonDict:
    return {
        "initial_state": to_jsonable(trace.initial_state),
        "external_inputs": to_jsonable(trace.external_inputs),
        "steps": [trace_step_to_dict(step) for step in trace.steps],
        "metadata": to_jsonable(trace.metadata),
        "final_output": to_jsonable(trace.final_output),
        "final_state": to_jsonable(trace.final_state),
        "labels": list(trace.labels),
    }


def invariant_violation_to_dict(violation: Any) -> JsonDict:
    return {
        "invariant_name": violation.invariant_name,
        "description": violation.description,
        "message": violation.message,
        "state": to_jsonable(violation.state),
        "trace": trace_to_dict(violation.trace),
        "metadata": to_jsonable(violation.metadata),
    }


def dead_branch_to_dict(dead_branch: Any) -> JsonDict:
    return {
        "reason": dead_branch.reason,
        "function_name": dead_branch.function_name,
        "function_input": to_jsonable(dead_branch.function_input),
        "state": to_jsonable(dead_branch.state),
        "trace": trace_to_dict(dead_branch.trace),
        "metadata": to_jsonable(dead_branch.metadata),
    }


def exception_branch_to_dict(exception_branch: Any) -> JsonDict:
    return {
        "error_type": exception_branch.error_type,
        "message": exception_branch.message,
        "function_name": exception_branch.function_name,
        "function_input": to_jsonable(exception_branch.function_input),
        "state": to_jsonable(exception_branch.state),
        "trace": trace_to_dict(exception_branch.trace),
    }


def reachability_failure_to_dict(failure: Any) -> JsonDict:
    return {
        "name": failure.name,
        "description": failure.description,
        "message": failure.message,
    }


def check_report_to_dict(report: Any) -> JsonDict:
    exported = {
        "ok": report.ok,
        "summary": report.summary,
        "traces": [trace_to_dict(trace) for trace in report.traces],
        "violations": [
            invariant_violation_to_dict(violation)
            for violation in report.violations
        ],
        "dead_branches": [
            dead_branch_to_dict(dead_branch)
            for dead_branch in report.dead_branches
        ],
        "exception_branches": [
            exception_branch_to_dict(exception_branch)
            for exception_branch in report.exception_branches
        ],
        "reachability_failures": [
            reachability_failure_to_dict(failure)
            for failure in report.reachability_failures
        ],
        "explored_sequences": to_jsonable(report.explored_sequences),
    }
    assumption_card = getattr(report, "assumption_card", None)
    if assumption_card is not None:
        to_dict = getattr(assumption_card, "to_dict", None)
        exported["assumption_card"] = to_dict() if callable(to_dict) else to_jsonable(assumption_card)
    return exported


def to_json_text(value: Any, indent: int = 2) -> str:
    return json.dumps(to_jsonable(value), indent=indent, sort_keys=True)


def trace_to_json_text(trace: Any, indent: int = 2) -> str:
    return json.dumps(trace_to_dict(trace), indent=indent, sort_keys=True)


def check_report_to_json_text(report: Any, indent: int = 2) -> str:
    return json.dumps(check_report_to_dict(report), indent=indent, sort_keys=True)


__all__ = [
    "JsonDict",
    "check_report_to_dict",
    "check_report_to_json_text",
    "dead_branch_to_dict",
    "exception_branch_to_dict",
    "invariant_violation_to_dict",
    "reachability_failure_to_dict",
    "to_json_text",
    "to_jsonable",
    "trace_step_to_dict",
    "trace_to_dict",
    "trace_to_json_text",
    "type_name",
]
