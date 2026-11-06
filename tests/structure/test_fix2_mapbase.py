"""Fixtures for the second map-base fix (reports/fix2-mapbase.md). Each test reproduces one defect pattern
of the last validation on synthetic code: environment variable names behind an Enum-keyed table, a
module-level mapping and a getenv wrapper; import bindings that no import root reaches (TYPE_CHECKING, a
relative import inside try, a function-level import of a vendored copy, a test importing a sibling test);
and the cold build in worker processes giving the same map as one process."""
import sqlite3

from flowguard.structure import store


def env_tokens(m, ident):
    return {t for (t,) in m.con.execute(
        "SELECT t.tok FROM post p JOIN tok t ON t.tid = p.tid JOIN node n ON n.nid = p.nid "
        "WHERE n.id = ? AND t.kind = 'env'", (ident,))}


ENV = {
    "plat/__init__.py": "",
    "plat/names.py": """
        from enum import Enum

        class Provider(str, Enum):
            OPENAI = "openai"
            PLACES = "places"

        class EnvVar(Enum):
            MAPS = "ACME_MAPS_TOKEN"
            STORE = "ACME_STORE_KEY"
    """,
    "plat/broker.py": """
        import os
        from typing import Final
        from plat.names import Provider, EnvVar

        _ENV_BY_PROVIDER: Final[dict] = {Provider.OPENAI: "ACME_OPENAI_KEY", Provider.PLACES: "ACME_PLACES_KEY"}

        class Broker:
            def __init__(self, environment=None):
                self._environment = os.environ if environment is None else environment

            def _secret_for(self, provider):
                environment_variable = _ENV_BY_PROVIDER.get(provider)
                if environment_variable is None:
                    return None
                value = self._environment.get(environment_variable, "")
                return value.strip() or None

        def every_token():
            return {member.name: os.environ.get(member.value) for member in EnvVar}
    """,
    "plat/wrap.py": """
        import os

        OPENAI_VARIABLE = "ACME_OPENAI_KEY"

        def _read(name, default=None):
            value = os.getenv(name, default)
            return value.strip() if value else None

        def openai_key():
            return _read(OPENAI_VARIABLE)

        def places_key():
            return _read(name="ACME_PLACES_KEY")

        def not_a_secret():
            return len("ACME_PLACES_KEY")
    """,
}


def test_environment_names_through_a_table_an_enum_and_a_wrapper(repo):
    repo.write(ENV)
    m = repo.build()
    assert env_tokens(m, "plat.broker:Broker._secret_for") == {"env:ACME_OPENAI_KEY", "env:ACME_PLACES_KEY"}
    assert env_tokens(m, "plat.broker:every_token") == {"env:ACME_MAPS_TOKEN", "env:ACME_STORE_KEY"}
    assert env_tokens(m, "plat.wrap:openai_key") == {"env:ACME_OPENAI_KEY"}       # a constant passed in
    assert env_tokens(m, "plat.wrap:places_key") == {"env:ACME_PLACES_KEY"}       # a keyword argument
    assert env_tokens(m, "plat.wrap:not_a_secret") == set()                       # not a wrapper call
    found = {h["id"] for h in m.other_homes("plat.broker:Broker._secret_for", 10)}
    assert {"plat.wrap:openai_key", "plat.wrap:places_key"} <= found, found


IMPORTS = {
    "app/__init__.py": "",
    "app/types.py": "class Plan:\n    pass\n",
    "app/core.py": """
        from typing import TYPE_CHECKING
        if TYPE_CHECKING:
            from app.types import Plan

        def make(x):
            from vendored_matio import load
            import json
            return load(x), json

        def broken():
            from app.never_written import thing
            return thing
    """,
    "app/third_party/vendored_matio.py": "def load(x):\n    return x\n",
    "lib/json.py": "def dumps(x):\n    return x\n",
    "Step10/plot_artifact.py": "class PlotArtifact:\n    pass\n",
    "Step10/plots_step10.py": """
        try:
            from . import plot_artifact
        except ImportError:
            plot_artifact = None
    """,
    "tests/__init__.py": "",
    "tests/step5/__init__.py": "",
    "tests/step5/test_export_step5.py": "def _result():\n    return 1\n\ndef test_a():\n    assert _result()\n",
    "tests/step5/test_report_step5.py": "from test_export_step5 import _result\n\ndef test_b():\n    assert _result()\n",
}


def test_import_bindings_no_root_reaches_get_an_edge_of_their_kind(repo):
    repo.write(IMPORTS)
    m = repo.build()
    files = {n["id"]: n["file"] for n in m.nodes(kind="module")}

    def edges(src):
        return {(files.get(e["dst"], e["dst"]), e["kind"], e["prov"], e["line"]) for e in m.edges(src)
                if e["kind"].startswith("imports")}
    core = edges("app.core")
    assert ("app/types.py", "imports-typing", "resolved", 3) in core
    assert ("app/third_party/vendored_matio.py", "imports-unrooted", "guessed", 6) in core
    assert not any(f == "lib/json.py" for f, *_ in core)                # `import json` is the standard library
    assert ("missing:app.never_written", "imports", "resolved", 11) in core   # a real miss stays missing
    plots = next(i for i, f in files.items() if f == "Step10/plots_step10.py")
    assert ("Step10/plot_artifact.py", "imports-optional", "resolved", 2) in edges(plots)
    report = next(i for i, f in files.items() if f == "tests/step5/test_report_step5.py")
    assert ("tests/step5/test_export_step5.py", "imports-unrooted", "guessed", 1) in edges(report)
    assert [n["id"] for n in m.nodes(kind="missing")] == ["missing:app.never_written"]


def test_extraction_in_worker_processes_gives_the_same_map(repo, tmp_path):
    files = {"many/__init__.py": ""}
    for i in range(30):
        files[f"many/mod{i:02d}.py"] = (f"LIMIT_{i} = {i * 100 + 7}\n\n"
                                        f"def check_{i}(x):\n    if x > LIMIT_{i}:\n        return 'big'\n"
                                        f"    return 'small'\n\n"
                                        f"def use_{i}(x):\n    from many.mod{(i + 1) % 30:02d} import check_{(i + 1) % 30}\n"
                                        f"    return check_{(i + 1) % 30}(x)\n")
    repo.write(files)
    rows = {}
    for workers in ("1", "3"):
        db = tmp_path / f"w{workers}.sqlite"
        stats = store.build(repo.path, db, workers=int(workers))
        assert stats["workers"] == int(workers) and stats["parsed"] == 31
        con = sqlite3.connect(db)
        rows[workers] = {q: sorted(con.execute(q).fetchall(), key=repr) for q in (
            "SELECT id, kind, fp, sig, raw FROM node", "SELECT src, dst, kind, prov, line FROM edge",
            "SELECT node, line, field, op, value, identity FROM site", "SELECT path, sha, data FROM file",
            "SELECT t.tok, n.id FROM post p JOIN tok t ON t.tid = p.tid JOIN node n ON n.nid = p.nid")}
        con.close()
    assert rows["1"] == rows["3"]
    assert store.build(repo.path, tmp_path / "w3.sqlite")["changed"] is False     # no change: nothing re-read


def _busy(n, seed):
    """Unrelated decisions a busy tool function also makes."""
    return "\n".join(f"    if options.get('opt_{seed}_{i}', 0) > {11 + (seed * 7 + i * 13) % 900}:\n"
                     f"        report.append('opt_{seed}_{i}')" for i in range(n))


VERSION_HOME = """
    import sys

    MIN_PYTHON = (3, 12)
    MAX_PYTHON_EXCLUSIVE = (3, 13)

    def is_supported_python(info=None):
        major, minor = (info or sys.version_info)[:2]
        return MIN_PYTHON <= (major, minor) < MAX_PYTHON_EXCLUSIVE
"""
COPIES = {
    "tools/run_a.py": ("import platform", "if platform.python_version() != '3.12.10':\n        raise SystemExit('pinned')"),
    "tools/run_b.py": ("import sys", "if sys.version_info[:2] != (3, 12):\n        report.append('python')\n        return report"),
    "tools/run_c.py": ("import sys", "ok = sys.version_info[:2] in ((3, 12),)\n    if not ok:\n        return ['python']"),
    "tools/run_d.py": ("import sys", "from plat.runtime import MIN_PYTHON\n    if sys.version_info < MIN_PYTHON:\n"
                                     "        raise SystemExit('old')"),
}


def busy_repo():
    files = {"plat/__init__.py": "", "tools/__init__.py": "", "plat/runtime.py": VERSION_HOME}
    for i, (rel, (imp, check)) in enumerate(sorted(COPIES.items())):
        files[rel] = f"{imp}\n\n\ndef run(options, report):\n    {check}\n{_busy(15, i)}\n    return report\n"
    files["tools/numpy_check.py"] = ("def numpy_ok(version, report):\n    if version < (1, 26):\n        report.append('np')\n"
                                     + _busy(15, 9) + "\n    return report\n")
    files["tools/schema.py"] = "def schema_ok(doc):\n    if doc['schema'] != '2.1':\n        return False\n    return True\n"
    return files


def test_copies_inside_busy_functions_are_found_by_their_decision_sites(repo):
    from _similarity_reference import similar_homes
    repo.write(busy_repo())
    m = repo.build()
    want = {f"{rel[:-3].replace('/', '.')}:run" for rel in COPIES}
    for words in ("", "The interpreter policy: CPython only, nothing else."):    # words never filter
        found = {h["id"]: h for h in m.other_homes("plat.runtime:is_supported_python", 50, words=words)}
        assert set(found) == want, found                                         # 4 of 4, no decoy
        assert all(h["how"] == "sites" and "version 3.12" in h["reason"] for h in found.values())
    assert "compares with plat.runtime:MIN_PYTHON" in found["tools.run_d:run"]["reason"]   # function-level import
    alike = {h["id"] for h in similar_homes(m.con, "plat.runtime:is_supported_python", 50)}
    assert len(alike & want) < len(want)        # whole-function likeness alone misses copies that do much else


UNITS = {
    "fees/__init__.py": "",
    "fees/late.py": """
        GRACE_DAYS = 14

        def late_fee_due(days_overdue):
            return days_overdue > 14

        def blocked(balance_pence):
            return balance_pence >= 5000

        def graced(days_overdue):
            return days_overdue > GRACE_DAYS
    """,
    "jobs/__init__.py": "",
    "jobs/copies.py": """
        REMINDER_DAYS = 14

        def by_seconds(overdue_seconds):
            if overdue_seconds > 14 * 24 * 3600:
                return "fee"
            return "none"

        def by_hours(hours_overdue):
            return hours_overdue > 336

        def by_weeks(weeks_overdue):
            return weeks_overdue > 2

        def by_pounds(balance_pounds):
            return balance_pounds >= 50

        def signup_bonus(days_since_signup):
            return days_since_signup > 14

        def big_order(quantity):
            return quantity >= 5000

        def remind(days_overdue):
            return days_overdue > REMINDER_DAYS
    """,
}


def test_a_constant_equal_after_unit_conversion_matches_on_the_same_field(repo):
    repo.write(UNITS)
    m = repo.build()
    late = {h["id"] for h in m.other_homes("fees.late:late_fee_due", 20)}
    assert {"jobs.copies:by_seconds", "jobs.copies:by_hours", "jobs.copies:by_weeks"} <= late, late
    assert not late & {"jobs.copies:signup_bonus", "jobs.copies:big_order"}     # 14 days on another field
    money = {h["id"] for h in m.other_homes("fees.late:blocked", 20)}
    assert "jobs.copies:by_pounds" in money and "jobs.copies:big_order" not in money
    named = {h["id"] for h in m.other_homes("fees.late:graced", 20)}
    assert "jobs.copies:remind" not in named      # GRACE_DAYS and REMINDER_DAYS: two named decisions, both 14


CONFIG = {
    "svc/__init__.py": "",
    "svc/retry.py": """
        def should_retry(attempt, config):
            limit = config.get("max_retries", 3)
            return attempt < limit
    """,
    "svc/jobs.py": """
        def run_job(job, settings, report):
            if job.kind == "batch":
                report.append("batch")
            if job.attempts >= settings["max_retries"]:
                report.append("give up")
                return report
            if job.size > 50:
                report.append("big")
            return report

        def other(job, settings):
            return job.attempts >= settings["timeout_seconds"]
    """,
}


def test_a_config_key_a_site_reads_is_a_signature(repo):
    repo.write(CONFIG)
    m = repo.build()
    found = {h["id"]: h for h in m.other_homes("svc.retry:should_retry", 10)}
    assert set(found) == {"svc.jobs:run_job"}, found
    assert "reads config max_retries" in found["svc.jobs:run_job"]["reason"]
