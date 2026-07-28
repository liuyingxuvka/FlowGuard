from __future__ import annotations

from model import run_review


def main() -> int:
    review, reports = run_review()
    for report in reports:
        print(report.format_text())
        print()
    print("=== flowguard structure simplification composite ===")
    print(f"status: {'OK' if review.ok else 'BLOCKED'}")
    return 0 if review.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
