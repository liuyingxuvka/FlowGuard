"""Content-identified execution facts and fresh native witness proofs."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from flowguard.map.common import atomic_write_text, normalize_newlines

from .project import UnsupportedWorld, directory_stamp, file_stamp, replay, state_key
from .skeleton import derive


def content_identity(spec):
    package = Path(__file__).resolve().parents[1]
    engine = [[path.relative_to(package).as_posix(), state_key(normalize_newlines(path.read_bytes()).decode("utf-8"))]
              for path in sorted(package.rglob("*.py"))]
    source = {name: file_stamp(Path(spec["root"]) / name) for name in spec["input_files"]}
    source[".flowguard/skeleton.py"] = file_stamp(Path(spec["root"]) / ".flowguard/skeleton.py")
    return state_key({"engine_source": engine, "python": sys.version,
                      "executable": file_stamp(sys.executable), "source": source, "spec": spec})


def footprint_identity(footprint):
    if not footprint.get("reusable", False):
        return None
    try:
        for path, previous in footprint["files"].items():
            if file_stamp(path) != previous:
                return None
        for path, previous in footprint["directories"].items():
            if directory_stamp(path) != previous:
                return None
    except (OSError, ValueError):
        return None
    return state_key(footprint)


def cache_root(root):
    root = Path(root).resolve()
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--git-common-dir"], capture_output=True, text=True)
    if result.returncode == 0:
        path = Path(result.stdout.strip())
        path = path if path.is_absolute() else root / path
        path = path / "flowguard/cache/behave"
    else:
        path = root / ".flowguard/cache/behave"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cached(path, identity):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        facts = value["facts"]
        if value["identity"] == identity and value["body"] == state_key(facts) and footprint_identity(facts["footprint"]):
            return facts
    except (OSError, ValueError, KeyError, TypeError):
        pass
    return None


def audit(root, *, worlds=None, seeds=(0, 1), steps=64, node_cap=1000, alphabet_cap=1000, use_cache=True, starts=None):
    """Explore actual worlds; missing check implementations remain explicit on every call."""
    spec = derive(root)
    identity = content_identity(spec)
    directory = cache_root(root)
    runs, errors = [], []
    for world in worlds or ("default", "small", "crowded"):
        if world not in spec["worlds"]:
            raise ValueError("unknown world: " + world)
        for seed in seeds:
            start = {"world": world, "seed": seed, **(starts or {}).get(world, {})}
            if "settings" in start:
                raise ValueError("audit explores shipped settings; variants cannot clear a shipped goal")
            options = dict(seed=seed, steps=steps, node_cap=node_cap, alphabet_cap=alphabet_cap)
            key = state_key({"identity": identity, "start": start, "options": options})
            path = directory / (key + ".json")
            facts = _cached(path, identity) if use_cache else None
            reused = facts is not None
            if facts is None:
                try:
                    facts = replay(spec, [], start, operation="explore", options=options)
                except UnsupportedWorld as exc:
                    errors.append({"world": world, "seed": seed, "reason": str(exc)})
                    continue
                if footprint_identity(facts["footprint"]):
                    atomic_write_text(path, json.dumps({"identity": identity, "body": state_key(facts), "facts": facts}, ensure_ascii=False))
            for witness in facts["witnesses"]:
                witness["identity"] = identity
                witness["footprint"] = facts["footprint"]
            runs.append({"world": world, "seed": seed, "reused": reused, "facts": facts})
    hits = {name for run in runs for name in run["facts"]["execution"]["hit_functions"]}
    return {"identity": identity, "runs": runs, "errors": errors,
            "missing_checks": ["GC" + str(number) for number in range(1, 10)],
            "coverage": {"hit_functions": sorted(hits), "known_functions": len(spec["source_functions"]),
                         "front_doors": spec["unknown"], "ui": "requested" if starts else "not requested"},
            "facts_reused": sum(run["reused"] for run in runs), "items": []}


def prove(root, candidate, *, persist=True):
    """A recipe is evidence only after a fresh child proves it under current shipped inputs."""
    from .report import item_id

    spec = derive(root)
    identity = content_identity(spec)
    prefix = candidate["prefix"]
    allowed = {"receiver", "name", "args", "kwargs", "replace", "property"}
    if any(set(row) - allowed or row["name"].startswith("_") for row in prefix):
        return {"state": "engine-defect", "reason": "private edit or non-public prefix", "matched": False}
    if candidate.get("outcomes") is not None and len(candidate["outcomes"]) != len(prefix):
        return {"state": "engine-defect", "reason": "witness outcomes do not match its public prefix", "matched": False}
    start = dict(candidate.get("start", {}))
    if set(start) - {"world", "seed", "files", "settings", "ui"}:
        return {"state": "engine-defect", "reason": "unrecognized starting-state edit", "matched": False}
    ignored = start.pop("settings", None)
    same_inputs = candidate.get("identity") == identity and not ignored and bool(footprint_identity(candidate.get("footprint", {})))
    options = {"goal": candidate["semantic"], "outcomes": candidate.get("outcomes")}
    try:
        if candidate.get("negative"):
            facts = replay(spec, [], start, operation="search", options={"goal": candidate["semantic"], "prefix": prefix, **candidate["bounds"]})
            matched = not facts["found"] and facts["extent"]["complete"]
        else:
            facts = replay(spec, prefix, start, operation="prove", options=options)
            matched = facts["matched"]
    except UnsupportedWorld as exc:
        return {"state": "unchecked", "reason": str(exc), "matched": False, "ignored_settings": ignored}
    if not footprint_identity(facts["footprint"]):
        return {"state": "unchecked", "reason": "execution inputs are incomplete or changed during proof", "matched": False}
    result = {"state": "reproduced" if matched else "engine-defect" if same_inputs else "no-longer-reproduces",
              "matched": matched, "id": item_id(candidate["semantic"]), "semantic": candidate["semantic"],
              "ignored_settings": ignored, "proof": facts, "identity": identity}
    if persist and matched:
        recipe = {**candidate, "identity": identity, "footprint": facts["footprint"], "start": start}
        path = cache_root(root) / "witnesses" / (result["id"] + ".json")
        atomic_write_text(path, json.dumps(recipe, ensure_ascii=False))
    return result
