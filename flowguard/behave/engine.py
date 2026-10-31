"""Content-identified execution facts and fresh native witness proofs."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

from flowguard.map.common import atomic_write_text, normalize_newlines

from .project import UnsupportedWorld, directory_stamp, file_stamp, replay, state_key, ui_identity
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
    traces = [trace for run in runs for trace in run["facts"]["traces"]]
    traces.extend({**trace, "origin": "test"} for trace in test_replay.get("replays", []) if trace["eligible"])
    settings = {"candidates": [], "information": [], "unknown": [], "profiles": [], "traces": len(traces)}
    if spec.get("settings"):
        settings_key = state_key({"identity": identity, "traces": traces, "test_replay": replay_token, "alphabet_cap": alphabet_cap})
        settings_path = directory / ("settings-" + settings_key + ".json")
        settings = _cached(settings_path, identity) if use_cache and replay_token is not None else None
        if settings is None:
            try:
                settings = replay(spec, [], operation="settings", options={"traces": traces, "alphabet_cap": alphabet_cap}, timeout=300)
                if replay_token is not None and footprint_identity(settings["footprint"]):
                    atomic_write_text(settings_path, json.dumps({"identity": identity, "body": state_key(settings), "facts": settings}, ensure_ascii=False))
            except UnsupportedWorld as exc:
                settings = {"candidates": [], "information": [], "profiles": [], "unknown": [{"check": "GC5", "reason": str(exc)}]}
    saved = collect_saves(root, steps=steps, node_cap=node_cap, alphabet_cap=alphabet_cap)
    saved_scope = {"sources": [{key: value for key, value in row.items() if key != "spec"} for row in saved["sources"]],
                   "files": [], "unknown": [{"check": "GC4", **row} for row in saved["unknown"]],
                   "fixture_loads": saved.get("fixture_loads", []), "current_identity": identity,
                   "fixture_scope": saved["fixture_scope"],
                   "no_saved_files": saved["no_saved_files"]}
    saved_candidates = []
    saved_hits = set()
    for seed in seeds if saved["saves"] else ():
        options = dict(saves=saved["saves"], seed=seed, steps=steps, node_cap=node_cap, alphabet_cap=alphabet_cap)
        key = state_key({"identity": identity, "saved_files": options})
        path = directory / ("saved-" + key + ".json")
        facts = _cached(path, identity) if use_cache else None
        if facts is None:
            try:
                facts = replay(spec, [], operation="saved", options=options, timeout=300)
            except UnsupportedWorld as exc:
                saved_scope["unknown"].append({"check": "GC4", "reason": str(exc), "seed": seed})
                continue
            if footprint_identity(facts["footprint"]):
                atomic_write_text(path, json.dumps({"identity": identity, "body": state_key(facts), "facts": facts}, ensure_ascii=False))
        saved_scope["files"].extend({**row, "seed": seed} for row in facts["files"])
        saved_scope["unknown"].extend(facts["unknown"])
        saved_hits.update(facts["execution"]["hit_functions"])
        saved_candidates.extend({**candidate, "identity": identity, "footprint": facts["footprint"]} for candidate in facts["candidates"])
    hits = saved_hits | set(settings.get("execution", {}).get("hit_functions", [])) | {name for run in runs for name in run["facts"]["execution"]["hit_functions"]}
    candidates = {}
    for run in runs:
        for check in ("reach", "stuck", "agreement"):
            for candidate in run["facts"][check]["candidates"]:
                key = state_key(candidate["semantic"])
                candidate.update(identity=identity, footprint=run["facts"]["footprint"])
                candidates.setdefault(key, candidate)
    for candidate in saved_candidates:
        candidates.setdefault(state_key(candidate["semantic"]), candidate)
    for candidate in settings["candidates"]:
        candidate.update(identity=identity, footprint=settings["footprint"])
        candidates.setdefault(state_key(candidate["semantic"]), candidate)
    items = []
    for candidate in candidates.values():
        proof = prove(root, candidate)
        if proof["matched"]:
            items.append({**candidate, "id": proof["id"], "proof": proof})
        else:
            errors.append({"world": candidate["start"].get("world", "test-public-prefix"), "seed": candidate["start"].get("seed"),
                           "reason": proof.get("reason", proof["state"])})
    return {"identity": identity, "runs": runs, "errors": errors,
            "missing_checks": ["GC" + str(number) for number in (6, 7, 8, 9)],
            "coverage": {"hit_functions": sorted(hits), "known_functions": len(spec["source_functions"]),
                         "front_doors": spec["unknown"], "ui": "requested" if starts else "not requested"},
            "facts_reused": sum(run["reused"] for run in runs), "items": items, "saved_files": saved_scope,
            "settings": {key: value for key, value in settings.items() if key not in {"candidates", "footprint", "execution"}},
            "advice": spec.get("optional_argument_advice", []),
            "test_scope": {key: value for key, value in recordings.items() if key not in {"recordings", "footprint"}}}


def prove(root, candidate, *, persist=True):
    """A recipe is evidence only after a fresh child proves it under current shipped inputs."""
    from .report import item_id

    spec = derive(root)
    identity = content_identity(spec)
    semantic = candidate["semantic"]
    if str(semantic.get("receiver", "")).startswith("ui:"):
        try:
            actor = ui_identity(spec, candidate["prefix"], semantic["receiver"])
        except UnsupportedWorld as exc:
            return {"state": "engine-defect", "reason": str(exc), "matched": False}
        candidate = {**candidate, "search_goal": candidate.get("search_goal", semantic),
                     "semantic": {**semantic, **actor}}
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
    saved = candidate.get("saved_file")
    if saved:
        # The old side is executable provenance, not a remembered claim that these bytes loaded.
        source, file = saved["source"], saved["file"]
        try:
            load = {"receiver": "system", "name": spec["persistence"]["load"],
                    "args": [{"$file": file["name"]}], "replace": True}
            if not prefix or prefix[0] != load:
                raise UnsupportedWorld("the saved-file witness must begin with its actual public load")
            old_spec = derive(source["root"])
            old_inputs = {name: file_stamp(Path(old_spec["root"]) / name) for name in old_spec["input_files"]}
            old_inputs[".flowguard/skeleton.py"] = file_stamp(Path(old_spec["root"]) / ".flowguard/skeleton.py")
            if state_key(old_inputs) != source["source_identity"] or old_spec["persistence"] != source["persistence"]:
                raise UnsupportedWorld("the identified saved-file source or persistence binding changed")
            tree = subprocess.run(["git", "-C", str(root), "rev-parse", source["revision"] + "^{tree}"], capture_output=True, text=True)
            if tree.returncode or tree.stdout.strip() != source["tree"]:
                raise UnsupportedWorld("the saved-file source revision is unavailable or changed")
            recipe = saved.get("recipe")
            old = replay(old_spec, [], (recipe or {}).get("start", {}), operation="saves", timeout=300,
                         options={"prefixes": [recipe["prefix"]], "steps": 1} if recipe else {"generate": False, "committed": [file]})
            reproduced = next((row for row in old["saves"] if row["file"]["bytes"] == file["bytes"] and row["old_load"]["outcome"] == "success"), None)
            if reproduced is None or not footprint_identity(old["footprint"]):
                raise UnsupportedWorld("the source public save/load no longer reproduces the accepted bytes")
            if start.get("files", {}).get(file["name"]) != file["bytes"]:
                raise UnsupportedWorld("the current load recipe does not contain the identified saved bytes")
        except (UnsupportedWorld, OSError, ValueError, KeyError) as exc:
            return {"state": "unchecked", "reason": str(exc), "matched": False, "ignored_settings": ignored}
    search_goal = candidate.get("search_goal", candidate["semantic"])
    options = {"goal": search_goal, "outcomes": candidate.get("outcomes")}
    try:
        if semantic.get("check") == "GC2":
            facts = replay(spec, prefix, start, operation="agreement-proof", options={"comparison": candidate["comparison"]})
            matched = facts["matched"]
            if not matched and facts["unknown"]:
                raise UnsupportedWorld(facts["unknown"][0]["reason"])
        elif semantic.get("check") == "GC5":
            facts = replay(spec, [], operation="settings-proof", options={"traces": candidate["settings_traces"],
                           "setting": semantic["setting"], "alphabet_cap": candidate["alphabet_cap"]}, timeout=300)
            matched = any(row["semantic"] == semantic for row in facts["candidates"])
            if not matched and not facts["information"] and facts["unknown"]:
                raise UnsupportedWorld(facts["unknown"][0]["reason"])
        elif semantic.get("kind") in {"loading", "loading_crash"}:
            expected = "crash" if semantic["kind"] == "loading_crash" else "refusal"
            facts = replay(spec, prefix, start, operation="loading-proof", options={"outcome": expected})
            matched = facts["matched"]
        elif candidate.get("negative"):
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


def old_releases(root):
    """Export reachable tagged source bytes; a tagless HEAD is only a fixture baseline."""
    import hashlib
    import os
    import tempfile

    root = Path(root).resolve()
    unknown = []
    def git(*args, binary=False):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
        if result.returncode:
            raise ValueError(result.stderr.decode("utf-8", "replace").strip() or "Git source history unavailable")
        return result.stdout if binary else result.stdout.decode("utf-8").strip()
    try:
        if Path(git("rev-parse", "--show-toplevel")).resolve() != root:
            raise ValueError("historical saved files require the selected Git project root")
        commits = git("rev-list", "--topo-order", "HEAD").splitlines()
        order = {revision: position for position, revision in enumerate(commits)}
        tagged = {}
        for row in git("for-each-ref", "--merged=HEAD", "--format=%(refname:strip=2) %(objectname) %(*objectname)", "refs/tags").splitlines():
            values = row.split()
            revision = values[2] if len(values) == 3 else values[1]
            if revision in order:
                tagged.setdefault(revision, []).append(values[0])
        object_format = git("rev-parse", "--show-object-format")
        if object_format not in {"sha1", "sha256"}:
            raise ValueError("unsupported Git object format")
    except (OSError, ValueError, UnicodeError, IndexError) as exc:
        return {"sources": [], "unknown": [{"kind": "history", "reason": str(exc)}], "no_history": True}
    no_history = not tagged
    if no_history:
        unknown.append({"kind": "history", "reason": "no reachable release tag; only committed HEAD fixtures can supply starts"})
    revisions = sorted(tagged, key=lambda revision: (order[revision], revision)) if tagged else commits[:1]
    if commits[0] not in revisions:
        revisions.append(commits[0])  # Committed fixtures may require the current committed loader.
    directory = cache_root(root) / "old-sources"
    directory.mkdir(parents=True, exist_ok=True)
    sources = []
    for revision in revisions:
        tag = sorted(tagged.get(revision, []))[0] if revision in tagged else None
        destination = directory / revision
        try:
            tree = git("rev-parse", revision + "^{tree}")
            entries = []
            for record in git("ls-tree", "-r", "-z", "--full-tree", revision, binary=True).split(b"\0"):
                if not record:
                    continue
                header, name = record.split(b"\t", 1)
                mode, kind, identifier = header.decode("ascii").split()
                relative = Path(os.fsdecode(name))
                if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts or kind != "blob" or mode not in {"100644", "100755", "120000"}:
                    raise ValueError("historical source entry cannot be exported: " + os.fsdecode(name))
                entries.append((relative, mode, identifier))
            expected = {relative.as_posix() for relative, _mode, _identifier in entries}
            expected.update(parent.as_posix() for relative, _mode, _identifier in entries for parent in relative.parents if parent != Path("."))
            def verify():
                actual = set()
                for folder, directories, names in os.walk(destination, followlinks=False):
                    actual.update((Path(folder) / name).relative_to(destination).as_posix() for name in [*directories, *names])
                if actual != expected:
                    raise ValueError("historical source cache has different paths")
                for relative, mode, identifier in entries:
                    path = destination / relative
                    if mode == "120000":
                        if not path.is_symlink():
                            raise ValueError("historical source cache changed an entry kind")
                        data = os.fsencode(os.readlink(path))
                    else:
                        if path.is_symlink() or not path.is_file() or bool(path.stat().st_mode & 0o111) != (mode == "100755"):
                            raise ValueError("historical source cache changed an entry kind or mode")
                        data = path.read_bytes()
                    digest = hashlib.new(object_format, b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()
                    if digest != identifier:
                        raise ValueError("historical source cache changed bytes: " + relative.as_posix())
            if not destination.exists():
                result = subprocess.run(["git", "-C", str(root), "cat-file", "--batch"],
                                        input="".join(identifier + "\n" for _relative, _mode, identifier in entries).encode("ascii"), capture_output=True)
                if result.returncode:
                    raise ValueError("historical Git blobs could not be read")
                with tempfile.TemporaryDirectory(prefix=revision + "-", dir=directory) as temporary:
                    temporary = Path(temporary)
                    position = 0
                    links = []
                    for relative, mode, identifier in entries:
                        end = result.stdout.index(b"\n", position)
                        observed, kind, size = result.stdout[position:end].decode("ascii").split()
                        size = int(size)
                        position = end + 1
                        data = result.stdout[position:position + size]
                        position += size + 1
                        if observed != identifier or kind != "blob" or len(data) != size:
                            raise ValueError("historical Git blob receipt disagrees with its tree")
                        path = temporary / relative
                        path.parent.mkdir(parents=True, exist_ok=True)
                        if mode == "120000":
                            links.append((path, data))
                        else:
                            path.write_bytes(data)
                            path.chmod(0o755 if mode == "100755" else 0o644)
                    for path, data in links:
                        path.symlink_to(os.fsdecode(data))
                    try:
                        temporary.rename(destination)
                    except FileExistsError:
                        pass
                    finally:
                        # TemporaryDirectory still owns its old pathname after a successful rename.
                        if not temporary.exists():
                            temporary.mkdir()
            if destination.is_symlink():
                raise ValueError("historical source cache is a symlink")
            verify()
            spec = derive(destination)
            files = {name: file_stamp(destination / name) for name in [*spec["input_files"], ".flowguard/skeleton.py"]}
            sources.append({"revision": revision, "tree": tree, "tag": tag, "tags": sorted(tagged.get(revision, [])),
                            "root": str(destination), "spec": spec, "persistence": spec.get("persistence"),
                            "source_identity": state_key(files), "identity": content_identity(spec),
                            "kind": "release" if tag else "committed-baseline"})
        except (OSError, ValueError, UnicodeError, KeyError, TypeError) as exc:
            unknown.append({"kind": "historical-source", "revision": revision, "tag": tag, "reason": str(exc)})
    return {"sources": sources, "unknown": unknown, "no_history": no_history}


def collect_saves(root, *, steps=8, node_cap=1000, alphabet_cap=1000):
    """Collect native saved bytes once per identified source and actual schema family."""
    import base64

    root = Path(root).resolve()
    fixture_scope = {"extensions": [".json"], "selection": "Git HEAD tracked files excluding .git and .flowguard",
                     "other_formats": "not screened"}
    if not derive(root).get("persistence"):
        return {"sources": [], "saves": [], "unknown": [{"kind": "persistence", "scope": "not-applicable",
                "reason": "no source-bound public save/load; historical sources were not inspected"}],
                "no_saved_files": True, "no_history": None, "fixture_loads": [], "fixture_scope": fixture_scope}
    history = old_releases(root)
    sources, unknown = history["sources"], list(history["unknown"])
    committed = []
    fixture_revision = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True)
    fixture_tree = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD^{tree}"], capture_output=True, text=True)
    result = subprocess.run(["git", "-C", str(root), "ls-tree", "-r", "-z", "--name-only", "HEAD"], capture_output=True)
    if result.returncode == 0:
        for raw_name in result.stdout.split(b"\0"):
            if not raw_name:
                continue
            name = raw_name.decode("utf-8", "surrogateescape")
            path = Path(name)
            if path.suffix.lower() != ".json" or any(part in {".git", ".flowguard"} for part in path.parts):
                continue
            data = subprocess.run(["git", "-C", str(root), "show", "HEAD:" + name], capture_output=True)
            if data.returncode:
                unknown.append({"kind": "committed-fixture", "name": name, "reason": "committed bytes unavailable"})
                continue
            committed.append({"name": name, "bytes": base64.b64encode(data.stdout).decode("ascii")})
    saves, schemas, seen_files, fixture_loads = [], set(), set(), []
    remaining = list(committed)
    generated_sources = 0
    for source in sources:
        spec = source["spec"]
        if not source.get("persistence"):
            unknown.append({"kind": "persistence", "revision": source["revision"], "tag": source["tag"], "reason": "no source-bound public save/load"})
            continue
        if source["kind"] != "release" and not remaining:
            continue
        options = {"prefixes": [], "committed": remaining, "steps": steps,
                   "node_cap": node_cap, "alphabet_cap": alphabet_cap, "generate": source["kind"] == "release"}
        start = {"world": "default", "seed": 0} if options["generate"] else {}
        identity = source["identity"]
        path = cache_root(root) / ("saved-files-" + state_key({"source": identity, "start": start, "options": options}) + ".json")
        facts = _cached(path, identity)
        if facts is None:
            try:
                facts = replay(spec, [], start, operation="saves", options=options, timeout=300)
            except UnsupportedWorld as exc:
                unknown.append({"kind": "saved-file-collection", "revision": source["revision"], "tag": source["tag"], "reason": str(exc)})
                continue
            if footprint_identity(facts.get("footprint", {})):
                atomic_write_text(path, json.dumps({"identity": identity, "body": state_key(facts), "facts": facts}, ensure_ascii=False))
        unknown.extend({"source": {key: source[key] for key in ("revision", "tree", "tag", "root")}, **row} if isinstance(row, dict) else {"kind": "saved-file-collection", "revision": source["revision"], "reason": str(row)} for row in facts.get("unknown", []))
        generated = [row for row in facts.get("saves", []) if row.get("recipe") is not None]
        first_generated = bool(generated) and generated_sources == 0
        if generated:
            generated_sources += 1
        novel = set()
        for row in facts.get("saves", []):
            kind = "generated" if row.get("recipe") is not None else "committed"
            accepted = row.get("old_load", {}).get("outcome") == "success"
            if kind == "committed":
                fixture_loads.append({"name": row["file"]["name"], "source_revision": source["revision"], "old_load": row.get("old_load")})
                if not accepted:
                    continue
                remaining = [file for file in remaining if file["name"] != row["file"]["name"]]
            elif not accepted:
                unknown.append({"kind": "old-load", "revision": source["revision"], "tag": source["tag"], "root": source["root"],
                                "name": row["file"]["name"], "old_load": row.get("old_load"),
                                "reason": "the generating source did not accept its own saved bytes"})
                continue
            schema = row.get("schema")
            token = state_key(schema) if schema is not None else None
            if kind == "generated" and not first_generated and token is not None and token in schemas and accepted:
                continue
            identity_file = (source["revision"], kind, row["file"]["name"], row["file"]["sha256"])
            if identity_file in seen_files:
                continue
            seen_files.add(identity_file)
            provenance = {key: source[key] for key in ("revision", "tree", "tag", "root", "persistence", "source_identity", "identity")}
            provenance["kind"] = "current-fixture" if kind == "committed" and source["kind"] == "committed-baseline" else kind
            if kind == "committed":
                provenance.update(fixture_revision=fixture_revision.stdout.strip(), fixture_tree=fixture_tree.stdout.strip(), fixture_path=row["file"]["name"])
            saves.append({**row, "source": provenance})
            if kind == "generated" and accepted and token is not None:
                novel.add(token)
        schemas.update(novel)
    return {"sources": sources, "saves": saves, "unknown": unknown, "no_saved_files": not saves,
            "no_history": history["no_history"], "fixture_loads": fixture_loads, "fixture_scope": fixture_scope}
