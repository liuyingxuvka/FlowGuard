"""Run the local v0.18.4 DevelopmentProcessFlow checks."""

from __future__ import annotations

from model import run_checks


def main() -> int:
    release, broken = run_checks()
    print(release.format_text(max_findings=8))
    print()
    print(broken.format_text(max_findings=8))
    return 0 if release.ok and not broken.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
