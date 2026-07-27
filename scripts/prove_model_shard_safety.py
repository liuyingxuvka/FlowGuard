"""Prove that one isolated-output model is safe for parallel regression shards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from flowguard.shard_safety import prove_manifest_model_shard_safety


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = prove_manifest_model_shard_safety(
        Path(args.root),
        args.model,
        output_dir=Path(args.output_dir),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print("status:", "PASS" if result["ok"] else "FAIL")
        for name, passed in result["checks"].items():
            print(f"- {name}: {'PASS' if passed else 'FAIL'}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
