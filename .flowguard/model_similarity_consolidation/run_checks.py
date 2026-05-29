"""Run the model similarity consolidation self-model."""

from __future__ import annotations

import json
from pathlib import Path

import model


def main() -> int:
    rows = model.run_review()
    ok = all(row_ok for _, row_ok, _ in rows)
    print("=== flowguard model similarity consolidation self-model ===")
    print(f"status: {'OK' if ok else 'BLOCKED'}")
    print(f"cases: {len(rows)}")
    for name, row_ok, summary in rows:
        print(f"- {name}: {'OK' if row_ok else 'BLOCKED'} :: {summary}")
    result_path = Path(__file__).with_name("result.json")
    result_path.write_text(
        json.dumps(
            {
                "status": "passed" if ok else "failed",
                "cases": [
                    {"name": name, "ok": row_ok, "summary": summary}
                    for name, row_ok, summary in rows
                ],
            },
            indent=2,
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
