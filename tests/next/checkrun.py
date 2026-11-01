"""Running `python -m flowguard._next check|show` in a subprocess, as the AI's tool call
does (stdout and stderr captured, so nothing inherits the caller's output), timed."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


@dataclass
class Run:
    code: int
    out: str
    err: str
    seconds: float

    @property
    def lines(self) -> list[str]:
        return self.out.splitlines()

    @property
    def first(self) -> str:
        return self.lines[0] if self.lines else ""

    @property
    def data(self) -> dict:
        lines = self.lines
        assert len(lines) == 1, self.out
        return json.loads(lines[0])


def env(seed=None) -> dict:
    e = {**os.environ, "PYTHONPATH": str(REPO)}
    e.pop("MV", None)
    if seed is not None:
        e["PYTHONHASHSEED"] = str(seed)
    return e


def command(*args) -> list[str]:
    return [sys.executable, "-m", "flowguard._next", *args]


def run_check(root, *args, timeout=120, seed=None, cwd=None) -> Run:
    start = time.monotonic()
    res = subprocess.run(command("check", *args), cwd=str(cwd or root), capture_output=True, text=True,
                         timeout=timeout, env=env(seed))
    return Run(res.returncode, res.stdout, res.stderr, time.monotonic() - start)


def start_check(root, *args) -> subprocess.Popen:
    return subprocess.Popen(command("check", *args), cwd=str(root), stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, env=env())


def gone(pid: int) -> bool:
    """The process no longer runs (a zombie counts as gone)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return True
    stat = Path(f"/proc/{pid}/stat")
    if stat.exists():
        try:
            return stat.read_text().rsplit(")", 1)[1].split()[0] == "Z"
        except FileNotFoundError:
            return True
    return False


def group_gone(pgid: int) -> bool:
    """No process of the group runs (zombies count as gone)."""
    proc = Path("/proc")
    if proc.is_dir():
        for d in proc.iterdir():
            if d.name.isdigit():
                try:
                    fields = (d / "stat").read_text().rsplit(")", 1)[1].split()
                except (FileNotFoundError, ProcessLookupError):
                    continue
                if int(fields[2]) == pgid and fields[0] != "Z":
                    return False
        return True
    try:
        os.killpg(pgid, 0)
    except ProcessLookupError:
        return True
    return False


def wait_until(predicate, timeout: float, step: float = 0.05) -> float | None:
    """Seconds until predicate() held, or None if it did not within timeout."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if predicate():
            return time.monotonic() - start
        time.sleep(step)
    return None
