"""Check route registry, API projections, suite owners, and prompt route ids."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="FlowGuard repository root")
    parser.add_argument("--json", action="store_true", help="emit stable JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import flowguard
    from flowguard.route_topology import load_suite_routing_snapshot, validate_route_parity

    report = validate_route_parity(
        root,
        flowguard.default_flowguard_route_profiles(),
        load_suite_routing_snapshot(root),
        public_route_ids=tuple(flowguard.FLOWGUARD_ROUTE_API),
        internal_route_ids=tuple(flowguard.FLOWGUARD_INTERNAL_ROUTE_API),
    )
    print(report.to_json_text() if args.json else report.format_text())
    return 0 if report.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
