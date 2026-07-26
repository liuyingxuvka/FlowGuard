"""Run the provider-neutral WorkContext executable model."""

from __future__ import annotations

import json

import model


def main() -> int:
    report = model.run_model_checks()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
