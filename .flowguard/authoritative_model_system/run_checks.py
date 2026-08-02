from __future__ import annotations

from pathlib import Path

from model import run_review
from semantic_self_model import review_semantic_self_mesh, run_known_bad_review


ROOT = Path(__file__).resolve().parents[2]


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


if __name__ == "__main__":
    raise SystemExit(main())
