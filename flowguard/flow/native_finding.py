"""One native drift identity and witness selection for check and its picture."""
from dataclasses import dataclass, field
import ast
import pprint
import hashlib
import json

from .checks import CONFLICT, Finding, make_finding


@dataclass(frozen=True)
class _NativeFinding(Finding):
    # Persist through the conflict owner, not the public Finding.to_json surface.
    native_origin: dict = field(default_factory=dict, repr=False, compare=False)


def oracle_identity(trace):
    """Identify the model oracle without publishing its states or expected outputs."""
    if not isinstance(trace, dict) or not isinstance(trace.get("steps"), list):
        return None
    keys = ("external_input", "function_name", "function_input", "function_output", "old_state", "new_state", "label")
    oracle = {"initial_state": trace.get("initial_state"),
              "steps": [{key: row.get(key) for key in keys} for row in trace["steps"]]}
    return hashlib.sha256(json.dumps(oracle, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _inputs_literal(data):
    if isinstance(data.get("replay_inputs_literal"), str):
        return data["replay_inputs_literal"]
    # Existing checked AdapterRuns already retained their actual inputs; this is
    # a format upgrade of that receipt, never a reconstruction from expected output.
    rows = data.get("inputs")
    if not isinstance(rows, list) or any(not isinstance(row, dict) or
            set(row) != {"function", "arguments", "external_input"} for row in rows):
        return None
    values = [{"external_input": row["external_input"], "function_name": row["function"],
               "function_input": row["arguments"]} for row in rows]
    text = pprint.pformat(values, sort_dicts=False, width=100)
    return text if ast.literal_eval(text) == values else None


def native_drift(model, core):
    """The canonical finding and its first actual cached AdapterRun, or None."""
    native = core.info.get("native", {}) if core is not None else {}
    if native.get("status") != "drift":
        return None
    mismatches = [(key, data) for key, data in native.get("checks", {}).items()
                  if data.get("status") == "drift"]
    if native.get("walk", {}).get("status") == "drift":
        mismatches.append(("walk", native["walk"]))
    key, data = mismatches[0] if mismatches else ("", {})
    summary = {"check": key, "reason": data.get("reason", ""),
               "other_mismatches": max(0, len(mismatches) - 1),
               "record": f".flowguard/cache/flow/parts/{core.digest}.json"}
    finding = make_finding("MODEL DRIFT", CONFLICT, model, "native model correspondence",
                           "the model and real code differ; inspect the actual conformance path before deciding which side is stale",
                           detail={"native": summary, "code_status": "drift"})
    origin = {"schema": "flowguard.native-drift-origin.v1", "inputs_literal": _inputs_literal(data),
              "code_inputs": native.get("code_inputs"),
              "model_oracle_digest": oracle_identity(data.get("trace")),
              "witness": {"record": summary["record"], "check": key}}
    finding = _NativeFinding(**finding.__dict__, native_origin=origin)
    return finding, data
