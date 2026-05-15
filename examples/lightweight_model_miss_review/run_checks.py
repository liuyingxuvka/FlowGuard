from __future__ import annotations

from model import run_review


def main() -> int:
    result = run_review()
    print("=== lightweight model-miss review ===")
    print(result.format_text())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
