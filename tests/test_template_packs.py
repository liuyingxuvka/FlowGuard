import json
import unittest
from dataclasses import replace

from flowguard.template_packs import (
    HardPredicate,
    TEMPLATE_PACK_MANIFEST_SCHEMA,
    TemplatePack,
    TemplatePackInstanceReceipt,
    TemplatePackManifest,
    TemplatePackSelectionReceipt,
    ValidatedTemplatePackRegistry,
    instantiate_template_packs,
    seal_template_pack_manifest,
    select_template_packs,
    template_pack_manifest_digest,
    validate_template_pack_instance_receipt,
    validate_template_pack_manifest,
    validate_template_pack_selection_receipt,
)


def specialized_pack(
    template_id,
    field_name,
    *,
    context_key="kind",
    operator="equals",
    expected="document",
    priority=0,
    composable=False,
    template=None,
    required_parameters=(),
):
    return TemplatePack(
        template_id=template_id,
        version="1",
        priority=priority,
        predicates=(HardPredicate(context_key, operator, expected),),
        composable=composable,
        owned_fields=tuple((template or {field_name: template_id}).keys()),
        required_parameters=tuple(required_parameters),
        template=template or {field_name: template_id},
    )


def base_pack(template_id="base", field_name="base_field"):
    return TemplatePack(
        template_id=template_id,
        version="1",
        base=True,
        owned_fields=(field_name,),
        template={field_name: "base"},
    )


def sealed_manifest(*templates, manifest_id="registry", version="1"):
    return seal_template_pack_manifest(
        TemplatePackManifest(
            manifest_id=manifest_id,
            version=version,
            templates=tuple(templates),
        )
    )


class TemplatePackManifestTests(unittest.TestCase):
    def test_manifest_identity_is_canonical_and_round_trips(self):
        alpha = specialized_pack("alpha", "alpha_field")
        beta = specialized_pack("beta", "beta_field")
        first = sealed_manifest(alpha, beta)
        reordered = sealed_manifest(beta, alpha)

        self.assertEqual(first.manifest_digest, reordered.manifest_digest)
        self.assertEqual(first.manifest_digest, template_pack_manifest_digest(first))
        self.assertTrue(validate_template_pack_manifest(first).ok)

        round_trip = TemplatePackManifest.from_dict(json.loads(first.to_json_text()))
        self.assertEqual(first.to_dict(), round_trip.to_dict())
        self.assertTrue(validate_template_pack_manifest(round_trip).ok)

        one_of_forward = specialized_pack(
            "ordered",
            "field",
            operator="one_of",
            expected=["a", "b"],
        )
        one_of_reverse = specialized_pack(
            "ordered",
            "field",
            operator="one_of",
            expected=["b", "a"],
        )
        self.assertEqual(
            sealed_manifest(one_of_forward).manifest_digest,
            sealed_manifest(one_of_reverse).manifest_digest,
        )

    def test_manifest_requires_current_schema_and_current_digest(self):
        draft = TemplatePackManifest(
            manifest_id="registry",
            version="1",
            templates=(specialized_pack("alpha", "field"),),
        )
        self.assertIn("missing_manifest_digest", validate_template_pack_manifest(draft).findings)

        sealed = seal_template_pack_manifest(draft)
        stale = replace(sealed, version="2")
        self.assertIn("manifest_digest_mismatch", validate_template_pack_manifest(stale).findings)

        unknown = seal_template_pack_manifest(replace(draft, schema_version="flowguard.template-pack-manifest.v0"))
        self.assertIn(
            "unsupported_manifest_schema:flowguard.template-pack-manifest.v0",
            validate_template_pack_manifest(unknown).findings,
        )

    def test_structural_validation_reports_ambiguous_owners_and_parameters(self):
        duplicate_left = specialized_pack("duplicate", "left")
        duplicate_right = specialized_pack("duplicate", "right")
        bad_base = TemplatePack(
            template_id="base-one",
            version="1",
            base=True,
            composable=True,
            predicates=(HardPredicate("kind", "equals", "x"),),
            owned_fields=("base",),
            template={"base": "x"},
        )
        second_base = base_pack("base-two", "other_base")
        mismatched = TemplatePack(
            template_id="mismatch",
            version="1",
            predicates=(HardPredicate("kind", "equals", "x"),),
            owned_fields=("declared", "declared"),
            required_parameters=("unused", "unused"),
            template={"actual": "${needed}"},
        )
        non_boolean = TemplatePack.from_dict(
            {
                "template_id": "non-boolean",
                "version": "1",
                "base": "false",
                "composable": 1,
                "predicates": [{"key": "kind", "operator": "equals", "expected": "x"}],
                "owned_fields": ["field"],
                "template": {"field": "value"},
            }
        )
        manifest = sealed_manifest(
            duplicate_left,
            duplicate_right,
            bad_base,
            second_base,
            mismatched,
            non_boolean,
        )
        findings = validate_template_pack_manifest(manifest).findings

        self.assertIn("duplicate_template_id:duplicate", findings)
        self.assertIn("multiple_base_templates", findings)
        self.assertIn("base_predicates_not_allowed:base-one", findings)
        self.assertIn("base_composable_not_allowed:base-one", findings)
        self.assertIn("duplicate_owned_field:mismatch:declared", findings)
        self.assertTrue(any(item.startswith("owned_fields_mismatch:mismatch:") for item in findings))
        self.assertIn("duplicate_required_parameter:mismatch:unused", findings)
        self.assertTrue(any(item.startswith("required_parameters_mismatch:mismatch:") for item in findings))
        self.assertIn("base_must_be_boolean:non-boolean", findings)
        self.assertIn("composable_must_be_boolean:non-boolean", findings)

    def test_predicate_validation_is_bounded(self):
        invalid = TemplatePack(
            template_id="invalid",
            version="1",
            predicates=(
                HardPredicate("", "execute_python", {"code": "pass"}),
                HardPredicate("tier", "one_of", []),
                HardPredicate("optional", "exists", "false"),
            ),
            owned_fields=("field",),
            template={"field": "value"},
        )
        findings = validate_template_pack_manifest(sealed_manifest(invalid)).findings

        self.assertIn("predicate:invalid:0:missing_key", findings)
        self.assertIn("predicate:invalid:0:unsupported_operator:execute_python", findings)
        self.assertIn("predicate:invalid:1:one_of_expected_must_be_nonempty_array", findings)
        self.assertIn("predicate:invalid:2:exists_expected_must_be_boolean", findings)


class TemplatePackSelectionTests(unittest.TestCase):
    def test_all_bounded_predicate_operators_are_conjunctive_and_composable(self):
        templates = (
            specialized_pack("equals", "a", context_key="kind", operator="equals", expected="doc", composable=True),
            specialized_pack("one-of", "b", context_key="tier", operator="one_of", expected=["pro", "enterprise"], composable=True),
            specialized_pack("contains", "c", context_key="tags", operator="contains", expected="blue", composable=True),
            specialized_pack("contains-all", "d", context_key="roles", operator="contains_all", expected=["author", "reviewer"], composable=True),
            specialized_pack("not-present", "e", context_key="optional", operator="exists", expected=False, composable=True),
        )
        manifest = sealed_manifest(*templates)
        receipt = select_template_packs(
            manifest,
            {
                "kind": "doc",
                "tier": "pro",
                "tags": ["green", "blue"],
                "roles": ["reviewer", "author", "reader"],
            },
        )

        self.assertEqual("composed", receipt.disposition)
        self.assertEqual(
            ("contains", "contains-all", "equals", "not-present", "one-of"),
            receipt.selected_template_ids,
        )

    def test_failed_or_missing_predicate_excludes_entry(self):
        matching = specialized_pack("matching", "match", expected="document")
        failing = specialized_pack("failing", "fail", expected="spreadsheet")
        missing = specialized_pack("missing", "missing", context_key="tier", expected="pro")
        receipt = select_template_packs(sealed_manifest(matching, failing, missing), {"kind": "document"})

        self.assertEqual("selected", receipt.disposition)
        self.assertEqual(("matching",), receipt.matched_template_ids)

    def test_equals_and_one_of_use_strict_json_types(self):
        equals_true = specialized_pack("equals-true", "a", expected=True)
        one_of_true = specialized_pack(
            "one-of-true",
            "b",
            operator="one_of",
            expected=[True],
        )
        receipt = select_template_packs(
            sealed_manifest(equals_true, one_of_true),
            {"kind": 1},
        )

        self.assertEqual("no_match", receipt.disposition)

    def test_zero_match_uses_declared_base_only_as_fallback(self):
        specialized = specialized_pack("specialized", "special", expected="special")
        manifest = sealed_manifest(base_pack(), specialized)
        fallback = select_template_packs(manifest, {"kind": "other"})
        matched = select_template_packs(manifest, {"kind": "special"})

        self.assertEqual("base_selected", fallback.disposition)
        self.assertEqual((), fallback.matched_template_ids)
        self.assertEqual(("base",), fallback.selected_template_ids)
        self.assertEqual("selected", matched.disposition)
        self.assertEqual(("specialized",), matched.selected_template_ids)
        self.assertNotIn("base", matched.matched_template_ids)

    def test_zero_match_without_base_is_explicit(self):
        receipt = select_template_packs(
            sealed_manifest(specialized_pack("specialized", "field", expected="special")),
            {"kind": "other"},
        )
        self.assertEqual("no_match", receipt.disposition)
        self.assertEqual((), receipt.selected_template_ids)

    def test_composable_many_uses_priority_then_id_order(self):
        beta = specialized_pack("beta", "b", priority=20, composable=True)
        zeta = specialized_pack("zeta", "z", priority=10, composable=True)
        alpha = specialized_pack("alpha", "a", priority=10, composable=True)
        receipt = select_template_packs(sealed_manifest(beta, zeta, alpha), {"kind": "document"})

        self.assertEqual("composed", receipt.disposition)
        self.assertEqual(("alpha", "zeta", "beta"), receipt.selected_template_ids)

    def test_non_composable_many_fails_closed(self):
        composable = specialized_pack("composable", "a", composable=True)
        exclusive = specialized_pack("exclusive", "b", composable=False)
        receipt = select_template_packs(sealed_manifest(composable, exclusive), {"kind": "document"})

        self.assertEqual("conflict", receipt.disposition)
        self.assertEqual((), receipt.selected_template_ids)
        self.assertIn("non_composable_matches:exclusive", receipt.findings)

    def test_field_owner_conflict_fails_closed(self):
        left = specialized_pack("left", "shared", composable=True)
        right = specialized_pack("right", "shared", composable=True)
        receipt = select_template_packs(sealed_manifest(left, right), {"kind": "document"})

        self.assertEqual("conflict", receipt.disposition)
        self.assertEqual((), receipt.selected_template_ids)
        self.assertIn("field_owner_conflict:shared=left|right", receipt.findings)

    def test_invalid_manifest_emits_auditable_receipt(self):
        manifest = TemplatePackManifest(
            manifest_id="registry",
            version="1",
            templates=(specialized_pack("one", "field"),),
        )
        receipt = select_template_packs(manifest, {"kind": "document"})

        self.assertEqual("invalid_manifest", receipt.disposition)
        self.assertIn("missing_manifest_digest", receipt.findings)
        self.assertTrue(receipt.selection_digest.startswith("sha256:"))

    def test_selection_receipt_is_deterministic_and_stale_on_any_input_change(self):
        pack = specialized_pack("one", "field")
        manifest = sealed_manifest(pack)
        context = {"kind": "document"}
        receipt = select_template_packs(manifest, context)

        self.assertEqual(receipt, select_template_packs(manifest, dict(context)))
        self.assertTrue(validate_template_pack_selection_receipt(manifest, context, receipt).current)
        self.assertFalse(
            validate_template_pack_selection_receipt(manifest, {"kind": "other"}, receipt).current
        )

        changed_manifest = sealed_manifest(
            specialized_pack("one", "field", template={"field": "changed"})
        )
        self.assertFalse(
            validate_template_pack_selection_receipt(changed_manifest, context, receipt).current
        )

        tampered = replace(receipt, selected_template_ids=("other",))
        self.assertFalse(validate_template_pack_selection_receipt(manifest, context, tampered).current)

        round_trip = TemplatePackSelectionReceipt.from_dict(json.loads(receipt.to_json_text()))
        self.assertEqual(receipt, round_trip)

        mutable_ids = ["one"]
        normalized = TemplatePackSelectionReceipt(
            manifest_digest="manifest",
            context_digest="context",
            matched_template_ids=mutable_ids,
            selected_template_ids=mutable_ids,
            disposition="selected",
            findings=[],
        )
        mutable_ids.append("later")
        self.assertEqual(("one",), normalized.selected_template_ids)


class TemplatePackInstanceTests(unittest.TestCase):
    def parameterized_manifest(self):
        pack = specialized_pack(
            "parameterized",
            "greeting",
            template={
                "greeting": "Hello ${name}",
                "limit": "${limit}",
                "nested": {"owner": "${name}", "items": ["${limit}"]},
            },
            required_parameters=("name", "limit"),
        )
        return sealed_manifest(pack)

    def test_instantiation_is_strict_deterministic_and_immutable(self):
        manifest = self.parameterized_manifest()
        context = {"kind": "document"}
        parameters = {"name": "Ada", "limit": 3}
        selection = select_template_packs(manifest, context)
        instance = instantiate_template_packs(manifest, context, selection, parameters)

        self.assertEqual("instantiated", instance.status)
        self.assertEqual("Hello Ada", instance.rendered_template["greeting"])
        self.assertEqual(3, instance.rendered_template["limit"])
        self.assertEqual((3,), instance.rendered_template["nested"]["items"])
        with self.assertRaises(TypeError):
            instance.rendered_template["greeting"] = "tampered"
        self.assertTrue(
            validate_template_pack_instance_receipt(
                manifest,
                context,
                selection,
                parameters,
                instance,
            ).current
        )
        self.assertEqual(
            instance,
            TemplatePackInstanceReceipt.from_dict(json.loads(instance.to_json_text())),
        )

    def test_missing_and_extra_parameters_block_instantiation(self):
        manifest = self.parameterized_manifest()
        context = {"kind": "document"}
        selection = select_template_packs(manifest, context)

        missing = instantiate_template_packs(manifest, context, selection, {"name": "Ada"})
        extra = instantiate_template_packs(
            manifest,
            context,
            selection,
            {"name": "Ada", "limit": 3, "unused": True},
        )

        self.assertEqual("blocked", missing.status)
        self.assertIn("missing_parameters:limit", missing.findings)
        self.assertEqual("blocked", extra.status)
        self.assertIn("unexpected_parameters:unused", extra.findings)

    def test_nonselectable_and_stale_selection_receipts_block(self):
        no_match_manifest = sealed_manifest(
            specialized_pack("one", "field", expected="special")
        )
        no_match = select_template_packs(no_match_manifest, {"kind": "other"})
        blocked = instantiate_template_packs(
            no_match_manifest,
            {"kind": "other"},
            no_match,
            {},
        )
        self.assertEqual("blocked", blocked.status)
        self.assertIn("selection_not_selectable:no_match", blocked.findings)

        selectable_manifest = sealed_manifest(specialized_pack("one", "field"))
        old_context = {"kind": "document"}
        selection = select_template_packs(selectable_manifest, old_context)
        stale = instantiate_template_packs(
            selectable_manifest,
            {"kind": "other"},
            selection,
            {},
        )
        self.assertEqual("blocked", stale.status)
        self.assertIn("selection_receipt_stale", stale.findings)

    def test_instance_receipt_is_stale_on_parameter_context_manifest_or_output_change(self):
        manifest = self.parameterized_manifest()
        context = {"kind": "document"}
        parameters = {"name": "Ada", "limit": 3}
        selection = select_template_packs(manifest, context)
        instance = instantiate_template_packs(manifest, context, selection, parameters)

        self.assertFalse(
            validate_template_pack_instance_receipt(
                manifest,
                context,
                selection,
                {"name": "Grace", "limit": 3},
                instance,
            ).current
        )
        self.assertFalse(
            validate_template_pack_instance_receipt(
                manifest,
                {"kind": "other"},
                selection,
                parameters,
                instance,
            ).current
        )

        changed_pack = specialized_pack(
            "parameterized",
            "greeting",
            template={
                "greeting": "Welcome ${name}",
                "limit": "${limit}",
                "nested": {"owner": "${name}", "items": ["${limit}"]},
            },
            required_parameters=("name", "limit"),
        )
        changed_manifest = sealed_manifest(changed_pack)
        self.assertFalse(
            validate_template_pack_instance_receipt(
                changed_manifest,
                context,
                selection,
                parameters,
                instance,
            ).current
        )

        tampered = replace(instance, rendered_template={"greeting": "tampered"})
        self.assertFalse(
            validate_template_pack_instance_receipt(
                manifest,
                context,
                selection,
                parameters,
                tampered,
            ).current
        )

    def test_registry_wrapper_rejects_invalid_manifest_and_uses_same_receipts(self):
        draft = TemplatePackManifest(
            manifest_id="registry",
            version="1",
            templates=(specialized_pack("one", "field"),),
            schema_version=TEMPLATE_PACK_MANIFEST_SCHEMA,
        )
        with self.assertRaises(ValueError):
            ValidatedTemplatePackRegistry(draft)

        registry = ValidatedTemplatePackRegistry(seal_template_pack_manifest(draft))
        context = {"kind": "document"}
        selection = registry.select(context)
        instance = registry.instantiate(context, selection, {})
        self.assertEqual("instantiated", instance.status)
        self.assertTrue(registry.validate_selection(context, selection).current)
        self.assertTrue(registry.validate_instance(context, selection, {}, instance).current)


if __name__ == "__main__":
    unittest.main()
