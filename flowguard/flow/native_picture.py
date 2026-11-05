"""Present checked native drift facts through the existing picture/cache owners."""
from __future__ import annotations

import json

from .native_finding import native_drift
from .parts import PartResult, part_digest
from .project import PROG, ProjectError, read_conflicts


def cached_drift(root, identifier):
    """Read the exact checked core through jobs.lookup, including native footprints."""
    stored = read_conflicts(root) or {}
    entry = next((row for row in stored.get("conflicts", [])
                  if row["id"] == identifier and row["kind"] == "MODEL DRIFT"), None)
    if entry is None:
        return None
    model = entry["model"]
    receipt = stored.get("models", {}).get(model, {}).get("core")
    advice = f"{identifier}: checked native evidence is missing or stale; run {PROG} check {model}"
    if not isinstance(receipt, dict) or not isinstance(receipt.get("planned"), dict):
        raise ProjectError(advice)
    from .jobs import Planned, lookup
    try:
        planned = Planned.from_json(receipt["planned"])
    except (KeyError, TypeError, ValueError) as error:
        raise ProjectError(advice) from error
    if planned.spec.kind != "core" or planned.spec.model != model:
        raise ProjectError(advice)
    core = lookup(root, planned)
    if core is None or core.digest != receipt.get("digest"):
        raise ProjectError(advice)
    drift = native_drift(model, core)
    if drift is None or drift[0].id != identifier or not drift[1].get("conformance"):
        raise ProjectError(advice)
    return core, *drift


def _text(finding, run):
    """Paired trace facts; an unknown projection never becomes a model-domain node."""
    from .diagram import _esc
    comparison = run["conformance"]
    expected = (comparison.get("expected_trace") or {}).get("steps", [])
    failed = comparison.get("failed_step_index")
    if not expected or not isinstance(failed, int) or not 1 <= failed <= len(expected):
        raise ProjectError(f"{finding.id}: the checked mismatch has no drawable observation; "
                           f"run {PROG} check {finding.model}")
    observations = comparison.get("replayed_steps", [])
    native_steps = run.get("native", {}).get("steps", [])
    model_steps = run.get("trace", {}).get("steps", [])
    prefix = len(native_steps) - len(model_steps)
    lines, arrows = ["flowchart LR"], 0

    def value(data):
        return _esc(json.dumps(data, ensure_ascii=False, sort_keys=True))

    def box(identifier, title, rows):
        label = "<br/>".join([title, *rows])
        lines.append(f'  {identifier}["{label}"]')

    for index, step in enumerate(expected[:failed]):
        name = "construction / declared prefix" if index == 0 else step["function_name"]
        call = name if index == 0 else name + " " + json.dumps(step["function_input"], ensure_ascii=False, sort_keys=True)
        box(f"E{index}", "model expected", [_esc(name), "state: " + value(step["new_state"]),
            "output: " + value(step["function_output"]), "outcome: " + _esc(step["label"])])
        raw = native_steps[prefix + index - 1] if index > 0 else None
        if index < len(observations):
            observed = observations[index]
            rows = ["state: " + value(observed["observed_state"]),
                    "output: " + value(observed["observed_output"]),
                    "outcome: " + _esc(observed["label"])]
        else:
            # Retain actual projection errors and native facts. Expected state/output
            # never fills a missing observation, including unknown real values.
            message = "; ".join(row["message"] for row in comparison["violations"]
                                if row["step_index"] == index + 1)
            rows = ["projection unavailable: " + _esc(message)]
            if raw is not None:
                rows.append("native value graph: " + value(raw["value"]))
        if raw is not None:
            rows += ["native outcome: " + _esc(raw["outcome"]), "actual call: " + value(raw["call"])]
        box(f"O{index}", "code observed", [_esc(name), *rows])
        if index:
            lines.append(f'  E{index - 1} -- "{_esc(call)}" --> E{index}')
            lines.append(f'  O{index - 1} -- "recorded native call" --> O{index}')
            arrows += 2
    message = "; ".join(row["message"] for row in comparison["violations"] if row["step_index"] == failed)
    lines.append(f'  E{failed - 1} -. "{_esc(message)}" .-> O{failed - 1}')
    lines += ["  classDef drift fill:#fdd,stroke:#c00,stroke-width:2px",
              f"  class E{failed - 1},O{failed - 1} drift"]
    first = (f"{finding.model}: MODEL DRIFT {finding.subject}; model expected / code observed; "
             f"checked witness through observation {failed} (construction then calls); "
             "finite native observations, not a model-domain state graph")
    return first, "\n".join(lines) + "\n", 2 * failed, arrows + 1


def draw_drift(ctx, cached):
    from .diagram import picture_name, picture_text, write_pictures
    core, finding, run = cached
    if ctx.spec.option("native_core", core.digest) != core.digest:
        raise ProjectError(f"{finding.id}: checked native evidence changed; run {PROG} check {finding.model}")
    line, text, boxes, arrows = _text(finding, run)
    name = picture_name(ctx.spec.model, finding, text, True)
    (files, reason), = write_pictures(ctx.root, [(name, text)])
    info = {"first_line": picture_text(line, files, reason), "mermaid": text,
            "subject": finding.subject, "subject_id": finding.id, "drawn": True,
            "files": files, "rendered": reason is None, "reason": reason,
            "boxes": boxes, "arrows": arrows,
            "native_core": core.digest,
            "native": {"bound": True, "footprints": core.info["native"]["footprints"]}}
    return PartResult(ctx.spec.kind, ctx.spec.model, part_digest(ctx.root, ctx.spec, core.reads),
                      core.complete, [], info, core.reads, files if reason is None else files[:1])
