"""Budgeted graph/model-group execution for large FlowGuard models."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .core import InvariantResult
from .export import to_jsonable
from .loop import GraphEdge
from .schema import SCHEMA_VERSION


TransitionFn = Callable[[Any], Iterable[GraphEdge | tuple[str, Any]]]
StateIdFn = Callable[[Any], str]
StateEncoder = Callable[[Any], Any]
StateDecoder = Callable[[Any], Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stable_json(value: Any) -> str:
    return json.dumps(to_jsonable(value), sort_keys=True, separators=(",", ":"))


def _default_state_id(state: Any) -> str:
    return _stable_json(state)


def _default_encode_state(state: Any) -> Any:
    return to_jsonable(state)


def _default_decode_state(payload: Any) -> Any:
    return payload


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", value.strip())
    return safe.strip("._-") or "model"


def _callable_name(value: Any) -> str:
    return str(getattr(value, "__module__", "")) + "." + str(
        getattr(value, "__qualname__", getattr(value, "__name__", type(value).__name__))
    )


def _invariant_name(invariant: Any) -> str:
    return str(getattr(invariant, "name", getattr(invariant, "__name__", type(invariant).__name__)))


def _invariant_description(invariant: Any) -> str:
    return str(getattr(invariant, "description", ""))


def _progress_disabled_by_environment() -> bool:
    value = os.environ.get("FLOWGUARD_PROGRESS")
    return value is not None and value.strip().lower() in {"0", "false", "no", "off"}


def _progress_thresholds(total_work: int, progress_steps: int) -> tuple[tuple[int, int], ...]:
    if total_work < 1 or progress_steps < 1:
        return ()
    thresholds: dict[int, int] = {}
    for step in range(1, progress_steps + 1):
        threshold = max(1, (total_work * step + progress_steps - 1) // progress_steps)
        percent = min(100, (step * 100) // progress_steps)
        thresholds[threshold] = percent
    return tuple(sorted(thresholds.items()))


def _coerce_edge(state: Any, raw: GraphEdge | tuple[str, Any]) -> GraphEdge:
    if isinstance(raw, GraphEdge):
        return raw
    label, new_state = raw
    return GraphEdge(old_state=state, new_state=new_state, label=label)


def _file_digest(path: Path) -> dict[str, str]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"path": str(path), "sha256": digest.hexdigest()}


@dataclass(frozen=True, init=False)
class BudgetedGraphConfig:
    """Configuration for one budgeted reachable-graph model group."""

    model_name: str
    initial_states: tuple[Any, ...]
    transition_fn: TransitionFn
    state_id: StateIdFn
    encode_state: StateEncoder
    decode_state: StateDecoder
    run_root: Path
    budget_per_shard: int
    max_shards_per_run: int
    invariants: tuple[Any, ...]
    required_labels: tuple[str, ...]
    fingerprint_parts: tuple[Any, ...]
    fingerprint_files: tuple[Path, ...]
    max_failure_samples: int
    progress_steps: int

    def __init__(
        self,
        model_name: str,
        initial_states: Sequence[Any],
        transition_fn: TransitionFn,
        *,
        state_id: StateIdFn | None = None,
        encode_state: StateEncoder | None = None,
        decode_state: StateDecoder | None = None,
        run_root: str | Path = ".flowguard/budgeted-model-groups",
        budget_per_shard: int = 10_000,
        max_shards_per_run: int = 1,
        invariants: Sequence[Any] = (),
        required_labels: Sequence[str] = (),
        fingerprint_parts: Sequence[Any] = (),
        fingerprint_files: Sequence[str | Path] = (),
        max_failure_samples: int = 20,
        progress_steps: int = 10,
    ) -> None:
        if not model_name or not str(model_name).strip():
            raise ValueError("model_name is required")
        initial = tuple(initial_states)
        if not initial:
            raise ValueError("initial_states must not be empty")
        if budget_per_shard < 1:
            raise ValueError("budget_per_shard must be at least 1")
        if max_shards_per_run < 1:
            raise ValueError("max_shards_per_run must be at least 1")
        if max_failure_samples < 0:
            raise ValueError("max_failure_samples must be non-negative")

        object.__setattr__(self, "model_name", str(model_name))
        object.__setattr__(self, "initial_states", initial)
        object.__setattr__(self, "transition_fn", transition_fn)
        object.__setattr__(self, "state_id", state_id or _default_state_id)
        object.__setattr__(self, "encode_state", encode_state or _default_encode_state)
        object.__setattr__(self, "decode_state", decode_state or _default_decode_state)
        object.__setattr__(self, "run_root", Path(run_root))
        object.__setattr__(self, "budget_per_shard", int(budget_per_shard))
        object.__setattr__(self, "max_shards_per_run", int(max_shards_per_run))
        object.__setattr__(self, "invariants", tuple(invariants))
        object.__setattr__(self, "required_labels", tuple(str(label) for label in required_labels))
        object.__setattr__(self, "fingerprint_parts", tuple(fingerprint_parts))
        object.__setattr__(self, "fingerprint_files", tuple(Path(path) for path in fingerprint_files))
        object.__setattr__(self, "max_failure_samples", int(max_failure_samples))
        object.__setattr__(self, "progress_steps", int(progress_steps))


@dataclass(frozen=True)
class BudgetedGraphFailure:
    """One stored failure sample from a budgeted model group."""

    kind: str
    name: str
    message: str
    state_id: str
    state: Any = None
    metadata: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "name": self.name,
            "message": self.message,
            "state_id": self.state_id,
            "state": to_jsonable(self.state),
            "metadata": to_jsonable(self.metadata),
        }


@dataclass(frozen=True)
class BudgetedShardReport:
    """Summary for one processed shard."""

    shard_index: int
    status: str
    processed_state_count: int
    edge_count: int
    pending_state_count: int
    started_at: str
    finished_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "shard_index": self.shard_index,
            "status": self.status,
            "processed_state_count": self.processed_state_count,
            "edge_count": self.edge_count,
            "pending_state_count": self.pending_state_count,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass(frozen=True)
class BudgetedGraphReport:
    """Structured outcome of a budgeted graph/model-group run."""

    ok: bool
    status: str
    complete: bool
    model_name: str
    fingerprint: str
    run_dir: str
    budget_per_shard: int
    max_shards_per_run: int
    known_state_count: int
    processed_state_count: int
    processed_this_run: int
    pending_state_count: int
    edge_count: int
    edge_count_this_run: int
    shard_count: int
    shards_processed_this_run: int
    labels: tuple[str, ...] = ()
    required_labels: tuple[str, ...] = ()
    missing_labels: tuple[str, ...] = ()
    failure_count: int = 0
    failures: tuple[BudgetedGraphFailure, ...] = ()
    shards: tuple[BudgetedShardReport, ...] = ()
    reused_complete_result: bool = False
    summary: str = ""

    def format_text(self, max_examples: int = 3) -> str:
        lines = [
            f"status: {self.status}",
            self.summary
            or (
                f"model={self.model_name} complete={self.complete} "
                f"processed={self.processed_state_count} pending={self.pending_state_count}"
            ),
            f"ok: {self.ok}",
            f"budget_per_shard: {self.budget_per_shard}",
            f"known_states: {self.known_state_count}",
            f"processed_states: {self.processed_state_count}",
            f"pending_states: {self.pending_state_count}",
            f"edges: {self.edge_count}",
            f"shards: {self.shard_count}",
            f"processed_this_run: {self.processed_this_run}",
            f"shards_this_run: {self.shards_processed_this_run}",
            f"missing_labels: {len(self.missing_labels)}",
            f"failures: {self.failure_count}",
            f"run_dir: {self.run_dir}",
        ]
        if self.missing_labels:
            lines.extend(["", f"missing_labels: {', '.join(self.missing_labels)}"])
        for failure in self.failures[:max_examples]:
            lines.extend(
                [
                    "",
                    f"failure: {failure.kind}:{failure.name}",
                    f"message: {failure.message}",
                    f"state_id: {failure.state_id}",
                ]
            )
        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "complete": self.complete,
            "model_name": self.model_name,
            "fingerprint": self.fingerprint,
            "run_dir": self.run_dir,
            "budget_per_shard": self.budget_per_shard,
            "max_shards_per_run": self.max_shards_per_run,
            "known_state_count": self.known_state_count,
            "processed_state_count": self.processed_state_count,
            "processed_this_run": self.processed_this_run,
            "pending_state_count": self.pending_state_count,
            "edge_count": self.edge_count,
            "edge_count_this_run": self.edge_count_this_run,
            "shard_count": self.shard_count,
            "shards_processed_this_run": self.shards_processed_this_run,
            "labels": list(self.labels),
            "required_labels": list(self.required_labels),
            "missing_labels": list(self.missing_labels),
            "failure_count": self.failure_count,
            "failures": [failure.to_dict() for failure in self.failures],
            "shards": [shard.to_dict() for shard in self.shards],
            "reused_complete_result": self.reused_complete_result,
            "summary": self.summary,
        }

    def to_json_text(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def budgeted_graph_fingerprint(config: BudgetedGraphConfig) -> str:
    """Return the stable fingerprint used for a model-group ledger directory."""

    file_parts = [_file_digest(path) for path in config.fingerprint_files]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "model_name": config.model_name,
        "transition_fn": _callable_name(config.transition_fn),
        "initial_state_ids": [config.state_id(state) for state in config.initial_states],
        "required_labels": config.required_labels,
        "invariants": [
            {
                "name": _invariant_name(invariant),
                "description": _invariant_description(invariant),
                "callable": _callable_name(getattr(invariant, "check", invariant)),
            }
            for invariant in config.invariants
        ],
        "budget_per_shard": config.budget_per_shard,
        "fingerprint_parts": to_jsonable(config.fingerprint_parts),
        "fingerprint_files": file_parts,
    }
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()[:24]


def budgeted_graph_run_dir(config: BudgetedGraphConfig) -> Path:
    return config.run_root / _safe_name(config.model_name) / budgeted_graph_fingerprint(config)


def _connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS states (
            state_key TEXT PRIMARY KEY,
            payload TEXT NOT NULL,
            status TEXT NOT NULL,
            depth INTEGER NOT NULL,
            discovered_at TEXT NOT NULL,
            processed_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS labels (
            label TEXT PRIMARY KEY,
            count INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS counters (
            key TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS failures (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            name TEXT NOT NULL,
            message TEXT NOT NULL,
            state_key TEXT NOT NULL,
            state_payload TEXT,
            metadata TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS shards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            status TEXT NOT NULL,
            processed_state_count INTEGER NOT NULL,
            edge_count INTEGER NOT NULL,
            pending_state_count INTEGER NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_states_status ON states(status)")
    conn.execute("UPDATE states SET status = 'pending' WHERE status = 'processing'")
    conn.commit()
    return conn


def _set_meta(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, _stable_json(value)),
    )


def _get_counter(conn: sqlite3.Connection, key: str) -> int:
    row = conn.execute("SELECT value FROM counters WHERE key = ?", (key,)).fetchone()
    return int(row[0]) if row else 0


def _add_counter(conn: sqlite3.Connection, key: str, delta: int) -> None:
    conn.execute(
        """
        INSERT INTO counters(key, value) VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = value + excluded.value
        """,
        (key, int(delta)),
    )


def _count_states(conn: sqlite3.Connection, status: str | None = None) -> int:
    if status is None:
        row = conn.execute("SELECT COUNT(*) FROM states").fetchone()
    else:
        row = conn.execute("SELECT COUNT(*) FROM states WHERE status = ?", (status,)).fetchone()
    return int(row[0])


def _insert_state(
    conn: sqlite3.Connection,
    config: BudgetedGraphConfig,
    state: Any,
    *,
    depth: int,
    status: str = "pending",
) -> bool:
    state_key = str(config.state_id(state))
    payload = _stable_json(config.encode_state(state))
    now = _utc_now()
    cursor = conn.execute(
        """
        INSERT OR IGNORE INTO states(state_key, payload, status, depth, discovered_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (state_key, payload, status, int(depth), now),
    )
    if cursor.rowcount:
        return True

    row = conn.execute("SELECT payload FROM states WHERE state_key = ?", (state_key,)).fetchone()
    if row and str(row[0]) != payload:
        _record_failure(
            conn,
            config,
            kind="state_id",
            name="state_id_collision",
            message="state_id returned the same key for different encoded states",
            state_key=state_key,
            state=state,
            metadata={"existing_payload": row[0]},
        )
    return False


def _next_pending(conn: sqlite3.Connection) -> tuple[str, str, int] | None:
    row = conn.execute(
        "SELECT state_key, payload, depth FROM states WHERE status = 'pending' ORDER BY rowid LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    conn.execute("UPDATE states SET status = 'processing' WHERE state_key = ?", (row[0],))
    return str(row[0]), str(row[1]), int(row[2])


def _mark_processed(conn: sqlite3.Connection, state_key: str) -> None:
    conn.execute(
        "UPDATE states SET status = 'processed', processed_at = ? WHERE state_key = ?",
        (_utc_now(), state_key),
    )
    _add_counter(conn, "processed_state_count", 1)


def _record_label(conn: sqlite3.Connection, label: str) -> None:
    conn.execute(
        """
        INSERT INTO labels(label, count) VALUES (?, 1)
        ON CONFLICT(label) DO UPDATE SET count = count + 1
        """,
        (str(label),),
    )


def _record_failure(
    conn: sqlite3.Connection,
    config: BudgetedGraphConfig,
    *,
    kind: str,
    name: str,
    message: str,
    state_key: str,
    state: Any,
    metadata: Any = None,
) -> None:
    _add_counter(conn, "failure_count", 1)
    if _get_counter(conn, "failure_count") > config.max_failure_samples:
        return
    conn.execute(
        """
        INSERT INTO failures(kind, name, message, state_key, state_payload, metadata, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(kind),
            str(name),
            str(message),
            str(state_key),
            _stable_json(config.encode_state(state)),
            _stable_json(metadata),
            _utc_now(),
        ),
    )


def _check_invariant(invariant: Any, state: Any) -> InvariantResult:
    check = getattr(invariant, "check", None)
    try:
        if check is not None:
            result = check(state, None)
        else:
            result = invariant(state, None)
    except TypeError:
        try:
            if check is not None:
                result = check(state)
            else:
                result = invariant(state)
        except Exception as exc:
            return InvariantResult.fail(
                f"invariant raised {type(exc).__name__}: {exc}",
                {"invariant": _invariant_name(invariant)},
            )
    except Exception as exc:
        return InvariantResult.fail(
            f"invariant raised {type(exc).__name__}: {exc}",
            {"invariant": _invariant_name(invariant)},
        )

    if isinstance(result, InvariantResult):
        return result
    if bool(result):
        return InvariantResult.pass_()
    return InvariantResult.fail(f"invariant failed: {_invariant_name(invariant)}")


def _read_labels(conn: sqlite3.Connection) -> tuple[str, ...]:
    rows = conn.execute("SELECT label FROM labels ORDER BY label").fetchall()
    return tuple(str(row[0]) for row in rows)


def _read_failures(conn: sqlite3.Connection, config: BudgetedGraphConfig) -> tuple[BudgetedGraphFailure, ...]:
    rows = conn.execute(
        """
        SELECT kind, name, message, state_key, state_payload, metadata
        FROM failures
        ORDER BY id
        LIMIT ?
        """,
        (config.max_failure_samples,),
    ).fetchall()
    failures: list[BudgetedGraphFailure] = []
    for row in rows:
        state_payload = json.loads(row[4]) if row[4] else None
        metadata = json.loads(row[5]) if row[5] else None
        try:
            state = config.decode_state(state_payload)
        except Exception:
            state = state_payload
        failures.append(
            BudgetedGraphFailure(
                kind=str(row[0]),
                name=str(row[1]),
                message=str(row[2]),
                state_id=str(row[3]),
                state=state,
                metadata=metadata,
            )
        )
    return tuple(failures)


def _read_shards(conn: sqlite3.Connection) -> tuple[BudgetedShardReport, ...]:
    rows = conn.execute(
        """
        SELECT id, status, processed_state_count, edge_count, pending_state_count, started_at, finished_at
        FROM shards
        ORDER BY id
        """
    ).fetchall()
    return tuple(
        BudgetedShardReport(
            shard_index=int(row[0]),
            status=str(row[1]),
            processed_state_count=int(row[2]),
            edge_count=int(row[3]),
            pending_state_count=int(row[4]),
            started_at=str(row[5]),
            finished_at=str(row[6]),
        )
        for row in rows
    )


def _build_report(
    conn: sqlite3.Connection,
    config: BudgetedGraphConfig,
    *,
    fingerprint: str,
    run_dir: Path,
    processed_this_run: int,
    edge_count_this_run: int,
    shards_processed_this_run: int,
    reused_complete_result: bool,
) -> BudgetedGraphReport:
    labels = _read_labels(conn)
    missing_labels = tuple(label for label in config.required_labels if label not in set(labels))
    failure_count = _get_counter(conn, "failure_count")
    pending_state_count = _count_states(conn, "pending")
    complete = pending_state_count == 0
    if failure_count:
        status = "failed"
    elif not complete:
        status = "incomplete"
    elif missing_labels:
        status = "failed"
    else:
        status = "complete"
    ok = status == "complete"
    processed_state_count = _get_counter(conn, "processed_state_count")
    edge_count = _get_counter(conn, "edge_count")
    shard_count = len(_read_shards(conn))
    summary = (
        f"model={config.model_name} status={status} complete={complete} "
        f"processed={processed_state_count} pending={pending_state_count} "
        f"edges={edge_count} shards={shard_count}"
    )
    return BudgetedGraphReport(
        ok=ok,
        status=status,
        complete=complete,
        model_name=config.model_name,
        fingerprint=fingerprint,
        run_dir=str(run_dir),
        budget_per_shard=config.budget_per_shard,
        max_shards_per_run=config.max_shards_per_run,
        known_state_count=_count_states(conn),
        processed_state_count=processed_state_count,
        processed_this_run=processed_this_run,
        pending_state_count=pending_state_count,
        edge_count=edge_count,
        edge_count_this_run=edge_count_this_run,
        shard_count=shard_count,
        shards_processed_this_run=shards_processed_this_run,
        labels=labels,
        required_labels=config.required_labels,
        missing_labels=missing_labels,
        failure_count=failure_count,
        failures=_read_failures(conn, config),
        shards=_read_shards(conn),
        reused_complete_result=reused_complete_result,
        summary=summary,
    )


def _emit_progress(message: str, enabled: bool) -> None:
    if enabled:
        print(message, file=sys.stderr, flush=True)


def _process_one_shard(
    conn: sqlite3.Connection,
    config: BudgetedGraphConfig,
    *,
    shard_index: int,
    progress_enabled: bool,
) -> tuple[BudgetedShardReport, int, int]:
    started_at = _utc_now()
    processed = 0
    edges = 0
    thresholds = _progress_thresholds(config.budget_per_shard, config.progress_steps)
    next_threshold_index = 0

    _emit_progress(
        (
            f"[flowguard-budget] start model={config.model_name} shard={shard_index} "
            f"budget={config.budget_per_shard} processed_total={_get_counter(conn, 'processed_state_count')} "
            f"pending={_count_states(conn, 'pending')}"
        ),
        progress_enabled,
    )

    while processed < config.budget_per_shard:
        pending = _next_pending(conn)
        if pending is None:
            break

        state_key, payload_text, depth = pending
        try:
            state = config.decode_state(json.loads(payload_text))
        except Exception as exc:
            _record_failure(
                conn,
                config,
                kind="decode",
                name="decode_state",
                message=f"decode_state raised {type(exc).__name__}: {exc}",
                state_key=state_key,
                state=json.loads(payload_text),
            )
            _mark_processed(conn, state_key)
            processed += 1
            continue

        for invariant in config.invariants:
            result = _check_invariant(invariant, state)
            if result.ok:
                continue
            _record_failure(
                conn,
                config,
                kind="invariant",
                name=_invariant_name(invariant),
                message=result.message,
                state_key=state_key,
                state=state,
                metadata=result.metadata,
            )

        try:
            raw_edges = tuple(config.transition_fn(state))
        except Exception as exc:
            _record_failure(
                conn,
                config,
                kind="transition",
                name=_callable_name(config.transition_fn),
                message=f"transition_fn raised {type(exc).__name__}: {exc}",
                state_key=state_key,
                state=state,
            )
            raw_edges = ()

        for raw_edge in raw_edges:
            try:
                edge = _coerce_edge(state, raw_edge)
            except Exception as exc:
                _record_failure(
                    conn,
                    config,
                    kind="edge",
                    name="edge_coercion",
                    message=f"edge could not be read: {type(exc).__name__}: {exc}",
                    state_key=state_key,
                    state=state,
                )
                continue
            _record_label(conn, edge.label)
            _insert_state(conn, config, edge.new_state, depth=depth + 1)
            edges += 1

        _mark_processed(conn, state_key)
        processed += 1

        if progress_enabled:
            while (
                next_threshold_index < len(thresholds)
                and processed >= thresholds[next_threshold_index][0]
            ):
                _, percent = thresholds[next_threshold_index]
                _emit_progress(
                    (
                        f"[flowguard-budget] progress model={config.model_name} shard={shard_index} "
                        f"{percent}% work={processed}/{config.budget_per_shard} "
                        f"total_processed={_get_counter(conn, 'processed_state_count')} "
                        f"pending={_count_states(conn, 'pending')}"
                    ),
                    progress_enabled,
                )
                next_threshold_index += 1

    _add_counter(conn, "edge_count", edges)
    finished_at = _utc_now()
    pending_count = _count_states(conn, "pending")
    status = "complete" if pending_count == 0 else "incomplete"
    conn.execute(
        """
        INSERT INTO shards(status, processed_state_count, edge_count, pending_state_count, started_at, finished_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (status, processed, edges, pending_count, started_at, finished_at),
    )
    shard = BudgetedShardReport(
        shard_index=shard_index,
        status=status,
        processed_state_count=processed,
        edge_count=edges,
        pending_state_count=pending_count,
        started_at=started_at,
        finished_at=finished_at,
    )
    _emit_progress(
        (
            f"[flowguard-budget] shard_end model={config.model_name} shard={shard_index} "
            f"status={status} processed={processed}/{config.budget_per_shard} "
            f"total_processed={_get_counter(conn, 'processed_state_count')} pending={pending_count}"
        ),
        progress_enabled,
    )
    return shard, processed, edges


def run_budgeted_graph_checks(config: BudgetedGraphConfig) -> BudgetedGraphReport:
    """Process up to ``max_shards_per_run`` budgeted shards for a graph model.

    The same model fingerprint uses the same ledger directory, so repeated calls
    continue from pending states rather than restarting from the initial states.
    """

    fingerprint = budgeted_graph_fingerprint(config)
    run_dir = budgeted_graph_run_dir(config)
    conn = _connect(run_dir / "ledger.sqlite3")
    progress_enabled = config.progress_steps > 0 and not _progress_disabled_by_environment()
    processed_this_run = 0
    edge_count_this_run = 0
    shards_processed_this_run = 0
    reused_complete_result = False

    try:
        _set_meta(
            conn,
            "manifest",
            {
                "schema_version": SCHEMA_VERSION,
                "model_name": config.model_name,
                "fingerprint": fingerprint,
                "budget_per_shard": config.budget_per_shard,
                "max_shards_per_run": config.max_shards_per_run,
                "required_labels": config.required_labels,
                "created_or_seen_at": _utc_now(),
            },
        )
        if _count_states(conn) == 0:
            for state in config.initial_states:
                _insert_state(conn, config, state, depth=0)
            conn.commit()

        if _count_states(conn, "pending") == 0:
            reused_complete_result = True
            return _build_report(
                conn,
                config,
                fingerprint=fingerprint,
                run_dir=run_dir,
                processed_this_run=0,
                edge_count_this_run=0,
                shards_processed_this_run=0,
                reused_complete_result=reused_complete_result,
            )

        for _ in range(config.max_shards_per_run):
            if _count_states(conn, "pending") == 0:
                break
            shard_index = len(_read_shards(conn)) + 1
            shard, processed, edges = _process_one_shard(
                conn,
                config,
                shard_index=shard_index,
                progress_enabled=progress_enabled,
            )
            del shard
            conn.commit()
            processed_this_run += processed
            edge_count_this_run += edges
            shards_processed_this_run += 1
            if _count_states(conn, "pending") == 0:
                break

        return _build_report(
            conn,
            config,
            fingerprint=fingerprint,
            run_dir=run_dir,
            processed_this_run=processed_this_run,
            edge_count_this_run=edge_count_this_run,
            shards_processed_this_run=shards_processed_this_run,
            reused_complete_result=reused_complete_result,
        )
    finally:
        conn.close()


__all__ = [
    "BudgetedGraphConfig",
    "BudgetedGraphFailure",
    "BudgetedGraphReport",
    "BudgetedShardReport",
    "StateDecoder",
    "StateEncoder",
    "StateIdFn",
    "TransitionFn",
    "budgeted_graph_fingerprint",
    "budgeted_graph_run_dir",
    "run_budgeted_graph_checks",
]
