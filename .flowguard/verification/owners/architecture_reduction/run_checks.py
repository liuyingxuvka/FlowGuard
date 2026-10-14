from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT), str(ROOT / ".flowguard/models/owners/architecture_reduction")]

from model import run_review  # noqa: E402

from flowguard.map.runner import run_owner
def _native_owner_main() -> tuple:
    report = run_review()
    print(f"scenario_report: status={'pass' if report.ok else 'blocked'} cases={len(report.results)}")
    return report


if __name__ == "__main__":
    raise SystemExit(run_owner(_native_owner_main))
