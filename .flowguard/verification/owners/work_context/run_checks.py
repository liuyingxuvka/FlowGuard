"""Run the provider-neutral WorkContext executable model."""

from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "work_context"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))

from pathlib import Path
import sys


import json

import model


def main() -> int:
    report = model.run_model_checks()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1

from flowguard.map.runner import run_owner
if __name__ == "__main__":
    raise SystemExit(run_owner(main))
