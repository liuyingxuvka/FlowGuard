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
    known = []
    for path in sorted((directory / "witnesses").glob("*.json")):
        try:
            recipe = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(recipe.get("semantic"), dict) and isinstance(recipe.get("prefix"), list):
                known.append({key: recipe[key] for key in ("semantic", "prefix", "outcomes", "start") if key in recipe})
        except (OSError, ValueError, TypeError):
            continue
    recording_path = directory / ("recordings-" + identity + ".json")
    has_tests = any(Path(name).name.startswith("test_") or Path(name).name.endswith("_test.py") for name in spec["input_files"])
    recordings = _cached(recording_path, identity) if use_cache else None
    if recordings is None:
        if has_tests:
            try:
                recordings = replay(spec, [], operation="record", timeout=120)
                if footprint_identity(recordings["footprint"]):
                    atomic_write_text(recording_path, json.dumps({"identity": identity, "body": state_key(recordings), "facts": recordings}, ensure_ascii=False))
            except UnsupportedWorld as exc:
                recordings = {"recordings": [], "scope_error": str(exc)}
        else:
            recordings = {"recordings": []}
    recording_footprint = footprint_identity(recordings.get("footprint", {}))
    recording_token = state_key([recordings, recording_footprint]) if recording_footprint else state_key("no test files") if not has_tests else None
    replay_path = directory / ("replayed-tests-" + identity + "-" + str(recording_token) + ".json")
    test_replay = _cached(replay_path, identity) if use_cache and recording_token is not None else None
    if test_replay is None:
        if recordings["recordings"]:
            try:
                test_replay = replay(spec, [], operation="witnesses", options={"recordings": recordings["recordings"]}, timeout=300)
                if recording_token is not None and footprint_identity(test_replay["footprint"]):
                    atomic_write_text(replay_path, json.dumps({"identity": identity, "body": state_key(test_replay), "facts": test_replay}, ensure_ascii=False))
            except UnsupportedWorld as exc:
                test_replay = {"witnesses": [], "prefixes": [], "scope_error": str(exc)}
        else:
            test_replay = {"witnesses": [], "prefixes": []}
    replay_footprint = footprint_identity(test_replay.get("footprint", {}))
    replay_token = state_key([recording_token, test_replay, replay_footprint]) if replay_footprint else state_key([recording_token, "no recorded public prefixes"]) if recording_token is not None and not recordings["recordings"] else None
    for world in worlds or ("default", "small", "crowded"):
        if world not in spec["worlds"]:
            raise ValueError("unknown world: " + world)
        for seed in seeds:
            start = {"world": world, "seed": seed, **(starts or {}).get(world, {})}
            if "settings" in start:
                raise ValueError("audit explores shipped settings; variants cannot clear a shipped goal")
            options = dict(seed=seed, steps=steps, node_cap=node_cap, alphabet_cap=alphabet_cap)
            key = state_key({"identity": identity, "start": start, "options": options, "known": known,
                             "recordings": recording_token, "test_replay": replay_token})
            path = directory / (key + ".json")
            facts = _cached(path, identity) if use_cache and recording_token is not None and replay_token is not None else None
            reused = facts is not None
            if facts is None:
                try:
                    facts = replay(spec, [], start, operation="audit", options={**options, "known": known, "test_replay": {key: value for key, value in test_replay.items() if key not in {"replays", "footprint", "execution"}}}, timeout=300)
                except UnsupportedWorld as exc:
                    errors.append({"world": world, "seed": seed, "reason": str(exc)})
                    continue
                if recording_token is not None and replay_token is not None and footprint_identity(facts["footprint"]):
                    atomic_write_text(path, json.dumps({"identity": identity, "body": state_key(facts), "facts": facts}, ensure_ascii=False))
            for witness in facts["witnesses"]:
                witness["identity"] = identity
                witness["footprint"] = facts["footprint"]
            runs.append({"world": world, "seed": seed, "reused": reused, "facts": facts})
    hits = {name for run in runs for name in run["facts"]["execution"]["hit_functions"]}
    candidates = {}
    for run in runs:
        for check in ("reach", "stuck"):
            for candidate in run["facts"][check]["candidates"]:
                key = state_key(candidate["semantic"])
                candidate.update(identity=identity, footprint=run["facts"]["footprint"])
                candidates.setdefault(key, candidate)
    items = []
    for candidate in candidates.values():
        proof = prove(root, candidate)
        if proof["matched"]:
            items.append({**candidate, "id": proof["id"], "proof": proof})
        else:
            errors.append({"world": candidate["start"].get("world", "test-public-prefix"), "seed": candidate["start"].get("seed"),
                           "reason": proof.get("reason", proof["state"])})
    return {"identity": identity, "runs": runs, "errors": errors,
            "missing_checks": ["GC" + str(number) for number in (2, 4, 5, 6, 7, 8, 9)],
            "coverage": {"hit_functions": sorted(hits), "known_functions": len(spec["source_functions"]),
                         "front_doors": spec["unknown"], "ui": "requested" if starts else "not requested"},
            "facts_reused": sum(run["reused"] for run in runs), "items": items,
            "test_scope": {key: value for key, value in recordings.items() if key not in {"recordings", "footprint"}}}


def prove(root, candidate, *, persist=True):
    """A recipe is evidence only after a fresh child proves it under current shipped inputs."""
    from .report import item_id

    spec = derive(root)
    identity = content_identity(spec)
    semantic = candidate["semantic"]
    if str(semantic.get("receiver", "")).startswith("ui:"):
        construction = next((row for row in candidate["prefix"] if row.get("construct") == "ui" and row["receiver"] == semantic["receiver"]), None)
        if construction is None:
            return {"state": "engine-defect", "reason": "the UI witness has no public construction event", "matched": False}
        parameters = [row for row in spec["ui_constructor"]["parameters"] if row["name"] != spec["ui_constructor"]["system_parameter"]]
        actor = {row["name"]: row["default"] for row in parameters if "default" in row}
        actor.update({row["name"]: value for row, value in zip(parameters, construction.get("args", []))})
        actor.update(construction.get("kwargs", {}))
        candidate = {**candidate, "search_goal": candidate.get("search_goal", semantic),
                     "semantic": {**semantic, "receiver": spec["ui"], "actor": actor}}
    prefix = candidate["prefix"]
    allowed = {"receiver", "name", "args", "kwargs", "replace", "property", "construct"}
    if any(set(row) - allowed or row.get("name", "").startswith("_") or row.get("construct") not in {None, "ui"} for row in prefix):
        return {"state": "engine-defect", "reason": "private edit or non-public prefix", "matched": False}
    if candidate.get("outcomes") is not None and len(candidate["outcomes"]) != len(prefix):
        return {"state": "engine-defect", "reason": "witness outcomes do not match its public prefix", "matched": False}
    start = dict(candidate.get("start", {}))
    if set(start) - {"world", "seed", "files", "settings", "ui"}:
        return {"state": "engine-defect", "reason": "unrecognized starting-state edit", "matched": False}
    ignored = start.pop("settings", None)
    same_inputs = candidate.get("identity") == identity and not ignored and bool(footprint_identity(candidate.get("footprint", {})))
    search_goal = candidate.get("search_goal", candidate["semantic"])
    options = {"goal": search_goal, "outcomes": candidate.get("outcomes")}
    try:
        if candidate.get("negative"):
            facts = replay(spec, [], start, operation="search", options={"goal": search_goal, "prefix": prefix, **candidate["bounds"]}, timeout=300)
            matched = not facts["found"] and facts["extent"]["complete"]
        else:
            facts = replay(spec, prefix, start, operation="prove", options=options)
            matched = facts["matched"]
    except UnsupportedWorld as exc:
        return {"state": "unchecked", "reason": str(exc), "matched": False, "ignored_settings": ignored}
    if not footprint_identity(facts["footprint"]):
        return {"state": "unchecked", "reason": "execution inputs are incomplete or changed during proof", "matched": False}
    identifier = item_id(candidate["semantic"])
    previous_path = cache_root(root) / "witnesses" / (identifier + ".json")
    if previous_path.is_file():
        previous = json.loads(previous_path.read_text(encoding="utf-8"))
        if previous["semantic"] != candidate["semantic"]:
            identifier = item_id(candidate["semantic"], length=6)
    result = {"state": "reproduced" if matched else "engine-defect" if same_inputs else "no-longer-reproduces",
              "matched": matched, "id": identifier, "semantic": candidate["semantic"],
              "ignored_settings": ignored, "proof": facts, "identity": identity}
    if persist and matched:
        recipe = {**candidate, "identity": identity, "footprint": facts["footprint"], "start": start}
        path = cache_root(root) / "witnesses" / (result["id"] + ".json")
        atomic_write_text(path, json.dumps(recipe, ensure_ascii=False))
    return result
