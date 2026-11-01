"""Shared job ownership and immutable input facts; callers derive all verdicts.

The engine supplies a closed input manifest and execute(job, writer, deadline).
This module does not explore, judge rules, persist verdicts or select budgets.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tempfile
import time

from flowguard.map.common import atomic_write_text
from flowguard.map.runner import PROCESS_OWNER_ENV


def _key(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _write(path, value):
    atomic_write_text(path, json.dumps(value, ensure_ascii=False, sort_keys=True))


def cache_directory(root):
    root = Path(root).resolve()
    git = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"], capture_output=True, text=True)
    common = Path(git.stdout.strip()) if git.returncode == 0 else root / ".flowguard"
    if not common.is_absolute():
        common = root / common
    path = common / "flowguard/cache/jobs" if git.returncode == 0 else common / "cache/jobs"
    path.mkdir(parents=True, exist_ok=True)
    return path.resolve()


@contextmanager
def key_lock(path, *, blocking=False):
    """The OS handle is authority; stored PIDs never decide lock ownership."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = path.open("a+b")
    if handle.tell() == 0:
        handle.write(b"0")
        handle.flush()
    acquired = False
    try:
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK if blocking else msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_EX | (0 if blocking else fcntl.LOCK_NB))
            acquired = True
        except BlockingIOError:
            pass
        except OSError as exc:
            if os.name != "nt" or exc.errno not in (13, 36):
                raise
        yield acquired
    finally:
        if acquired:
            handle.seek(0)
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def _relative(name):
    value = Path(name)
    if value.is_absolute() or ".." in value.parts:
        raise ValueError("snapshot inputs must be source-relative paths")
    return value.as_posix()


def _stamp(path, root):
    from .inputs import file_stamp
    row = file_stamp(path)
    if "resolved" in row:
        actual = Path(row["resolved"])
        try:
            row["resolved"] = {"root": "source", "path": actual.relative_to(root).as_posix()}
        except ValueError:
            row["resolved"] = {"external": str(actual)}
    return row


def _logical_value(value, root):
    if isinstance(value, list):
        return [_logical_value(item, root) for item in value]
    if not isinstance(value, dict):
        return value
    row = {key: _logical_value(item, root) for key, item in value.items()}
    if isinstance(value.get("resolved"), str):
        path = Path(value["resolved"])
        try:
            row["resolved"] = {"root": "source", "path": path.relative_to(root).as_posix()}
        except ValueError:
            row["resolved"] = {"external": str(path)}
    return row


def _manifest(root, selection, directory_uses=None):
    from .inputs import directory_stamp
    from .inputs import module_lookup_stamp
    files = set(selection["files"])
    directories, uses = {}, {}
    given = {}
    for raw, usage in (directory_uses or {}).items():
        path = Path(raw)
        try:
            name = path.relative_to(root).as_posix() if path.is_absolute() else _relative(raw)
        except ValueError:
            continue
        given[name] = usage
    for name in selection["directories"]:
        path = root / name
        listing = directory_stamp(path)
        directories[name] = {"listing": listing, "mode": stat.S_IMODE(path.stat().st_mode) if path.exists() else None}
        usage = given.get(name, {})
        if usage.get("kind") == "module-lookup" and usage.get("lookups"):
            uses[name] = {"kind": "module-lookup", "lookups": {
                leaf: _logical_value(module_lookup_stamp(path, leaf), root) for leaf in usage["lookups"]}}
        else:
            for child, kind, *_ in listing.get("entries", []):
                if kind != "directory":
                    files.add((Path(name) / child).as_posix())
    return {"selection": selection, "files": {name: _stamp(root / name, root) for name in sorted(files)},
            "directories": directories, "directory_uses": uses}


def _manifest_identity(manifest):
    return {"selection": manifest["selection"], "files": manifest["files"],
            "directories": {name: {"mode": row["mode"], "use": manifest["directory_uses"][name]}
                            if name in manifest.get("directory_uses", {}) else row
                            for name, row in manifest["directories"].items()}}


def _inputs_key(inputs):
    return _key({**inputs, "manifest": _manifest_identity(inputs["manifest"])})


def _copied_inputs(manifest):
    # Copying preserves membership/content, but the filesystem may enumerate
    # another order. Keep both raw receipts; actual consumers decide below.
    return {**manifest, "directories": {name: {**row, "listing": {
        **row["listing"], "entries": sorted(row["listing"].get("entries", []), key=lambda item: item[0])}}
        for name, row in manifest["directories"].items()}}


def _runtime():
    from .inputs import file_stamp
    package = Path(__file__).resolve().parents[1]
    return {"python": sys.version, "executable": file_stamp(sys.executable),
            "engine": {str(path): file_stamp(path) for path in sorted(package.rglob("*.py"))}}


def _copy_snapshot(root, destination, manifest):
    # Create listed entries in their actual order before filling file bytes.
    destination.mkdir()
    for name, row in sorted(manifest["directories"].items(), key=lambda pair: len(Path(pair[0]).parts)):
        directory = destination / name
        directory.mkdir(parents=True, exist_ok=True)
        for child, kind, mode, link in row["listing"].get("entries", []):
            target = directory / child
            if kind == "directory":
                target.mkdir(exist_ok=True)
            elif kind == "link":
                target.symlink_to(link)
            else:
                target.touch()
            if kind != "link":
                target.chmod(mode)
    for name, row in manifest["files"].items():
        target, source = destination / name, root / name
        if row.get("missing"):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_symlink():
            if not target.is_symlink():
                target.symlink_to(os.readlink(source))
        elif source.is_file():
            shutil.copyfile(source, target)
            target.chmod(row["mode"])
        elif source.is_dir():
            target.mkdir(exist_ok=True)
            target.chmod(row["mode"])
        else:
            raise ValueError("an explicit source input is not an ordinary file: " + name)
    for name, row in sorted(manifest["directories"].items(), key=lambda pair: -len(Path(pair[0]).parts)):
        if row["mode"] is not None:
            (destination / name).chmod(row["mode"])


@dataclass(frozen=True)
class Job:
    path: Path
    data: dict

    @property
    def key(self):
        return self.data["key"]

    @property
    def snapshot(self):
        return self.path / "source"

    @property
    def manifest(self):
        return self.data["inputs"]["manifest"]

    @property
    def planned(self):
        return self.request["slices"]

    @property
    def request(self):
        return self.data["inputs"]["request"]

    @property
    def bindings(self):
        return self.data["bindings"]

    def valid(self):
        return (_runtime() == self.data["inputs"]["runtime"]
                and _manifest(self.snapshot, self.manifest["selection"], self.manifest.get("directory_uses"))
                == self.data["snapshot_manifest"])

    def matches(self, root):
        current = _manifest(Path(root).resolve(), self.manifest["selection"], self.manifest.get("directory_uses"))
        return _manifest_identity(current) == _manifest_identity(self.manifest)


def open_job(path):
    path = Path(path).resolve()
    data = json.loads((path / "request.json").read_text())
    if _inputs_key(data["inputs"]) != data["key"] or path.name != data["key"]:
        raise ValueError("job inputs do not match their content key")
    return Job(path, data)


def prepare(root, *, files, directories=(), request, directory_uses=None, bindings=None):
    """Freeze only explicit program inputs; no environment, HOME or credentials."""
    root = Path(root).resolve()
    directory = cache_directory(root)
    selected_files = sorted({_relative(name) for name in files})
    selected_dirs = {_relative(name) for name in directories}
    selection = {"files": selected_files, "directories": sorted(selected_dirs)}
    inputs = {"manifest": _manifest(root, selection, directory_uses), "request": request, "runtime": _runtime()}
    if len(set(request["slices"])) != len(request["slices"]):
        raise ValueError("planned slice keys must be unique")
    key = _inputs_key(inputs)
    path = directory / key
    with key_lock(directory / (key + ".prepare.lock"), blocking=True):
        if not path.exists():
            staging = Path(tempfile.mkdtemp(prefix="prepare-", dir=directory))
            try:
                _copy_snapshot(root, staging / "source", inputs["manifest"])
                if _manifest(root, selection, directory_uses) != inputs["manifest"]:
                    raise ValueError("source inputs changed while preparing the snapshot")
                snapshot_manifest = _manifest(staging / "source", selection, inputs["manifest"].get("directory_uses"))
                if _copied_inputs(snapshot_manifest) != _copied_inputs(inputs["manifest"]):
                    raise ValueError("snapshot did not preserve the exact input manifest")
                _write(staging / "request.json", {"key": key, "inputs": inputs,
                       "bindings": {**(bindings or {}), "source": str(root)},
                       "snapshot_manifest": snapshot_manifest,
                       "physical_directory_uses": directory_uses or {}, "prepared_at": time.time()})
                staging.rename(path)
            finally:
                if staging.exists():
                    shutil.rmtree(staging)
    job = open_job(path)
    if not job.valid():
        raise ValueError("job snapshot or engine inputs changed")
    return job


class Writer:
    def __init__(self, job):
        self.job = job
        self.input_error = None

    def _path(self, key):
        if key not in self.job.planned:
            raise ValueError("unplanned slice")
        return self.job.path / "slices" / (_key(key) + ".json")

    def _valid(self, facts):
        from .inputs import footprint_identity
        self.input_error = None
        if not self.job.valid() or not footprint_identity(facts.get("footprint", {})):
            return False
        # Keep physical paths. An explicit mapping additionally proves that each
        # observed snapshot input belongs to the original logical manifest.
        for kind in ("files", "directories"):
            for raw in facts["footprint"][kind]:
                path = Path(raw)
                try:
                    name = path.relative_to(self.job.snapshot).as_posix()
                except ValueError:
                    try:
                        path.relative_to(Path(self.job.data["bindings"]["source"]))
                    except ValueError:
                        pass
                    else:
                        if not any(path.is_relative_to(Path(root)) for root in self.job.bindings.get("read_roots", [])):
                            self.input_error = "execution read live source instead of the frozen snapshot: " + str(path)
                            return False
                    continue  # External dependencies retain their actual absolute footprint.
                if name not in self.job.manifest[kind]:
                    return False
                if kind == "directories":
                    actual = facts["footprint"].get("directory_uses", {}).get(raw, {})
                    if name in self.job.manifest.get("directory_uses", {}):
                        expected = self.job.manifest["directory_uses"][name]
                        if (actual.get("kind") != "module-lookup"
                                or set(actual.get("lookups", {})) - set(expected["lookups"])):
                            self.input_error = "execution consumed more than the declared module lookups: " + name
                            return False
                    elif actual.get("kind") == "module-lookup" and actual.get("lookups"):
                        entries = {item[0]: item[1] for item in self.job.manifest["directories"][name]["listing"].get("entries", [])}
                        if any(entries.get(leaf) == "directory" and (Path(name) / leaf).as_posix()
                               not in self.job.manifest["directories"] for leaf in actual["lookups"]):
                            self.input_error = "module lookup needs an unlisted source package: " + name
                            return False
                    elif facts["footprint"]["directories"][raw] != self.job.manifest["directories"][name]["listing"]:
                        self.input_error = "source snapshot cannot preserve application directory enumeration order: " + name
                        return False
        return True

    def load_slice(self, key):
        try:
            row = json.loads(self._path(key).read_text())
            facts = row["facts"]
            if row["job"] == self.job.key and row["slice"] == key and row["body"] == _key(facts) and self._valid(facts):
                return facts
        except (OSError, ValueError, KeyError, TypeError):
            pass
        return None

    def save_slice(self, key, facts):
        if {"word", "verdict", "judgment", "J"} & facts.keys():
            raise ValueError("store native input facts, not a command verdict")
        if not self._valid(facts):
            raise ValueError(self.input_error or "slice inputs are incomplete, uncovered or changed")
        row = {"job": self.job.key, "slice": key, "body": _key(facts), "facts": facts}
        _write(self._path(key), row)
        self.progress()
        return {"slice": key, "body": row["body"], "path": self._path(key).relative_to(self.job.path).as_posix()}

    def progress(self, *, state="active", failures=()):
        done = [key for key in self.job.planned if self.load_slice(key) is not None]
        row = {"key": self.job.key, "owner": os.getpid(), "state": state, "done": done,
               "pending": [key for key in self.job.planned if key not in done], "failures": list(failures),
               "updated_at": time.time(), "snapshot": str(self.job.snapshot)}
        _write(self.job.path / "progress.json", row)
        return row

    def finish(self):
        row = self.progress()
        if row["pending"] or not self.job.valid():
            return False
        facts = {key: self.load_slice(key) for key in row["done"]}
        if any(value is None for value in facts.values()) or not all(self._valid(value) for value in facts.values()):
            return False
        refs = [{"slice": key, "path": self._path(key).relative_to(self.job.path).as_posix(),
                 "body": _key(facts[key])} for key in row["done"]]
        _write(self.job.path / "completed.json", {"key": self.job.key, "slices": refs})
        return True


def _busy(job):
    with key_lock(job.path / "owner.lock") as acquired:
        return not acquired


def read_slice(job, key):
    return Writer(job).load_slice(key)


def read_all(job):
    return {key: facts for key in job.planned if (facts := read_slice(job, key)) is not None}


def _view(job):
    writer = Writer(job)
    done = [key for key in job.planned if writer.load_slice(key) is not None]
    pending = [key for key in job.planned if key not in done]
    valid = job.valid()
    complete = not pending and valid
    try:
        progress = json.loads((job.path / "progress.json").read_text())
    except (OSError, ValueError):
        progress = {}
    return {"key": job.key, "complete": complete, "done": done, "pending": pending,
            "state": "invalid" if not valid else "complete" if complete else "active" if _busy(job) else progress.get("state", "pending"),
            "failures": progress.get("failures", []), "owner": progress.get("owner"),
            "snapshot": str(job.snapshot), "request": job.data["inputs"]["request"]}


def serve(job, execute, *, deadline=None):
    """The real worker owns the lock; execute uses existing engine slice owners."""
    if not isinstance(job, Job):
        job = open_job(job)
    with key_lock(job.path / "owner.lock") as acquired:
        if not acquired:
            return None
        writer = Writer(job)
        writer.progress()
        try:
            execute(job, writer, deadline)
            complete = writer.finish()
            writer.progress(state="complete" if complete else "paused")
        except Exception as exc:
            writer.progress(state="failed", failures=[{"type": type(exc).__name__, "reason": str(exc)}])
    return _view(job)


_DETACHED_PROCESSES = []


def start_detached_process(command: list[str], *, cwd: Path, env: dict,
                           stdout_path: Path, stderr_path: Path) -> int:
    """Start a durable coordinator around the shared finite-process owner.

    The coordinator runs flowguard.map.runner.run_isolated_process without an
    outer timeout. It survives the requesting CLI and cleans the worker's
    remaining descendants if its leader dies. Native calls retain their own
    timeouts. No environment or credentials are serialized to disk.
    """
    global _DETACHED_PROCESSES
    _DETACHED_PROCESSES = [process for process in _DETACHED_PROCESSES if process.poll() is None]
    child_env = dict(env)
    child_env.pop(PROCESS_OWNER_ENV, None)
    supervisor = (
        "import os,sys;from pathlib import Path;"
        "from flowguard.map.runner import run_isolated_process;"
        "done,_,_=run_isolated_process(sys.argv[1:],cwd=Path.cwd(),env=dict(os.environ),timeout=None);"
        "raise SystemExit(done.returncode)"
    )
    options = ({"creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP}
               if os.name == "nt" else {"start_new_session": True})
    with Path(stdout_path).open("ab") as output, Path(stderr_path).open("ab") as error:
        process = subprocess.Popen([sys.executable, "-c", supervisor, *command], cwd=cwd, env=child_env,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=error, close_fds=True, **options)
    _DETACHED_PROCESSES.append(process)
    return process.pid


def run_or_attach(job, *, execute, worker_command, env, wait=100, foreground=False):
    """wait=None means unlimited. Deadline-aware slice execution stays in engine."""
    if wait is not None and wait < 0:
        raise ValueError("wait must be nonnegative or None")
    deadline = None if wait is None else time.monotonic() + wait
    current = _view(job)
    if current["complete"]:
        return current
    # A previous worker that no longer holds its OS lock is recovered in this
    # call. No stale-PID deletion or AI-managed polling protocol is needed.
    if foreground or ((job.path / "progress.json").exists() and not _busy(job)):
        return serve(job, execute, deadline=deadline) or _view(job)
    with key_lock(job.path / "launch.lock") as launch:
        if launch and not _busy(job):
            start_detached_process(worker_command, cwd=job.path, env=env,
                                   stdout_path=job.path / "worker.stdout", stderr_path=job.path / "worker.stderr")
            # Only the bounded library waits; neither the skill nor its AI
            # caller is asked to write a sleep loop.
            startup = time.monotonic() + 1
            while not _busy(job) and time.monotonic() < startup and (deadline is None or time.monotonic() < deadline):
                if (job.path / "progress.json").exists():
                    break
                time.sleep(.01)
    while True:
        current = _view(job)
        if current["complete"] or current["state"] in {"failed", "paused"}:
            return current
        if not _busy(job) and (job.path / "progress.json").exists():
            return serve(job, execute, deadline=deadline) or _view(job)
        if deadline is not None and time.monotonic() >= deadline:
            return current
        time.sleep(.02 if deadline is None else min(.02, max(0, deadline - time.monotonic())))
