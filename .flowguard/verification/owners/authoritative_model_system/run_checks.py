from __future__ import annotations

from pathlib import Path
import sys

_FLOWGUARD_PROJECT_ROOT = Path(__file__).resolve().parents[4]
_FLOWGUARD_MODEL_ROOT = _FLOWGUARD_PROJECT_ROOT / ".flowguard" / "models" / "owners" / "authoritative_model_system"
for _flowguard_path in (_FLOWGUARD_PROJECT_ROOT, _FLOWGUARD_MODEL_ROOT):
    if str(_flowguard_path) not in sys.path:
        sys.path.insert(0, str(_flowguard_path))


from pathlib import Path
import sys

from model import run_review
from semantic_self_model import review_semantic_self_mesh, run_known_bad_review


ROOT = Path(__file__).resolve().parents[4]


def main() -> int:
    report = run_review()
    print(report.format_text())
    print()
    semantic_report = review_semantic_self_mesh(ROOT)
    print(semantic_report.format_text())
    print()
    known_bad_ok, known_bad_failures = run_known_bad_review(ROOT)
    print(
        "semantic self-mesh known-bad review: "
        f"{'pass' if known_bad_ok else 'fail'}; "
        f"cases=6; unexpected={','.join(known_bad_failures) or 'none'}"
    )
    return 0 if report.ok and semantic_report.ok and known_bad_ok else 1

from flowguard.native_case_runner import native_main
if __name__ == "__main__":
    raise SystemExit(native_main("model:authoritative_model_system", main))
