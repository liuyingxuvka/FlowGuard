"""Private source-checkout entry point for completion readiness."""

from __future__ import annotations

from pathlib import Path
import sys


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(_REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPOSITORY_ROOT))

from flowguard.completion_readiness import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
