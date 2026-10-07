"""Run the sole native producer for corpus aggregation and coverage semantics."""
from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[4]
MODEL_ROOT = ROOT / ".flowguard/models/owners/problem_corpus_coverage"
for path in (ROOT, MODEL_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import model
from model import run_review
from flowguard.native_case_runner import native_main


def main() -> int:
    result = run_review()
    rows = result["native_cases"]
    for row in rows:
        print(f"{row['name']}: {'PASS' if row['ok'] else 'FAIL'}")
    return 0 if rows and all(row["ok"] for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(native_main(
        "model:problem_corpus_coverage", main,
        declared_source_exporter=model.export_path_quality_source,
    ))
