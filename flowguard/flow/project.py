"""The project around the models: its root, the model files, stored request lines,
`.flowguard/conflicts.json`, the cache directory and manifests, git (changed models,
files at a revision) and the overlapping-views warning."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from .checks import WARNING, Finding, make_finding, replay_spec
from .model import Loaded, natural_key, request_file

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


def request_line(root: Path, rid: str) -> str | None:
    """The first non-empty line of the stored request, cut at 100 characters."""
    path = request_file(root, rid)
    if path is None or not path.is_file():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            text = line.strip()
            return text if len(text) <= 100 else text[:99] + "…"
    return ""


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
    conflicts = data.get("conflicts", [])
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
    if not isinstance(data.get("unknown", []), list) or not all(isinstance(u, str) for u in data.get("unknown", [])):
        return "'unknown' is not a list of model ids"
    models = data.get("models", {})
    if not isinstance(models, dict) or not all(isinstance(v, dict) for v in models.values()):
        return "'models' is not an object of model records"
    return None


def unreadable_text(reason: str, merge: bool = False) -> str:
    """The one line every command gives for an unreadable conflicts.json: the file, why, and
    the step that restores it (`git checkout -- FILE` refuses a file a merge left unmerged)."""
    name = CONFLICTS.as_posix()
    step = (f"keep one side: git checkout --ours -- {name}; then run {PROG} check" if merge
            else f"git checkout -- {name}")
    return f"{name} cannot be read ({reason}); its open conflicts are unknown until it is restored ({step})"


def read_conflicts(root) -> dict | None:
    """The last final check's record (None when there is none yet). A file that is not that
    record (unreadable, not JSON, git merge markers, a wrong shape) raises ConflictsUnreadable
    with the one line that names it and its restore step."""
    path = Path(root) / CONFLICTS
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise ConflictsUnreadable(unreadable_text(f"{type(e).__name__}: {e}")) from e
    if any(line.startswith(_MERGE_MARKERS) for line in text.splitlines()):
        raise ConflictsUnreadable(unreadable_text("it holds git merge markers", merge=True))
    try:
        data = json.loads(text)
    except ValueError as e:
        raise ConflictsUnreadable(unreadable_text(f"it is not valid JSON: {e}")) from e
    problem = _shape_problem(data)
    if problem is not None:
        raise ConflictsUnreadable(unreadable_text(problem))
    data.setdefault("conflicts", [])
    data.setdefault("unknown", [])
    return data


def _atomic_write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    os.replace(tmp, path)


def conflicts_text(data: dict) -> str:
    """The deterministic text of conflicts.json: sorted keys and lists, no timestamps."""
    data = dict(data)
    data["conflicts"] = sorted(data.get("conflicts", []), key=lambda c: (c["model"], c["kind"], c["id"]))
    data["unknown"] = sorted(data.get("unknown", []))
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_conflicts(root, data: dict) -> None:
    """Rewrite .flowguard/conflicts.json (only after a final verdict, never on RUNNING)."""
    path = Path(root) / CONFLICTS
    text = conflicts_text(data)
    if path.is_file() and path.read_text(encoding="utf-8") == text:
        return
    _atomic_write(path, text)


def conflict_entry(f: Finding) -> dict:
    """A conflict as conflicts.json keeps it: enough to show it, and its shrunk path with
    the condition to test where the path ends (a capped check replays it, design M6)."""
    if "entry" in f.detail:                     # a conflict kept from the file: as it was
        return dict(f.detail["entry"])
    out = {"id": f.id, "kind": f.kind, "model": f.model, "subject": f.subject,
           "sources": list(f.sources), "text": f.text}
    spec = replay_spec(f)
    if spec is not None:
        out.update(path=list(f.path), replay=spec)
    return out


def new_and_open(previous: dict | None, ids) -> tuple[list[str], list[str]]:
    """Split conflict ids into new (not in the previous file) and open (in both)."""
    before = {c["id"] for c in (previous or {}).get("conflicts", [])}
    ids = list(dict.fromkeys(ids))
    return [i for i in ids if i not in before], [i for i in ids if i in before]


def cache_dir(root) -> Path:
    return Path(root) / ".flowguard" / "cache" / "flow"


def manifest_path(root, model_id: str) -> Path:
    return cache_dir(root) / "manifests" / f"{model_id}.json"


def read_manifest(root, model_id: str) -> list[str] | None:
    path = manifest_path(root, model_id)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))["reads"]


def write_manifest(root, model_id: str, reads) -> None:
    _atomic_write(manifest_path(root, model_id), json.dumps({"reads": sorted(reads)}, indent=1) + "\n")


def file_digest(root, rel: str) -> str | None:
    path = Path(root) / rel
    if not path.is_file():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
