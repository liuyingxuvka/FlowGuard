from pathlib import Path
import sys

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "hierarchical_model_mesh"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODEL_ROOT = PROJECT_ROOT / ".flowguard" / "models" / "owners" / "hierarchical_model_mesh"
sys.path.insert(0, str(MODEL_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from model import run_review  # noqa: E402

from flowguard.map.runner import run_owner
def _native_owner_main() -> tuple:
    report = run_review()
    print(f"scenario_report: status={'pass' if report.ok else 'blocked'} cases={len(report.results)}")
    return report


if __name__ == "__main__":
    raise SystemExit(run_owner(_native_owner_main))
