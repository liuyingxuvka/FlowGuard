"""Source identities used by target wording and promotion input checks."""

from __future__ import annotations
import hashlib
import json
from datetime import datetime, timezone
from .common import git_blob, git_common_directory, git_head, normalize_newlines, read_source
from .inventory import build_inventory, function_digests
from .mapfile import ignore_patterns, load_map
from .targetfile import TARGET_RELDIR, model_helper_digests, target_base

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
        for directory in (".flowguard/requests", ".flowguard/changes", ".flowguard/release-base")
        for p in (root / directory).rglob("*") if p.is_file()
    )
    return {path: _file_hash(root / path) for path in sorted(paths)}


def _git_head(root):
    """Whether root is in a Git repository with a first commit; a failing Git raises with its own message."""
    return git_common_directory(root) is not None and git_head(root) is not None


def _record_base(root):
    """Capture design inputs and complete helper source state, never proof results."""
    data = {"schema": "flowguard.target-base.v1", "helpers": model_helper_digests(root),
            "started": datetime.now(timezone.utc).isoformat()}
    head = git_head(root) if git_common_directory(root) is not None else None
    if head:
        data["git"] = head
    else:
        from .plan import function_identities
        current = load_map(root) if (root / ".flowguard/map.json").exists() else {}
        inv = build_inventory(root, ignore_patterns(current), write_cache=False)
        data["files"] = {}
        for path in inv.source:
            identity = {"sha256": _file_hash(root / path)}
            if path.endswith(".py"):
                identity["functions"] = function_identities(read_source(root / path))
            data["files"][path] = identity
    (root / TARGET_RELDIR / "base.json").write_text(
        json.dumps(data, sort_keys=True) + "\n", encoding="utf-8"
    )


_target_base = target_base  # the one reader, in targetfile so status reads it without the target commands


NO_GIT_FACTS = "without Git only whole-file facts exist"


def _code_changes(root, tree, model_ids, *, base=None):
    """(changes to each model's owned and consumed anchors, other changes in its anchor files) since target start.

    With Git a Python anchor file gives function facts: only a changed anchor, or a function nested in it, is
    credited; other functions and module-level code are reported, never counted. A file without function facts
    (no Git, not Python, removed, does not parse) is one whole-file change that says so."""
    base = _target_base(root) if base is None else base
    if "git" not in base and "files" not in base:
        return {}, {}
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
                changes[path] = [(f"{path} (whole file: {NO_GIT_FACTS})", True)]
            continue
        old = git_blob(root, base["git"], path)  # None: added since the base; a failing Git raises
        if old == raw:
            continue
        if raw is None or not path.endswith(".py"):
            reason = "removed" if raw is None else "not Python source, so no function facts"
            changes[path] = [(f"{path} (whole file: {reason})", True)]
            continue
        try:
            before = function_digests(normalize_newlines(old or b"").decode("utf-8"))
            after = function_digests(normalize_newlines(raw).decode("utf-8"))
        except (UnicodeError, SyntaxError, ValueError) as error:
            changes[path] = [(f"{path} (whole file: it does not parse: {error})", True)]
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
        changes[path] = [(path + ":" + name, False) for name in changed]
        if (
            before["bindings"] != after["bindings"]
            or before["statements"] != after["statements"]
        ):
            changes[path].append((path + " (module level)", False))
    output, unanchored = {}, {}
    for mid, items in anchors.items():
        relevant, other = [], []
        for path in sorted({anchor.partition(":")[0] for anchor in items}):
            for changed, whole_file in changes.get(path, []):
                if whole_file or any(anchor == changed or changed.startswith(anchor + ".") for anchor in items):
                    relevant.append(changed)
                else:
                    other.append(changed)
        if relevant:
            output[mid] = sorted(set(relevant))
        if other:
            unanchored[mid] = sorted(set(other))
    return output, unanchored
