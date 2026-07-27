"""Executable serial/parallel equivalence proof for model regressions."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from .model_regressions import (
    ModelRegressionEntry,
    ModelRegressionManifest,
    input_inventory_fingerprint,
    resolve_entry_input_inventory,
)


PROOF_SCHEMA = "flowguard.model_shard_safety_proof.v1"
CONTRACT_SCHEMA = "flowguard.model_shard_safety_contract.v1"


@dataclass(frozen=True)
class ShardSafetyRun:
    run_id: str
    output_dir: str
    exit_code: int
    result_path: str
    result_sha256: str
    projection: Mapping[str, Any]
    artifact_paths: tuple[str, ...]
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and bool(self.projection.get("ok"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "output_dir": self.output_dir,
            "exit_code": self.exit_code,
            "ok": self.ok,
            "result_path": self.result_path,
            "result_sha256": self.result_sha256,
            "projection": dict(self.projection),
            "artifact_paths": list(self.artifact_paths),
            "stdout_tail": self.stdout_tail if not self.ok else "",
            "stderr_tail": self.stderr_tail if not self.ok else "",
        }


def _sha256(path: Path) -> str:
    return f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"


def _repository_files(root: Path) -> tuple[Path, ...]:
    completed = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError("git file inventory is required for shard-safety proof")
    return tuple(
        root / item.decode("utf-8", errors="surrogateescape")
        for item in completed.stdout.split(b"\0")
        if item
    )


def _repository_snapshot(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in _repository_files(root):
        relative = path.relative_to(root).as_posix()
        result[relative] = _sha256(path) if path.is_file() else "<missing>"
    return result


def _semantic_projection(payload: Mapping[str, Any]) -> dict[str, Any]:
    runs = tuple(
        {
            "run_id": str(item.get("run_id", "")),
            "ok": bool(item.get("ok")),
            "exit_code": item.get("exit_code"),
        }
        for item in payload.get("evidence_runs", ())
        if isinstance(item, Mapping)
    )
    reports: dict[str, Any] = {}
    for name, report in sorted(dict(payload.get("reports", {})).items()):
        if not isinstance(report, Mapping):
            reports[str(name)] = report
            continue
        reports[str(name)] = {
            "ok": bool(report.get("ok")),
            "decision": report.get("decision"),
            "findings": report.get("findings", ()),
        }
    return {
        "ok": bool(payload.get("ok")),
        "evidence_generation_ok": bool(payload.get("evidence_generation_ok")),
        "canonical_contract_chain_ok": bool(payload.get("canonical_contract_chain_ok")),
        "evidence_runs": runs,
        "child_results": dict(sorted(dict(payload.get("child_results", {})).items())),
        "reports": reports,
    }


def _run_copy(root: Path, entry: ModelRegressionEntry, run_id: str, output_dir: Path) -> ShardSafetyRun:
    output_dir.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ)
    pythonpath = str(root)
    if env.get("PYTHONPATH"):
        pythonpath += os.pathsep + env["PYTHONPATH"]
    env.update(
        {
            "FLOWGUARD_OUTPUT_DIR": str(output_dir),
            "FLOWGUARD_MODEL_ID": entry.model_id,
            "PYTHONPATH": pythonpath,
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
        }
    )
    completed = subprocess.run(
        entry.command(root=root),
        cwd=root,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=entry.timeout_seconds,
    )
    result_path = output_dir / "result.json"
    payload: Mapping[str, Any] = {}
    if result_path.is_file():
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    artifacts = tuple(
        sorted(
            path.resolve().as_posix()
            for path in output_dir.rglob("*")
            if path.is_file()
        )
    )
    return ShardSafetyRun(
        run_id=run_id,
        output_dir=output_dir.resolve().as_posix(),
        exit_code=completed.returncode,
        result_path=result_path.resolve().as_posix(),
        result_sha256=_sha256(result_path) if result_path.is_file() else "",
        projection=_semantic_projection(payload),
        artifact_paths=artifacts,
        stdout_tail=completed.stdout[-4000:],
        stderr_tail=completed.stderr[-4000:],
    )


def _overlapping_artifacts(runs: Sequence[ShardSafetyRun]) -> tuple[str, ...]:
    seen: set[str] = set()
    overlaps: set[str] = set()
    for run in runs:
        current = set(run.artifact_paths)
        overlaps.update(seen & current)
        seen.update(current)
    return tuple(sorted(overlaps))


def prove_model_shard_safety(
    root: str | Path,
    entry: ModelRegressionEntry,
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run one serial baseline and concurrent copies under isolated output roots."""

    root_path = Path(root).resolve()
    contract = dict(entry.shard_safety_proof)
    if contract.get("schema_version") != CONTRACT_SCHEMA:
        raise ValueError(f"{entry.model_id}: missing current shard-safety proof contract")
    copies = int(contract.get("parallel_copies", 0))
    if copies < 2:
        raise ValueError("shard-safety proof requires at least two parallel copies")
    proof_root = (
        Path(output_dir).resolve()
        if output_dir is not None
        else Path(tempfile.mkdtemp(prefix=f"flowguard-shard-proof-{entry.model_id}-"))
    )
    proof_root.mkdir(parents=True, exist_ok=True)
    before_repository = _repository_snapshot(root_path)
    before_inventory = resolve_entry_input_inventory(root_path, entry)
    before_input_fingerprint = input_inventory_fingerprint(before_inventory)
    started = time.time()

    serial = _run_copy(root_path, entry, "serial-baseline", proof_root / "serial")
    with ThreadPoolExecutor(max_workers=copies, thread_name_prefix="flowguard-shard-proof") as executor:
        futures = tuple(
            executor.submit(
                _run_copy,
                root_path,
                entry,
                f"parallel-{index + 1}",
                proof_root / f"parallel-{index + 1}",
            )
            for index in range(copies)
        )
        parallel = tuple(future.result() for future in futures)
    runs = (serial, *parallel)

    after_inventory = resolve_entry_input_inventory(root_path, entry)
    after_input_fingerprint = input_inventory_fingerprint(after_inventory)
    after_repository = _repository_snapshot(root_path)
    repository_mutations = tuple(
        sorted(
            path
            for path in set(before_repository) | set(after_repository)
            if before_repository.get(path) != after_repository.get(path)
        )
    )
    projections = tuple(run.projection for run in runs)
    semantic_equivalence = bool(projections) and all(item == projections[0] for item in projections[1:])
    overlaps = _overlapping_artifacts(runs)
    checks = {
        "all_runs_passed": all(run.ok for run in runs),
        "serial_parallel_semantic_equivalence": semantic_equivalence,
        "disjoint_artifact_ownership": not overlaps,
        "stable_input_inventory": before_input_fingerprint == after_input_fingerprint,
        "zero_repository_mutation": not repository_mutations,
    }
    ok = all(checks.values())
    receipt = {
        "schema_version": PROOF_SCHEMA,
        "proof_id": str(contract.get("proof_id", "")),
        "model_id": entry.model_id,
        "ok": ok,
        "terminal": True,
        "contract": contract,
        "input_inventory_fingerprint": before_input_fingerprint,
        "post_input_inventory_fingerprint": after_input_fingerprint,
        "checks": checks,
        "repository_mutations": list(repository_mutations),
        "overlapping_artifact_paths": list(overlaps),
        "runs": [run.to_dict() for run in runs],
        "started_at_epoch": started,
        "finished_at_epoch": time.time(),
        "claim_boundary": (
            "This receipt proves serial/parallel equivalence and shared-state isolation only "
            "for the exact model inputs, runner, environment, and proof contract recorded here."
        ),
    }
    encoded = json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    receipt["receipt_fingerprint"] = f"sha256:{hashlib.sha256(encoded).hexdigest()}"
    (proof_root / "result.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return receipt


def prove_manifest_model_shard_safety(
    root: str | Path,
    model_id: str,
    *,
    output_dir: str | Path | None = None,
) -> dict[str, Any]:
    manifest = ModelRegressionManifest.load(root)
    matches = tuple(entry for entry in manifest.entries if entry.model_id == model_id)
    if len(matches) != 1:
        raise ValueError(f"expected exactly one manifest entry for {model_id!r}")
    return prove_model_shard_safety(root, matches[0], output_dir=output_dir)


__all__ = [
    "CONTRACT_SCHEMA",
    "PROOF_SCHEMA",
    "ShardSafetyRun",
    "prove_manifest_model_shard_safety",
    "prove_model_shard_safety",
]
