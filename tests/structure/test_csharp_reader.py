from pathlib import Path
import json

from flowguard.structure.readers.csharp import extract


def read(source):
    return extract(Path("."), "sample.cs", source.encode("utf-8"), "csharp/sample.cs", False)


def calls(facts, name):
    return [row for row in facts["syntax_calls"] if row["text"] == name]


def test_namespace_partial_overloads_constructor_and_local_functions_are_distinct():
    f = read("namespace Acme; public partial class Calc { public Calc(){} "
             "public int Run(int x){ int Local(int n)=>n+1; return Local(x); } "
             "public int Run(string x)=>x.Length; } partial class Calc { partial void Hook(); }")
    assert f["parse_error"] == ""
    rows = f["nodes"]
    assert any(n["kind"] == "namespace" and n["qual"] == "Acme" for n in rows)
    assert len([n for n in rows if n["kind"] == "class" and n["raw"]["declared_qual"] == "Acme.Calc"]) == 2
    assert len([n for n in rows if n["raw"]["declared_qual"] == "Acme.Calc.Run"]) == 2
    assert len({n["qual"] for n in rows}) == len(rows)
    assert any(n["raw"]["declaration_kind"] == "constructor_declaration" for n in rows)
    local = next(n for n in rows if n["raw"]["declaration_kind"] == "local_function_statement")
    assert local["qual"] == "Acme.Calc.Run.Local" and local["kind"] == "function"
    call = calls(f, "Local")[0]
    assert call["scope"] == "Acme.Calc.Run" and call["candidate"] == local["qual"] and call["reason"] == ""
    assert all(n["fp"] and n["column"] >= 1 and n["end_column"] >= 1 for n in rows)


def test_using_namespace_alias_and_static_are_source_declarations_not_fake_targets():
    f = read("global using System; using Tools = Acme.Utilities; namespace App; using static System.Math; class C {}")
    deps = f["dependencies"]
    assert [(d["module"], d["alias"]) for d in deps] == [
        ("System", ""), ("Acme.Utilities", "Tools"), ("System.Math", "")]
    assert deps[-1]["scope"] == "App" and deps[-1]["name"] == "*"
    assert all(d["kind"] == "using" and d["reason"] for d in deps)


def test_literal_member_and_string_keys_are_written_or_read_without_inventing_rhs():
    f = read('class C { int count = 1; void Run(dynamic other, string key) { '
             'this.count += 2; cfg["limit"] = 3; cfg[key] = other.Value; count++; return; } '
             'int Read(){ return count + cfg["limit"]; } }')
    writes = {a["target"]: a for a in f["assignments"] if a["target"] in {"this.count", 'cfg["limit"]', "cfg[key]", "count"}}
    assert (writes["this.count"]["field"], writes["this.count"]["value"], writes["this.count"]["operation"]) == ("count", 2, "update")
    assert writes['cfg["limit"]']["field"] == "limit" and writes['cfg["limit"]']["literal"]
    assert writes["cfg[key]"]["field"] == "" and writes["cfg[key]"]["value"] is None and not writes["cfg[key]"]["literal"]
    assert writes["count"]["operation"] == "update"
    assert any(r.get("field") == "count" for r in f["symbol_reads"])
    assert any(r["text"] == 'cfg["limit"]' and r.get("field") == "limit" for r in f["symbol_reads"])
    assert any(k[0:2] == ("field", "limit") for k in f["keys"])
    assert not any(k[0:2] == ("field", "key") for k in f["keys"])


def test_static_lexical_calls_work_but_overload_virtual_generic_and_dynamic_do_not():
    f = read("namespace App { public class C { static int Unique(int x)=>x; "
             "static int Pick(int x)=>x; static int Pick(string x)=>0; "
             "virtual int Virtual(int x)=>x; static T Generic<T>(T x)=>x; "
             "void Run(int x, dynamic d){ Unique(x); Pick(1); Virtual(x); Generic<int>(x); Unique(d); d.Unique(x); new C(); } } }")
    unique = calls(f, "Unique")
    assert unique[0]["candidate"] == "App.C.Unique" and unique[0]["reason"] == ""
    assert "dynamic" in unique[1]["reason"]
    assert "overload" in calls(f, "Pick")[0]["reason"]
    assert calls(f, "Virtual")[0]["reason"]
    assert calls(f, "Generic<int>")[0]["reason"]
    assert calls(f, "d.Unique")[0]["reason"]
    assert calls(f, "C")[0]["reason"]
    assert all(c["resolved"] is None for c in f["syntax_calls"])


def test_local_parameter_capture_lambda_and_field_shadow_are_not_static_bindings():
    f = read("class C { static void Helper(){} void Run(System.Action Helper){ "
             "void Local(){ Helper(); } Local(); } "
             "void Other(){ System.Action<System.Action> use = Helper => Helper(); } }")
    helpers = calls(f, "Helper")
    assert len(helpers) == 2 and all("shadows" in row["reason"] for row in helpers)
    assert calls(f, "Local")[0]["reason"] == ""
    local = next(n for n in f["nodes"] if n["raw"]["declaration_kind"] == "local_function_statement")
    assert "Helper" in local["raw"]["shadows"]
    f = read("class C { System.Action Helper; void Run(){ Helper(); } }")
    assert "field callable" in calls(f, "Helper")[0]["reason"]


def test_partial_generic_conditional_and_inherited_contexts_stay_unknown():
    examples = [
        "partial class C { static int Helper(int x)=>x; void Run(){ Helper(1); } }",
        "class C<T> { static int Helper(int x)=>x; void Run(){ Helper(1); } }",
        "class C : Base { static int Helper(int x)=>x; void Run(){ Helper(1); } }",
        "class C {\n#if FEATURE\nstatic int Helper(int x)=>x;\n#endif\nvoid Run(){ Helper(1); }}",
    ]
    for source in examples:
        f = read(source)
        assert f["parse_error"] == ""
        assert calls(f, "Helper")[0]["reason"]
    overloads = read("class C { static void F(){} static void F(){} static void F(){} void R(){ F(); } }")
    assert len({n["qual"] for n in overloads["nodes"]}) == len(overloads["nodes"])
    assert len([n for n in overloads["nodes"] if n["raw"]["declared_qual"] == "C.F"]) == 3


def test_unicode_positions_normalized_newlines_and_name_fingerprints():
    f = read('\ufeffnamespace Café;\r\nclass C { static int café(int x) => x + 1; }\r\n')
    method = next(n for n in f["nodes"] if n["kind"] == "method")
    assert f["parse_error"] == "" and (method["line"], method["column"]) == (2, 11)
    same = read("namespace Other; class C { static int renamed(int x) => x + 1; }")
    renamed = next(n for n in same["nodes"] if n["kind"] == "method")
    assert method["fp"] == renamed["fp"]
    different = read("class C { static int renamed(int x) => x + 2; }")
    assert method["fp"] != next(n for n in different["nodes"] if n["kind"] == "method")["fp"]
    assert isinstance(json.dumps(f, ensure_ascii=False), str)


def test_parse_failure_is_explicit_and_dynamic_indices_remain_unknown():
    f = read("class C { void Run( {")
    assert "syntax error" in f["parse_error"]
    f = read("class C { object Read(dynamic obj, string key){ return obj[key]; } }")
    row = next(r for r in f["symbol_reads"] if r["text"] == "obj[key]")
    assert row["resolved"] is None and row["field"] == "" and row["reason"]
