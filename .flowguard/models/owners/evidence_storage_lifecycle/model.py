"""Finite storage-effect owner for retained evidence, independent of validation.

All physical mutations occur inside a fresh TemporaryDirectory owned by this
invocation. Current heads, pins and explicit preserve paths express storage
reachability. This owner does not infer every live producer or external
consumer, reinterpret target check results, or authorize production deletion.
"""
from __future__ import annotations

import json
from pathlib import Path
import tempfile

from flowguard.evidence_lifecycle import (
    EvidenceLifecycleError, PINS_SCHEMA, apply_evidence_gc, audit_evidence,
    evidence_execution_lease, fingerprint_payload, plan_evidence_gc, publish_run,
    purge_evidence_quarantine, read_current_head, read_evidence_execution_lease,
    resolve_object_path, restore_evidence_quarantine,
    settle_cleanup_unconfirmed_lease, store_text_object, verify_text_object,
    write_json_atomic,
)

MODEL_ID = "evidence_storage_lifecycle"
CASE_CONTRACTS = (
    ("storage_object_escape", "object_escape_rejected", "resolve_object_path",
     "descriptor ../outside", "EvidenceLifecycleError and outside bytes unchanged"),
    ("storage_object_identity_corruption", "corrupted_object_rejected", "verify_text_object",
     "stored gzip bytes altered", "verification False, never accepted as identical"),
    ("storage_foreign_authority_subject", "child_cannot_be_parent_or_replace_parent", "publish_run/read_current_head",
     "child consumer requests parent, or child attempts replacing parent head", "identity rejection and existing parent head unchanged"),
    ("storage_foreign_or_tampered_gc_plan", "foreign_root_and_plan_tamper_rejected", "apply_evidence_gc",
     "valid plan used against different root; unsigned plan field altered", "rejection before any path move"),
    ("storage_stale_gc_plan", "changed_candidate_stale_plan_rejected", "plan_evidence_gc/apply_evidence_gc",
     "candidate contents changed after planning", "rejection, original directories intact, no quarantine"),
    ("storage_reachable_evidence_removed", "forged_reachable_candidates_rejected", "audit_evidence/plan_evidence_gc/apply_evidence_gc",
     "current, pinned, explicitly preserved rows inserted into re-signed plan", "exact recomputation rejects and preserves all rows"),
    ("storage_restore_destination_collision", "restore_collision_rejected", "restore_evidence_quarantine",
     "original destination exists before restore", "collision rejected before move; quarantine and destination preserved"),
    ("storage_unknown_or_escaped_quarantine", "unknown_and_active_store_purge_rejected", "restore_evidence_quarantine/purge_evidence_quarantine",
     "unknown id, ../scope, receipts", "no deletion outside exact existing quarantine"),
    ("storage_invalid_current_purge", "invalid_current_blocks_purge", "audit_evidence/purge_evidence_quarantine",
     "current result bytes altered after quarantine", "audit blockers reject purge; quarantine remains"),
    ("storage_active_resource_reexecution", "active_resource_blocks_other_execution", "evidence_execution_lease",
     "same owner/resource leased with a second execution identity", "exclusive acquisition rejects and first token remains"),
    ("storage_unconfirmed_cleanup_release", "wrong_episode_and_live_descendants_block_release", "settle_cleanup_unconfirmed_lease",
     "wrong episode token, then nonempty descendant observation", "both rejected and residual lease remains"),
)
PROTECTED_FAILURE_IDS = tuple(row[0] for row in CASE_CONTRACTS)


def _row(name, kind, ok, observation, finding=""):
    return {"name": name, "case_kind": kind, "ok": bool(ok), "expected_ok": True,
            "observed_status": observation["status"],
            "finding_codes": [finding] if finding else [],
            "observation_json": json.dumps(observation, sort_keys=True)}


def _denied(callback):
    try:
        callback()
    except EvidenceLifecycleError as error:
        return {"status": "violation", "error": type(error).__name__, "message": str(error)}
    return {"status": "ok", "error": ""}


def _publish(root, name, *, authority_kind="standalone", update_head=True, finished=1):
    run = root / "scope" / name
    result = run / "result.json"
    write_json_atomic(result, {"status": "fixture-only", "payload": name})
    manifest = publish_run(run, kind="storage-owner-fixture", status="fixture-only",
        result_path=result, started_at_epoch=0, finished_at_epoch=finished,
        update_head=update_head, authority_kind=authority_kind,
        parent_scope="fixture-parent" if authority_kind == "child" else "")
    return run, manifest


def _store(root):
    old, old_manifest = _publish(root, "old", finished=1)
    pinned, pinned_manifest = _publish(root, "pinned", finished=2)
    current, current_manifest = _publish(root, "current", finished=3)
    preserved, _ = _publish(root, "preserved", update_head=False, finished=4)
    write_json_atomic(root / "PINS.json", {"schema_version": PINS_SCHEMA,
        "pins": [{"run_path": "scope/pinned", "run_id": pinned_manifest["run_id"]}]})
    return old, pinned, current, preserved


def _plan(root):
    return plan_evidence_gc(root, keep=0, preserve_paths=("scope/preserved",))


def object_cases():
    with tempfile.TemporaryDirectory(prefix="flowguard-storage-object-") as directory:
        root = Path(directory)
        run = root / "run"
        text = "complete evidence\n" + "x" * 128
        first = store_text_object(run, text, tail_chars=12)
        second = store_text_object(run, text, tail_chars=12)
        object_path = resolve_object_path(run, first)
        good = (first == second and verify_text_object(run, first)
                and first["logical_bytes"] == len(text.encode())
                and first["diagnostic_tail"] == text[-12:] and first["diagnostic_truncated"])
        rows = [_row("complete_identity_and_deduplicated_storage", "good", good,
                     {"status": "ok" if good else "violation", "descriptor": first})]
        outside = root / "outside"
        outside.write_bytes(b"protected")
        denied = _denied(lambda: resolve_object_path(run, {**first, "object_path": "../outside"}))
        rows.append(_row("object_escape_rejected", "bad",
            denied["status"] == "violation" and outside.read_bytes() == b"protected", denied,
            "storage_object_escape"))
        original = object_path.read_bytes()
        object_path.write_bytes(original + b"corrupt")
        rejected = not verify_text_object(run, first)
        rows.append(_row("corrupted_object_rejected", "bad", rejected,
            {"status": "violation" if rejected else "ok", "verification": not rejected},
            "storage_object_identity_corruption"))
        return rows


def authority_cases():
    with tempfile.TemporaryDirectory(prefix="flowguard-storage-authority-") as directory:
        root = Path(directory)
        parent, _ = _publish(root, "parent", authority_kind="parent")
        head_bytes = (parent.parent / "CURRENT.json").read_bytes()
        parent_head = read_current_head(parent.parent, expected_authority_kind="parent")
        child_scope = root / "child-domain"
        child, _ = _publish(child_scope, "child", authority_kind="child")
        child_head = read_current_head(child.parent, expected_authority_kind="child")
        good = parent_head["authority_kind"] == "parent" and child_head["authority_kind"] == "child"
        rows = [_row("explicit_parent_and_child_namespaces", "good", good,
            {"status": "ok" if good else "violation", "parent": parent_head, "child": child_head})]
        read_denied = _denied(lambda: read_current_head(child.parent, expected_authority_kind="parent"))
        unbound_denied = _denied(lambda: read_current_head(child.parent))
        replace_denied = _denied(lambda: _publish(root, "foreign-child", authority_kind="child"))
        untouched = (parent.parent / "CURRENT.json").read_bytes() == head_bytes
        bad_ok = all(row["status"] == "violation" for row in (read_denied, unbound_denied, replace_denied)) and untouched
        rows.append(_row("child_cannot_be_parent_or_replace_parent", "bad", bad_ok,
            {"status": "violation" if bad_ok else "ok", "read": read_denied,
             "unspecified": unbound_denied, "replace": replace_denied, "parent_unchanged": untouched},
            "storage_foreign_authority_subject"))
        return rows


def gc_identity_cases():
    with tempfile.TemporaryDirectory(prefix="flowguard-storage-gc-identity-") as directory:
        root = Path(directory) / "store"
        old, pinned, current, preserved = _store(root)
        plan = _plan(root)
        selected = [row["path"] for row in plan["candidates"]]
        good = selected == ["scope/old"]
        rows = [_row("current_pin_and_explicit_preserve_excluded", "good", good,
            {"status": "ok" if good else "violation", "plan": plan})]
        foreign = _denied(lambda: apply_evidence_gc(Path(directory) / "foreign", plan))
        tampered = _denied(lambda: apply_evidence_gc(root, {**plan, "keep": 99}))
        intact = all(path.is_dir() for path in (old, pinned, current, preserved))
        ok = foreign["status"] == tampered["status"] == "violation" and intact
        rows.append(_row("foreign_root_and_plan_tamper_rejected", "bad", ok,
            {"status": "violation" if ok else "ok", "foreign": foreign, "tampered": tampered,
             "all_original_paths_intact": intact}, "storage_foreign_or_tampered_gc_plan"))

        audit = audit_evidence(root)
        forged_body = {key: value for key, value in plan.items() if key != "plan_id"}
        forged_body["candidates"] = [{key: row[key] for key in ("path", "classification", "fingerprint", "stored_bytes")}
                                     for row in audit["runs"]]
        forged = {**forged_body, "plan_id": fingerprint_payload(forged_body)}
        guarded = _denied(lambda: apply_evidence_gc(root, forged))
        intact = all(path.is_dir() for path in (old, pinned, current, preserved))
        ok = guarded["status"] == "violation" and intact and not (root / ".quarantine").exists()
        rows.append(_row("forged_reachable_candidates_rejected", "bad", ok,
            {"status": "violation" if ok else "ok", "denial": guarded, "all_reachable_intact": intact},
            "storage_reachable_evidence_removed"))

        (old / "late-evidence.txt").write_text("changed after frozen plan", encoding="utf-8")
        stale = _denied(lambda: apply_evidence_gc(root, plan))
        ok = stale["status"] == "violation" and old.is_dir() and not (root / ".quarantine").exists()
        rows.append(_row("changed_candidate_stale_plan_rejected", "bad", ok,
            {"status": "violation" if ok else "ok", "denial": stale}, "storage_stale_gc_plan"))
        return rows


def quarantine_cases():
    with tempfile.TemporaryDirectory(prefix="flowguard-storage-quarantine-") as directory:
        root = Path(directory)
        old, pinned, current, preserved = _store(root)
        original_bytes = (old / "result.json").read_bytes()
        current_bytes = (current / "result.json").read_bytes()
        receipt = apply_evidence_gc(root, _plan(root))
        quarantine = root / ".quarantine" / receipt["quarantine_id"]
        moved = quarantine / "runs/scope/old"
        moved_ok = (receipt["status"] == "pass" and not old.exists() and moved.is_dir()
                    and (moved / "result.json").read_bytes() == original_bytes
                    and all(path.is_dir() for path in (pinned, current, preserved)))
        rows = [_row("quarantine_moves_exact_unreachable_run", "good", moved_ok,
            {"status": "ok" if moved_ok else "violation", "receipt": receipt})]
        old.mkdir()
        (old / "collision.txt").write_bytes(b"protected collision")
        collision = _denied(lambda: restore_evidence_quarantine(root, receipt["quarantine_id"]))
        ok = (collision["status"] == "violation" and moved.is_dir()
              and (old / "collision.txt").read_bytes() == b"protected collision")
        rows.append(_row("restore_collision_rejected", "bad", ok,
            {"status": "violation" if ok else "ok", "denial": collision}, "storage_restore_destination_collision"))
        (old / "collision.txt").unlink()
        old.rmdir()
        restored = restore_evidence_quarantine(root, receipt["quarantine_id"])
        ok = (restored["restored"] == ["scope/old"] and not quarantine.exists()
              and (old / "result.json").read_bytes() == original_bytes
              and (current / "result.json").read_bytes() == current_bytes)
        rows.append(_row("restore_preserves_original_bytes", "good", ok,
            {"status": "ok" if ok else "violation", "receipt": restored}))

        denied = (
            _denied(lambda: restore_evidence_quarantine(root, "unknown")),
            _denied(lambda: purge_evidence_quarantine(root, "unknown")),
            _denied(lambda: purge_evidence_quarantine(root, "../scope")),
            _denied(lambda: purge_evidence_quarantine(root, "receipts")),
        )
        ok = all(row["status"] == "violation" for row in denied) and current.is_dir() and old.is_dir()
        rows.append(_row("unknown_and_active_store_purge_rejected", "bad", ok,
            {"status": "violation" if ok else "ok", "denials": denied}, "storage_unknown_or_escaped_quarantine"))

        receipt = apply_evidence_gc(root, _plan(root))
        quarantine = root / ".quarantine" / receipt["quarantine_id"]
        (current / "result.json").write_bytes(current_bytes + b"corrupt")
        denied = _denied(lambda: purge_evidence_quarantine(root, receipt["quarantine_id"]))
        ok = denied["status"] == "violation" and quarantine.is_dir()
        rows.append(_row("invalid_current_blocks_purge", "bad", ok,
            {"status": "violation" if ok else "ok", "denial": denied}, "storage_invalid_current_purge"))
        (current / "result.json").write_bytes(current_bytes)
        purged = purge_evidence_quarantine(root, receipt["quarantine_id"])
        final = root / ".quarantine/receipts" / ("purge-" + receipt["quarantine_id"] + ".json")
        pending = root / ".quarantine/receipts" / ("purge-pending-" + receipt["quarantine_id"] + ".json")
        ok = (purged["status"] == "pass" and not quarantine.exists() and final.is_file()
              and not pending.exists() and all(path.is_dir() for path in (pinned, current, preserved))
              and audit_evidence(root)["status"] == "pass")
        rows.append(_row("exact_purge_after_valid_reachability_audit", "good", ok,
            {"status": "ok" if ok else "violation", "receipt": purged}))
        return rows


def lease_cases():
    with tempfile.TemporaryDirectory(prefix="flowguard-storage-lease-") as directory:
        locks = Path(directory) / "leases"
        arguments = {"owner_id": "owner:storage-fixture", "resource_key": "resource:one",
                     "execution_key": "execution:first", "lease_token": "token:first"}
        with evidence_execution_lease(locks, **arguments) as lease:
            def second_execution():
                with evidence_execution_lease(locks, owner_id=arguments["owner_id"],
                        resource_key=arguments["resource_key"], execution_key="execution:second"):
                    pass
            denied = _denied(second_execution)
            current = read_evidence_execution_lease(locks, owner_id=arguments["owner_id"],
                resource_key=arguments["resource_key"], execution_key=arguments["execution_key"])
            ok = denied["status"] == "violation" and current["lease_token"] == "token:first"
            rows = [_row("active_resource_blocks_other_execution", "bad", ok,
                {"status": "violation" if ok else "ok", "denial": denied}, "storage_active_resource_reexecution")]
            lease["_preserve_residual"] = True
            lease["incident_episode_token"] = "episode:one"
        settlement = {"owner_id": arguments["owner_id"], "resource_key": arguments["resource_key"],
                      "execution_key": arguments["execution_key"]}
        wrong = _denied(lambda: settle_cleanup_unconfirmed_lease(locks, **settlement,
                        incident_episode_token="episode:foreign", descendant_process_ids=()))
        live = _denied(lambda: settle_cleanup_unconfirmed_lease(locks, **settlement,
                        incident_episode_token="episode:one", descendant_process_ids=(123,)))
        residual = read_evidence_execution_lease(locks, **settlement)
        ok = (wrong["status"] == live["status"] == "violation"
              and residual["cleanup_status"] == "cleanup_unconfirmed")
        rows.append(_row("wrong_episode_and_live_descendants_block_release", "bad", ok,
            {"status": "violation" if ok else "ok", "wrong_episode": wrong, "live_descendants": live},
            "storage_unconfirmed_cleanup_release"))
        settle_cleanup_unconfirmed_lease(locks, **settlement,
            incident_episode_token="episode:one", descendant_process_ids=())
        cleared = read_evidence_execution_lease(locks, **settlement) is None
        rows.append(_row("exact_episode_and_reported_zero_settle_residual", "good", cleared,
            {"status": "ok" if cleared else "violation", "lease_absent": cleared,
             "boundary": "fixture-created lease, exact episode, caller-provided zero observation; not an independent production process-tree proof"}))
        return rows


def run_review():
    cases = object_cases() + authority_cases() + gc_identity_cases() + quarantine_cases() + lease_cases()
    return {"native_cases": cases, "claim_boundary": __doc__}


def export_path_quality_source(model_instance_fingerprint):
    from flowguard.model_path_quality import compile_declared_path_quality_source
    from flowguard.source_identity import functional_source_fingerprint
    root = Path(__file__).resolve().parents[4]
    paths = (".flowguard/models/owners/evidence_storage_lifecycle/model.py",
             ".flowguard/verification/owners/evidence_storage_lifecycle/run_checks.py",
             "flowguard/evidence_lifecycle.py", "flowguard/_hashing.py")
    contracts = {failure: {"protected_failure_id": failure, "known_bad_case_id": bad,
                          "actual_apis": apis, "finite_input": inputs, "required_observation": observed,
                          "mutation_boundary": "fresh invocation-owned TemporaryDirectory only",
                          "claim_boundary": "storage identity and effects; no target check success or unregistered live-consumer inference"}
                 for failure, bad, apis, inputs, observed in CASE_CONTRACTS}
    return compile_declared_path_quality_source(model_id=MODEL_ID,
        model_instance_fingerprint=model_instance_fingerprint, graph_scope="native_check_contract",
        source_refs=tuple({"path": path, "source_fingerprint": functional_source_fingerprint(root, path)} for path in paths),
        declared_contracts=contracts)
