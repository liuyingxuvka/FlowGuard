"""Thin normal-domain entry: produce a task context once from a frozen request."""
from pathlib import Path
import argparse
import json
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    source = Path(__file__).resolve().parents[1]
    if str(source) not in sys.path:
        sys.path.insert(0, str(source))
    from flowguard.functional_read import strict_json_bytes
    from flowguard.functional_task_context import produce_functional_task_context
    from flowguard.evidence_receipts import tokenize_command
    root = args.root.resolve()
    request_path = args.request.resolve()
    request_path.relative_to(root)
    from flowguard.model_authority_store import _selected_file_bytes
    payload = _selected_file_bytes(root, request_path.relative_to(root).as_posix())
    request = strict_json_bytes(payload)
    command_args = [sys.executable, "-B", str(Path(__file__).resolve()),
        *(argv if argv is not None else sys.argv[1:])]
    # The domain's command identity is a string shared by its proof, publication
    # freeze and independent verifier. JSON retains exact argument boundaries.
    command = json.dumps(list(tokenize_command(command_args, workspace_root=root,
        python_prefix=sys.prefix)), ensure_ascii=False, separators=(",", ":"))
    result = produce_functional_task_context(repository_root=root, request=request,
        output_directory=args.output_dir, command=command)
    if _selected_file_bytes(root, request_path.relative_to(root).as_posix()) != payload:
        result = {"status": "blocked", "reason": "functional_producer_request_changed"}
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
