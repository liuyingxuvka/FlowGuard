"""Source identities used by target wording and promotion input checks."""

from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from .common import normalize_newlines
from .inventory import build_inventory, function_digests
from .mapfile import ignore_patterns, load_map
from .targetfile import TARGET_RELDIR, model_helper_digests

_FIELD_CODES = {
    "pattern_dead": ("files",),
    "component_empty": ("files",),
    "test_missing": ("tests",),
    "dep_undeclared": ("depends_on", "layer"),
    "dep_unused": ("depends_on", "layer"),
    "layer_violation": ("depends_on", "layer"),
    "dependency_cycle": ("depends_on", "layer"),
}
_VOLATILE = {"status", "fingerprint", "_hint"}


def _changed_fields(current, planned) -> set[str]:
    """Field names whose values differ between a current component and its target entry."""
    keys = (set(current) | set(planned)) - _VOLATILE
    return {key for key in keys if current.get(key) != planned.get(key)}


def _subject_changed(finding, current, planned, layers_changed) -> bool:
    """Whether the target changes what this component finding is about (FG-317 table)."""
    changed = _changed_fields(current, planned)
    if finding.code in ("anchor_broken", "entrypoint_unmodeled"):
        anchors = [
            anchor
            for anchor in current.get("entrypoints", [])
            if anchor in finding.message
            or (
                anchor.partition(":")[0] in finding.message
                and repr(anchor.partition(":")[2]) in finding.message
            )
            or finding.message == f"anchor file missing: {anchor.partition(':')[0]}"
        ]
        if anchors:
            return any(
                anchor not in planned.get("entrypoints", []) for anchor in anchors
            )
        return "entrypoints" in changed
    if finding.code in _FIELD_CODES:
        return bool(changed & set(_FIELD_CODES[finding.code])) or (
            layers_changed and _FIELD_CODES[finding.code][-1] == "layer"
        )
    return bool(changed)


def _file_hash(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _promotion_inputs(root, data):
    """Operation-local byte identities, never stored as a check result or cache."""
    inv = build_inventory(
        root,
        ignore_patterns(data),
        with_bodies=False,
        write_cache=False,
        import_roots=tuple(data.get("import_roots", ())),
    )
    paths = set(inv.files) | {".flowguard/map.json"}
    paths.update(
        p.relative_to(root).as_posix()
        for p in (root / ".flowguard/models").glob("*.py")
        if p.is_file()
    )
    paths.update(
        p.relative_to(root).as_posix()
        for p in (root / TARGET_RELDIR).rglob("*")
        if p.is_file()
    )
    paths.update(
        p.relative_to(root).as_posix()
        for directory in (".flowguard/requests", ".flowguard/changes")
        for p in (root / directory).rglob("*") if p.is_file()
    )
    return {path: _file_hash(root / path) for path in sorted(paths)}


def _git(root, *arguments):
    try:
        return subprocess.run(["git", "-C", str(root), *arguments], capture_output=True)
    except OSError:
        return None


def _git_head(root):
    result = _git(root, "rev-parse", "--verify", "HEAD")
    return result is not None and result.returncode == 0


def _record_base(root):
    """Capture design inputs and complete helper source state, never proof results."""
    data = {"schema": "flowguard.target-base.v1", "helpers": model_helper_digests(root),
            "started": datetime.now(timezone.utc).isoformat()}
    if _git_head(root):
        data["git"] = _git(root, "rev-parse", "HEAD").stdout.decode().strip()
    else:
        current = load_map(root) if (root / ".flowguard/map.json").exists() else {}
        inv = build_inventory(root, ignore_patterns(current), write_cache=False)
        data["files"] = {
            path: {"sha256": _file_hash(root / path)} for path in inv.source
        }
    (root / TARGET_RELDIR / "base.json").write_text(
        json.dumps(data, sort_keys=True) + "\n", encoding="utf-8"
    )


def _target_base(root):
    """Read target input identity once for design diagnostics, never promotion."""
    try:
        return json.loads(
            (root / TARGET_RELDIR / "base.json").read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return {"git": "HEAD"} if _git_head(root) else {}


def _code_changes(root, tree, model_ids, *, base=None):
    """Changed source symbols relevant to each target's owned and consumed anchors."""
    base = _target_base(root) if base is None else base
    if "git" not in base and "files" not in base:
        return {}
    anchors = {}
    for mid in sorted(model_ids):
        contract = tree.nodes[mid].contract
        anchors[mid] = list(contract.get("IMPLEMENTED_BY", {}).values()) + list(
            contract.get("USES", {}).values()
        )
    changes = {}
    for path in sorted(
        {anchor.partition(":")[0] for items in anchors.values() for anchor in items}
    ):
        current = root / path
        raw = current.read_bytes() if current.is_file() else None
        if "git" not in base:
            before = base["files"].get(path, {}).get("sha256")
            after = hashlib.sha256(raw).hexdigest() if raw is not None else None
            if before != after:
                changes[path] = [path]
            continue
        previous = _git(root, "show", base["git"] + ":" + path)
        old = (
            previous.stdout
            if previous is not None and previous.returncode == 0
            else None
        )
        if old == raw:
            continue
        if raw is None or not path.endswith(".py"):
            changes[path] = [path]
            continue
        try:
            before = function_digests(normalize_newlines(old or b"").decode("utf-8"))
            after = function_digests(normalize_newlines(raw).decode("utf-8"))
        except (UnicodeError, SyntaxError, ValueError):
            changes[path] = [path]
            continue

        def identities(digests):
            return {
                **{
                    name: (item["sig_digest"], item["body_digest"])
                    for name, item in digests["functions"].items()
                },
                **{
                    name: item["class_digest"]
                    for name, item in digests["classes"].items()
                },
            }

        left, right = identities(before), identities(after)
        changed = {
            name
            for name in left.keys() | right.keys()
            if left.get(name) != right.get(name)
        }
        changed = sorted(
            name
            for name in changed
            if not any(
                name.startswith(parent + ".") for parent in changed if parent != name
            )
        )
        if changed:
            changes[path] = [path + ":" + name for name in changed]
        elif (
            before["bindings"] != after["bindings"]
            or before["statements"] != after["statements"]
        ):
            changes[path] = [path]
    output = {}
    for mid, items in anchors.items():
        relevant = []
        fallback = []
        for path in sorted({anchor.partition(":")[0] for anchor in items}):
            candidates = changes.get(path, [])
            fallback.extend(candidates)
            for changed in candidates:
                for anchor in items:
                    if (
                        anchor == changed
                        or changed == path
                        and anchor.partition(":")[0] == path
                        or anchor.startswith(changed + ".")
                        or changed.startswith(anchor + ".")
                    ):
                        relevant.append(changed)
                        break
        values = sorted(set(relevant or fallback))
        if values:
            output[mid] = values
    return output
