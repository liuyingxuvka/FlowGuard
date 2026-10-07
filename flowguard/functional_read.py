"""Strict, finite consumption of task-local functional evidence; never a producer."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Mapping


def strict_json_bytes(payload: bytes):
    def pairs(rows):
        result = {}
        for key, value in rows:
            if key in result:
                raise ValueError("duplicate JSON key: " + key)
            result[key] = value
        return result
    def bad_constant(value):
        raise ValueError("non-finite JSON number: " + value)
    return json.loads(payload.decode("utf-8"), object_pairs_hook=pairs, parse_constant=bad_constant)


def exact_record(value, expected, label):
    if not isinstance(value, Mapping) or set(value) != set(expected):
        raise ValueError(label + " has missing or unknown fields")
    return dict(value)


def _wire_shape(value, template, label, *, string_arrays=()):
    """Check explicit type projections before constructors can coerce values."""
    data = exact_record(value, template, label)
    for key, expected in template.items():
        actual = data[key]
        if isinstance(expected, bool):
            valid = type(actual) is bool
        elif isinstance(expected, int):
            valid = type(actual) is int
        elif isinstance(expected, str):
            valid = isinstance(actual, str)
        elif isinstance(expected, list):
            valid = isinstance(actual, list)
        elif isinstance(expected, dict):
            valid = isinstance(actual, dict)
        else:
            valid = actual is None or isinstance(actual, dict)
        if not valid:
            raise ValueError(label + "." + key + " has an invalid wire type")
        if key in string_arrays:
            if any(not isinstance(item, str) for item in actual) or len(actual) != len(set(actual)):
                raise ValueError(label + "." + key + " must contain unique strings")
    return data


def _roundtrip(record, value, label):
    if json.dumps(record.to_dict(), sort_keys=True, allow_nan=False) != json.dumps(value, sort_keys=True, allow_nan=False):
        raise ValueError(label + " is not its exact canonical projection")
    return record


def parse_task_fact_observation(value):
    from .task_coverage_demand import TaskFactObservation
    template = TaskFactObservation("wire", "request").to_dict()
    return _roundtrip(TaskFactObservation(**_wire_shape(value, template, "task observation")), value, "task observation")


def parse_task_fact_source_snapshot(value):
    from .task_coverage_demand import TaskFactSourceSnapshot
    template = TaskFactSourceSnapshot("request", "wire", "sha256:" + "0" * 64).to_dict()
    data = _wire_shape(value, template, "task source snapshot")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", data["source_fingerprint"]):
        raise ValueError("task source fingerprint must be an exact sha256 identity")
    data["observations"] = tuple(parse_task_fact_observation(row) for row in data["observations"])
    return _roundtrip(TaskFactSourceSnapshot(**data), value, "task source snapshot")


def parse_task_facts(value):
    from .task_coverage_demand import TaskFacts
    arrays = ("requested_outcome_ids", "affected_surface_ids", "change_kinds", "risk_signal_ids", "related_model_ids", "topology_signal_ids", "caller_requested_owner_ids")
    data = _wire_shape(value, TaskFacts("wire", "wire").to_dict(), "task facts", string_arrays=arrays)
    snapshots = tuple(parse_task_fact_source_snapshot(row) for row in data["source_snapshots"])
    observations = tuple(parse_task_fact_observation(row) for row in data["fact_observations"])
    keys = {(row.fact_id, row.source_plane) for snapshot in snapshots for row in snapshot.observations}
    data["fact_observations"] = tuple(row for row in observations if (row.fact_id, row.source_plane) not in keys)
    data["source_snapshots"] = snapshots
    return _roundtrip(TaskFacts(**data), value, "task facts")


def parse_coverage_demand_row(value):
    from .task_coverage_demand import CoverageDemandRow
    template = CoverageDemandRow("wire", "wire", "wire", (), False, "not_triggered", "wire").to_dict()
    data = _wire_shape(value, template, "coverage row", string_arrays=("coverage_ids", "evidence_ids", "evidence_fingerprints", "blocker_codes"))
    return _roundtrip(CoverageDemandRow(**data), value, "coverage row")


def parse_owner_coverage_resolution(value):
    from .task_coverage_demand import OwnerCoverageResolution
    template = OwnerCoverageResolution("wire", "wire", "wire", "sha256:" + "0" * 64, "existing_model_preflight", "blocked", ("wire",), blocker_codes=("wire",)).to_dict()
    data = _wire_shape(value, template, "owner resolution", string_arrays=("obligation_ids", "evidence_ids", "evidence_fingerprints", "blocker_codes"))
    return _roundtrip(OwnerCoverageResolution(**data), value, "owner resolution")


def parse_task_coverage_demand(value):
    from .task_coverage_demand import TaskCoverageDemand
    data = _wire_shape(value, TaskCoverageDemand("wire", "wire", "sha256:" + "0" * 64, "ordinary", ()).to_dict(), "coverage demand", string_arrays=("fact_diagnostic_codes",))
    data["rows"] = tuple(parse_coverage_demand_row(row) for row in data["rows"])
    data["fact_observations"] = tuple(parse_task_fact_observation(row) for row in data["fact_observations"])
    data["source_snapshots"] = tuple(parse_task_fact_source_snapshot(row) for row in data["source_snapshots"])
    return _roundtrip(TaskCoverageDemand(**data), value, "coverage demand")


def parse_model_maturation_report(value):
    from .model_maturation import ModelMaturationReport, ModelMaturationFinding, ModelMaturationIteration
    from .maintenance_obligation import MaintenanceObligation
    from .model_path_quality import normalize_path_quality_material
    arrays = ("recommended_actions", "scoped_signal_ids", "required_path_quality_model_ids", "path_quality_subject_fingerprints", "path_quality_result_fingerprints", "next_actions", "open_gap_fingerprints", "owner_resolution_ids", "owner_resolution_fingerprints", "owner_resolution_owner_ids")
    data = _wire_shape(value, ModelMaturationReport(False, "wire", "blocked", "blocked").to_dict(), "maturation report", string_arrays=arrays)
    data["findings"] = tuple(_roundtrip(ModelMaturationFinding(**_wire_shape(row, ModelMaturationFinding("wire", "wire").to_dict(), "maturation finding")), row, "maturation finding") for row in data["findings"])
    obligation_template = MaintenanceObligation("wire", "wire", "wire").to_dict()
    obligation_arrays = tuple(key for key, item in obligation_template.items() if isinstance(item, list))
    data["maintenance_obligations"] = tuple(_roundtrip(MaintenanceObligation(**_wire_shape(row, obligation_template, "maintenance obligation", string_arrays=obligation_arrays)), row, "maintenance obligation") for row in data["maintenance_obligations"])
    required, subjects, results = normalize_path_quality_material(data["required_path_quality_model_ids"], data["path_quality_subjects"], data["path_quality_results"])
    data.update(required_path_quality_model_ids=required, path_quality_subjects=subjects, path_quality_results=results)
    if data["iteration_record"] is not None:
        template = ModelMaturationIteration("wire", "wire", "wire", 0, "wire", "wire", "wire", "wire").to_dict()
        record = _wire_shape(data["iteration_record"], template, "maturation iteration", string_arrays=tuple(k for k,v in template.items() if isinstance(v, list)))
        data["iteration_record"] = _roundtrip(ModelMaturationIteration(**{k:v for k,v in record.items() if k != "iteration_fingerprint"}), record, "maturation iteration")
    return _roundtrip(ModelMaturationReport(**data), value, "maturation report")


def normalize_functional_artifact_path(value):
    if not isinstance(value, str):
        raise ValueError("functional artifact path must be a string")
    path = PurePosixPath(value)
    if not value or "\\" in value or path.is_absolute() or PureWindowsPath(value).drive or any(part in {".", ".."} for part in path.parts) or path.as_posix() != value:
        raise ValueError("functional artifact path must be canonical repository-relative")
    return value


def read_root_reference(root: Path, reference: Mapping, read_context=None):
    from .model_authority_store import _selected_file_bytes
    if read_context is not None and Path(root).resolve() != read_context.root:
        raise ValueError("functional reference context belongs to another root")
    ref = exact_record(reference, ("path", "sha256"), "file reference")
    path = normalize_functional_artifact_path(ref["path"])
    if not isinstance(ref["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
        raise ValueError("functional raw fingerprint must be 64 lowercase hexadecimal digits")
    raw = read_context.artifact_bytes(path) if read_context is not None else _selected_file_bytes(root, path)
    current = (read_context.raw_fingerprint(path, artifact=True).removeprefix("sha256:")
               if read_context is not None else hashlib.sha256(raw).hexdigest())
    if current != ref["sha256"]:
        raise ValueError("functional input raw fingerprint changed: " + path)
    return strict_json_bytes(raw)


def functional_gap(code, *, task_id="", reference="", next_owner="task-model-maturation", reason=""):
    return {"task_id": task_id, "stopping_disposition": "needs_evidence", "gap_ids": [code],
        "first_gap": {"gap_id": code, "input_ref": reference, "next_owner_id": next_owner, "reason": reason},
        "next_actions": [next_owner + ":" + code], "deepest_proven_layer": "unknown"}


GROWTH_FIELDS = ("schema", "task_id", "accepted_head_fingerprint", "source_kind",
                 "source_request_ref", "declared_path_changes", "observations", "observation_fingerprint")


def normalize_observed_path_changes(rows):
    """Validate finite declarations; declarations never prove historical events."""
    if not isinstance(rows, (list, tuple)):
        raise ValueError("observed path changes must be an array")
    normalized = []
    for raw in rows:
        row = exact_record(raw, ("kind", "path", "previous_path"), "observed path change")
        if row["kind"] not in {"add", "modify", "delete", "rename"}:
            raise ValueError("unknown observed path change kind")
        normalize_functional_artifact_path(row["path"])
        previous = row["previous_path"]
        if not isinstance(previous, str):
            raise ValueError("previous path must be a string")
        if row["kind"] == "rename":
            normalize_functional_artifact_path(previous)
            if previous == row["path"]:
                raise ValueError("rename must name different old and new paths")
        elif previous:
            raise ValueError("only rename may name a previous path")
        normalized.append(row)
    identities = [(row["kind"], row["path"], row["previous_path"]) for row in normalized]
    if len(identities) != len(set(identities)):
        raise ValueError("duplicate observed path declaration")
    return normalized


def observed_change_paths(rows):
    return tuple(sorted({path for row in normalize_observed_path_changes(rows)
                         for path in (row["path"], row["previous_path"]) if path}))


def observe_functional_growth_paths(read_context, paths):
    """Record exact finite present/missing/unavailable states using one cache."""
    from .model_authority_store import _selected_path_is_missing
    from .model_authority import ModelAuthorityError
    observations = []
    for path in sorted(set(paths)):
        normalize_functional_artifact_path(path)
        try:
            row = {"path": path, "state": "present",
                   "raw_fingerprint": read_context.raw_fingerprint(path), "message": ""}
        except (OSError, ValueError, ModelAuthorityError) as exc:
            try:
                missing = _selected_path_is_missing(read_context.root, path, accounting=read_context.accounting)
            except (OSError, ValueError, ModelAuthorityError):
                missing = False
            if missing:
                read_context.missing_paths.add(path)
            row = {"path": path, "state": "missing" if missing else "unavailable",
                   "raw_fingerprint": "", "message": "" if missing else str(exc)}
        observations.append(row)
    return observations


def load_functional_growth_observation(*, repository_root, growth_observation_ref,
                                      accepted_head_fingerprint, read_context, task_id=None):
    """Authenticate an original finite request, its observation and current bytes."""
    from .model_authority import canonical_fingerprint
    root = Path(repository_root).resolve()
    if root != read_context.root:
        raise ValueError("growth read context belongs to another root")
    doc = exact_record(read_root_reference(root, growth_observation_ref, read_context),
                       GROWTH_FIELDS, "functional growth observation")
    if (doc["schema"] != "flowguard.functional_growth_observation.v1"
            or doc["source_kind"] != "explicit_task_paths"
            or not isinstance(doc["task_id"], str) or not doc["task_id"]
            or doc["accepted_head_fingerprint"] != accepted_head_fingerprint
            or (task_id is not None and doc["task_id"] != task_id)):
        raise ValueError("functional growth task/head identity differs")
    payload = {key: doc[key] for key in GROWTH_FIELDS if key != "observation_fingerprint"}
    if canonical_fingerprint(payload) != doc["observation_fingerprint"]:
        raise ValueError("functional growth observation fingerprint differs")
    changes = normalize_observed_path_changes(doc["declared_path_changes"])
    source = exact_record(read_root_reference(root, doc["source_request_ref"], read_context),
        ("task_id", "purpose", "requested_outcome_ids", "read_only", "implementation_requested",
         "release_requested", "declared_path_changes"), "original functional request plane")
    if (not isinstance(source, Mapping) or source.get("task_id") != doc["task_id"]
            or source.get("declared_path_changes") != changes):
        raise ValueError("functional growth original request differs")
    paths = observed_change_paths(changes)
    if not paths or not isinstance(doc["observations"], list):
        raise ValueError("functional growth requires nonempty original paths")
    recorded = []
    for raw in doc["observations"]:
        row = exact_record(raw, ("path", "state", "raw_fingerprint", "message"), "growth observation row")
        normalize_functional_artifact_path(row["path"])
        if (row["state"] not in {"present", "missing", "unavailable"}
                or not isinstance(row["message"], str)
                or not isinstance(row["raw_fingerprint"], str)
                or (row["state"] == "present" and not re.fullmatch(r"sha256:[0-9a-f]{64}", row["raw_fingerprint"]))
                or (row["state"] != "present" and row["raw_fingerprint"])):
            raise ValueError("invalid growth observation state")
        recorded.append(row)
    if tuple(row["path"] for row in recorded) != paths:
        raise ValueError("functional growth finite path denominator differs")
    current = observe_functional_growth_paths(read_context, paths)
    if current != recorded:
        raise ValueError("functional growth observed state or raw bytes changed")
    return doc


def functional_task_growth_reference(*, repository_root, task_context_ref, read_context):
    """Select the one original public-surface observation, never synthesize paths."""
    root = Path(repository_root).resolve()
    doc = read_root_reference(root, task_context_ref, read_context)
    facts = parse_task_facts(read_root_reference(root, doc["task_facts_ref"], read_context))
    surfaces = [row for row in facts.source_snapshots if row.source_plane == "public_surface"]
    if len(surfaces) != 1:
        raise ValueError("functional task lacks one original public surface plane")
    plane = read_root_reference(root, {"path": surfaces[0].source_ref,
        "sha256": surfaces[0].source_fingerprint.removeprefix("sha256:")}, read_context)
    exact_record(plane, ("affected_surface_ids", "source", "growth_observation_ref"), "functional public surface plane")
    return plane["growth_observation_ref"]

def apply_functional_growth_to_selected_read(*, repository_root, selected_read, read_context,
                                            task_context_ref=None, growth_observation_ref=None,
                                            functional_understanding=None):
    """Consume one original growth ref and update the already-built closure."""
    from dataclasses import replace
    from .model_authority_store import _observe_growth_paths
    original = None
    task_id = None
    if task_context_ref is not None:
        if functional_understanding is None or "functional_task_context_invalid" in functional_understanding.get("gap_ids", ()):
            raise ValueError("invalid task context cannot authorize growth inputs")
        task_id = functional_understanding["task_id"]
        original = functional_task_growth_reference(repository_root=repository_root,
            task_context_ref=task_context_ref, read_context=read_context)
        if growth_observation_ref is not None and growth_observation_ref != original:
            raise ValueError("read growth observation differs from original task input")
    else:
        original = growth_observation_ref
    if original is None:
        return selected_read, None
    observed = load_functional_growth_observation(repository_root=repository_root,
        growth_observation_ref=original, accepted_head_fingerprint=selected_read.authority_head_fingerprint,
        task_id=task_id, read_context=read_context)
    growth = _observe_growth_paths(read_context, observed_change_paths(observed["declared_path_changes"]))
    architecture = dict(selected_read.architecture)
    if growth["growth_gaps"]:
        architecture["facts_scope"] = [dict(row, understanding_status="needs_evidence")
                                      for row in architecture.get("facts_scope", ())]
    return replace(selected_read, architecture=architecture, **growth), original


DIAGNOSTIC_FIELDS = ("schema", "task_id", "accepted_head_fingerprint", "task_facts_ref",
    "coverage_demand_ref", "maturation_report_ref", "preflight_report_ref", "prerequisite_report_ref",
    "input_refs", "missing_paths", "producer_source_sha256", "command", "status",
    "first_gap", "gap_ids", "next_actions", "terminal_reason", "claim_boundary", "growth_report_ref")
PRODUCER_SOURCE_NAMES = ("functional_task_context.py", "functional_read.py",
                         "model_maturation.py", "model_maturation_receipt.py")


def derive_functional_diagnostic_projection(*, repository_root, diagnostic, facts, read_context):
    """Copy only actual non-success report observations; never create verified evidence."""
    root = Path(repository_root).resolve()
    report = None
    rows, report_path, terminal = [], "", "needs_evidence"
    actions = []
    if diagnostic["maturation_report_ref"] is not None:
        ref = diagnostic["maturation_report_ref"]
        report = parse_model_maturation_report(read_root_reference(root, ref, read_context))
        if report.task_id != facts.task_id or report.terminal_reason == "model_maturation_closed_for_task":
            raise ValueError("diagnostic cannot transport a closed maturation claim")
        terminal = report.terminal_reason or report.decision or "needs_evidence"
        if terminal == "model_maturation_closed_for_task":
            raise ValueError("diagnostic cannot claim maturation success")
        report_path = ref["path"]
        rows = [{"gap_id": terminal, "input_ref": report_path, "next_owner_id": "task-model-maturation",
                 "reason": terminal}]
        actions = list(report.next_actions or report.recommended_actions)
    if diagnostic["growth_report_ref"] is not None:
        ref = diagnostic["growth_report_ref"]
        growth = exact_record(read_root_reference(root, ref, read_context),
            ("schema", "task_id", "accepted_head_fingerprint", "growth_observation_ref", "growth_gaps",
             "checked_observed_paths", "observation_fingerprint", "live_unregistered_file_detection"), "functional growth report")
        if (growth["schema"] != "flowguard.functional_growth_report.v1"
                or growth["task_id"] != facts.task_id
                or growth["accepted_head_fingerprint"] != diagnostic["accepted_head_fingerprint"]):
            raise ValueError("functional growth report identity differs")
        if not rows and growth["growth_gaps"]:
            rows = [{"gap_id": row["gap_id"], "input_ref": ref["path"],
                     "next_owner_id": row["next_owner_id"], "reason": row["next_action"]}
                    for row in growth["growth_gaps"]]
            actions = [row["next_owner_id"] + ":" + row["gap_id"] if row["next_owner_id"]
                       else row["next_action"] for row in growth["growth_gaps"]]
    if diagnostic["prerequisite_report_ref"] is not None:
        ref = diagnostic["prerequisite_report_ref"]
        prerequisite = exact_record(read_root_reference(root, ref, read_context),
            ("schema", "task_id", "task_fingerprint", "accepted_head_fingerprint", "checks", "ok",
             "native_execution_count", "final_maturation_dependency_count", "outcome_binding"), "diagnostic prerequisites")
        if (prerequisite.get("schema") != "flowguard.functional_task_prerequisites.v1"
                or prerequisite.get("task_id") != facts.task_id
                or prerequisite.get("task_fingerprint") != facts.fingerprint
                or prerequisite.get("accepted_head_fingerprint") != diagnostic["accepted_head_fingerprint"]
                or type(prerequisite.get("ok")) is not bool):
            raise ValueError("functional diagnostic prerequisite identity differs")
        if not isinstance(prerequisite["checks"], list) or not isinstance(prerequisite["outcome_binding"], dict):
            raise ValueError("functional diagnostic prerequisite records invalid")
        for counter in ("native_execution_count", "final_maturation_dependency_count"):
            if type(prerequisite[counter]) is not int or prerequisite[counter] != 0:
                raise ValueError("diagnostic prerequisite counter invalid")
        for check in prerequisite["checks"]:
            exact_record(check, ("check_id", "ok", "gap_ids"), "diagnostic prerequisite check")
            if (not isinstance(check["check_id"], str) or type(check["ok"]) is not bool
                    or not isinstance(check["gap_ids"], list)
                    or any(not isinstance(gap, str) for gap in check["gap_ids"])):
                raise ValueError("diagnostic prerequisite check type invalid")
        failed = [row for row in prerequisite["checks"] if row["ok"] is False]
        if not rows and failed:
            row = failed[0]
            gap_ids = row["gap_ids"] or [row["check_id"]]
            reason = prerequisite.get("outcome_binding", {}).get("reason", ",".join(gap_ids))
            rows = [{"gap_id": gap_id, "input_ref": ref["path"], "next_owner_id": "task-model-maturation",
                     "reason": reason} for gap_id in gap_ids]
    if diagnostic["preflight_report_ref"] is not None:
        ref = diagnostic["preflight_report_ref"]
        preflight = read_root_reference(root, ref, read_context)
        exact_record(preflight, ("preflight", "report"), "functional diagnostic preflight")
        from .existing_model_preflight import ExistingModelPreflight, ExistingModelPreflightReport, ExistingModelPreflightFinding
        _wire_shape(preflight["preflight"], ExistingModelPreflight("wire", "wire").to_dict(), "diagnostic original preflight")
        report_data = _wire_shape(preflight["report"], ExistingModelPreflightReport(False, "wire", "blocked").to_dict(), "diagnostic original preflight report")
        for finding in report_data["findings"]:
            _wire_shape(finding, ExistingModelPreflightFinding("wire", "wire").to_dict(), "diagnostic original preflight finding")
            if finding["severity"] not in {"blocker", "warning", "info"}:
                raise ValueError("diagnostic original preflight severity invalid")
        if preflight["preflight"].get("preflight_id") != "preflight:" + facts.task_id:
            raise ValueError("functional diagnostic preflight task differs")
        blockers = [row for row in preflight["report"]["findings"] if row["severity"] == "blocker"]
        if not rows and blockers:
            rows = [{"gap_id": row["code"], "input_ref": ref["path"], "next_owner_id": "existing-model-owner",
                     "reason": row["message"]} for row in blockers]
    if not rows:
        raise ValueError("functional diagnostic has no original non-success report")
    if not actions:
        actions = [row["next_owner_id"] + ":" + row["gap_id"] if row["next_owner_id"]
                   else row["reason"] for row in rows]
    return {"task_id": facts.task_id, "stopping_disposition": terminal,
        "gap_ids": list(dict.fromkeys(row["gap_id"] for row in rows)), "first_gap": rows[0],
        "next_actions": list(dict.fromkeys(actions)), "deepest_proven_layer": "unknown",
        "maturation_decision": report.decision if report is not None else "not_run",
        "maturation_terminal_reason": report.terminal_reason if report is not None else "needs_evidence",
        "maturation_confidence": report.confidence if report is not None else "blocked",
        "satisfied_outcome_ids": [], "missing_outcome_ids": list(facts.requested_outcome_ids)}


def _load_diagnostic_context(*, root, doc, facts, selected_read, read_context):
    diagnostic = exact_record(read_root_reference(root, doc["diagnostic_ref"], read_context),
                              DIAGNOSTIC_FIELDS, "functional diagnostic")
    if (doc["maturation_receipt_ref"] is not None
            or diagnostic["schema"] != "flowguard.functional_task_diagnostic.v1"
            or diagnostic["status"] != "needs_evidence"
            or diagnostic["claim_boundary"] != "diagnostic_observation_only"
            or diagnostic["task_id"] != facts.task_id
            or diagnostic["accepted_head_fingerprint"] != selected_read.authority_head_fingerprint
            or not isinstance(diagnostic["command"], str) or not diagnostic["command"]):
        raise ValueError("functional diagnostic task/head or authority boundary invalid")
    for key in ("task_facts_ref", "coverage_demand_ref", "maturation_report_ref"):
        if diagnostic[key] != doc[key]:
            raise ValueError("functional diagnostic context/report reference differs")
    if diagnostic["coverage_demand_ref"] is not None:
        demand = parse_task_coverage_demand(read_root_reference(root, diagnostic["coverage_demand_ref"], read_context))
        if demand.task_id != facts.task_id:
            raise ValueError("functional diagnostic demand task differs")
    if set(diagnostic["producer_source_sha256"]) != set(PRODUCER_SOURCE_NAMES):
        raise ValueError("functional diagnostic producer source inventory differs")
    for name, expected in diagnostic["producer_source_sha256"].items():
        from .functional_task_context import _producer_source_fingerprint
        if _producer_source_fingerprint(root, name, read_context) != expected:
            raise ValueError("functional diagnostic producer source changed")
    if not isinstance(diagnostic["input_refs"], list):
        raise ValueError("functional diagnostic inputs must be an array")
    paths = [ref["path"] for ref in diagnostic["input_refs"]]
    if paths != sorted(set(paths)):
        raise ValueError("functional diagnostic input denominator is not canonical")
    for ref in diagnostic["input_refs"]:
        # Source files need not contain JSON. Authenticate their exact raw bytes.
        exact_record(ref, ("path", "sha256"), "diagnostic input reference")
        path = normalize_functional_artifact_path(ref["path"])
        if not isinstance(ref["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", ref["sha256"]):
            raise ValueError("functional diagnostic input raw fingerprint invalid")
        if read_context.raw_fingerprint(path, artifact=True) != "sha256:" + ref["sha256"]:
            raise ValueError("functional diagnostic current input changed: " + path)
    missing = diagnostic["missing_paths"]
    if not isinstance(missing, list) or missing != sorted(set(missing)) or set(missing) & set(paths):
        raise ValueError("functional diagnostic missing paths are not canonical")
    from .model_authority_store import _selected_path_is_missing
    for path in missing:
        normalize_functional_artifact_path(path)
        if not _selected_path_is_missing(root, path, accounting=read_context.accounting):
            raise ValueError("functional diagnostic missing path became present: " + path)
        read_context.missing_paths.add(path)
    required = {ref["path"] for key, ref in diagnostic.items()
                if key.endswith("_ref") and ref is not None}
    if not required <= set(paths):
        raise ValueError("functional diagnostic original report input omitted")
    if {snapshot.source_plane for snapshot in facts.source_snapshots} != {
            "request", "current_model", "public_surface", "lifecycle"}:
        raise ValueError("functional diagnostic requires four independent source planes")
    for snapshot in facts.source_snapshots:
        preflight_ref = diagnostic["preflight_report_ref"]
        if (snapshot.source_plane == "current_model" and preflight_ref is not None
                and snapshot.source_ref == str(root / preflight_ref["path"])):
            # The native preflight projection carries its semantic report identity,
            # while the diagnostic inventory authenticates the original file bytes.
            # Bind this exact producer-owned plane to both identities.
            from .evidence_receipts import fingerprint_value
            preflight = exact_record(read_root_reference(root, preflight_ref, read_context),
                                     ("preflight", "report"), "original preflight projection")
            if (preflight_ref["path"] not in paths
                    or fingerprint_value(preflight["report"]) != snapshot.source_fingerprint
                    or preflight["report"].get("preflight_id") != preflight["preflight"].get("preflight_id")):
                raise ValueError("functional diagnostic preflight plane identity differs")
            continue
        if snapshot.source_ref not in paths:
            raise ValueError("functional diagnostic source plane omitted")
        read_root_reference(root, {"path": snapshot.source_ref,
            "sha256": snapshot.source_fingerprint.removeprefix("sha256:")}, read_context)
    from .functional_task_context import _current_selected_state, _finite_native_material
    state, _, _, _, _ = _current_selected_state(root, next(
        read_root_reference(root, ref, read_context)["primary_model_id"]
        for ref in diagnostic["input_refs"] if ref["path"].endswith("/producer-request.json")),
        read_context, selected_read)
    if doc["native_owner_receipt_refs"]:
        if {ref.get("owner_id") for ref in doc["native_owner_receipt_refs"] if isinstance(ref, Mapping)} != {
                "model:" + model for model in selected_read.selected_model_ids}:
            raise ValueError("functional diagnostic native leaf scope differs")
        try:
            _finite_native_material(root, state, doc["native_owner_receipt_refs"], read_context)
        except (OSError, ValueError, RuntimeError):
            # Diagnostic transport grants no current native authority. Failed
            # leaf currentness leaves its finite declaration unauthenticated.
            pass
    growth_ref = functional_task_growth_reference(repository_root=root,
        task_context_ref=doc["_context_ref"], read_context=read_context)
    if growth_ref is not None:
        growth = load_functional_growth_observation(repository_root=root, growth_observation_ref=growth_ref,
            accepted_head_fingerprint=selected_read.authority_head_fingerprint,
            task_id=facts.task_id, read_context=read_context)
        if growth_ref["path"] not in paths or growth["source_request_ref"]["path"] not in paths:
            raise ValueError("functional diagnostic growth inputs omitted")
        from .model_authority_store import _observe_growth_paths
        actual_growth = _observe_growth_paths(read_context, observed_change_paths(growth["declared_path_changes"]))
        original_growth = read_root_reference(root, diagnostic["growth_report_ref"], read_context)
        if original_growth["growth_observation_ref"] != growth_ref or any(
                original_growth[key] != (list(value) if isinstance(value, tuple) else value)
                for key, value in actual_growth.items()):
            raise ValueError("functional diagnostic growth report differs from current finite observation")
    result = derive_functional_diagnostic_projection(repository_root=root, diagnostic=diagnostic,
        facts=facts, read_context=read_context)
    for key in ("first_gap", "gap_ids", "next_actions", "terminal_reason"):
        actual = result["stopping_disposition"] if key == "terminal_reason" else result[key]
        if diagnostic[key] != actual:
            raise ValueError("functional diagnostic projection differs from original reports")
    result["gap_report_ref"] = doc["diagnostic_ref"]
    return result


def load_functional_read_context(*, repository_root, task_context_ref, selected_read, read_context):
    """Consume a finite original task and its canonical verified receipt, with no writes."""
    root = Path(repository_root).resolve()
    task_id = ""
    try:
        doc = read_root_reference(root, task_context_ref, read_context)
        doc = exact_record(doc, ("schema", "task_id", "task_facts_ref", "coverage_demand_ref", "maturation_report_ref", "maturation_receipt_ref", "outcome_refs", "native_owner_receipt_refs", "context_kind", "diagnostic_ref"), "functional task context")
        if doc["schema"] != "flowguard.functional_read_context.v1" or not isinstance(doc["task_id"], str):
            raise ValueError("invalid functional task context identity")
        task_id = doc["task_id"]
        facts = parse_task_facts(read_root_reference(root, doc["task_facts_ref"], read_context))
        if facts.task_id != task_id:
            raise ValueError("functional task identity differs")
        if not isinstance(doc["outcome_refs"], list) or not isinstance(doc["native_owner_receipt_refs"], list):
            raise ValueError("functional evidence selectors must be arrays")
        if doc["context_kind"] == "diagnostic":
            return _load_diagnostic_context(root=root, doc=dict(doc, _context_ref=task_context_ref),
                facts=facts, selected_read=selected_read, read_context=read_context)
        if doc["context_kind"] != "verified_maturation" or doc["diagnostic_ref"] is not None:
            raise ValueError("functional task context kind is invalid")
        demand = parse_task_coverage_demand(read_root_reference(root, doc["coverage_demand_ref"], read_context))
        report = parse_model_maturation_report(read_root_reference(root, doc["maturation_report_ref"], read_context))
        if facts.task_id != task_id or demand.task_id != task_id or report.task_id != task_id:
            raise ValueError("functional task identities differ")
        if not isinstance(doc["outcome_refs"], list) or not isinstance(doc["native_owner_receipt_refs"], list):
            raise ValueError("functional evidence selectors must be arrays")
        from .functional_task_context import verify_functional_task_context
        return verify_functional_task_context(root=root, doc=doc, facts=facts, demand=demand,
            report=report, selected_read=selected_read, read_context=read_context)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        return functional_gap("functional_task_context_invalid", task_id=task_id,
            reference=str(task_context_ref.get("path", "")) if isinstance(task_context_ref, Mapping) else "", reason=str(exc))
