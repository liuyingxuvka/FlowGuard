from pathlib import Path
import sys

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "mesh_target_split_derivation"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[4]
MODEL_ROOT = PROJECT_ROOT / ".flowguard" / "models" / "owners" / "mesh_target_split_derivation"
sys.path.insert(0, str(MODEL_ROOT))
sys.path.insert(0, str(PROJECT_ROOT))

from model import run_review  # noqa: E402

from flowguard.native_case_runner import native_main
def _native_owner_main() -> int:
    report = run_review()
    print(report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(native_main("model:mesh_target_split_derivation", _native_owner_main))
