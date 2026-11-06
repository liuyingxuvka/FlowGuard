"""Reading through the 1.x readers: BOM, coding cookie, CRLF; fingerprints; keys."""

STANDING = """
def refusal(member, today):
    \"\"\"Why the member may not borrow, or None.\"\"\"
    if member.suspended:
        return "suspended"
    if (today - member.expires_on).days > 3:
        return "expired"
    return None
"""


def test_bom_crlf_and_cookie_files_are_read(repo):
    plain = STANDING.lstrip("\n")
    repo.write({
        "pkg/__init__.py": "",
        "pkg/plain.py": plain,
        "pkg/bom.py": b"\xef\xbb\xbf" + plain.replace("\n", "\r\n").encode(),
        "pkg/latin.py": b"# -*- coding: latin-1 -*-\n# caf\xe9\n" + plain.encode(),
    })
    m = repo.build()
    assert m.stats["parsed"] == 4
    assert not [n for n in m.nodes(kind="module") if n["id"].startswith("pkg.") and not m.nodes(module=n["id"])]
    fps = {m.node(f"pkg.{name}:refusal")["fp"] for name in ("plain", "bom", "latin")}
    assert len(fps) == 1, "BOM, CRLF and a coding cookie do not change the body"
    sites = m.sites("pkg.bom:refusal")
    assert [(s["field"], s["op"], s["value"]) for s in sites] == [
        ("member.suspended", "truth", ""), ("(today - member.expires_on).days", "Gt", "3")]
    assert all(s["leads"] == "return" for s in sites)


def test_source_newline_equivalence_uses_the_shared_content_owner(repo):
    from flowguard.map.common import content_digest
    source = b'def answer():\n    return 42\n'
    repo.write({'answer.py': source})
    first = repo.build()
    original = first.node('answer:answer')
    first.close()
    repo.write({'answer.py': source.replace(b'\n', b'\r')})
    second = repo.build()
    try:
        assert second.stats['parsed'] == 0
        assert second.node('answer:answer') == original
        stored = second.con.execute('SELECT sha FROM file WHERE path=?', ('answer.py',)).fetchone()[0]
        assert stored == content_digest(repo.path / 'answer.py')
    finally:
        second.close()


def test_fingerprint_ignores_name_docstring_and_positions_only(repo):
    repo.write({"a.py": STANDING, "b.py": "\n\n\n" + STANDING.replace("refusal", "why_not").replace(
        '"""Why the member may not borrow, or None."""', '"""Another text."""'),
                "c.py": STANDING.replace("> 3", ">= 3")})
    m = repo.build()
    assert m.node("a:refusal")["fp"] == m.node("b:why_not")["fp"]
    assert m.node("a:refusal")["fp"] != m.node("c:refusal")["fp"]
    assert m.node("a:refusal")["doc"] == "Why the member may not borrow, or None."


def test_keys_routes_sql_env_config_versions(repo):
    repo.write({"web.py": """
        import os
        from flask import Flask
        app = Flask(__name__)
        __version__ = "2.4.1"

        @app.route("/api/loans", methods=["POST"])
        def create_loan(db, config):
            if os.environ.get("KWP_READONLY"):
                raise PermissionError("read only")
            if config["max_loans"] < 1:
                return None
            if db.schema_version not in ("1.2", "1.3"):
                raise RuntimeError("schema")
            db.execute("INSERT INTO loans (member, item) VALUES (?, ?)")
            return db.execute("SELECT id FROM members WHERE active = 1")
    """})
    m = repo.build()
    keys = {(k["kind"], k["value"], k["node"]) for k in m.keys()}
    assert ("route", "POST /api/loans", "web:create_loan") in keys
    assert ("env", "KWP_READONLY", "web:create_loan") in keys
    assert ("config", "max_loans", "web:create_loan") in keys
    assert ("version", "1.2", "web:create_loan") in keys and ("version", "1.3", "web:create_loan") in keys
    assert ("version", "2.4.1", "web") in keys
    assert {("sql", "loans", "web:create_loan"), ("sql", "members", "web:create_loan")} <= keys
    membership = [s for s in m.sites("web:create_loan") if s["op"] == "NotIn"]
    assert membership and membership[0]["vkind"] == "set"


def test_match_arms_and_excluded_paths(repo):
    repo.write({
        "pyproject.toml": '[tool.flowguard]\nexclude = ["vendor/**"]\n',
        "loans.py": """
            def status_action(loan):
                match loan.status:
                    case "lost" | "damaged":
                        raise ValueError("not returnable")
                    case "out":
                        return "return"
                    case _:
                        return None
        """,
        "vendor/big.py": "def huge():\n    return 1\n",
    })
    m = repo.build()
    sites = [(s["field"], s["op"], s["const"], s["leads"]) for s in m.sites("loans:status_action")]
    assert sites == [("loan.status", "In", "('lost', 'damaged')", "raise"), ("loan.status", "Eq", "'out'", "return")]
    assert m.node("vendor.big:huge") is None and m.stats["files"] == 1
