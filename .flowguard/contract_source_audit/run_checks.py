"""Run the Python contract source audit rollout review."""

from __future__ import annotations

from model import run_rollout_review


def main() -> int:
    results = run_rollout_review()
    print("=== flowguard python contract source audit rollout ===")
    failed = []
    for name, ok, codes in results:
        status = "PASS" if ok else "FAIL"
        print(f"{name}: {status} codes={list(codes)}")
        if not ok:
            failed.append(name)
    print(f"cases: {len(results)}")
    print(f"failed: {len(failed)}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
