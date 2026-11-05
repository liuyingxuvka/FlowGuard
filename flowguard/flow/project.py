"""The project around the models: its root, the model files, stored request lines,
`.flowguard/conflicts.json`, the cache directory and manifests, git (changed models,
files at a revision) and the overlapping-views warning."""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path

from ..map.common import normalize_newlines
from ._process import read_text, record_access
from .checks import WARNING, Finding, make_finding, replay_spec
from . import history
from .model import REQUESTS, Loaded, natural_key, request_file

FLOW_DIR = Path(".flowguard") / "flow"
PROG = "python -m flowguard"            # the command every printed next step uses
CONFLICTS = Path(".flowguard") / "conflicts.json"


class ProjectError(Exception):
    """Not a project, not a git repository, or a usage mistake about models."""


def find_root(start: Path) -> Path:
    """The nearest directory at or above start that has `.flowguard/`."""
    here = Path(start).resolve()
    for d in [here, *here.parents]:
        if (d / ".flowguard").is_dir():
            return d
    raise ProjectError(f"not a FlowGuard project: no .flowguard/ at or above {here}")


def legacy_artifacts(root: Path) -> list[Path]:
    """Old executable formats to migrate; reading this list executes neither format."""
    directory = Path(root) / ".flowguard"
    legacy = [path for path in (directory / "map.json", directory / "target") if path.exists()]
    legacy.extend((directory / "models").glob("*.py"))
    return sorted(legacy)


def require_current_format(root: Path) -> None:
    legacy = legacy_artifacts(root)
    if legacy:
        names = ", ".join(path.relative_to(root).as_posix() for path in sorted(legacy))
        raise ProjectError("upgrade old model artifacts before checking: " + names
                           + "; move each useful rule, bad case and binding to a flow model or test, then remove the old artifacts")


def model_files(root: Path) -> list[Path]:
    """The models: `*.py` directly in .flowguard/flow/ whose name does not start with `_`."""
    flow = Path(root) / FLOW_DIR
    if not flow.is_dir():
        return []
    return sorted(p for p in flow.glob("*.py") if p.is_file() and not p.name.startswith("_"))


def resolve_models(root: Path, names: list[str]) -> list[Path]:
    """Model ids or paths inside .flowguard/flow/ -> model files (a usage error otherwise)."""
    root = Path(root).resolve()
    flow = root / FLOW_DIR
    known = {p.stem: p for p in model_files(root)}
    out = []
    for name in names:
        if name in known:
            out.append(known[name])
            continue
        p = Path(name)
        p = (p if p.is_absolute() else Path.cwd() / p).resolve()
        if p.parent != flow or p.suffix != ".py" or p.name.startswith("_"):
            raise ProjectError(f"{name}: models live in {FLOW_DIR.as_posix()}/ (give a model id or a file there)")
        if not p.is_file():
            raise ProjectError(f"{name}: no such model file")
        out.append(p)
    return out


def _request_problem(root: Path, rid: str) -> str | None:
    """Use the request owner's storage and integrity check for a model source."""
    from ..map.common import MapError
    from ..map.requests import validate_request_links

    if request_file(root, rid) is None:
        return (f"{rid!r} is no request id (the name of a file in {REQUESTS.as_posix()}/, such as R10); "
                "name the stored request it comes from")
    try:
        validate_request_links(root, [dict(id=rid, part=False)])
    except MapError as error:
        return str(error)
    return None


def request_line(root: Path, rid: str) -> str | None:
    """The first prose line, falling back to a heading-only request, cut at 100 characters."""
    path = request_file(root, rid)
    if path is None or _request_problem(root, rid) is not None:
        return None
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    text = next((line for line in lines if not re.match(r"#{1,6}(?:\s|$)", line)), lines[0] if lines else "")
    return text if len(text) <= 100 else text[:99] + "…"


def request_lines(root: Path, sources) -> list[tuple[str, str]]:
    """(id, words) for each source in natural order; no source at all is the AI's own."""
    if not sources:
        return [("", "the AI's own")]
    out = []
    for rid in sorted(set(sources), key=natural_key):
        line = request_line(root, rid)
        out.append((rid, line if line is not None else "(not a stored request)"))
    return out


class ConflictsUnreadable(ProjectError):
    """.flowguard/conflicts.json exists but cannot be read as the record a final check writes:
    its open conflicts are unknown, so nothing may be decided from it or written over it."""


_MERGE_MARKERS = ("<<<<<<< ", "||||||| ", "=======", ">>>>>>> ")
_ENTRY_TEXT = ("id", "kind", "model", "subject", "text")


def _shape_problem(data) -> str | None:
    """What makes parsed JSON not a conflicts record (None: it is one)."""
    if not isinstance(data, dict):
        return "it is not a JSON object"
    if "conflicts" not in data:
        return "it has no 'conflicts' list"
    conflicts = data["conflicts"]
    if not isinstance(conflicts, list):
        return "'conflicts' is not a list"
    for n, c in enumerate(conflicts):
        if not isinstance(c, dict):
            return f"conflicts[{n}] is not an object"
        for key in _ENTRY_TEXT:
            if not isinstance(c.get(key), str):
                return f"conflicts[{n}] has no '{key}'" if key not in c else f"conflicts[{n}].{key} is not text"
        if not isinstance(c.get("sources", []), list):
            return f"conflicts[{n}].sources is not a list"
        if "history" in c:
            problem = history.shape_problem(c["history"])
            if problem is not None:
                return f"conflicts[{n}].history: {problem}"
            scope = c["history"]["baseline"]["scope"]
            if scope is not None and scope["model"] != c["model"]:
                return f"conflicts[{n}].history: baseline model mismatch"
    if not isinstance(data.get("unknown", []), list) or not all(isinstance(u, str) for u in data.get("unknown", [])):
        return "'unknown' is not a list of model ids"
    models = data.get("models", {})
    if not isinstance(models, dict) or not all(isinstance(v, dict) for v in models.values()):
        return "'models' is not an object of model records"
    return None


def unreadable_text(root, reason: str, merge: bool = False) -> str:
    """The one line every command gives for an unreadable conflicts.json: the file, why, and
    the step that restores it (`git checkout -- FILE` refuses a file a merge left unmerged)."""
    name = CONFLICTS.as_posix()
    from ..map.common import git_common_directory, git_run
    tracked = (git_common_directory(root) is not None
               and git_run(root, "ls-files", "--error-unmatch", "--", name, allowed=(0, 1)).returncode == 0)
    if tracked:
        step = (f"keep one side: git checkout --ours -- {name}; then run {PROG} check" if merge
                else f"git checkout -- {name}")
    else:
        step = f"restore {name} from your project backup; then run {PROG} check"
    return f"{name} cannot be read ({reason}); its open conflicts are unknown until it is restored ({step})"


def read_conflicts(root) -> dict | None:
    """The last final check's record (None when there is none yet). A file that is not that
    record (unreadable, not JSON, git merge markers, a wrong shape) raises ConflictsUnreadable
    with the one line that names it and its restore step."""
    path = Path(root) / CONFLICTS
    if not path.exists():
        return None
    if not path.is_file():
        raise ConflictsUnreadable(unreadable_text(root, "it is not a regular file"))
    try:
        text = read_text(path)
    except (OSError, UnicodeDecodeError) as e:
        raise ConflictsUnreadable(unreadable_text(root, f"{type(e).__name__}: {e}")) from e
    if any(line.startswith(_MERGE_MARKERS) for line in text.splitlines()):
        raise ConflictsUnreadable(unreadable_text(root, "it holds git merge markers", merge=True))
    try:
        data = history.unpack_wire(json.loads(text))
        if isinstance(data, dict):
            for key in ('conflicts', 'closed'):
                if isinstance(data.get(key), list):
                    data[key] = history.unpack_entries(data[key])
    except ValueError as e:
        raise ConflictsUnreadable(unreadable_text(root, f"it is not valid JSON: {e}")) from e
    problem = _shape_problem(data)
    if problem is not None:
        raise ConflictsUnreadable(unreadable_text(root, problem))
    data.setdefault("unknown", [])
    return data


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    with record_access(path):
        os.replace(tmp, path)


def conflicts_text(data: dict) -> str:
    """The deterministic text of conflicts.json: sorted keys and lists, no timestamps."""
    data = dict(data)
    data["conflicts"] = sorted(data.get("conflicts", []), key=lambda c: (c["model"], c["kind"], c["id"]))
    data["unknown"] = sorted(data.get("unknown", []))
    for key in ('conflicts', 'closed'):
        if isinstance(data.get(key), list):
            data[key] = history._shared_entries(data[key])
    return json.dumps(history.pack_wire(data, indent=2), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_conflicts(root, data: dict) -> None:
    """Rewrite .flowguard/conflicts.json (only after a final verdict, never on RUNNING)."""
    path = Path(root) / CONFLICTS
    text = conflicts_text(data)
    if path.is_file() and read_text(path) == text:
        return
    _atomic_write(path, text)


def conflict_entry(f: Finding, *, observation=None, previous=None) -> dict:
    """A conflict as conflicts.json keeps it: enough to show it, and its shrunk path with
    the condition to test where the path ends (a capped check replays it, design M6)."""
    if "entry" in f.detail:                     # a conflict kept from the file: as it was
        out = dict(f.detail["entry"])
    else:
        out = {"id": f.id, "kind": f.kind, "model": f.model, "subject": f.subject,
               "sources": list(f.sources), "text": f.text}
        spec = replay_spec(f)
        if spec is not None:
            out.update(path=list(f.path), replay=spec)
    if f.detail.get('target'):
        out.setdefault('detail', {})['target'] = dict(f.detail['target'])
    if f.detail.get('model_name'):
        out['model_name'] = f.detail['model_name']
    if f.detail.get('subject_terms'):
        out['subject_terms'] = list(f.detail['subject_terms'])
    if f.detail.get('attribution'):
        out['attribution'] = dict(f.detail['attribution'])
    for key in ('saved_sample','exception','native_load'):
        if key in f.detail:
            out.setdefault('detail',{})[key] = f.detail[key]
    origin = getattr(f, 'native_origin', None)
    if previous is not None:
        origin = previous.get('detail', {}).get('native_origin')
        if 'original_model_source' in previous.get('detail', {}):
            out.setdefault('detail', {})['original_model_source'] = previous['detail']['original_model_source']
    if origin:
        out.setdefault('detail', {})['native_origin'] = dict(origin)
    return history.bind(out, observation, previous)


def compare_conflict(entry: dict, observation: dict) -> dict:
    """An explicit future CLI hook: persist model absence/retention, never close.

    The caller must establish absence from the new findings. Native confirmation,
    regression creation and immutable decisions remain their respective owners.
    Existing check/status/release routes do not invoke this private foundation yet.
    """
    return history.compared(entry, observation)


def new_and_open(previous: dict | None, ids) -> tuple[list[str], list[str]]:
    """Split conflict ids into new (not in the previous file) and open (in both)."""
    before = {c["id"] for c in (previous or {}).get("conflicts", [])}
    ids = list(dict.fromkeys(ids))
    return [i for i in ids if i not in before], [i for i in ids if i in before]


def cache_dir(root) -> Path:
    return Path(root) / ".flowguard" / "cache" / "flow"


def manifest_path(root, model_id: str, kind: str = "core") -> Path:
    """An injective, platform-safe key: UTF-8 hex model directory and part filename."""
    return cache_dir(root) / "manifests" / model_id.encode("utf-8").hex() / f"{kind.encode('utf-8').hex()}.json"


def read_manifest(root, model_id: str, kind: str = "core") -> list[str] | None:
    path = manifest_path(root, model_id, kind)
    if not path.is_file():
        return None
    return json.loads(read_text(path))["reads"]


def write_manifest(root, model_id: str, reads, kind: str = "core") -> None:
    _atomic_write(manifest_path(root, model_id, kind), json.dumps({"reads": sorted(reads)}, indent=1) + "\n")


def file_digest(root, rel: str) -> str | None:
    path = Path(root) / rel
    if not path.is_file():
        return None
    data = path.read_bytes()
    if path.suffix.lower() in (".py", ".pyi", ".js"):
        data = normalize_newlines(data)
    return hashlib.sha256(data).hexdigest()


def _git(root, *args, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=check)


def _require_git(root):
    res = _git(root, "rev-parse", "--is-inside-work-tree", check=False)
    if res.returncode != 0 or res.stdout.strip() != b"true":
        raise ProjectError(f"not a git repository: {root} (the change cannot be computed without git)")


def changed_files(root) -> set[str]:
    """Files under the root that differ from HEAD (tracked or new), relative to the root."""
    root = Path(root).resolve()
    _require_git(root)
    out = set()
    if _git(root, "rev-parse", "--verify", "-q", "HEAD", check=False).returncode == 0:
        diff = _git(root, "diff", "--name-only", "--relative", "HEAD", "--").stdout.decode()
        out.update(line for line in diff.splitlines() if line)
        others = ["ls-files", "--others", "--exclude-standard"]
    else:                                            # no commit yet: everything is new
        others = ["ls-files", "--others", "--cached", "--exclude-standard"]
    listed = _git(root, *others).stdout.decode()
    out.update(line for line in listed.splitlines() if line)
    return out


def changed_models(root) -> list[Path]:
    """Models whose file, or a file their last load read (manifest), changed since HEAD."""
    root = Path(root).resolve()
    changed = changed_files(root)
    out = []
    for path in model_files(root):
        rel = path.relative_to(root).as_posix()
        reads = read_manifest(root, path.stem) or []
        if rel in changed or any(r in changed for r in reads):
            out.append(path)
    return out


def export_at(root, rev: str, paths: list[str], dest: Path) -> None:
    """Write the given root-relative files as they are at git revision rev under dest;
    files that do not exist at rev are left out."""
    root = Path(root).resolve()
    _require_git(root)
    dest = Path(dest)
    for rel in sorted(set(paths)):
        res = _git(root, "show", f"{rev}:./{rel}", check=False)
        if res.returncode != 0:
            if _git(root, "rev-parse", "--verify", "-q", f"{rev}^{{commit}}", check=False).returncode != 0:
                raise ProjectError(f"unknown revision {rev!r}")
            continue
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(res.stdout)


def overlaps(loaded: list[Loaded]) -> list[Finding]:
    """Until composition (S3a): two models that declare the same field family over code
    they both cover are overlapping views; one warning on each."""
    return overlap_views([(ld.model.id or ld.model.name, [f.family for f in ld.model.fields], ld.model.covers)
                          for ld in loaded])


def unstored_sources(root: Path, views) -> list[Finding]:
    """A source= naming no stored request: a model warning per id of the model that names it,
    from (model id, {id: what names it}) as a core part records them. It is read at each
    check, so storing the owner's words with `req add` ends it at once."""
    out = []
    for mid, sources in sorted(views, key=lambda v: v[0]):
        for rid in sorted(sources, key=natural_key):
            problem = _request_problem(root, rid)
            if problem is None:
                continue
            uses = ", ".join(sources[rid])
            out.append(make_finding("SOURCE", WARNING, mid, f"source {rid!r} is not a stored request",
                                    f"source {rid!r} is not a stored request ({uses}): {problem}",
                                    detail={"source": rid, "named_by": list(sources[rid])}))
    return out


def overlap_views(views) -> list[Finding]:
    """The same warnings from (model id, field families, covers) facts, as a core part
    records them, so the caller of `check` needs no model code."""
    out = []
    items = sorted(views, key=lambda v: v[0])
    for a, fams_a, covers_a in items:
        fa = set(fams_a)
        ca = {c.partition(":")[0] for c in covers_a}
        for other, fams_b, covers_b in items:
            if other == a:
                continue
            shared_files = ca & {c.partition(":")[0] for c in covers_b}
            if not shared_files:
                continue
            for fam in sorted(fa & set(fams_b)):
                out.append(make_finding(
                    "OVERLAP", WARNING, a, f"field '{fam}' is also declared by {other}",
                    f"field '{fam}' is also declared by {other}; overlapping views of "
                    f"{', '.join(sorted(shared_files))} (one owner per field)",
                    detail={"field": fam, "other": other, "files": sorted(shared_files)}))
    return out


def staged_models(root, previous):
    """Index-affected models using the same manifests/bindings as changed work."""
    root = Path(root).resolve()
    _require_git(root)
    changed = set(_git(root, 'diff', '--cached', '--name-only', '--relative', '-z', '--').stdout.decode().split('\0')) - {''}
    current = {path.stem:path.relative_to(root).as_posix() for path in model_files(root)}
    for mid in (previous or {}).get('models', {}):
        current.setdefault(mid, (FLOW_DIR / (mid + '.py')).as_posix())
    out = []
    for mid, rel in sorted(current.items()):
        row = (previous or {}).get('models', {}).get(mid, {})
        inputs = set(read_manifest(root, mid) or ()) | set(row.get('inputs', {})) | {rel}
        scope = row.get('observation', {}).get('scope') or {}
        inputs.update(anchor.partition(':')[0] for anchor in scope.get('coverage', {}).get('anchors', []))
        if inputs & changed:
            out.append(mid)
    audit = (previous or {}).get('code_audit')
    authority_paths = set()
    if audit:
        from .codeaudit import declared_entries
        from .decisions import read_decision, decision_paths
        for entry in [*(previous or {}).get('conflicts', []), *declared_entries(previous)]:
            for identifier in entry.get('history', {}).get('decision_refs', []):
                authority_paths.update(decision_paths(read_decision(root, identifier)))
    if audit and ((set(audit.get('inputs', {})) | authority_paths) & changed or any(path.endswith('.py') for path in changed)):
        from .codeaudit import PROJECT
        out.append(PROJECT)
    return out


def running_models(root):
    """Read existing job status/plan records; never start, resume or replace a job."""
    from . import jobs
    out = set()
    for path in (cache_dir(root) / 'jobs').glob('*/*/status.json'):
        status = jobs.read_json(path) or {}
        if status.get('state') != 'running':
            continue
        pid = jobs.worker_pid(path.parent)
        if pid is not None and not jobs.pid_alive(pid):
            continue
        plan = jobs.read_json(path.parent / 'plan.json') or {}
        for item in plan.get('planned', plan.get('parts', [])):
            if isinstance(item, dict) and isinstance(item.get('model'), str):
                out.add(item['model'])
    return out
