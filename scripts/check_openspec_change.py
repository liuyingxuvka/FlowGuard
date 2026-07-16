"""Run OpenSpec validation through an explicit cross-platform executable bridge."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def _openspec_command() -> list[str]:
    if os.name == "nt":
        command = shutil.which("openspec.cmd")
        if not command:
            candidate = Path.home() / "AppData" / "Roaming" / "npm" / "openspec.cmd"
            if candidate.is_file():
                command = str(candidate)
        if not command:
            raise FileNotFoundError("openspec.cmd was not found on PATH")
        shell = os.environ.get("COMSPEC") or shutil.which("cmd.exe")
        if not shell:
            raise FileNotFoundError("cmd.exe was not found")
        return [shell, "/d", "/s", "/c", command]
    command = shutil.which("openspec")
    if not command:
        raise FileNotFoundError("openspec was not found on PATH")
    return [command]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--change", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    command = _openspec_command() + ["validate", args.change]
    if args.strict:
        command.append("--strict")
    completed = subprocess.run(command, text=True, check=False)
    return completed.returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, OSError) as exc:
        sys.stderr.write(f"{exc}\n")
        raise SystemExit(1)
