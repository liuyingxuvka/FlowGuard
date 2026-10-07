"""Execute the single finite Python engine owner through the native bridge."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
MODEL_ROOT = ROOT / ".flowguard/models/owners/python_function_state_verification"
for path in (ROOT, MODEL_ROOT):
    sys.path.insert(0, str(path))

from model import export_path_quality_source, run_review
from flowguard.native_case_runner import native_main


def main():
    report = run_review()
    for case in report["native_cases"]:
        print(f'{case["name"]}: {"PASS" if case["ok"] else "FAIL"} observed={case["observed_status"]}')
    return 0 if all(case["ok"] for case in report["native_cases"]) else 1


if __name__ == "__main__":
    raise SystemExit(native_main("model:python_function_state_verification", main,
                                declared_source_exporter=export_path_quality_source))
