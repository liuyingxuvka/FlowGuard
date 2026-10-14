"""Compatibility wrapper: use python -m flowguard.pytest_shards_cli."""

from flowguard.pytest_shards_cli import main


if __name__ == "__main__":
    raise SystemExit(main())
