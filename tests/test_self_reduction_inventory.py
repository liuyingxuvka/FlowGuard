from dataclasses import replace
from types import SimpleNamespace

from flowguard.evidence_receipts import fingerprint_value
from flowguard.self_reduction_inventory import (
    SelfReductionCandidateBinding,
    SelfReductionCurrentNecessityWitness,
    SelfReductionRetainDisposition,
    SelfReductionUniverseMember,
    derive_self_reduction_retain_dispositions,
    derive_self_reduction_universe,
)


def _current_contract(
    surface,
    *,
    suffix,
    semantic_value="preserve-current-result",
):
    return SimpleNamespace(
        behavior_block_id=f"behavior:{suffix}",
        implementation_surface_id=surface.surface_id,
        model_element_id=f"model:{suffix}",
        owner_id=f"owner:{suffix}",
        owner_contract_id=f"contract:{suffix}",
        accepted=True,
        source_fingerprint=surface.content_fingerprint,
        semantic_spec_ids=(f"semantic-spec:{suffix}",),
        oracle_ids=(f"oracle:{suffix}",),
        intent_contribution_ids=(f"intent:{suffix}",),
        fingerprint=f"sha256:contract:{suffix}",
        semantic_value=semantic_value,
    )


def _install_current_behavior(
    bundle,
    contracts,
    *,
    supporting_relations=(),
):
    """Install one exact current intent/model/code/test projection for tests."""

    contracts = tuple(contracts)
    supporting_relations = tuple(supporting_relations)
    bundle.behavior_report.contracts = contracts
    bundle.behavior_report.supporting_relations = supporting_relations
    contributions = []
    authorities = []
    semantic_specs = []
    oracles = []
    bindings = []
    cases = []
    coverage = []
    execution = []
    test_nodes = []
    contract_by_block = {
        contract.behavior_block_id: contract for contract in contracts
    }
    relation_by_surface = {
        relation.supporting_surface_id: relation
        for relation in supporting_relations
    }
    surface_by_id = {
        surface.surface_id: surface for surface in bundle.inventory.surfaces
    }
    for contract in contracts:
        suffix = contract.behavior_block_id.removeprefix("behavior:")
        contribution_id = contract.intent_contribution_ids[0]
        source_fingerprint = f"sha256:intent-source:{suffix}"
        expectation_fingerprint = f"sha256:expectation:{suffix}"
        contributions.append(
            SimpleNamespace(
                contribution_id=contribution_id,
                disposition="accepted",
                target_ids=(contract.model_element_id,),
                source_kind="current-effective-intent",
                source_id=f"source:{suffix}",
                source_owner_id=f"source-owner:{suffix}",
                expectation_id=f"expectation:{suffix}",
                source_fingerprint=source_fingerprint,
                expectation_fingerprint=expectation_fingerprint,
                rationale=f"current goal for {suffix}",
            )
        )
        authorities.append(
            SimpleNamespace(
                source_kind="current-effective-intent",
                source_id=f"source:{suffix}",
                source_owner_id=f"source-owner:{suffix}",
                expectation_id=f"expectation:{suffix}",
                current_source_fingerprint=source_fingerprint,
                current_expectation_fingerprint=expectation_fingerprint,
                target_ids=(contract.model_element_id,),
                status="current",
                fingerprint=f"sha256:intent-authority:{suffix}",
            )
        )
        semantic_specs.append(
            SimpleNamespace(
                semantic_spec_id=contract.semantic_spec_ids[0],
                covered_model_element_ids=(contract.model_element_id,),
                semantics=(
                    ("input", "current declared input"),
                    ("output", contract.semantic_value),
                    ("state", "current state is preserved"),
                    ("error", "declared errors remain visible"),
                ),
                fingerprint=f"sha256:semantic-spec:{suffix}",
            )
        )
        oracles.append(
            SimpleNamespace(
                oracle_id=contract.oracle_ids[0],
                fingerprint=f"sha256:oracle:{suffix}",
            )
        )
        test_id = f"test:{suffix}"
        case_id = f"case:{suffix}"
        coverage_id = f"coverage:{suffix}"
        test_nodes.append(
            SimpleNamespace(
                node_id=test_id,
                source_fingerprint=f"sha256:test:{suffix}",
            )
        )
        cases.append(
            SimpleNamespace(
                case_id=case_id,
                behavior_block_id=contract.behavior_block_id,
            )
        )
        coverage.append(
            SimpleNamespace(
                coverage_id=coverage_id,
                behavior_block_id=contract.behavior_block_id,
                implementation_surface_id=contract.implementation_surface_id,
                test_node_id=test_id,
            )
        )
        execution.append(
            SimpleNamespace(
                coverage_id=coverage_id,
                execution_owner_id=f"check:{suffix}",
                disposition="pass",
                receipt_id=f"receipt:{suffix}",
                receipt_fingerprint=f"sha256:receipt:{suffix}",
            )
        )
        bindings.append(
            SimpleNamespace(
                binding_id=f"binding:{suffix}",
                implementation_surface_id=contract.implementation_surface_id,
                model_element_id=contract.model_element_id,
                owner_contract_id=contract.owner_contract_id,
                implementation_content_fingerprint=contract.source_fingerprint,
                semantic_spec_ids=contract.semantic_spec_ids,
                oracle_ids=contract.oracle_ids,
                test_evidence_ids=(test_id,),
                consumer_surface_ids=(
                    ()
                    if contract.implementation_surface_id == "surface:public"
                    else ("consumer:current",)
                ),
                fingerprint=f"sha256:binding:{suffix}",
            )
        )
    for supporting_surface_id, relation in relation_by_surface.items():
        contract = contract_by_block[relation.behavior_block_id]
        suffix = contract.behavior_block_id.removeprefix("behavior:")
        surface = surface_by_id[supporting_surface_id]
        bindings.append(
            SimpleNamespace(
                binding_id=f"binding:supporting:{supporting_surface_id}",
                implementation_surface_id=supporting_surface_id,
                model_element_id=contract.model_element_id,
                owner_contract_id=contract.owner_contract_id,
                implementation_content_fingerprint=surface.content_fingerprint,
                semantic_spec_ids=contract.semantic_spec_ids,
                oracle_ids=contract.oracle_ids,
                test_evidence_ids=(f"test:{suffix}",),
                consumer_surface_ids=(contract.implementation_surface_id,),
                fingerprint=f"sha256:binding:supporting:{supporting_surface_id}",
            )
        )
    bundle.intent_inventory = SimpleNamespace(
        complete=True,
        fingerprint=fingerprint_value(
            tuple(row.contribution_id for row in contributions)
        ),
        contributions=tuple(contributions),
        source_authorities=tuple(authorities),
    )
    bundle.binding_report = SimpleNamespace(
        ok=True,
        fingerprint=fingerprint_value(
            tuple(binding.implementation_surface_id for binding in bindings)
        ),
        bindings=tuple(bindings),
        semantic_specs=tuple(semantic_specs),
        oracles=tuple(oracles),
    )
    bundle.behavior_report.case_contracts = tuple(cases)
    bundle.behavior_report.coverage_edges = tuple(coverage)
    bundle.behavior_report.coverage_execution_evidence = tuple(execution)
    bundle.test_inventory.nodes = tuple(test_nodes)
    bundle.test_inventory.required_node_ids = tuple(
        row.node_id for row in test_nodes
    )
    return bundle


def _bundle(*, inventory_findings=()):
    surfaces = (
        SimpleNamespace(
            surface_id="surface:public",
            path="flowguard/public.py",
            symbol="run",
            surface_kind="entrypoint",
            roles=("entrypoint",),
            content_fingerprint="sha256:public",
            structure_fingerprint="sha256:public-shape",
        ),
        SimpleNamespace(
            surface_id="surface:helper",
            path="flowguard/helper.py",
            symbol="_helper",
            surface_kind="function",
            roles=(),
            content_fingerprint="sha256:helper",
            structure_fingerprint="sha256:helper-shape",
        ),
    )
    bundle = SimpleNamespace(
        inventory=SimpleNamespace(
            boundary=SimpleNamespace(subject_revision=fingerprint_value("subject")),
            surfaces=surfaces,
            required_surface_ids=tuple(row.surface_id for row in surfaces),
            findings=inventory_findings,
            file_dispositions=(),
            inventory_fingerprint=fingerprint_value("inventory"),
        ),
        implementation_inventory_audit=SimpleNamespace(
            ok=not inventory_findings,
            status="complete" if not inventory_findings else "blocked",
            inventory_fingerprint=fingerprint_value("inventory"),
            findings=inventory_findings,
            fingerprint="sha256:inventory-audit",
        ),
        target_system_report=SimpleNamespace(
            provider_results=(
                SimpleNamespace(provider_id="provider:a", fingerprint="sha256:provider"),
            )
        ),
        behavior_report=SimpleNamespace(
            fingerprint=fingerprint_value("behavior"),
            contracts=(),
            supporting_relations=(),
            coverage_execution_evidence=(),
            coverage_edges=(),
            case_contracts=(),
            test_node_dispositions=(),
        ),
        resource_inventory=SimpleNamespace(
            members=(
                SimpleNamespace(
                    member_id="resource:a",
                    category_evidence_fingerprint="sha256:resource",
                ),
            )
        ),
        test_inventory=SimpleNamespace(
            inventory_fingerprint=fingerprint_value("test-inventory"),
            nodes=(
                SimpleNamespace(node_id="test:a", source_fingerprint="sha256:test"),
            ),
            required_node_ids=("test:a",),
        ),
    )
    return _install_current_behavior(
        bundle,
        (_current_contract(surfaces[1], suffix="a"),),
    )


def test_owned_signal_stays_on_one_canonical_surface_record():
    bundle = _bundle()
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    assert records
    assert all(isinstance(row, SelfReductionRetainDisposition) for row in records)
    covered = {member_id for row in records for member_id in row.member_ids}
    assert "surface:public" not in covered
    assert "surface:helper" in covered
    helper = next(row for row in universe.members if row.member_id == "surface:helper")
    assert helper.signal_kinds == ("helper_signal",)
    assert not any(row.member_id.startswith("signal:") for row in universe.members)
    signal_record = next(
        row for row in records if "surface:helper" in row.member_ids
    )
    assert signal_record.basis == "current_necessity_witness"
    assert len(signal_record.necessity_witnesses) == 1
    assert isinstance(
        signal_record.necessity_witnesses[0],
        SelfReductionCurrentNecessityWitness,
    )
    assert {
        "surface:helper",
        "behavior:a",
        "owner:a",
        "contract:a",
        "model:a",
    } <= set(signal_record.owner_refs)
    assert {
        "sha256:helper",
        "sha256:helper-shape",
        fingerprint_value("behavior"),
    } <= set(signal_record.evidence_fingerprints)


def test_current_model_regression_evidence_is_not_misread_as_a_test_node():
    bundle = _bundle()
    contract = bundle.behavior_report.contracts[0]
    model_validation_id = "check:model-regression:model:a"
    binding = bundle.binding_report.bindings[0]
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "test_evidence_ids": (
                    *binding.test_evidence_ids,
                    model_validation_id,
                ),
                "test_evidence_fingerprints": (
                    (model_validation_id, "sha256:model-regression:a"),
                ),
            }
        ),
    )
    bundle.behavior_report.path_quality_bindings = (
        SimpleNamespace(
            model_element_id=contract.model_element_id,
            ready=True,
            compact_current_fingerprint="sha256:path-quality:a",
        ),
    )
    bundle.behavior_report.findings = ()
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    witness = next(
        witness
        for record in records
        for witness in record.necessity_witnesses
        if witness.member_id == binding.implementation_surface_id
    )
    assert witness.test_node_ids == ("test:a",)
    assert witness.model_validation_evidence_ids == (model_validation_id,)
    assert "sha256:model-regression:a" in witness.evidence_fingerprints


def test_current_model_regression_can_prove_necessity_without_claiming_ordinary_test_completion():
    bundle = _bundle()
    contract = bundle.behavior_report.contracts[0]
    model_validation_id = "check:model-regression:model:a"
    binding = bundle.binding_report.bindings[0]
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "test_evidence_ids": (model_validation_id,),
                "test_evidence_fingerprints": (
                    (model_validation_id, "sha256:model-regression:a"),
                ),
            }
        ),
    )
    bundle.behavior_report.path_quality_bindings = (
        SimpleNamespace(
            model_element_id=contract.model_element_id,
            ready=True,
            compact_current_fingerprint="sha256:path-quality:a",
        ),
    )
    bundle.behavior_report.findings = ()
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    witness = next(
        witness
        for record in records
        for witness in record.necessity_witnesses
        if witness.member_id == binding.implementation_surface_id
    )
    assert witness.test_node_ids == ()
    assert witness.model_validation_evidence_ids == (model_validation_id,)
    assert witness.coverage_ids == ()
    assert witness.current_receipt_ids == ()


def test_unknown_mixed_test_evidence_cannot_create_necessity_authority():
    bundle = _bundle()
    binding = bundle.binding_report.bindings[0]
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "test_evidence_ids": (
                    *binding.test_evidence_ids,
                    "unknown:test-evidence",
                ),
            }
        ),
    )
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    assert not any(
        witness.member_id == binding.implementation_surface_id
        for record in records
        for witness in record.necessity_witnesses
    )
    assert all(row.universe_fingerprint == universe.fingerprint for row in records)


def test_current_necessity_witness_binds_current_path_quality_without_replacing_callers():
    bundle = _bundle()
    current_path_fingerprint = fingerprint_value("path-quality:model:a:current")
    binding = bundle.binding_report.bindings[0]
    model_validation_id = "check:model-regression:model:a"
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "test_evidence_ids": (
                    *binding.test_evidence_ids,
                    model_validation_id,
                ),
                "test_evidence_fingerprints": (
                    (model_validation_id, "sha256:model-regression:model:a"),
                ),
            }
        ),
    )
    bundle.behavior_report.path_quality_bindings = (
        SimpleNamespace(
            model_element_id="model:a",
            ready=True,
            compact_current_fingerprint=current_path_fingerprint,
        ),
    )
    bundle.behavior_report.findings = ()
    universe = derive_self_reduction_universe(bundle)

    current_records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )
    current_record = next(
        row for row in current_records if row.member_ids == ("surface:helper",)
    )
    witness = current_record.necessity_witnesses[0]
    assert witness.path_quality_binding_fingerprint == current_path_fingerprint
    assert current_path_fingerprint in witness.evidence_fingerprints
    assert witness.caller_ids == ("consumer:current",)

    bundle.behavior_report.path_quality_bindings = (
        SimpleNamespace(
            model_element_id="model:a",
            ready=False,
            compact_current_fingerprint=fingerprint_value(
                "path-quality:model:a:stale"
            ),
        ),
    )
    necessity_gaps = {}
    stale_records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        necessity_gap_sink=necessity_gaps,
    )
    assert "surface:helper" not in {
        member_id
        for row in stale_records
        for member_id in row.member_ids
    }
    assert necessity_gaps["surface:helper"] == (
        "path_quality_binding_not_ready",
    )


def test_current_necessity_does_not_confuse_missing_static_caller_with_reduction_safety():
    bundle = _bundle()
    binding = bundle.binding_report.bindings[0]
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "consumer_surface_ids": (),
            }
        ),
    )
    universe = derive_self_reduction_universe(bundle)
    necessity_gaps = {}

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        necessity_gap_sink=necessity_gaps,
    )

    assert "surface:helper" in {
        member_id
        for row in records
        for member_id in row.member_ids
    }
    assert "surface:helper" not in necessity_gaps
    witness = next(
        witness
        for row in records
        for witness in row.necessity_witnesses
        if witness.member_id == "surface:helper"
    )
    assert witness.caller_ids == ()
    assert witness.behavior_commitment_ids == ()


def test_planned_coverage_is_scoped_to_the_exact_implementation_surface():
    bundle = _bundle()
    bundle.behavior_report.coverage_edges = (
        *bundle.behavior_report.coverage_edges,
        SimpleNamespace(
            coverage_id="coverage:sibling",
            behavior_block_id="behavior:a",
            implementation_surface_id="surface:public",
            test_node_id="test:sibling",
        ),
    )
    bundle.test_inventory.nodes = (
        *bundle.test_inventory.nodes,
        SimpleNamespace(
            node_id="test:sibling",
            source_fingerprint="sha256:test:sibling",
        ),
    )
    universe = derive_self_reduction_universe(bundle)
    necessity_gaps = {}

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        necessity_gap_sink=necessity_gaps,
    )

    witness = next(
        witness
        for record in records
        for witness in record.necessity_witnesses
        if witness.member_id == "surface:helper"
    )
    assert witness.test_node_ids == ("test:a",)
    assert witness.coverage_ids == ("coverage:a",)
    assert "surface:helper" not in necessity_gaps


def test_exact_surface_planned_checker_does_not_impersonate_executable_test_identity():
    bundle = _bundle()
    binding = bundle.binding_report.bindings[0]
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "test_evidence_ids": ("test:other",),
                "test_evidence_fingerprints": (
                    ("test:other", "sha256:test:other"),
                ),
            }
        ),
    )
    bundle.test_inventory.nodes = (
        *bundle.test_inventory.nodes,
        SimpleNamespace(
            node_id="test:other",
            source_fingerprint="sha256:test:other",
        ),
    )
    universe = derive_self_reduction_universe(bundle)
    necessity_gaps = {}

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        necessity_gap_sink=necessity_gaps,
    )

    witness = next(
        witness
        for record in records
        for witness in record.necessity_witnesses
        if witness.member_id == "surface:helper"
    )
    assert witness.test_node_ids == ("test:other",)
    assert witness.coverage_ids == ()
    assert "surface:helper" not in necessity_gaps


def test_current_native_check_identity_is_not_misclassified_as_unknown_test():
    bundle = _bundle()
    binding = bundle.binding_report.bindings[0]
    bundle.binding_report.bindings = (
        SimpleNamespace(
            **{
                **vars(binding),
                "test_evidence_ids": (
                    *binding.test_evidence_ids,
                    "check:owner-specific-diagnostic",
                ),
                "test_evidence_fingerprints": (
                    *getattr(binding, "test_evidence_fingerprints", ()),
                    (
                        "check:owner-specific-diagnostic",
                        "sha256:owner-specific-diagnostic",
                    ),
                ),
            }
        ),
    )
    universe = derive_self_reduction_universe(bundle)
    necessity_gaps = {}

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        necessity_gap_sink=necessity_gaps,
    )

    assert "surface:helper" in {
        member_id
        for record in records
        for member_id in record.member_ids
    }
    assert "surface:helper" not in necessity_gaps


def test_supporting_test_with_no_behavior_owner_is_not_a_check_owner_gap():
    bundle = _bundle()
    bundle.behavior_report.test_node_dispositions = (
        SimpleNamespace(
            test_node_id="test:a",
            disposition="supporting",
            owner_ids=(),
            coverage_ids=(),
            rationale="current required test has no exact behavior edge",
        ),
    )

    universe = derive_self_reduction_universe(bundle)
    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    assert universe.source_complete is True
    assert not any(
        row.member_id.startswith("check-owner-missing:")
        or row.member_id.startswith("coverage-owner-missing:")
        for row in universe.members
    )
    assert any(row.member_id == "test:a" for row in universe.members)
    assert "test:a" in {
        member_id for record in records for member_id in record.member_ids
    }


def test_behavior_coverage_without_behavior_owner_is_a_typed_gap():
    bundle = _bundle()
    bundle.behavior_report.test_node_dispositions = (
        SimpleNamespace(
            test_node_id="planned:test:a",
            disposition="behavior_coverage",
            owner_ids=(),
            coverage_ids=("coverage:a",),
            rationale="malformed exact coverage row",
        ),
    )

    universe = derive_self_reduction_universe(bundle)

    assert universe.source_complete is False
    assert "coverage-owner-missing:planned:test:a" in universe.source_gap_ids
    gap = next(
        row
        for row in universe.members
        if row.member_id == "coverage-owner-missing:planned:test:a"
    )
    assert gap.member_kind == "coverage_owner_gap"
    assert "execution owner" not in gap.rationale


def test_shared_not_run_coverage_rows_create_one_native_check_design_owner():
    bundle = _bundle()
    bundle.behavior_report.coverage_execution_evidence = tuple(
        SimpleNamespace(
            coverage_id=f"coverage:{name}",
            execution_owner_id="native-check:shared",
            disposition="not_run",
            receipt_fingerprint="",
        )
        for name in ("a", "b", "c")
    )
    bundle.behavior_report.test_node_dispositions = tuple(
        SimpleNamespace(
            test_node_id=f"planned:{name}",
            disposition="behavior_coverage",
            owner_ids=("behavior-owner:a",),
            coverage_ids=(f"coverage:{name}",),
            rationale="exact planned coverage",
        )
        for name in ("a", "b", "c")
    )

    universe = derive_self_reduction_universe(bundle)
    check_members = tuple(
        row for row in universe.members if row.member_kind == "check_owner"
    )
    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    assert len(check_members) == 1
    assert check_members[0].member_id == "check:native-check:shared"
    assert len(check_members[0].evidence_fingerprints) == 1
    assert not any(
        row.member_id.startswith("check-design-owner:")
        for row in universe.members
    )
    assert "check:native-check:shared" in {
        member_id for record in records for member_id in record.member_ids
    }


def test_unknown_unowned_signal_surface_stays_unresolved_without_fallback():
    bundle = _bundle()
    bundle.behavior_report.contracts = ()
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    covered = {member_id for row in records for member_id in row.member_ids}
    signal = next(
        row for row in universe.members if row.member_id == "surface:helper"
    )
    assert signal.disposition == "unresolved"
    assert signal.signal_kinds == ("helper_signal",)
    assert signal.member_id not in covered


def test_singleton_supporting_signal_requires_exact_current_owner_relation():
    bundle = _bundle()
    contract = _current_contract(
        bundle.inventory.surfaces[0],
        suffix="public",
    )
    supporting_relations = (
        SimpleNamespace(
            supporting_surface_id="surface:helper",
            behavior_block_id="behavior:public",
            evidence_id="supporting-edge:helper:public",
            evidence_fingerprint="sha256:helper-shape",
        ),
    )
    _install_current_behavior(
        bundle,
        (contract,),
        supporting_relations=supporting_relations,
    )
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    covered = {member_id for row in records for member_id in row.member_ids}
    assert "surface:helper" in covered
    signal_record = next(
        row for row in records if "surface:helper" in row.member_ids
    )
    assert {
        "surface:helper",
        "surface:public",
        "supporting-edge:helper:public",
        "contract:public",
        "owner:public",
    } <= set(signal_record.owner_refs)
    assert {
        "sha256:helper",
        "sha256:helper-shape",
        "sha256:public",
        "sha256:public-shape",
    } <= set(signal_record.evidence_fingerprints)

    bundle.behavior_report.supporting_relations = (
        SimpleNamespace(
            supporting_surface_id="surface:helper",
            behavior_block_id="behavior:public",
            evidence_id="supporting-edge:helper:public",
            evidence_fingerprint="sha256:stale-helper-shape",
        ),
    )
    stale_records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )
    stale_covered = {
        member_id for row in stale_records for member_id in row.member_ids
    }
    assert "surface:helper" not in stale_covered


def test_ambiguous_supporting_owners_leave_surface_and_signal_unresolved():
    bundle = _bundle()
    bundle.behavior_report.contracts = tuple(
        SimpleNamespace(
            behavior_block_id=f"behavior:{name}",
            implementation_surface_id="surface:public",
            model_element_id=f"model:{name}",
            owner_id=f"owner:{name}",
            owner_contract_id=f"contract:{name}",
            accepted=True,
            source_fingerprint="sha256:public",
        )
        for name in ("one", "two")
    )
    bundle.behavior_report.supporting_relations = tuple(
        SimpleNamespace(
            supporting_surface_id="surface:helper",
            behavior_block_id=f"behavior:{name}",
            evidence_id=f"supporting-edge:helper:{name}",
            evidence_fingerprint="sha256:helper-shape",
        )
        for name in ("one", "two")
    )
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    covered = {member_id for row in records for member_id in row.member_ids}
    assert {
        "surface:helper",
        "signal:helper_signal:surface:helper",
    }.isdisjoint(covered)


def test_unaccepted_direct_owner_leaves_surface_and_signal_unresolved():
    bundle = _bundle()
    bundle.behavior_report.contracts = (
        SimpleNamespace(
            **{
                **vars(bundle.behavior_report.contracts[0]),
                "accepted": False,
            }
        ),
    )
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle, universe, candidate_bindings=()
    )

    covered = {member_id for row in records for member_id in row.member_ids}
    assert {
        "surface:helper",
        "signal:helper_signal:surface:helper",
    }.isdisjoint(covered)


def _candidate_bundle(*, distinct_commitments: bool):
    bundle = _bundle()
    second = SimpleNamespace(
        surface_id="surface:helper-two",
        path="flowguard/helper_two.py",
        symbol="_helper_two",
        surface_kind="function",
        roles=(),
        content_fingerprint="sha256:helper-two",
        structure_fingerprint="sha256:helper-two-shape",
    )
    bundle.inventory.surfaces = (*bundle.inventory.surfaces, second)
    bundle.inventory.required_surface_ids = (
        *bundle.inventory.required_surface_ids,
        second.surface_id,
    )
    first_contract = _current_contract(
        bundle.inventory.surfaces[1],
        suffix="a",
        semantic_value="first current result",
    )
    second_contract = _current_contract(
        second,
        suffix="two",
        semantic_value=(
            "second genuinely different result"
            if distinct_commitments
            else "first current result"
        ),
    )
    _install_current_behavior(bundle, (first_contract, second_contract))
    return bundle


def _helper_candidate_binding() -> SelfReductionCandidateBinding:
    return SelfReductionCandidateBinding(
        candidate_id="candidate:helper-pair",
        signal="helper_path",
        member_ids=("surface:helper", "surface:helper-two"),
        source_signal_ids=("surface:helper", "surface:helper-two"),
        observable_contract_fingerprint=fingerprint_value(
            {"candidate": "helper-pair"}
        ),
    )


def test_same_commitment_candidate_stays_without_candidate_level_retain():
    bundle = _candidate_bundle(distinct_commitments=False)
    universe = derive_self_reduction_universe(bundle)
    candidate = _helper_candidate_binding()

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    covered = {member_id for row in records for member_id in row.member_ids}
    assert {"surface:helper", "surface:helper-two"} <= covered
    assert not any(row.member_id.startswith("signal:") for row in universe.members)
    assert not any(
        row.basis == "different_current_semantics" for row in records
    )
    assert not any(
        candidate.candidate_id in row.owner_refs for row in records
    )
    member_witnesses = tuple(
        witness
        for row in records
        for witness in row.necessity_witnesses
        if witness.member_id in candidate.member_ids
    )
    assert len(member_witnesses) == 2
    assert len(
        {
            witness.semantic_obligation_fingerprint
            for witness in member_witnesses
        }
    ) == 1
    assert len({witness.semantic_spec_ids for witness in member_witnesses}) == 2
    assert len({witness.test_node_ids for witness in member_witnesses}) == 2


def test_distinct_current_commitments_create_candidate_level_retain_without_self_proof():
    bundle = _candidate_bundle(distinct_commitments=True)
    universe = derive_self_reduction_universe(bundle)
    candidate = _helper_candidate_binding()

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    candidate_records = tuple(
        row
        for row in records
        if row.basis == "different_current_semantics"
    )
    assert len(candidate_records) == 1
    disposition = candidate_records[0]
    assert disposition.candidate_ids == (candidate.candidate_id,)
    assert disposition.member_ids == candidate.member_ids
    assert dict(disposition.member_owner_bindings) == {
        "surface:helper": "owner:a",
        "surface:helper-two": "owner:two",
    }
    assert candidate.candidate_id not in disposition.owner_refs
    assert candidate.fingerprint not in disposition.evidence_fingerprints
    assert (
        candidate.observable_contract_fingerprint
        not in disposition.evidence_fingerprints
    )


def test_distinct_current_semantics_retain_does_not_require_caller_resolution():
    bundle = _candidate_bundle(distinct_commitments=True)
    universe = derive_self_reduction_universe(bundle)
    candidate = replace(
        _helper_candidate_binding(),
        caller_resolution_gap_ids=("caller-resolution-gap:dynamic",),
    )

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    disposition = next(
        row
        for row in records
        if row.basis == "different_current_semantics"
    )
    assert disposition.candidate_ids == (candidate.candidate_id,)
    assert disposition.member_ids == candidate.member_ids
    assert set(dict(disposition.member_owner_bindings)) == set(
        candidate.member_ids
    )


def test_candidate_binding_alone_cannot_create_distinct_commitment_authority():
    bundle = _candidate_bundle(distinct_commitments=True)
    bundle.behavior_report.contracts = ()
    universe = derive_self_reduction_universe(bundle)
    candidate = _helper_candidate_binding()

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    assert not any(row.candidate_ids for row in records)
    assert not any(candidate.candidate_id in row.owner_refs for row in records)


def test_candidate_identity_cannot_change_member_semantics():
    bundle = _candidate_bundle(distinct_commitments=True)
    universe = derive_self_reduction_universe(bundle)
    first_candidate = _helper_candidate_binding()
    second_candidate = replace(
        first_candidate,
        candidate_id="candidate:renamed-helper-pair",
        observable_contract_fingerprint=fingerprint_value(
            {"candidate": "renamed-helper-pair"}
        ),
    )

    first_records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(first_candidate,),
    )
    second_records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(second_candidate,),
    )

    def semantic_bindings(records):
        return {
            witness.member_id: witness.semantic_obligation_fingerprint
            for row in records
            if row.basis == "current_necessity_witness"
            for witness in row.necessity_witnesses
        }

    assert semantic_bindings(first_records) == semantic_bindings(second_records)


def test_caller_resolution_gap_remains_visible_without_blocking_unchanged_retention():
    bundle = _candidate_bundle(distinct_commitments=True)
    universe = derive_self_reduction_universe(bundle)
    candidate = replace(
        _helper_candidate_binding(),
        caller_resolution_gap_ids=("caller-gap:dynamic-dispatch",),
    )

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    disposition = next(
        row for row in records if row.basis == "different_current_semantics"
    )
    assert disposition.candidate_ids == (candidate.candidate_id,)
    assert disposition.member_ids == candidate.member_ids
    candidate_witnesses = tuple(
        witness
        for row in records
        for witness in row.necessity_witnesses
        if witness.member_id in candidate.member_ids
    )
    assert {witness.member_id for witness in candidate_witnesses} == set(
        candidate.member_ids
    )
    assert not any(
        witness.caller_inventory_complete for witness in candidate_witnesses
    )


def test_internal_surface_without_static_consumer_remains_current_but_not_contraction_proven():
    bundle = _bundle()
    helper = bundle.inventory.surfaces[1]
    contract = _current_contract(helper, suffix="helper-no-consumer")
    _install_current_behavior(bundle, (contract,))
    bundle.binding_report.bindings = tuple(
        SimpleNamespace(
            **{
                **vars(binding),
                "consumer_surface_ids": (),
            }
        )
        if binding.implementation_surface_id == helper.surface_id
        else binding
        for binding in bundle.binding_report.bindings
    )
    universe = derive_self_reduction_universe(bundle)

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    assert helper.surface_id in {
        member_id for row in records for member_id in row.member_ids
    }
    helper_witness = next(
        witness
        for row in records
        for witness in row.necessity_witnesses
        if witness.member_id == helper.surface_id
    )
    assert helper_witness.caller_ids == ()
    assert helper_witness.behavior_commitment_ids == ()


def test_candidate_aggregate_caller_cannot_authorize_another_member():
    bundle = _bundle()
    public_surface, helper_surface = bundle.inventory.surfaces
    _install_current_behavior(
        bundle,
        (
            _current_contract(public_surface, suffix="public-group"),
            _current_contract(helper_surface, suffix="helper-group"),
        ),
    )
    universe = derive_self_reduction_universe(bundle)
    candidate = SelfReductionCandidateBinding(
        candidate_id="candidate:mixed-group",
        signal="shared_group",
        member_ids=(public_surface.surface_id, helper_surface.surface_id),
        source_signal_ids=(public_surface.surface_id, helper_surface.surface_id),
        observable_contract_fingerprint=fingerprint_value(
            {"candidate": "mixed-group"}
        ),
        caller_ids=("consumer:helper-only",),
        public_entrypoint_ids=(public_surface.surface_id,),
    )

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    covered = {member_id for row in records for member_id in row.member_ids}
    assert helper_surface.surface_id in covered
    assert public_surface.surface_id in covered
    public_witness = next(
        witness
        for row in records
        for witness in row.necessity_witnesses
        if witness.member_id == public_surface.surface_id
    )
    assert public_witness.caller_ids == ()


def test_partial_semantic_repeat_does_not_retain_a_whole_candidate_group():
    bundle = _candidate_bundle(distinct_commitments=True)
    third = SimpleNamespace(
        surface_id="surface:helper-three",
        path="flowguard/helper_three.py",
        symbol="_helper_three",
        surface_kind="function",
        roles=(),
        content_fingerprint="sha256:helper-three",
        structure_fingerprint="sha256:helper-three-shape",
    )
    bundle.inventory.surfaces = (*bundle.inventory.surfaces, third)
    bundle.inventory.required_surface_ids = (
        *bundle.inventory.required_surface_ids,
        third.surface_id,
    )
    _install_current_behavior(
        bundle,
        (
            _current_contract(
                bundle.inventory.surfaces[1],
                suffix="a",
                semantic_value="shared current result",
            ),
            _current_contract(
                bundle.inventory.surfaces[2],
                suffix="two",
                semantic_value="different current result",
            ),
            _current_contract(
                third,
                suffix="three",
                semantic_value="shared current result",
            ),
        ),
    )
    universe = derive_self_reduction_universe(bundle)
    candidate = SelfReductionCandidateBinding(
        candidate_id="candidate:three-helpers",
        signal="helper_path",
        member_ids=(
            "surface:helper",
            "surface:helper-two",
            "surface:helper-three",
        ),
        source_signal_ids=(
            "surface:helper",
            "surface:helper-two",
            "surface:helper-three",
        ),
        observable_contract_fingerprint=fingerprint_value(
            {"candidate": "three-helpers"}
        ),
    )

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    assert not any(
        row.basis == "different_current_semantics" for row in records
    )


def test_public_role_records_only_an_exact_current_external_commitment():
    bundle = _bundle()
    public_surface = bundle.inventory.surfaces[0]
    contract = _current_contract(public_surface, suffix="public")
    _install_current_behavior(bundle, (contract,))
    universe = derive_self_reduction_universe(bundle)

    without_commitment = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    def external_binding(
        *,
        code_contract_ids,
        test_evidence_ids,
        implementation_surface_id="surface:public",
        binding_id="binding:public",
    ):
        return {
            contract.model_element_id: (
                {
                    "commitment_id": "commitment:public-current",
                    "review_fingerprint": "sha256:bcl-review-current",
                    "model_element_id": contract.model_element_id,
                    "owner_contract_id": contract.owner_contract_id,
                    "implementation_surface_id": implementation_surface_id,
                    "binding_id": binding_id,
                    "code_contract_ids": code_contract_ids,
                    "test_evidence_ids": test_evidence_ids,
                    "binding_fingerprint": "sha256:bcl-binding-current",
                    "semantics": {
                        "actor_kind": "human",
                        "actor": "FlowGuard user",
                        "trigger": "invoke the public entrypoint",
                        "terminal_or_result": "declared result",
                        "failure_boundary": "declared error remains visible",
                    },
                },
            )
        }

    owner_only_commitment = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        external_commitment_bindings=external_binding(
            code_contract_ids=(contract.owner_contract_id,),
            test_evidence_ids=("test:public",),
        ),
    )
    wrong_test_commitment = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        external_commitment_bindings=external_binding(
            code_contract_ids=(
                contract.owner_contract_id,
                "code-contract:binding:public",
            ),
            test_evidence_ids=("test:another-surface",),
        ),
    )
    wrong_surface_commitment = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        external_commitment_bindings=external_binding(
            code_contract_ids=(
                contract.owner_contract_id,
                "code-contract:binding:public",
            ),
            test_evidence_ids=("test:public",),
            implementation_surface_id="surface:another",
        ),
    )
    with_commitment = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
        external_commitment_bindings=external_binding(
            code_contract_ids=(
                contract.owner_contract_id,
                "code-contract:binding:public",
            ),
            test_evidence_ids=("test:public",),
        ),
    )

    assert "surface:public" in {
        member_id
        for row in without_commitment
        for member_id in row.member_ids
    }
    assert all(
        not row.necessity_witnesses[0].behavior_commitment_ids
        for records in (
            owner_only_commitment,
            wrong_test_commitment,
            wrong_surface_commitment,
        )
        for row in records
        if row.member_ids == ("surface:public",)
    )
    public_record = next(
        row for row in with_commitment if row.member_ids == ("surface:public",)
    )
    assert public_record.basis == "current_necessity_witness"
    assert public_record.necessity_witnesses[0].behavior_commitment_ids == (
        "commitment:public-current",
    )


def test_retain_rows_group_only_exact_same_authority_and_cover_each_member_once():
    bundle = _bundle()
    shared_evidence = ("sha256:shared-authority",)
    members = (
        SelfReductionUniverseMember(
            member_id="check:shared:a",
            member_kind="check_owner",
            disposition="retain",
            rationale="shared current checker authority",
            source_ref="owner:shared",
            evidence_fingerprints=shared_evidence,
        ),
        SelfReductionUniverseMember(
            member_id="check:shared:b",
            member_kind="check_owner",
            disposition="retain",
            rationale="shared current checker authority",
            source_ref="owner:shared",
            evidence_fingerprints=shared_evidence,
        ),
        SelfReductionUniverseMember(
            member_id="check:other:c",
            member_kind="check_owner",
            disposition="retain",
            rationale="different current checker authority",
            source_ref="owner:other",
            evidence_fingerprints=("sha256:other-authority",),
        ),
    )
    universe = replace(
        derive_self_reduction_universe(bundle),
        members=members,
        universe_fingerprint="",
    )

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    assert len(records) == 2
    assert {
        row.member_ids for row in records
    } == {
        (
            "check:shared:a",
            "check:shared:b",
        ),
        ("check:other:c",),
    }
    covered = [member_id for row in records for member_id in row.member_ids]
    assert sorted(covered) == sorted(member.member_id for member in members)
    assert len(covered) == len(set(covered))


def test_multiple_signal_kinds_share_each_canonical_surface_record():
    bundle = _candidate_bundle(distinct_commitments=True)
    bundle.inventory.surfaces[1].symbol = "_validate_helper"
    bundle.inventory.surfaces[2].symbol = "_validate_helper_two"
    universe = derive_self_reduction_universe(bundle)
    candidate = _helper_candidate_binding()
    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(candidate,),
    )

    signal_members = {
        row.member_id: row
        for row in universe.members
        if row.member_id in candidate.source_signal_ids
    }
    assert set(signal_members) == set(candidate.source_signal_ids)
    assert all(
        {"helper_signal", "validation_signal"} <= set(row.signal_kinds)
        for row in signal_members.values()
    )
    assert not any(row.member_id.startswith("signal:") for row in universe.members)
    covered = {member_id for row in records for member_id in row.member_ids}
    assert set(candidate.source_signal_ids) <= covered


class _CountingIntervalSurface:
    def __init__(
        self,
        *,
        surface_id,
        path,
        symbol,
        line_start,
        line_end,
        counter,
    ):
        self.surface_id = surface_id
        self.path = path
        self.symbol = symbol
        self.surface_kind = "function"
        self.roles = ()
        self.calls = ()
        self.content_fingerprint = f"sha256:content:{surface_id}"
        self.structure_fingerprint = f"sha256:structure:{surface_id}"
        self._line_start = line_start
        self._line_end = line_end
        self._counter = counter

    @property
    def line_start(self):
        self._counter["line_reads"] += 1
        return self._line_start

    @property
    def line_end(self):
        self._counter["line_reads"] += 1
        return self._line_end


def _syntax_surface(
    surface_id,
    path,
    symbol,
    line_start,
    line_end,
    *,
    calls=(),
    roles=(),
    surface_kind="function",
    structure_fingerprint=None,
):
    return SimpleNamespace(
        surface_id=surface_id,
        path=path,
        symbol=symbol,
        line_start=line_start,
        line_end=line_end,
        calls=tuple(calls),
        roles=tuple(roles),
        surface_kind=surface_kind,
        content_fingerprint=f"sha256:content:{surface_id}",
        structure_fingerprint=(
            structure_fingerprint or f"sha256:structure:{surface_id}"
        ),
    )


def _bind_surfaces(bundle, surfaces):
    bundle.inventory.surfaces = tuple(surfaces)
    bundle.inventory.required_surface_ids = tuple(
        surface.surface_id for surface in surfaces
    )
    _install_current_behavior(
        bundle,
        tuple(
            _current_contract(
                surface,
                suffix=surface.surface_id,
                semantic_value=f"result:{surface.surface_id}",
            )
            for surface in surfaces
        ),
    )
    return bundle


def test_helper_validation_builder_and_serialization_share_one_record():
    bundle = _bundle()
    bundle.inventory.surfaces[1].symbol = "_validate_build_to_dict"

    universe = derive_self_reduction_universe(bundle)

    helper_rows = tuple(
        row for row in universe.members if row.member_id == "surface:helper"
    )
    assert len(helper_rows) == 1
    assert set(helper_rows[0].signal_kinds) == {
        "helper_signal",
        "validation_signal",
        "builder_signal",
        "serialization_signal",
    }
    assert not any(row.member_id.startswith("signal:") for row in universe.members)


def test_multiple_ordinary_calls_do_not_create_a_branch_signal(tmp_path):
    relative_path = "flowguard/ordinary_calls.py"
    source = tmp_path / relative_path
    source.parent.mkdir(parents=True)
    source.write_text(
        "def worker():\n    first()\n    second()\n",
        encoding="utf-8",
    )
    surface = _syntax_surface(
        "surface:worker",
        relative_path,
        "worker",
        1,
        3,
        calls=("first", "second"),
    )
    bundle = _bind_surfaces(_bundle(), (surface,))

    universe = derive_self_reduction_universe(bundle, root=tmp_path)
    member = next(row for row in universe.members if row.member_id == surface.surface_id)

    assert "branch_signal" not in member.signal_kinds
    assert member.branch_count == 0
    assert member.branch_fingerprint == ""
    assert universe.branch_site_count == 0
    assert universe.unbound_branch_site_count == 0


def test_module_surface_owns_top_level_branch_beyond_ast_module_declaration_line(
    tmp_path,
):
    relative_path = "flowguard/module_branch.py"
    source = tmp_path / relative_path
    source.parent.mkdir(parents=True)
    source.write_text(
        "VALUE = 1\nif VALUE:\n    RESULT = 2\n",
        encoding="utf-8",
    )
    module = _syntax_surface(
        "surface:module",
        relative_path,
        "<module>",
        1,
        1,
        surface_kind="module",
    )
    bundle = _bind_surfaces(_bundle(), (module,))

    universe = derive_self_reduction_universe(bundle, root=tmp_path)
    member = next(
        row for row in universe.members if row.member_id == module.surface_id
    )

    assert universe.branch_site_count == 1
    assert universe.unbound_branch_site_count == 0
    assert "branch_signal" in member.signal_kinds
    assert member.branch_count == 1


def test_cli_command_has_one_identity_on_its_canonical_surface(tmp_path):
    relative_path = "flowguard/cli_surface.py"
    source = tmp_path / relative_path
    source.parent.mkdir(parents=True)
    source.write_text(
        (
            "def build_parser(subparsers):\n"
            "    subparsers.add_parser('run')\n"
            "    subparsers.add_parser('run')\n"
        ),
        encoding="utf-8",
    )
    surface = _syntax_surface(
        "surface:cli",
        relative_path,
        "build_parser",
        1,
        3,
        calls=("add_parser", "add_parser"),
        roles=("entrypoint",),
        surface_kind="entrypoint",
    )
    bundle = _bind_surfaces(_bundle(), (surface,))

    universe = derive_self_reduction_universe(bundle, root=tmp_path)
    member = next(row for row in universe.members if row.member_id == surface.surface_id)

    assert universe.command_routes == (("run", "surface:cli"),)
    assert member.command_ids == ("run",)
    assert "command_route_signal" in member.signal_kinds
    assert not any(
        row.member_id.startswith("command-route:") for row in universe.members
    )


def test_branch_denominator_stays_complete_while_detail_is_affected_only(tmp_path):
    relative_path = "flowguard/branch_summary.py"
    source = tmp_path / relative_path
    source.parent.mkdir(parents=True)
    source.write_text(
        (
            "def first(value):\n"
            "    if value:\n"
            "        return 1\n"
            "    return 0\n\n"
            "def second(value):\n"
            "    if value:\n"
            "        return 2\n"
            "    return 0\n"
        ),
        encoding="utf-8",
    )
    surfaces = (
        _syntax_surface("surface:first", relative_path, "first", 1, 4),
        _syntax_surface("surface:second", relative_path, "second", 6, 9),
    )
    bundle = _bind_surfaces(_bundle(), surfaces)

    summary = derive_self_reduction_universe(bundle, root=tmp_path)
    affected = derive_self_reduction_universe(
        bundle,
        root=tmp_path,
        branch_expansion_surface_ids=("surface:first",),
    )
    deep = derive_self_reduction_universe(bundle, root=tmp_path, explicit_deep=True)

    assert summary.branch_site_count == affected.branch_site_count == deep.branch_site_count == 2
    assert summary.branch_fingerprint == affected.branch_fingerprint == deep.branch_fingerprint
    assert summary.branch_expansion_mode == "summary"
    assert affected.branch_expansion_mode == "affected"
    assert deep.branch_expansion_mode == "explicit_deep"
    assert all(
        not row.materialized_branch_site_ids
        for row in summary.members
        if row.member_id.startswith("surface:")
    )
    assert next(
        row for row in affected.members if row.member_id == "surface:first"
    ).materialized_branch_site_ids
    assert not next(
        row for row in affected.members if row.member_id == "surface:second"
    ).materialized_branch_site_ids
    assert all(
        row.materialized_branch_site_ids
        for row in deep.members
        if "branch_signal" in row.signal_kinds
    )
    assert summary.implementation_surface_ids == summary.required_implementation_surface_ids


def test_repeated_shape_expands_only_real_duplicate_branch_surfaces(tmp_path):
    paths = ("flowguard/a.py", "flowguard/b.py", "flowguard/c.py")
    surfaces = []
    for index, relative_path in enumerate(paths):
        source = tmp_path / relative_path
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(
            "def worker(value):\n    if value:\n        return 1\n    return 0\n",
            encoding="utf-8",
        )
        surfaces.append(
            _syntax_surface(
                f"surface:duplicate:{index}",
                relative_path,
                "worker",
                1,
                4,
                structure_fingerprint="sha256:shared-shape",
            )
        )
    bundle = _bind_surfaces(_bundle(), tuple(surfaces))

    universe = derive_self_reduction_universe(bundle, root=tmp_path)

    duplicate_rows = tuple(
        row for row in universe.members if row.member_id.startswith("surface:duplicate:")
    )
    assert universe.branch_expansion_mode == "affected"
    assert all("repeated_shape_signal" in row.signal_kinds for row in duplicate_rows)
    assert all(row.materialized_branch_site_ids for row in duplicate_rows)


def test_oversized_file_is_one_signal_row_with_bounded_hotspots():
    path = "flowguard/oversized.py"
    surfaces = tuple(
        _syntax_surface(
            f"surface:oversized:{index:03d}",
            path,
            f"function_{index:03d}",
            index * 20 + 1,
            index * 20 + 20,
        )
        for index in range(150)
    )
    bundle = _bind_surfaces(_bundle(), surfaces)

    universe = derive_self_reduction_universe(bundle)

    oversized_rows = tuple(
        row for row in universe.members if "oversized_boundary_signal" in row.signal_kinds
    )
    assert len(oversized_rows) == 1
    assert len(universe.oversized_boundaries) == 1
    boundary_path, hotspot_ids = universe.oversized_boundaries[0]
    assert boundary_path == path
    assert 1 <= len(hotspot_ids) <= 12
    assert set(universe.implementation_surface_ids) == set(
        universe.required_implementation_surface_ids
    )


def test_branch_containment_uses_one_interval_index_and_keeps_narrowest_owner(
    tmp_path,
):
    relative_path = "flowguard/dense.py"
    source_path = tmp_path / relative_path
    source_path.parent.mkdir(parents=True)
    source_lines = []
    surface_specs = []
    branch_lines = []
    for index in range(32):
        line_start = len(source_lines) + 1
        source_lines.extend(
            (
                f"def _validate_{index}(value):",
                "    if value:",
                "        return 1",
                "    return 0",
                "",
            )
        )
        surface_specs.append((index, line_start, line_start + 3))
        branch_lines.append(line_start + 1)
    source_path.write_text("\n".join(source_lines), encoding="utf-8")

    counter = {"line_reads": 0}
    surfaces = [
        _CountingIntervalSurface(
            surface_id="surface:outer",
            path=relative_path,
            symbol="_outer",
            line_start=1,
            line_end=len(source_lines),
            counter=counter,
        )
    ]
    surfaces.extend(
        _CountingIntervalSurface(
            surface_id=f"surface:{index}",
            path=relative_path,
            symbol=f"_validate_{index}",
            line_start=line_start,
            line_end=line_end,
            counter=counter,
        )
        for index, line_start, line_end in surface_specs
    )
    bundle = _bundle()
    bundle.inventory.surfaces = tuple(surfaces)
    bundle.inventory.required_surface_ids = tuple(
        surface.surface_id for surface in surfaces
    )
    _install_current_behavior(
        bundle,
        tuple(
            _current_contract(
                surface,
                suffix=surface.surface_id.removeprefix("surface:"),
                semantic_value=f"result:{surface.surface_id}",
            )
            for surface in surfaces
        ),
    )
    universe = derive_self_reduction_universe(bundle, root=tmp_path)
    universe_line_reads = counter["line_reads"]
    counter["line_reads"] = 0

    records = derive_self_reduction_retain_dispositions(
        bundle,
        universe,
        candidate_bindings=(),
    )

    assert universe_line_reads <= 3 * len(surfaces)
    assert counter["line_reads"] == 0
    covered = {member_id for row in records for member_id in row.member_ids}
    assert universe.branch_site_count == len(branch_lines)
    assert universe.unbound_branch_site_count == 0
    assert universe.branch_fingerprint.startswith("sha256:")
    assert not any(row.member_id.startswith("branch:") for row in universe.members)
    branch_surfaces = tuple(
        row for row in universe.members if "branch_signal" in row.signal_kinds
    )
    assert len(branch_surfaces) == len(branch_lines)
    assert all(row.branch_count == 1 for row in branch_surfaces)
    assert all(not row.materialized_branch_site_ids for row in branch_surfaces)
    first_branch = next(
        row for row in records if "surface:0" in row.member_ids
    )
    assert "owner:0" in first_branch.owner_refs
    assert "owner:outer" not in first_branch.owner_refs
    assert set(row.member_id for row in branch_surfaces) <= covered


def test_universe_is_independent_and_disposes_every_required_kind():
    universe = derive_self_reduction_universe(_bundle())

    assert universe.complete
    assert universe.audit_accounted
    assert not universe.cleanup_resolved
    assert universe.unresolved_member_ids
    assert universe.implementation_surface_ids == (
        "surface:helper",
        "surface:public",
    )
    assert {row.member_kind for row in universe.members} >= {
        "public_entrypoint",
        "implementation_surface",
        "provider",
        "model_owner",
        "check_owner",
        "resource",
        "test",
        "inventory_audit",
    }
    assert next(
        row for row in universe.members if row.member_id == "surface:public"
    ).signal_kinds == ("command_route_signal", "wrapper_facade_signal")
    assert next(
        row for row in universe.members if row.member_id == "surface:helper"
    ).signal_kinds == ("helper_signal",)
    assert {row.disposition for row in universe.members} <= {
        "retain",
        "contract",
        "unresolved",
    }
    assert all(row.rationale for row in universe.members)
    step_rows = tuple(row for row in universe.members if row.signal_kinds)
    assert step_rows
    assert {row.step_action for row in step_rows} == {"unresolved"}
    assert all(row.static_operation_count > 0 for row in step_rows)
    assert all(row.analysis_payload_bytes > 0 for row in step_rows)
    assert all(row.cost_source_ref for row in step_rows)
    assert universe.fingerprint.startswith("sha256:")


def test_discovery_gap_keeps_universe_incomplete_even_when_candidate_scan_is_empty():
    finding = SimpleNamespace(
        code="discovery_adapter_missing",
        message="the required discovery adapter is unavailable",
        severity="blocker",
        path="flowguard/unobserved.py",
        surface_id="",
    )

    universe = derive_self_reduction_universe(
        _bundle(inventory_findings=(finding,))
    )
    records = derive_self_reduction_retain_dispositions(
        _bundle(inventory_findings=(finding,)),
        universe,
        candidate_bindings=(),
    )

    assert not universe.complete
    assert universe.audit_accounted
    assert not universe.cleanup_resolved
    assert universe.source_complete is False
    assert universe.unresolved_member_ids
    matching_gaps = tuple(
        row
        for row in universe.members
        if row.member_kind == "inventory_gap" and row.rationale == finding.message
    )
    assert len(matching_gaps) == 1
    gap = matching_gaps[0]
    assert gap.disposition == "unresolved"
    assert "discovery adapter" in gap.rationale
    assert gap.member_id not in {
        member_id for row in records for member_id in row.member_ids
    }


def test_distinct_inventory_findings_each_keep_one_gap_identity():
    findings = (
        SimpleNamespace(
            code="dynamic_surface_unresolved",
            message="dynamic surface one is unresolved",
            severity="blocker",
            path="flowguard/one.py",
            surface_id="",
        ),
        SimpleNamespace(
            code="discovery_adapter_missing",
            message="discovery adapter two is missing",
            severity="blocker",
            path="flowguard/two.py",
            surface_id="",
        ),
    )

    universe = derive_self_reduction_universe(
        _bundle(inventory_findings=findings)
    )

    finding_gaps = tuple(
        row
        for row in universe.members
        if row.member_kind == "inventory_gap"
        and row.rationale in {finding.message for finding in findings}
    )
    assert len(finding_gaps) == 2
    assert len({row.member_id for row in finding_gaps}) == 2
    assert {row.rationale for row in finding_gaps} == {
        finding.message for finding in findings
    }


def test_empty_self_surface_denominator_cannot_be_complete():
    bundle = _bundle()
    bundle.inventory.surfaces = ()
    bundle.inventory.required_surface_ids = ()

    universe = derive_self_reduction_universe(bundle)

    assert not universe.complete
    assert universe.source_complete is False
    assert any(
        row.member_kind == "inventory_gap"
        and "no required implementation surfaces" in row.rationale.lower()
        for row in universe.members
    )


def test_behavior_owner_referencing_an_unobserved_surface_blocks_the_universe():
    bundle = _bundle()
    bundle.behavior_report.contracts = (
        SimpleNamespace(
            behavior_block_id="behavior:missing",
            implementation_surface_id="surface:missing",
            model_element_id="model:missing",
            owner_id="owner:missing",
            owner_contract_id="contract:missing",
            source_fingerprint="sha256:missing-behavior",
        ),
    )

    universe = derive_self_reduction_universe(bundle)

    assert not universe.complete
    assert any(
        row.member_kind == "inventory_gap"
        and row.source_ref == "surface:missing"
        for row in universe.members
    )
