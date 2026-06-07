"""Python source-audit helpers for Model-Test Alignment.

This module owns conservative AST extraction for declared code contracts and
test evidence. Public compatibility entrypoints remain in
``flowguard.model_test_alignment``.
"""

from __future__ import annotations

import ast
from typing import Mapping, Sequence

from .model_test_alignment import (
    SIDE_EFFECT_CALL_PREFIXES,
    TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT,
    TEST_ASSERTION_SCOPE_INTERNAL_PATH,
    TEST_ASSERTION_SCOPE_UNKNOWN,
    CodeContract,
    ContractSourceAuditFinding,
    ContractSourceAuditReport,
    PythonCodeContractEvidence,
    PythonTestAssertionEvidence,
    TestEvidence,
)


def _unique_sorted(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values if str(value)}))


def _tuple_set(values: Sequence[str]) -> set[str]:
    return {str(value) for value in values}


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _call_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _final_name(name: str) -> str:
    return name.rsplit(".", 1)[-1] if name else ""


def _symbol_matches_call(symbol: str, call_name: str) -> bool:
    if not symbol or not call_name:
        return False
    return call_name == symbol or _final_name(call_name) == _final_name(symbol)


def _literal_name(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Call):
        return _final_name(_call_name(node.func))
    return ""


def _subscript_key(node: ast.Subscript) -> str:
    slice_node = node.slice
    if isinstance(slice_node, ast.Constant) and isinstance(slice_node.value, str):
        return slice_node.value
    return ""


def _target_names(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return (node.attr,)
    if isinstance(node, ast.Subscript):
        key = _subscript_key(node)
        return (key,) if key else ()
    if isinstance(node, (ast.Tuple, ast.List)):
        names: list[str] = []
        for element in node.elts:
            names.extend(_target_names(element))
        return tuple(names)
    return ()


def _function_candidates(tree: ast.AST, symbol: str) -> tuple[ast.FunctionDef | ast.AsyncFunctionDef, ...]:
    parts = tuple(part for part in symbol.split(".") if part)
    if not parts:
        return ()
    target_name = parts[-1]
    class_name = parts[-2] if len(parts) >= 2 else ""
    candidates: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) or node.name != target_name:
            continue
        if not class_name:
            candidates.append(node)
            continue
        parent = getattr(node, "_flowguard_parent", None)
        if isinstance(parent, ast.ClassDef) and parent.name == class_name:
            candidates.append(node)
    return tuple(candidates)


def _attach_parents(tree: ast.AST) -> None:
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_flowguard_parent", parent)


def _parse_python_source(path: str, source_text: str) -> ast.AST | str:
    try:
        tree = ast.parse(source_text, filename=path or "<flowguard-source>")
    except SyntaxError as exc:
        return f"{exc.__class__.__name__}: {exc.msg}"
    _attach_parents(tree)
    return tree


def _extract_code_evidence_from_function(
    contract: CodeContract,
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> PythonCodeContractEvidence:
    args = list(node.args.posonlyargs) + list(node.args.args) + list(node.args.kwonlyargs)
    parameters = [arg.arg for arg in args if arg.arg not in {"self", "cls"}]
    calls: list[str] = []
    side_effects: list[str] = []
    state_reads: list[str] = []
    state_writes: list[str] = []
    return_values: list[str] = []
    raised_errors: list[str] = []
    declared_side_effects = set(contract.side_effects)

    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            name = _call_name(child.func)
            if name:
                calls.append(name)
                final = _final_name(name)
                if final in declared_side_effects or any(final.startswith(prefix) for prefix in SIDE_EFFECT_CALL_PREFIXES):
                    side_effects.append(final)
        elif isinstance(child, ast.Return):
            if child.value is not None:
                literal = _literal_name(child.value)
                if literal:
                    return_values.append(literal)
        elif isinstance(child, ast.Raise):
            if child.exc is not None:
                raised = _literal_name(child.exc)
                if raised:
                    raised_errors.append(raised)
        elif isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = list(child.targets) if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                state_writes.extend(_target_names(target))
        elif isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load):
            state_reads.append(child.id)
        elif isinstance(child, ast.Attribute) and isinstance(child.ctx, ast.Load):
            state_reads.append(child.attr)
        elif isinstance(child, ast.Subscript) and isinstance(child.ctx, ast.Load):
            key = _subscript_key(child)
            if key:
                state_reads.append(key)

    return PythonCodeContractEvidence(
        code_contract_id=contract.code_contract_id,
        path=contract.path,
        symbol=contract.symbol,
        found=True,
        parameters=_unique_sorted(parameters),
        returns_value=bool(return_values) or any(
            isinstance(child, ast.Return) and child.value is not None for child in ast.walk(node)
        ),
        return_values=_unique_sorted(return_values),
        raised_errors=_unique_sorted(raised_errors),
        state_reads=_unique_sorted(state_reads),
        state_writes=_unique_sorted(state_writes),
        side_effects=_unique_sorted(side_effects),
        calls=_unique_sorted(calls),
    )


def audit_python_code_contracts(
    code_contracts: Sequence[CodeContract],
    source_by_path: Mapping[str, str],
) -> tuple[PythonCodeContractEvidence, ...]:
    """Extract conservative AST evidence for declared Python code contracts."""

    parsed_by_path: dict[str, ast.AST | str] = {}
    evidence: list[PythonCodeContractEvidence] = []
    for contract in code_contracts:
        source_text = source_by_path.get(contract.path)
        if source_text is None:
            evidence.append(
                PythonCodeContractEvidence(
                    contract.code_contract_id,
                    path=contract.path,
                    symbol=contract.symbol,
                    parse_error="source path not supplied",
                )
            )
            continue
        parsed = parsed_by_path.get(contract.path)
        if parsed is None:
            parsed = _parse_python_source(contract.path, source_text)
            parsed_by_path[contract.path] = parsed
        if isinstance(parsed, str):
            evidence.append(
                PythonCodeContractEvidence(
                    contract.code_contract_id,
                    path=contract.path,
                    symbol=contract.symbol,
                    parse_error=parsed,
                )
            )
            continue
        candidates = _function_candidates(parsed, contract.symbol)
        if not candidates:
            evidence.append(
                PythonCodeContractEvidence(
                    contract.code_contract_id,
                    path=contract.path,
                    symbol=contract.symbol,
                )
            )
            continue
        evidence.append(_extract_code_evidence_from_function(contract, candidates[0]))
    return tuple(evidence)


def _find_test_function(tree: ast.AST, test_name: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == test_name:
            return node
    return None


def _assertion_count(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        elif isinstance(child, ast.Call):
            final = _final_name(_call_name(child.func))
            if final.startswith("assert") or final in {
                "assertEqual",
                "assertNotEqual",
                "assertTrue",
                "assertFalse",
                "assertIn",
                "assertNotIn",
                "assertRaises",
            }:
                count += 1
    return count


def _extract_test_evidence_from_function(
    evidence: TestEvidence,
    code_contracts_by_id: Mapping[str, CodeContract],
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> PythonTestAssertionEvidence:
    calls = _unique_sorted([_call_name(child.func) for child in ast.walk(node) if isinstance(child, ast.Call)])
    called_contracts: list[str] = []
    for code_contract_id in evidence.covered_code_contracts:
        contract = code_contracts_by_id.get(code_contract_id)
        if contract is None:
            continue
        if any(_symbol_matches_call(contract.symbol, call) for call in calls):
            called_contracts.append(code_contract_id)
    assert_count = _assertion_count(node)
    if called_contracts and assert_count:
        assertion_scope = TEST_ASSERTION_SCOPE_EXTERNAL_CONTRACT
    elif assert_count:
        assertion_scope = TEST_ASSERTION_SCOPE_INTERNAL_PATH
    else:
        assertion_scope = TEST_ASSERTION_SCOPE_UNKNOWN
    return PythonTestAssertionEvidence(
        evidence_id=evidence.evidence_id,
        path=evidence.path,
        test_name=evidence.test_name,
        found=True,
        called_code_contracts=_unique_sorted(called_contracts),
        assert_count=assert_count,
        assertion_scope=assertion_scope,
        calls=calls,
    )


def audit_python_test_assertions(
    test_evidence: Sequence[TestEvidence],
    code_contracts: Sequence[CodeContract],
    source_by_path: Mapping[str, str],
) -> tuple[PythonTestAssertionEvidence, ...]:
    """Extract conservative AST evidence for Python tests that claim contracts."""

    contracts_by_id = {contract.code_contract_id: contract for contract in code_contracts}
    parsed_by_path: dict[str, ast.AST | str] = {}
    result: list[PythonTestAssertionEvidence] = []
    for evidence in test_evidence:
        source_text = source_by_path.get(evidence.path)
        if source_text is None:
            result.append(
                PythonTestAssertionEvidence(
                    evidence.evidence_id,
                    path=evidence.path,
                    test_name=evidence.test_name,
                    parse_error="source path not supplied",
                )
            )
            continue
        parsed = parsed_by_path.get(evidence.path)
        if parsed is None:
            parsed = _parse_python_source(evidence.path, source_text)
            parsed_by_path[evidence.path] = parsed
        if isinstance(parsed, str):
            result.append(
                PythonTestAssertionEvidence(
                    evidence.evidence_id,
                    path=evidence.path,
                    test_name=evidence.test_name,
                    parse_error=parsed,
                )
            )
            continue
        test_name = evidence.test_name or evidence.evidence_id
        node = _find_test_function(parsed, test_name)
        if node is None:
            result.append(PythonTestAssertionEvidence(evidence.evidence_id, path=evidence.path, test_name=test_name))
            continue
        result.append(_extract_test_evidence_from_function(evidence, contracts_by_id, node))
    return tuple(result)


def _source_audit_decision(findings: Sequence[ContractSourceAuditFinding]) -> str:
    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    if not blockers:
        return "python_contract_source_audit_green"
    priority = (
        "source_contract_parse_error",
        "source_contract_missing_symbol",
        "source_contract_missing_input",
        "source_contract_missing_output",
        "source_contract_missing_state_write",
        "source_contract_missing_side_effect",
        "source_contract_extra_side_effect",
        "source_test_parse_error",
        "source_test_missing",
        "source_test_missing_code_contract_call",
        "source_test_missing_external_assertion",
        "source_test_internal_path_only",
    )
    codes = {finding.code for finding in blockers}
    for code in priority:
        if code in codes:
            return code
    return "python_contract_source_audit_blocked"


def review_python_contract_source_audit(
    code_contracts: Sequence[CodeContract],
    test_evidence: Sequence[TestEvidence],
    code_evidence: Sequence[PythonCodeContractEvidence],
    test_assertions: Sequence[PythonTestAssertionEvidence],
) -> ContractSourceAuditReport:
    """Review conservative Python source evidence against declared contracts."""

    code_evidence_by_id = {evidence.code_contract_id: evidence for evidence in code_evidence}
    test_assertions_by_id = {evidence.evidence_id: evidence for evidence in test_assertions}
    findings: list[ContractSourceAuditFinding] = []

    for contract in code_contracts:
        evidence = code_evidence_by_id.get(contract.code_contract_id)
        if evidence is None:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_symbol",
                    f"code contract {contract.code_contract_id} has no source audit evidence",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata=contract.to_dict(),
                )
            )
            continue
        if evidence.parse_error:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_parse_error",
                    f"code contract {contract.code_contract_id} source could not be parsed: {evidence.parse_error}",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        if not evidence.found:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_symbol",
                    f"code contract {contract.code_contract_id} symbol {contract.symbol} was not found",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        missing_inputs = _tuple_set(contract.external_inputs) - _tuple_set(evidence.parameters)
        if missing_inputs:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_input",
                    f"source for {contract.code_contract_id} is missing declared external inputs",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"missing": sorted(missing_inputs), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        if contract.external_outputs and not evidence.returns_value:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_output",
                    f"source for {contract.code_contract_id} has no return value for declared external outputs",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        missing_state_writes = _tuple_set(contract.state_writes) - _tuple_set(evidence.state_writes)
        if missing_state_writes:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_state_write",
                    f"source for {contract.code_contract_id} is missing declared state writes",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"missing": sorted(missing_state_writes), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        missing_side_effects = _tuple_set(contract.side_effects) - _tuple_set(evidence.side_effects)
        if missing_side_effects:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_missing_side_effect",
                    f"source for {contract.code_contract_id} is missing declared side effects",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"missing": sorted(missing_side_effects), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )
        extra_side_effects = _tuple_set(evidence.side_effects) - _tuple_set(contract.side_effects)
        if extra_side_effects:
            findings.append(
                ContractSourceAuditFinding(
                    "source_contract_extra_side_effect",
                    f"source for {contract.code_contract_id} has side-effect-looking calls not declared by the code contract",
                    code_contract_id=contract.code_contract_id,
                    path=contract.path,
                    metadata={"extra": sorted(extra_side_effects), "evidence": evidence.to_dict(), "contract": contract.to_dict()},
                )
            )

    for evidence in test_evidence:
        assertion = test_assertions_by_id.get(evidence.evidence_id)
        if assertion is None:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing",
                    f"test evidence {evidence.evidence_id} has no source audit evidence",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata=evidence.to_dict(),
                )
            )
            continue
        if assertion.parse_error:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_parse_error",
                    f"test evidence {evidence.evidence_id} source could not be parsed: {assertion.parse_error}",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata=assertion.to_dict(),
                )
            )
            continue
        if not assertion.found:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing",
                    f"test evidence {evidence.evidence_id} function {assertion.test_name} was not found",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata=assertion.to_dict(),
                )
            )
            continue
        missing_calls = _tuple_set(evidence.covered_code_contracts) - _tuple_set(assertion.called_code_contracts)
        if missing_calls:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing_code_contract_call",
                    f"test evidence {evidence.evidence_id} does not call declared code contract symbols",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata={"missing": sorted(missing_calls), "assertion": assertion.to_dict(), "evidence": evidence.to_dict()},
                )
            )
        if evidence.covered_code_contracts and assertion.assert_count <= 0:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_missing_external_assertion",
                    f"test evidence {evidence.evidence_id} calls no assertion for the external contract",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata={"assertion": assertion.to_dict(), "evidence": evidence.to_dict()},
                )
            )
        if evidence.covered_code_contracts and assertion.assertion_scope in {
            TEST_ASSERTION_SCOPE_INTERNAL_PATH,
            TEST_ASSERTION_SCOPE_UNKNOWN,
        }:
            findings.append(
                ContractSourceAuditFinding(
                    "source_test_internal_path_only",
                    f"test evidence {evidence.evidence_id} source does not prove the external contract boundary",
                    evidence_id=evidence.evidence_id,
                    path=evidence.path,
                    metadata={"assertion": assertion.to_dict(), "evidence": evidence.to_dict()},
                )
            )

    blockers = tuple(finding for finding in findings if finding.severity == "blocker")
    return ContractSourceAuditReport(
        ok=not blockers,
        decision=_source_audit_decision(findings),
        findings=tuple(findings),
        code_evidence=tuple(code_evidence),
        test_evidence=tuple(test_assertions),
    )


__all__ = [
    "audit_python_code_contracts",
    "audit_python_test_assertions",
    "review_python_contract_source_audit",
]
