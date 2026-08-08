"""Run the permanent, dynamically derived FlowGuard skill-suite topology model."""

from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path
import sys
from typing import Any, Iterable, Mapping


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from flowguard import run_exact_sequence
from flowguard.route_topology import HELPER_API_TARGETS
from flowguard.self_maintenance import default_flowguard_route_profiles
from flowguard.skill_suite import FLOWGUARD_SUITE_MAP, validate_skill_suite

import model


MODEL_PATH = ROOT / ".flowguard" / "codex_skill_satellites" / "model.py"
RUNNER_PATH = ROOT / ".flowguard" / "codex_skill_satellites" / "run_checks.py"


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _file_fingerprint(path: Path) -> str:
    if not path.is_file():
        return _fingerprint({"path": path.as_posix(), "state": "missing"})
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _paths_fingerprint(paths: Iterable[Path]) -> str:
    rows: list[dict[str, str]] = []
    for path in sorted({item.resolve() for item in paths}, key=lambda item: item.as_posix()):
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError:
            relative = path.as_posix()
        rows.append(
            {
                "path": relative,
                "sha256": _file_fingerprint(path),
                "state": "present" if path.is_file() else "missing",
            }
        )
    return _fingerprint(rows)


def _glob_files(patterns: Iterable[str]) -> tuple[Path, ...]:
    return tuple(
        sorted(
            {
                path.resolve()
                for pattern in patterns
                for path in ROOT.glob(pattern)
                if path.is_file()
            },
            key=lambda item: item.as_posix(),
        )
    )


def _reserved(member_id: str) -> bool:
    lowered = member_id.casefold()
    return lowered == "flowguard" or lowered.startswith("flowguard-")


def _contract_source(skill_dir: Path) -> Mapping[str, Any]:
    path = skill_dir / ".skillguard" / "contract-source.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, Mapping) else {}


def _strip_route_prefix(value: Any) -> str:
    route_id = str(value or "")
    return route_id[6:] if route_id.startswith("route:") else route_id


def _current_source() -> model.SuiteTopologySource:
    """Build the scenario from the real suite map, registry, files, and tests."""

    suite_map_path = ROOT / FLOWGUARD_SUITE_MAP
    suite_payload = json.loads(suite_map_path.read_text(encoding="utf-8"))
    raw_members = suite_payload.get("included_skills", ())
    if not isinstance(raw_members, list):
        raw_members = []

    # The validator owns the current author-source required-file policy.  We
    # consume its per-member keys and never duplicate that file list here.
    suite_report = validate_skill_suite(ROOT, check_private_inventories=False)
    member_reports = {row.skill_id: row for row in suite_report.members}
    canonical_members: list[model.CanonicalMember] = []
    for raw in raw_members:
        if not isinstance(raw, Mapping):
            continue
        member_id = str(raw.get("name", ""))
        report_row = member_reports.get(member_id)
        required_files = tuple(report_row.required_files) if report_row is not None else ()
        canonical_members.append(
            model.CanonicalMember(
                member_id=member_id,
                role=str(raw.get("role", "")),
                owner_route_id=str(raw.get("owner", "")),
                declared_path=str(raw.get("path", "")),
                required=bool(raw.get("required", False)),
                required_files=required_files,
            )
        )

    profiles = default_flowguard_route_profiles()
    route_registry: list[model.RouteRegistryEntry] = []
    for profile in profiles:
        is_public = (
            profile.route_role == model.PUBLIC_ROUTE_ROLE
            and profile.entry_policy == model.PUBLIC_ENTRY_POLICY
        )
        route_registry.append(
            model.RouteRegistryEntry(
                route_id=profile.route_id,
                route_role=profile.route_role,
                entry_policy=profile.entry_policy,
                owner_route_id=(profile.route_id if is_public else profile.canonical_owner_route),
                skill_id=profile.skill_name if is_public else "",
                member_role=(
                    model.KERNEL_ROLE
                    if is_public and profile.route_id == "model_first_function_flow"
                    else model.SATELLITE_ROLE if is_public else ""
                ),
            )
        )

    public_by_skill = {
        route.skill_id: route
        for route in route_registry
        if route.is_public and route.skill_id
    }
    discovered_members: list[model.DiscoveredMember] = []
    skill_root = ROOT / ".agents" / "skills"
    if skill_root.is_dir():
        for skill_dir in sorted(skill_root.iterdir(), key=lambda item: item.name):
            if not skill_dir.is_dir() or not (skill_dir / "SKILL.md").is_file():
                continue
            member_id = skill_dir.name
            if not _reserved(member_id):
                continue
            contract = _contract_source(skill_dir)
            route_id = _strip_route_prefix(contract.get("default_route_id"))
            registry = public_by_skill.get(member_id)
            discovered_members.append(
                model.DiscoveredMember(
                    member_id=member_id,
                    role=registry.member_role if registry is not None else "",
                    owner_route_id=str(contract.get("native_route_owner", "")),
                    route_id=route_id,
                    discovered_path=skill_dir.relative_to(ROOT).as_posix(),
                    present_files=tuple(
                        path.relative_to(skill_dir).as_posix()
                        for path in sorted(skill_dir.rglob("*"), key=lambda item: item.as_posix())
                        if path.is_file()
                    ),
                    reserved_identity=True,
                )
            )

    skill_input_paths = tuple(
        ROOT / member.declared_path / relative
        for member in canonical_members
        for relative in ("SKILL.md", "agents/openai.yaml")
    )
    contract_input_paths = tuple(
        ROOT / member.declared_path / relative
        for member in canonical_members
        for relative in member.required_files
        if relative.startswith(".skillguard/")
    )
    suite_script_paths = tuple(
        ROOT / relative
        for relative in (
            "flowguard/skill_suite.py",
            "flowguard/skill_contracts.py",
            "flowguard/route_topology.py",
            "flowguard/self_maintenance.py",
            "scripts/check_flowguard_skill_suite.py",
            "scripts/check_flowguard_route_parity.py",
        )
    )
    suite_test_paths = _glob_files(
        (
            "tests/test_skill*.py",
            "tests/test_*route*.py",
            "tests/test_full_validation_composition.py",
            "tests/test_installed_layout.py",
            "tests/test_project_adoption.py",
        )
    )
    route_registry_payload = {
        "profiles": [profile.to_dict() for profile in profiles],
        "helper_api_ids": sorted(HELPER_API_TARGETS),
    }
    identity = model.TopologyInputIdentity(
        suite_map_fingerprint=_file_fingerprint(suite_map_path),
        route_registry_fingerprint=_fingerprint(route_registry_payload),
        skill_inputs_fingerprint=_paths_fingerprint(skill_input_paths),
        contract_inputs_fingerprint=_paths_fingerprint(contract_input_paths),
        suite_scripts_fingerprint=_paths_fingerprint(suite_script_paths),
        suite_tests_fingerprint=_paths_fingerprint(suite_test_paths),
        model_fingerprint=_file_fingerprint(MODEL_PATH),
        runner_fingerprint=_file_fingerprint(RUNNER_PATH),
    )
    evidence_domains = tuple(
        model.EvidenceDomain(
            domain_id,
            "not_run",
            _fingerprint({"domain_id": domain_id, "status": "not_run"}),
        )
        for domain_id in model.EVIDENCE_DOMAIN_IDS
    )
    return model.SuiteTopologySource(
        suite_name=str(suite_payload.get("suite_name", "")),
        suite_schema=str(suite_payload.get("schema_version", "")),
        identity=identity,
        canonical_members=tuple(canonical_members),
        route_registry=tuple(route_registry),
        helper_api_ids=tuple(sorted(HELPER_API_TARGETS)),
        discovered_members=tuple(discovered_members),
        evidence_domains=evidence_domains,
    )


def _changed_fingerprint(value: str, label: str) -> str:
    return _fingerprint({"previous": value, "change": label})


_TOPOLOGY_IDENTITY_FIELDS = (
    "suite_map_fingerprint",
    "route_registry_fingerprint",
    "skill_inputs_fingerprint",
    "contract_inputs_fingerprint",
    "suite_scripts_fingerprint",
    "suite_tests_fingerprint",
    "model_fingerprint",
    "runner_fingerprint",
)


def _change_identity(
    source: model.SuiteTopologySource,
    label: str,
    *field_names: str,
) -> model.TopologyInputIdentity:
    changes = {}
    for field_name in field_names:
        if field_name not in _TOPOLOGY_IDENTITY_FIELDS:
            raise ValueError(f"unknown topology identity field: {field_name}")
        changes[field_name] = _changed_fingerprint(
            getattr(source.identity, field_name),
            label,
        )
    return replace(source.identity, **changes)


def _dynamic_add(source: model.SuiteTopologySource) -> model.SuiteTopologySource:
    member_id = "flowguard-dynamic-topology-probe"
    route_id = "dynamic_topology_probe"
    required_files = source.canonical_members[0].required_files
    member = model.CanonicalMember(
        member_id,
        model.SATELLITE_ROLE,
        route_id,
        f".agents/skills/{member_id}",
        True,
        required_files,
    )
    route = model.RouteRegistryEntry(
        route_id,
        model.PUBLIC_ROUTE_ROLE,
        model.PUBLIC_ENTRY_POLICY,
        route_id,
        member_id,
        model.SATELLITE_ROLE,
    )
    discovered = model.DiscoveredMember(
        member_id,
        model.SATELLITE_ROLE,
        route_id,
        route_id,
        member.declared_path,
        required_files,
    )
    return replace(
        source,
        identity=_change_identity(
            source,
            "dynamic-member-add",
            "suite_map_fingerprint",
            "route_registry_fingerprint",
            "skill_inputs_fingerprint",
            "contract_inputs_fingerprint",
        ),
        canonical_members=source.canonical_members + (member,),
        route_registry=source.route_registry + (route,),
        discovered_members=source.discovered_members + (discovered,),
    )


def _dynamic_remove(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str]:
    removed = next(member for member in source.canonical_members if member.role == model.SATELLITE_ROLE)
    return (
        replace(
            source,
            identity=_change_identity(
                source,
                "dynamic-member-remove",
                "suite_map_fingerprint",
                "route_registry_fingerprint",
                "skill_inputs_fingerprint",
                "contract_inputs_fingerprint",
            ),
            canonical_members=tuple(
                member for member in source.canonical_members if member.member_id != removed.member_id
            ),
            route_registry=tuple(
                route for route in source.route_registry if route.skill_id != removed.member_id
            ),
            discovered_members=tuple(
                member for member in source.discovered_members if member.member_id != removed.member_id
            ),
        ),
        removed.member_id,
    )


def _dynamic_role_swap(source: model.SuiteTopologySource) -> model.SuiteTopologySource:
    """Hypothetical coherent map+registry role change, with no fixed kernel id."""

    kernel = next(member for member in source.canonical_members if member.role == model.KERNEL_ROLE)
    satellite = next(member for member in source.canonical_members if member.role == model.SATELLITE_ROLE)
    kernel_route = next(route for route in source.route_registry if route.skill_id == kernel.member_id)
    satellite_route = next(route for route in source.route_registry if route.skill_id == satellite.member_id)

    members = tuple(
        replace(
            member,
            role=model.SATELLITE_ROLE,
            owner_route_id=satellite_route.route_id,
        )
        if member.member_id == kernel.member_id
        else replace(
            member,
            role=model.KERNEL_ROLE,
            owner_route_id=kernel_route.route_id,
        )
        if member.member_id == satellite.member_id
        else member
        for member in source.canonical_members
    )
    routes = tuple(
        replace(
            route,
            skill_id=satellite.member_id,
            member_role=model.KERNEL_ROLE,
        )
        if route.route_id == kernel_route.route_id
        else replace(
            route,
            skill_id=kernel.member_id,
            member_role=model.SATELLITE_ROLE,
        )
        if route.route_id == satellite_route.route_id
        else route
        for route in source.route_registry
    )
    discovered = tuple(
        replace(
            member,
            role=model.SATELLITE_ROLE,
            owner_route_id=satellite_route.route_id,
            route_id=satellite_route.route_id,
        )
        if member.member_id == kernel.member_id
        else replace(
            member,
            role=model.KERNEL_ROLE,
            owner_route_id=kernel_route.route_id,
            route_id=kernel_route.route_id,
        )
        if member.member_id == satellite.member_id
        else member
        for member in source.discovered_members
    )
    return replace(
        source,
        identity=_change_identity(
            source,
            "dynamic-role-swap",
            "suite_map_fingerprint",
            "route_registry_fingerprint",
            "skill_inputs_fingerprint",
            "contract_inputs_fingerprint",
        ),
        canonical_members=members,
        route_registry=routes,
        discovered_members=discovered,
    )


def _dynamic_required_file(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str, str]:
    target = source.canonical_members[0]
    relative = "topology/dynamic-required.json"
    members = tuple(
        replace(member, required_files=member.required_files + (relative,))
        if member.member_id == target.member_id
        else member
        for member in source.canonical_members
    )
    discovered = tuple(
        replace(member, present_files=member.present_files + (relative,))
        if member.member_id == target.member_id
        else member
        for member in source.discovered_members
    )
    return (
        replace(
            source,
            identity=_change_identity(
                source,
                "dynamic-required-file",
                "suite_map_fingerprint",
                "skill_inputs_fingerprint",
                "contract_inputs_fingerprint",
            ),
            canonical_members=members,
            discovered_members=discovered,
        ),
        target.member_id,
        relative,
    )


def _missing_member(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str]:
    target = source.canonical_members[0]
    return (
        replace(
            source,
            identity=_change_identity(source, "missing-member", "skill_inputs_fingerprint"),
            discovered_members=tuple(
                member for member in source.discovered_members if member.member_id != target.member_id
            ),
        ),
        target.member_id,
    )


def _extra_member(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str]:
    member_id = "flowguard-extra-topology-probe"
    required_files = source.canonical_members[0].required_files
    extra = model.DiscoveredMember(
        member_id,
        model.SATELLITE_ROLE,
        "",
        "",
        f".agents/skills/{member_id}",
        required_files,
    )
    return (
        replace(
            source,
            identity=_change_identity(source, "extra-member", "skill_inputs_fingerprint"),
            discovered_members=source.discovered_members + (extra,),
        ),
        member_id,
    )


def _duplicate_member(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str]:
    target = source.discovered_members[0]
    duplicate = replace(target, discovered_path=f"{target.discovered_path}-duplicate")
    return (
        replace(
            source,
            identity=_change_identity(source, "duplicate-member", "skill_inputs_fingerprint"),
            discovered_members=source.discovered_members + (duplicate,),
        ),
        target.member_id,
    )


def _misclassified_member(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str]:
    target = next(member for member in source.discovered_members if member.role == model.SATELLITE_ROLE)
    return (
        replace(
            source,
            identity=_change_identity(source, "misclassified-member", "contract_inputs_fingerprint"),
            discovered_members=tuple(
                replace(member, role=model.KERNEL_ROLE)
                if member.member_id == target.member_id
                else member
                for member in source.discovered_members
            ),
        ),
        target.member_id,
    )


def _internal_helper_exposed(source: model.SuiteTopologySource) -> tuple[model.SuiteTopologySource, str]:
    internal = next(route for route in source.route_registry if not route.is_public)
    member_id = f"flowguard-{internal.route_id.replace('_', '-')}-public-probe"
    exposed = model.DiscoveredMember(
        member_id,
        model.SATELLITE_ROLE,
        internal.owner_route_id,
        internal.route_id,
        f".agents/skills/{member_id}",
        source.canonical_members[0].required_files,
    )
    return (
        replace(
            source,
            identity=_change_identity(source, "internal-helper-public", "skill_inputs_fingerprint"),
            discovered_members=source.discovered_members + (exposed,),
        ),
        member_id,
    )


def _missing_required_file(
    source: model.SuiteTopologySource,
) -> tuple[model.SuiteTopologySource, str, str]:
    target = next(member for member in source.canonical_members if member.required_files)
    relative = target.required_files[0]
    return (
        replace(
            source,
            identity=_change_identity(source, "missing-required-file", "skill_inputs_fingerprint"),
            discovered_members=tuple(
                replace(
                    member,
                    present_files=tuple(path for path in member.present_files if path != relative),
                )
                if member.member_id == target.member_id
                else member
                for member in source.discovered_members
            ),
        ),
        target.member_id,
        relative,
    )


def _fixed_count_source(source: model.SuiteTopologySource) -> model.SuiteTopologySource:
    changed = _dynamic_add(source)
    return replace(
        changed,
        fixed_count_assertions=(
            model.FixedCountAssertion(
                "historical-fixed-count-probe",
                len({member.member_id for member in source.canonical_members}),
                True,
            ),
        ),
    )


def _sequence(source: model.SuiteTopologySource) -> tuple[model.TopologyAction, ...]:
    return (
        model.TopologyAction("load_source", source),
        model.TopologyAction("review_topology"),
        model.TopologyAction("claim_topology"),
    )


def _stale_sequence(
    source: model.SuiteTopologySource,
    changed: model.SuiteTopologySource,
) -> tuple[model.TopologyAction, ...]:
    return _sequence(source) + (
        model.TopologyAction("load_source", changed),
        model.TopologyAction("claim_topology"),
    )


def _run(workflow, sequence: tuple[model.TopologyAction, ...]):
    return run_exact_sequence(
        workflow=workflow,
        initial_state=model.initial_state(),
        external_input_sequence=sequence,
        invariants=model.INVARIANTS,
    )


def _state(run):
    return run.final_states[0] if len(run.final_states) == 1 else None


def _accepted(run) -> bool:
    state = _state(run)
    return bool(
        run.model_report.ok
        and state is not None
        and state.topology_claim == "accepted"
        and state.topology_status == model.TOPOLOGY_CURRENT
        and state.report is not None
        and state.report.status == "pass"
        and state.release_readiness == "not_owned"
    )


def _rejected_with(run, code: str, *, member_id: str = "", file_suffix: str = "") -> bool:
    state = _state(run)
    if not (
        run.model_report.ok
        and state is not None
        and state.topology_claim == "rejected"
        and state.report is not None
    ):
        return False
    return any(
        finding.code == code
        and (not member_id or finding.member_id == member_id)
        and (not file_suffix or finding.file_path.endswith(file_suffix))
        for finding in state.report.findings
    )


def _stale_rejected(run) -> bool:
    state = _state(run)
    return bool(
        run.model_report.ok
        and state is not None
        and state.topology_claim == "rejected"
        and state.topology_status == model.TOPOLOGY_STALE
        and state.reviewed_input_fingerprint != state.input_fingerprint
        and set(state.stale_domain_ids) == set(model.DOWNSTREAM_EVIDENCE_DOMAIN_IDS)
        and state.release_readiness == "not_owned"
    )


def _print_case(name: str, ok: bool) -> None:
    print(f"{name}: {'OK' if ok else 'UNEXPECTED'}")


def main() -> int:
    current = _current_source()
    added = _dynamic_add(current)
    removed, _ = _dynamic_remove(current)
    role_swapped = _dynamic_role_swap(current)
    required_changed, required_member_id, required_file = _dynamic_required_file(current)

    current_run = _run(model.build_correct_workflow(), _sequence(current))
    added_run = _run(model.build_correct_workflow(), _sequence(added))
    removed_run = _run(model.build_correct_workflow(), _sequence(removed))
    role_run = _run(model.build_correct_workflow(), _sequence(role_swapped))
    required_run = _run(model.build_correct_workflow(), _sequence(required_changed))

    current_state = _state(current_run)
    current_count = len({member.member_id for member in current.canonical_members})
    dynamic_ok = bool(
        _accepted(current_run)
        and _accepted(added_run)
        and _accepted(removed_run)
        and _accepted(role_run)
        and _accepted(required_run)
        and _state(added_run).report.reported_count == current_count + 1
        and _state(removed_run).report.reported_count == current_count - 1
        and _state(role_run).report.reported_count == current_count
        and any(
            member.member_id == required_member_id and required_file in member.required_files
            for member in _state(required_run).report.members
        )
    )

    missing, missing_id = _missing_member(current)
    extra, extra_id = _extra_member(current)
    duplicate, duplicate_id = _duplicate_member(current)
    misclassified, misclassified_id = _misclassified_member(current)
    helper_public, helper_public_id = _internal_helper_exposed(current)
    missing_file, missing_file_id, missing_file_relative = _missing_required_file(current)
    fixed_count = _fixed_count_source(current)

    missing_run = _run(model.build_correct_workflow(), _sequence(missing))
    extra_run = _run(model.build_correct_workflow(), _sequence(extra))
    duplicate_run = _run(model.build_correct_workflow(), _sequence(duplicate))
    misclassified_run = _run(model.build_correct_workflow(), _sequence(misclassified))
    helper_public_run = _run(model.build_correct_workflow(), _sequence(helper_public))
    missing_file_run = _run(model.build_correct_workflow(), _sequence(missing_file))
    fixed_count_run = _run(model.build_correct_workflow(), _sequence(fixed_count))

    exact_findings_ok = all(
        (
            _rejected_with(missing_run, "missing_declared_member", member_id=missing_id),
            _rejected_with(extra_run, "extra_reserved_member", member_id=extra_id),
            _rejected_with(duplicate_run, "duplicate_discovered_member", member_id=duplicate_id),
            _rejected_with(
                misclassified_run,
                "discovered_member_role_mismatch",
                member_id=misclassified_id,
            ),
            _rejected_with(
                helper_public_run,
                "internal_helper_exposed_public",
                member_id=helper_public_id,
            ),
            _rejected_with(
                missing_file_run,
                "required_member_file_missing",
                member_id=missing_file_id,
                file_suffix=missing_file_relative,
            ),
            _rejected_with(fixed_count_run, "fixed_count_mismatch"),
            _rejected_with(fixed_count_run, "fixed_count_parallel_authority"),
        )
    )

    stale_fields = (
        "suite_map_fingerprint",
        "route_registry_fingerprint",
        "skill_inputs_fingerprint",
        "contract_inputs_fingerprint",
        "suite_scripts_fingerprint",
        "suite_tests_fingerprint",
        "model_fingerprint",
        "runner_fingerprint",
    )
    stale_runs = {}
    for field_name in stale_fields:
        changed = replace(
            current,
            identity=replace(
                current.identity,
                **{
                    field_name: _changed_fingerprint(
                        getattr(current.identity, field_name),
                        f"freshness-{field_name}",
                    )
                },
            ),
        )
        stale_runs[field_name] = _run(
            model.build_correct_workflow(),
            _stale_sequence(current, changed),
        )
    stale_ok = all(_stale_rejected(run) for run in stale_runs.values())

    broken_member_runs = {
        "missing": _run(model.build_broken_member_findings_workflow(), _sequence(missing)),
        "extra": _run(model.build_broken_member_findings_workflow(), _sequence(extra)),
        "duplicate": _run(model.build_broken_member_findings_workflow(), _sequence(duplicate)),
        "misclassified": _run(
            model.build_broken_member_findings_workflow(),
            _sequence(misclassified),
        ),
        "internal_helper_public": _run(
            model.build_broken_member_findings_workflow(),
            _sequence(helper_public),
        ),
    }
    broken_fixed = _run(model.build_broken_fixed_count_workflow(), _sequence(fixed_count))
    broken_stale = _run(
        model.build_broken_stale_reuse_workflow(),
        _stale_sequence(current, added),
    )
    broken_collapsed = _run(
        model.build_broken_collapsed_domains_workflow(),
        _sequence(current),
    )
    broken_overclaim = _run(
        model.build_broken_topology_overclaim_workflow(),
        _sequence(current),
    )
    known_bad_ok = bool(
        all(not run.model_report.ok for run in broken_member_runs.values())
        and not broken_fixed.model_report.ok
        and not broken_stale.model_report.ok
        and not broken_collapsed.model_report.ok
        and not broken_overclaim.model_report.ok
    )

    domains_separate = bool(
        current_state is not None
        and {domain.domain_id for domain in current_state.evidence_domains}
        == set(model.EVIDENCE_DOMAIN_IDS)
        and current_state.release_readiness == "not_owned"
    )

    _print_case("current_real_suite_map_and_route_registry", _accepted(current_run))
    _print_case("dynamic_add_remove_role_and_required_file", dynamic_ok)
    _print_case("exact_member_and_file_findings", exact_findings_ok)
    _print_case("all_watched_input_families_stale_prior_topology", stale_ok)
    _print_case("evidence_domains_remain_separate", domains_separate)
    _print_case("known_bad_variants_are_rejected", known_bad_ok)
    if current_state is not None and current_state.report is not None:
        print(
            "derived topology: "
            f"members={current_state.report.reported_count} "
            f"internal_routes={len(current_state.report.internal_routes)} "
            f"helpers={len(current_state.report.helper_api_ids)} "
            "release_readiness=not_owned"
        )

    return 0 if all(
        (
            _accepted(current_run),
            dynamic_ok,
            exact_findings_ok,
            stale_ok,
            domains_separate,
            known_bad_ok,
        )
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
