"""Environment for running a model runner (`run_checks.py`) in a subprocess."""

from __future__ import annotations

import os
from pathlib import Path


def runner_environment(root: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.pop("GIT_INDEX_FILE", None)
    env.update(
        {
            "PYTHONPATH": str(root.resolve()),
            "PYTHONUTF8": "1",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return env
