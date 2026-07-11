"""Run the complete test suite from the canonical Git checkout.

The active FlowGuard workspace is a shadow tree without ``.git``. Starting a
canonical test collection inside the shadow pytest interpreter contaminates
``sys.modules`` with shadow ``tests`` modules, so this helper deliberately
starts a fresh interpreter with the canonical checkout as its working
directory.
"""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys


def canonical_root() -> Path:
    shadow_root = Path(__file__).resolve().parents[3]
    configured = os.environ.get("FLOWGUARD_FORMAL_ROOT", "").strip()
    root = Path(configured).expanduser().resolve() if configured else shadow_root.parent / "FlowGuard"
    if not root.joinpath(".git").exists():
        raise SystemExit(f"canonical FlowGuard Git checkout not found: {root}")
    return root


def main() -> int:
    root = canonical_root()
    passthrough = tuple(sys.argv[1:])
    pytest_args = passthrough or (
        "-q",
        "--junitxml=.flowguard/evidence/harden-ui-content-visibility/full-pytest.junit.xml",
    )
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", *pytest_args],
        cwd=root,
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
