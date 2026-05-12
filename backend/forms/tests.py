from django.core.exceptions import ValidationError
from django.test import TestCase
from types import SimpleNamespace

from .aggregation import aggregate_instance
from .branding import DEFAULT_PUBLIC_FOOTER_TEXT, DEFAULT_PUBLIC_PROGRAM_NAME
from .considerations_library import build_canonical_considerations_by_question
from .engine import evaluate, validate_answers
from .i18n import localize_schema, resolve_language
from .models import (
    InspectionConfigVersion,
    InspectionInstance,
    OrganizationBranding,
    RecipientLink,
    Submission,
    default_base_config,
)
from .pdf import (
    _DEFAULT_REPORT_FOOTER,
    _confidence_key,
    _cross_domain_compounding_note,
    _domain_interpretation_text,
    _elevated_global_note,
    _localized_classification,
    _localized_confidence,
    _render_considerations,
    _safeguard_statement,
    _section_interpretation_text,
    build_single_submission_pdf_outline,
    format_classification_display,
    generate_aggregated_pdf,
    generate_single_submission_pdf,
)
from .presentation import (
    domain_label,
    flag_label,
    indicator_label,
    language_label,
    pattern_label,
    tag_label,
)
from .report_data import assemble_single_submission_sri_report_data
from .sri_baseline import (
    SRI_BASELINE_CONFIG_VERSION_ID,
    SRI_BASELINE_INSTANCE_ID,
    SRI_BASELINE_INSTANCE_NAME,
)


class SriDefaultConfigTests(TestCase):
    def test_default_config_has_expected_sri_structure(self):
        config = default_base_config()
        schema = config["schema"]
        sections = schema["sections"]

        self.assertEqual(len(sections), 5)
        self.assertEqual(
            [s["id"] for s in sections],
            [
                "overnight_sleep_routines",
                "feeding_daytime_care",
                "transport_equipment_configuration",
                "home_layout_environmental_access",
                "ownership_review_cadence",
            ],
        )

        fields = [f for section in sections for f in section["fields"]]
        self.assertEqual(len(fields), 20)
        self.assertEqual([f["meta"]["sri_question_number"] for f in fields], list(range(1, 21)))

        field_ids = [f["id"] for f in fields]
        self.assertEqual(len(field_ids), len(set(field_ids)))

    def test_default_config_fields_are_select_with_options(self):
        config = default_base_config()
        fields = [f for section in config["schema"]["sections"] for f in section["fields"]]

        for field in fields:
            self.assertEqual(field["type"], "select")
            self.assertTrue(field["required"])
            self.assertGreater(len(field["options"]), 0)
            self.assertEqual(len({o["value"] for o in field["options"]}), len(field["options"]))

    def test_default_config_passes_publish_validation_and_runtime_validation(self):
        instance = InspectionInstance.objects.create(name="SRI Baseline")
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=instance,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )
        self.assertEqual(cfg.status, InspectionConfigVersion.STATUS_PUBLISHED)
        self.assertTrue(cfg.config_sha256)

        valid_answers = {}
        for section in cfg.config["schema"]["sections"]:
            for field in section["fields"]:
                valid_answers[field["id"]] = field["options"][0]["value"]

        # Should not raise.
        validate_answers(cfg.config, valid_answers)

    def _baseline_answers(self) -> dict[str, str]:
        config = default_base_config()
        answers: dict[str, str] = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        return answers

    def test_sri_path_cleared(self):
        config = default_base_config()
        answers = self._baseline_answers()

        result = evaluate(config, answers)

        self.assertEqual(result.classification, "Cleared")
        self.assertEqual(set(result.domain_classifications.values()), {"Cleared"})
        self.assertEqual(result.cross_domain_flags, [])

    def test_sri_path_watch(self):
        config = default_base_config()
        answers = self._baseline_answers()
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"

        result = evaluate(config, answers)

        self.assertEqual(result.classification, "Watch")
        self.assertEqual(result.domain_classifications["overnight_sleep_routines"], "Watch")
        self.assertIn("drift_conditions", result.indicators_by_domain["overnight_sleep_routines"])
        self.assertIn("review_cadence", result.indicators_by_domain["overnight_sleep_routines"])

    def test_sri_path_elevated(self):
        config = default_base_config()
        answers = self._baseline_answers()
        answers["home_supply_storage_distribution"] = "three_or_more_areas"
        answers["home_nighttime_room_movement_frequency"] = "frequently"

        result = evaluate(config, answers)

        self.assertEqual(result.classification, "Elevated")
        self.assertEqual(result.domain_classifications["home_layout_environmental_access"], "Elevated")
        self.assertGreaterEqual(
            result.indicator_signals_by_domain["home_layout_environmental_access"]["structural_complexity_exposure"][
                "high"
            ],
            2,
        )

    def test_sri_cross_domain_escalation_flag(self):
        config = default_base_config()
        answers = self._baseline_answers()

        # Domain 1 elevated via 3 moderate signals.
        answers["overnight_final_decision_authority"] = "shared_without_final_authority"
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"
        # Domain 2 elevated via 3 moderate signals.
        answers["transport_equipment_installer_clarity"] = "multiple_individuals"
        answers["transport_configuration_change_frequency"] = "occasionally"
        answers["transport_configuration_authority"] = "shared_authority"
        # Domain 3 elevated via 3 moderate signals.
        answers["home_supply_storage_distribution"] = "two_areas"
        answers["home_nighttime_room_movement_frequency"] = "sometimes"
        answers["home_setup_change_difficulty"] = "moderate_effort"

        result = evaluate(config, answers)

        elevated_domains = [k for k, v in result.domain_classifications.items() if v == "Elevated"]
        self.assertGreaterEqual(len(elevated_domains), 3)
        self.assertIn("multi_domain_structural_exposure", result.cross_domain_flags)
        self.assertIn("cross_domain_multi_exposure", result.patterns)

    def test_structural_considerations_trigger_for_watch_domain(self):
        config = default_base_config()
        answers = self._baseline_answers()
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"

        result = evaluate(config, answers)
        items = result.structural_considerations.get("overnight_sleep_routines", [])

        self.assertEqual(result.domain_classifications["overnight_sleep_routines"], "Watch")
        self.assertGreaterEqual(len(items), 1)
        self.assertLessEqual(len(items), 2)
        for item in items:
            self.assertEqual(item["classification_level"], "Watch")
            self.assertIn("text", item)
            self.assertTrue(item["text"])

    def test_structural_considerations_limits_and_deterministic_order(self):
        config = default_base_config()
        answers = self._baseline_answers()

        # Trigger multiple items across all domains.
        answers["overnight_final_decision_authority"] = "shared_without_final_authority"
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"

        answers["daytime_primary_caregiver"] = "shared_equally"
        answers["feeding_change_decision_process"] = "discussion_based_agreement"
        answers["feeding_review_checkin"] = "informal_checkins"

        answers["transport_equipment_installer_clarity"] = "multiple_individuals"
        answers["transport_configuration_change_frequency"] = "occasionally"
        answers["transport_configuration_authority"] = "shared_authority"

        answers["home_supply_storage_distribution"] = "two_areas"
        answers["home_nighttime_room_movement_frequency"] = "sometimes"
        answers["home_setup_change_difficulty"] = "moderate_effort"

        answers["caregiver_responsibility_clarity"] = "mostly"
        answers["routine_reassessment_timeline_set"] = "informally_planned"
        answers["temporary_routine_change_expectation"] = "occasionally"

        result = evaluate(config, answers)
        selected = result.structural_considerations
        total = sum(len(v) for v in selected.values())

        self.assertLessEqual(total, 8)
        for _, domain_items in selected.items():
            self.assertLessEqual(len(domain_items), 2)
            question_numbers = [x["question_number"] for x in domain_items]
            self.assertEqual(question_numbers, sorted(question_numbers))


class SriBaselineOperationalTests(TestCase):
    def test_seed_creates_baseline_template_and_published_config(self):
        inst = InspectionInstance.objects.get(pk=SRI_BASELINE_INSTANCE_ID)
        self.assertEqual(inst.kind, InspectionInstance.KIND_TEMPLATE)
        self.assertEqual(inst.name, SRI_BASELINE_INSTANCE_NAME)

        cfg = InspectionConfigVersion.objects.get(pk=SRI_BASELINE_CONFIG_VERSION_ID)
        self.assertEqual(cfg.inspection_instance_id, SRI_BASELINE_INSTANCE_ID)
        self.assertEqual(cfg.status, InspectionConfigVersion.STATUS_PUBLISHED)
        self.assertTrue(cfg.config_sha256)
        self.assertEqual(cfg.config["schema"]["title"], "Structured Wellbeing Risk Inspection")

        valid = {}
        for section in cfg.config["schema"]["sections"]:
            for field in section["fields"]:
                valid[field["id"]] = field["options"][0]["value"]
        validate_answers(cfg.config, valid)

    def test_submission_retains_original_config_version_after_new_publish(self):
        inst = InspectionInstance.objects.get(pk=SRI_BASELINE_INSTANCE_ID)
        v1 = InspectionConfigVersion.objects.get(pk=SRI_BASELINE_CONFIG_VERSION_ID)

        link = RecipientLink.objects.create(inspection_instance=inst, config_version=v1)
        answers = {}
        for section in v1.config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]

        sub = Submission.objects.create(
            recipient_link=link,
            config_version=v1,
            answers=answers,
            outputs={"classification": "Cleared"},
        )

        v2 = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_DRAFT,
        )
        v2.publish()
        v2.save()

        sub.refresh_from_db()
        self.assertEqual(sub.config_version_id, v1.id)
        self.assertEqual(sub.config_version_id, SRI_BASELINE_CONFIG_VERSION_ID)

    def test_published_baseline_config_rejects_content_change(self):
        cfg = InspectionConfigVersion.objects.get(pk=SRI_BASELINE_CONFIG_VERSION_ID)
        mutated = dict(cfg.config)
        mutated["schema"] = {**mutated["schema"], "title": "Tampered title"}

        cfg.config = mutated
        with self.assertRaises(ValidationError):
            cfg.save()


class SriReportDataAssemblyTests(TestCase):
    def _baseline_answers(self) -> dict[str, str]:
        config = default_base_config()
        answers: dict[str, str] = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        return answers

    def _outputs_for_answers(self, answers: dict[str, str]) -> dict:
        config = default_base_config()
        result = evaluate(config, answers)
        return {
            "classification": result.classification,
            "tags": result.tags,
            "patterns": result.patterns,
            "section_classifications": result.section_classifications,
            "domain_classifications": result.domain_classifications,
            "indicators_by_domain": result.indicators_by_domain,
            "indicator_signals_by_domain": result.indicator_signals_by_domain,
            "cross_domain_flags": result.cross_domain_flags,
            "structural_considerations": result.structural_considerations,
            "output_language": "en",
        }

    def test_report_contract_contains_milestone_fields(self):
        config = default_base_config()
        schema = config["schema"]
        answers = self._baseline_answers()
        outputs = self._outputs_for_answers(answers)

        report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )

        self.assertEqual(report.inspection_id, "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        self.assertEqual(report.inspection_standard, "SRI")
        self.assertEqual(report.inspection_standard_version, "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        self.assertEqual(report.overall_classification, "Cleared")
        self.assertEqual(len(report.domain_classification_overview), 5)
        self.assertEqual(len(report.domains), 5)
        self.assertEqual(report.cross_domain_summary_flags, [])
        self.assertTrue(report.methodology_scope["methodology"])
        self.assertTrue(report.methodology_scope["scope"])
        self.assertGreaterEqual(len(report.strengths_data), 1)

    def test_priority_order_and_considerations_are_deterministic(self):
        config = default_base_config()
        schema = config["schema"]
        answers = self._baseline_answers()
        # Trigger elevated in three domains (and cross-domain flag).
        answers["overnight_final_decision_authority"] = "shared_without_final_authority"
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"
        answers["transport_equipment_installer_clarity"] = "multiple_individuals"
        answers["transport_configuration_change_frequency"] = "occasionally"
        answers["transport_configuration_authority"] = "shared_authority"
        answers["home_supply_storage_distribution"] = "two_areas"
        answers["home_nighttime_room_movement_frequency"] = "sometimes"
        answers["home_setup_change_difficulty"] = "moderate_effort"

        outputs = self._outputs_for_answers(answers)
        report_a = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        report_b = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )

        self.assertIn("multi_domain_structural_exposure", report_a.cross_domain_summary_flags)
        self.assertEqual(report_a.priority_review_order, report_b.priority_review_order)
        self.assertEqual(report_a.selected_structural_considerations, report_b.selected_structural_considerations)
        # Highest-priority domains should be Elevated first.
        elevated_domains = {
            x["domain_id"]
            for x in report_a.domain_classification_overview
            if x["classification"] == "Elevated"
        }
        self.assertTrue(set(report_a.priority_review_order[: len(elevated_domains)]).issubset(elevated_domains))

    def test_pdf_outline_contains_phase_2_2_required_sections(self):
        config = default_base_config()
        schema = config["schema"]
        answers = self._baseline_answers()
        outputs = self._outputs_for_answers(answers)
        report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )

        outline = build_single_submission_pdf_outline(report)
        self.assertEqual(
            outline,
            [
                "Report Header",
                "Inspection Standard",
                "Executive Overview",
                "Overall Classification",
                "Priority Review Order",
                "Domain Classification Overview",
                "Domain Detail Sections",
                "Cross-Domain System Analysis",
                "Structural Strengths",
                "Methodology Overview",
                "Scope and Limitations",
            ],
        )

    def test_confidence_marker_derivation_from_signals(self):
        config = default_base_config()
        schema = config["schema"]

        # Low confidence: baseline with no moderate/high signals.
        low_outputs = self._outputs_for_answers(self._baseline_answers())
        low_report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=low_outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        overnight_low = next(x for x in low_report.domains if x.domain_id == "overnight_sleep_routines")
        self.assertEqual(overnight_low.confidence_marker, "Low Confidence")

        # Moderate confidence: moderate signals but no high signals.
        moderate_answers = self._baseline_answers()
        moderate_answers["overnight_routine_variability"] = "occasionally"
        moderate_answers["overnight_review_date_set"] = "informal_plan"
        moderate_outputs = self._outputs_for_answers(moderate_answers)
        moderate_report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=moderate_outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        overnight_moderate = next(x for x in moderate_report.domains if x.domain_id == "overnight_sleep_routines")
        self.assertEqual(overnight_moderate.confidence_marker, "Moderate Confidence")

        # High confidence: includes high-level signals in home domain.
        high_answers = self._baseline_answers()
        high_answers["home_supply_storage_distribution"] = "three_or_more_areas"
        high_answers["home_nighttime_room_movement_frequency"] = "frequently"
        high_outputs = self._outputs_for_answers(high_answers)
        high_report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=high_outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        home_high = next(x for x in high_report.domains if x.domain_id == "home_layout_environmental_access")
        self.assertEqual(home_high.confidence_marker, "High Confidence")

    def test_confidence_marker_parsing_and_display_support_spanish(self):
        self.assertEqual(_confidence_key("Confianza Alta"), "high")
        self.assertEqual(_confidence_key("Confianza Moderada"), "moderate")
        self.assertEqual(_confidence_key("Confianza Baja"), "low")
        self.assertEqual(_localized_confidence("High Confidence", lang="es"), "Confianza Alta")
        self.assertEqual(_localized_classification("Cleared", lang="es"), "Sin observaciones")

    def test_format_classification_display_normalizes_uppercase_tiers(self):
        self.assertEqual(format_classification_display("ELEVATED", lang="en"), "Elevated")
        self.assertEqual(format_classification_display("watch", lang="en"), "Watch")
        self.assertEqual(format_classification_display("CLEARED", lang="en"), "Cleared")
        self.assertEqual(format_classification_display("Elevated", lang="en"), "Elevated")
        self.assertEqual(format_classification_display("ELEVATED", lang="es"), "Elevado")
        self.assertEqual(format_classification_display("UNKNOWN_CUSTOM_TIER", lang="en"), "Unknown Custom Tier")

    def test_section_interpretation_text_matches_tier_when_classification_is_uppercase(self):
        elevated_en = _section_interpretation_text("ELEVATED", "en")
        self.assertIn("multiple interacting structural factors", elevated_en.lower())
        cleared_en = _section_interpretation_text("CLEARED", "en")
        self.assertIn("stable routine structure", cleared_en.lower())

    def test_section_interpretation_variants_differ_by_domain_index(self):
        w0 = _section_interpretation_text("Watch", "en", variant_index=0)
        w1 = _section_interpretation_text("Watch", "en", variant_index=1)
        self.assertNotEqual(w0, w1)
        self.assertIn("reported responses", w0.lower())
        self.assertIn("domain", w1.lower())
        es0 = _section_interpretation_text("Elevated", "es", variant_index=0)
        es2 = _section_interpretation_text("Elevated", "es", variant_index=2)
        self.assertNotEqual(es0, es2)

    def test_render_considerations_omit_question_number_prefixes(self):
        lines = _render_considerations(
            [
                {"question_number": 1, "text": "  First structural note.  "},
                {"question_number": 2, "text": "Second structural note."},
            ],
            lang="en",
        )
        self.assertEqual(lines, ["First structural note.", "Second structural note."])
        joined = " ".join(lines)
        self.assertNotIn("Question 1", joined)
        self.assertNotIn("Question 2", joined)
        self.assertNotIn("Pregunta", joined)

    def test_consideration_placement_and_display_limits(self):
        config = default_base_config()
        schema = config["schema"]
        outputs = {
            "classification": "Elevated",
            "domain_classifications": {
                "overnight_sleep_routines": "Elevated",
                "feeding_daytime_care": "Elevated",
                "transport_equipment_configuration": "Elevated",
                "home_layout_environmental_access": "Elevated",
                "ownership_review_cadence": "Elevated",
            },
            "section_classifications": {
                "overnight_sleep_routines": "Elevated",
                "feeding_daytime_care": "Elevated",
                "transport_equipment_configuration": "Elevated",
                "home_layout_environmental_access": "Elevated",
                "ownership_review_cadence": "Elevated",
            },
            "indicators_by_domain": {
                "overnight_sleep_routines": ["a", "b", "c"],
                "feeding_daytime_care": ["a", "b", "c"],
                "transport_equipment_configuration": ["a", "b", "c"],
                "home_layout_environmental_access": ["a", "b", "c"],
                "ownership_review_cadence": ["a", "b", "c"],
            },
            "indicator_signals_by_domain": {
                "overnight_sleep_routines": {"i": {"moderate": 1, "high": 1}},
                "feeding_daytime_care": {"i": {"moderate": 1, "high": 1}},
                "transport_equipment_configuration": {"i": {"moderate": 1, "high": 1}},
                "home_layout_environmental_access": {"i": {"moderate": 1, "high": 1}},
                "ownership_review_cadence": {"i": {"moderate": 1, "high": 1}},
            },
            "cross_domain_flags": ["multi_domain_structural_exposure"],
            "structural_considerations": {
                "overnight_sleep_routines": [
                    {"question_number": 4, "text": "A"},
                    {"question_number": 2, "text": "B"},
                    {"question_number": 3, "text": "C"},
                ],
                "feeding_daytime_care": [
                    {"question_number": 8, "text": "A"},
                    {"question_number": 5, "text": "B"},
                    {"question_number": 7, "text": "C"},
                ],
                "transport_equipment_configuration": [
                    {"question_number": 12, "text": "A"},
                    {"question_number": 9, "text": "B"},
                    {"question_number": 10, "text": "C"},
                ],
                "home_layout_environmental_access": [
                    {"question_number": 16, "text": "A"},
                    {"question_number": 13, "text": "B"},
                    {"question_number": 14, "text": "C"},
                ],
                "ownership_review_cadence": [
                    {"question_number": 20, "text": "A"},
                    {"question_number": 17, "text": "B"},
                    {"question_number": 18, "text": "C"},
                ],
            },
            "output_language": "en",
        }
        report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )

        # Enforced render constraints: max 2/domain, max 8 total.
        total = sum(len(v) for v in report.selected_structural_considerations.values())
        self.assertLessEqual(total, 8)
        for domain_id, items in report.selected_structural_considerations.items():
            self.assertLessEqual(len(items), 2)
            # Placement: the same considerations appear in the corresponding domain detail section.
            domain = next(x for x in report.domains if x.domain_id == domain_id)
            self.assertEqual(items, domain.structural_considerations)

    def test_domain_interpretation_uses_matrix_templates(self):
        config = default_base_config()
        watch_text = _domain_interpretation_text(
            config=config,
            domain_id="overnight_sleep_routines",
            report_language="en",
            classification="Watch",
            confidence_marker="Moderate Confidence",
            triggered_indicators=["drift_conditions"],
            indicator_count=2,
            consideration_count=2,
        )
        self.assertIn(
            "Reported responses indicate functioning routines with moderate complexity exposure.",
            watch_text,
        )
        self.assertIn(
            "Informal or temporary adjustments may stabilize into default patterns if not periodically reviewed.",
            watch_text,
        )

        elevated_text = _domain_interpretation_text(
            config=config,
            domain_id="overnight_sleep_routines",
            report_language="en",
            classification="Elevated",
            confidence_marker="High Confidence",
            triggered_indicators=["ownership_clarity"],
            indicator_count=3,
            consideration_count=2,
        )
        self.assertIn(
            "Reported responses indicate multiple interacting structural factors that may increase coordination demands over time.",
            elevated_text,
        )
        self.assertIn(
            "Absence of defined final authority may increase decision ambiguity during high-demand periods.",
            elevated_text,
        )

    def test_cross_domain_notes_and_safeguard_follow_matrix_rules(self):
        domains = [
            SimpleNamespace(classification="Elevated", triggered_indicators=["ownership_clarity"]),
            SimpleNamespace(classification="Watch", triggered_indicators=["ownership_clarity"]),
            SimpleNamespace(classification="Elevated", triggered_indicators=["drift_conditions"]),
        ]
        self.assertEqual(
            _cross_domain_compounding_note(domains=domains, lang="en"),
            "Similar structural patterns appear across multiple domains. Addressing ownership clarity and review cadence in one area may support broader system stability.",
        )
        self.assertEqual(
            _elevated_global_note(elevated_domain_count=3, lang="en"),
            "Multiple domains demonstrate elevated structural complexity based on reported inputs. This does not predict outcomes but suggests benefit from structured review.",
        )
        self.assertEqual(
            _safeguard_statement(elevated_domain_count=1, lang="en"),
            "Classification reflects structural configuration based solely on self-reported information. It does not evaluate medical or safety compliance and does not predict harm.",
        )

    def test_matrix_interpretation_templates_avoid_prohibited_language(self):
        prohibited_terms = [
            "high risk",
            "dangerous",
            "unsafe",
            "predictive",
            "likely to cause",
            "prevents",
            "reduces",
            "improves outcomes",
            "clinical risk",
        ]
        corpus = " ".join(
            [
                _domain_interpretation_text(
                    config=default_base_config(),
                    domain_id="overnight_sleep_routines",
                    report_language="en",
                    classification="Watch",
                    confidence_marker="Moderate Confidence",
                    triggered_indicators=["review_cadence"],
                    indicator_count=1,
                    consideration_count=1,
                ),
                _domain_interpretation_text(
                    config=default_base_config(),
                    domain_id="overnight_sleep_routines",
                    report_language="en",
                    classification="Elevated",
                    confidence_marker="High Confidence",
                    triggered_indicators=["structural_complexity_exposure"],
                    indicator_count=2,
                    consideration_count=2,
                    domain_index=1,
                ),
                _cross_domain_compounding_note(
                    domains=[SimpleNamespace(classification="Watch", triggered_indicators=["drift_conditions"])] * 2,
                    lang="en",
                ),
                _elevated_global_note(elevated_domain_count=3, lang="en"),
                _safeguard_statement(elevated_domain_count=1, lang="en"),
            ]
        ).lower()
        for term in prohibited_terms:
            self.assertNotIn(term, corpus)


class SriAggregationTests(TestCase):
    def _baseline_answers(self) -> dict[str, str]:
        config = default_base_config()
        answers: dict[str, str] = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        return answers

    def _outputs_for_answers(self, answers: dict[str, str]) -> dict:
        config = default_base_config()
        result = evaluate(config, answers)
        return {
            "classification": result.classification,
            "tags": result.tags,
            "patterns": result.patterns,
            "section_classifications": result.section_classifications,
            "domain_classifications": result.domain_classifications,
            "indicators_by_domain": result.indicators_by_domain,
            "indicator_signals_by_domain": result.indicator_signals_by_domain,
            "cross_domain_flags": result.cross_domain_flags,
            "structural_considerations": result.structural_considerations,
            "output_language": "en",
        }

    def test_aggregate_output_includes_sri_compatible_keys(self):
        inst = InspectionInstance.objects.create(
            kind=InspectionInstance.KIND_CAMPAIGN,
            organization_id="org-1",
            name="Aggregate test campaign",
        )
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )

        # Cleared submission
        link1 = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)
        Submission.objects.create(
            recipient_link=link1,
            config_version=cfg,
            answers=self._baseline_answers(),
            outputs=self._outputs_for_answers(self._baseline_answers()),
        )

        # Cross-domain elevated submission to produce flags/signals.
        answers2 = self._baseline_answers()
        answers2["overnight_final_decision_authority"] = "shared_without_final_authority"
        answers2["overnight_routine_variability"] = "occasionally"
        answers2["overnight_review_date_set"] = "informal_plan"
        answers2["transport_equipment_installer_clarity"] = "multiple_individuals"
        answers2["transport_configuration_change_frequency"] = "occasionally"
        answers2["transport_configuration_authority"] = "shared_authority"
        answers2["home_supply_storage_distribution"] = "two_areas"
        answers2["home_nighttime_room_movement_frequency"] = "sometimes"
        answers2["home_setup_change_difficulty"] = "moderate_effort"
        link2 = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)
        Submission.objects.create(
            recipient_link=link2,
            config_version=cfg,
            answers=answers2,
            outputs=self._outputs_for_answers(answers2),
        )

        counts = aggregate_instance(inst)
        self.assertIn("cross_domain_flag_counts", counts)
        self.assertIn("indicator_counts_by_domain", counts)
        self.assertIn("indicator_signal_totals_by_domain", counts)
        self.assertIn("multi_domain_structural_exposure", counts["cross_domain_flag_counts"])
        self.assertIn("overnight_sleep_routines", counts["indicator_counts_by_domain"])
        self.assertIn("home_layout_environmental_access", counts["indicator_signal_totals_by_domain"])

    def test_aggregate_output_ordering_is_deterministic(self):
        inst = InspectionInstance.objects.create(
            kind=InspectionInstance.KIND_CAMPAIGN,
            organization_id="org-1",
            name="Deterministic aggregate campaign",
        )
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )

        answers = self._baseline_answers()
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"

        for _ in range(2):
            link = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)
            Submission.objects.create(
                recipient_link=link,
                config_version=cfg,
                answers=answers,
                outputs=self._outputs_for_answers(answers),
            )

        counts_a = aggregate_instance(inst)
        counts_b = aggregate_instance(inst)
        self.assertEqual(counts_a, counts_b)


class SriMultilingualContentTests(TestCase):
    def _baseline_answers(self) -> dict[str, str]:
        config = default_base_config()
        answers: dict[str, str] = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        return answers

    def test_default_config_exposes_en_and_es_languages(self):
        config = default_base_config()
        output = config.get("output", {})
        self.assertEqual(output.get("default_language"), "en")
        self.assertIn("en", output.get("languages", []))
        self.assertIn("es", output.get("languages", []))

    def test_localize_schema_to_spanish_and_fallback(self):
        config = default_base_config()
        schema = config["schema"]

        es_schema = localize_schema(
            schema=schema,
            config=config,
            lang="es",
            default_lang="en",
        )
        self.assertEqual(
            es_schema["sections"][0]["title"],
            "Cobertura nocturna y rutinas de sueño",
        )
        self.assertEqual(
            es_schema["sections"][0]["fields"][0]["label"],
            "¿Cuántas personas adultas pueden responder por la noche si el bebé se despierta?",
        )

        fr_fallback = localize_schema(
            schema=schema,
            config=config,
            lang="fr",
            default_lang="en",
        )
        self.assertEqual(
            fr_fallback["sections"][0]["title"],
            "Overnight Coverage & Sleep Routines",
        )

    def test_language_resolution_and_consideration_text_fallback(self):
        selected = resolve_language(
            requested_lang="es",
            allowed_languages=["en", "es"],
            default_language="en",
        )
        self.assertEqual(selected, "es")
        selected_unknown = resolve_language(
            requested_lang="fr",
            allowed_languages=["en", "es"],
            default_language="en",
        )
        self.assertEqual(selected_unknown, "en")

        config = default_base_config()
        answers = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        # Trigger at least one consideration-bearing watch/elevated domain.
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"

        result_es = evaluate(config, answers, content_language="es", default_language="en")
        items = result_es.structural_considerations.get("overnight_sleep_routines", [])
        self.assertGreaterEqual(len(items), 1)
        for item in items:
            self.assertTrue(isinstance(item.get("text"), str) and item.get("text"))

    def test_canonical_consideration_libraries_are_used_for_all_languages_and_severities(self):
        config = default_base_config()

        # English Watch sample
        answers_en_watch = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers_en_watch[field["id"]] = field["options"][0]["value"]
        answers_en_watch["overnight_routine_variability"] = "occasionally"
        answers_en_watch["overnight_review_date_set"] = "informal_plan"
        result_en_watch = evaluate(config, answers_en_watch, content_language="en", default_language="en")
        en_items = result_en_watch.structural_considerations.get("overnight_sleep_routines", [])
        self.assertGreaterEqual(len(en_items), 2)
        self.assertEqual(
            en_items[0]["text"],
            "Some caregivers periodically review how sleep routines change under fatigue so expectations remain aligned across caregivers.",
        )
        self.assertEqual(
            en_items[1]["text"],
            "Some households set informal check-in points to revisit overnight routines as infant sleep patterns evolve.",
        )

        # Spanish Watch sample
        result_es_watch = evaluate(config, answers_en_watch, content_language="es", default_language="en")
        es_watch_items = result_es_watch.structural_considerations.get("overnight_sleep_routines", [])
        self.assertGreaterEqual(len(es_watch_items), 2)
        self.assertEqual(
            es_watch_items[0]["text"],
            "Algunos cuidadores revisan ocasionalmente cómo cambian las rutinas de sueño cuando hay cansancio, para mantener las expectativas alineadas entre quienes cuidan al bebé.",
        )
        self.assertEqual(
            es_watch_items[1]["text"],
            "En algunos hogares se establecen puntos informales de revisión para conversar nuevamente sobre las rutinas nocturnas a medida que cambian los patrones de sueño del bebé.",
        )

        # English Elevated sample
        answers_en_elevated = dict(answers_en_watch)
        answers_en_elevated["overnight_final_decision_authority"] = "shared_without_final_authority"
        result_en_elevated = evaluate(
            config,
            answers_en_elevated,
            content_language="en",
            default_language="en",
        )
        en_elevated_items = result_en_elevated.structural_considerations.get("overnight_sleep_routines", [])
        self.assertGreaterEqual(len(en_elevated_items), 2)
        self.assertEqual(
            en_elevated_items[0]["text"],
            "When overnight decisions do not have a clearly identified final authority, some caregivers establish a simple escalation rule so routine changes remain consistent.",
        )
        self.assertEqual(
            en_elevated_items[1]["text"],
            "When sleep routines are expected to vary frequently, some households periodically review the overnight approach so expectations remain coordinated.",
        )

        # Spanish Elevated sample
        answers_es_elevated = dict(answers_en_watch)
        answers_es_elevated["overnight_final_decision_authority"] = "shared_without_final_authority"
        result_es_elevated = evaluate(config, answers_es_elevated, content_language="es", default_language="en")
        elevated_items = result_es_elevated.structural_considerations.get("overnight_sleep_routines", [])
        self.assertGreaterEqual(len(elevated_items), 2)
        self.assertEqual(
            elevated_items[0]["text"],
            "Cuando no existe una autoridad final claramente identificada para decisiones nocturnas, algunos cuidadores establecen una regla sencilla de decisión final para mantener consistencia en las rutinas.",
        )
        self.assertEqual(
            elevated_items[1]["text"],
            "Cuando se espera que las rutinas de sueño cambien con frecuencia, algunas familias revisan periódicamente el enfoque nocturno para mantener las expectativas coordinadas.",
        )

    def test_english_elevated_does_not_fallback_to_spanish_override(self):
        config = default_base_config()
        answers = {}
        for section in config["schema"]["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        # Overnight domain elevated triggers
        answers["overnight_final_decision_authority"] = "shared_without_final_authority"
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"

        result = evaluate(config, answers, content_language="en", default_language="en")
        items = result.structural_considerations.get("overnight_sleep_routines", [])
        self.assertGreaterEqual(len(items), 2)
        # Should come from existing English elevated baseline copy, not Spanish override text.
        self.assertEqual(
            items[0]["text"],
            "When overnight decisions do not have a clearly identified final authority, some caregivers establish a simple escalation rule so routine changes remain consistent.",
        )
        self.assertEqual(
            items[1]["text"],
            "When sleep routines are expected to vary frequently, some households periodically review the overnight approach so expectations remain coordinated.",
        )

    def test_canonical_considerations_have_complete_q1_to_q20_language_severity_mapping(self):
        by_question = build_canonical_considerations_by_question()
        self.assertEqual(len(by_question), 20)

        config = default_base_config()
        expected_question_ids = {
            field["id"]
            for section in config["schema"]["sections"]
            for field in section["fields"]
            if field.get("meta", {}).get("sri_question_number") in range(1, 21)
        }
        self.assertEqual(set(by_question.keys()), expected_question_ids)

        for qid in expected_question_ids:
            entry = by_question[qid]
            self.assertIn("watch", entry)
            self.assertIn("elevated", entry)
            for severity in ("watch", "elevated"):
                self.assertIn("en", entry[severity])
                self.assertIn("es", entry[severity])
                self.assertTrue(isinstance(entry[severity]["en"], str) and entry[severity]["en"])
                self.assertTrue(isinstance(entry[severity]["es"], str) and entry[severity]["es"])

    def test_get_form_fields_respects_selected_language_and_fallback(self):
        inst = InspectionInstance.objects.create(name="Lang API test")
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )
        link = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)

        es_resp = self.client.get(
            f"/api/public/inspections/{inst.id}/links/{link.id}/",
            {"lang": "es"},
        )
        self.assertEqual(es_resp.status_code, 200)
        es_data = es_resp.json()
        self.assertEqual(es_data["selected_content_language"], "es")
        self.assertEqual(
            es_data["schema"]["sections"][0]["title"],
            "Cobertura nocturna y rutinas de sueño",
        )

        fr_resp = self.client.get(
            f"/api/public/inspections/{inst.id}/links/{link.id}/",
            {"lang": "fr"},
        )
        self.assertEqual(fr_resp.status_code, 200)
        fr_data = fr_resp.json()
        self.assertEqual(fr_data["selected_content_language"], "en")
        self.assertEqual(
            fr_data["schema"]["sections"][0]["title"],
            "Overnight Coverage & Sleep Routines",
        )

    def test_report_data_and_pdf_follow_submission_language_spanish(self):
        config = default_base_config()
        schema = config["schema"]
        answers = self._baseline_answers()
        answers["overnight_routine_variability"] = "occasionally"
        answers["overnight_review_date_set"] = "informal_plan"
        result = evaluate(config, answers, content_language="es", default_language="en")
        outputs = {
            "classification": result.classification,
            "domain_classifications": result.domain_classifications,
            "section_classifications": result.section_classifications,
            "indicators_by_domain": result.indicators_by_domain,
            "indicator_signals_by_domain": result.indicator_signals_by_domain,
            "cross_domain_flags": result.cross_domain_flags,
            "structural_considerations": result.structural_considerations,
            "output_language": "es",
        }

        report = assemble_single_submission_sri_report_data(
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config=config,
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        self.assertEqual(report.output_language, "es")
        self.assertIn("Cobertura nocturna", report.domains[0].domain_title)
        self.assertNotEqual(
            report.methodology_scope["methodology"],
            "Configuration-driven SRI deterministic indicator evaluation.",
        )

        pdf_bytes = generate_single_submission_pdf(
            config=config,
            schema=schema,
            outputs=outputs,
            output_language="es",
            report_data=report,
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_report_text_uses_spanish_default_when_spanish_override_missing(self):
        config = default_base_config()
        config["output"]["report"]["methodology"] = {"en": "English fallback methodology only."}
        schema = config["schema"]
        answers = self._baseline_answers()
        result = evaluate(config, answers, content_language="es", default_language="en")
        outputs = {
            "classification": result.classification,
            "domain_classifications": result.domain_classifications,
            "section_classifications": result.section_classifications,
            "indicators_by_domain": result.indicators_by_domain,
            "indicator_signals_by_domain": result.indicator_signals_by_domain,
            "cross_domain_flags": result.cross_domain_flags,
            "structural_considerations": result.structural_considerations,
            "output_language": "es",
        }
        report = assemble_single_submission_sri_report_data(
            config=config,
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            schema=schema,
            outputs=outputs,
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        self.assertEqual(
            report.methodology_scope["methodology"],
            "Evaluacion deterministica de indicadores SRI guiada por configuracion.",
        )


class OrganizationBrandingTests(TestCase):
    def test_get_form_fields_returns_organization_branding(self):
        inst = InspectionInstance.objects.create(
            kind=InspectionInstance.KIND_CAMPAIGN,
            name="NICU Program Intake",
            organization_id="org-hospital-001",
        )
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )
        OrganizationBranding.objects.create(
            organization_id="org-hospital-001",
            hospital_program_name="Starlight Children's Hospital",
            primary_color="#0F4C81",
            tagline="Family-centered neonatal transition program",
            footer_text="Confidential hospital program document.",
        )
        link = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)

        resp = self.client.get(f"/api/public/inspections/{inst.id}/links/{link.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("branding", data)
        self.assertEqual(data["branding"]["organization_id"], "org-hospital-001")
        self.assertEqual(data["branding"]["hospital_program_name"], "Starlight Children's Hospital")
        self.assertEqual(data["branding"]["primary_color"], "#0F4C81")
        self.assertEqual(data["branding"]["tagline"], "Family-centered neonatal transition program")
        self.assertEqual(data["branding"]["footer_text"], "Confidential hospital program document.")
        self.assertIsNone(data["branding"]["logo_url"])

    def test_get_form_fields_branding_fallback_without_org_brand(self):
        inst = InspectionInstance.objects.create(
            kind=InspectionInstance.KIND_CAMPAIGN,
            name="General Pediatric Program",
            organization_id="org-without-branding",
        )
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )
        link = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)

        resp = self.client.get(f"/api/public/inspections/{inst.id}/links/{link.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("branding", data)
        self.assertEqual(data["branding"]["organization_id"], "org-without-branding")
        self.assertEqual(data["branding"]["hospital_program_name"], "General Pediatric Program")
        self.assertEqual(data["branding"]["primary_color"], "#1F2937")
        self.assertEqual(data["branding"]["tagline"], "")
        self.assertEqual(data["branding"]["footer_text"], DEFAULT_PUBLIC_FOOTER_TEXT)
        self.assertIsNone(data["branding"]["logo_url"])

    def test_get_form_fields_public_branding_defaults_without_organization(self):
        inst = InspectionInstance.objects.create(name="", organization_id="")
        cfg = InspectionConfigVersion.objects.create(
            inspection_instance=inst,
            config=default_base_config(),
            status=InspectionConfigVersion.STATUS_PUBLISHED,
        )
        link = RecipientLink.objects.create(inspection_instance=inst, config_version=cfg)

        resp = self.client.get(f"/api/public/inspections/{inst.id}/links/{link.id}/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        self.assertIn("branding", data)
        self.assertEqual(data["branding"]["hospital_program_name"], DEFAULT_PUBLIC_PROGRAM_NAME)
        self.assertEqual(data["branding"]["footer_text"], DEFAULT_PUBLIC_FOOTER_TEXT)
        self.assertNotIn("Children", data["branding"]["hospital_program_name"])
        self.assertNotIn("Powered by No Regret LLC", data["branding"]["footer_text"])

    def test_single_submission_pdf_accepts_branding_payload(self):
        config = default_base_config()
        schema = config["schema"]
        answers = {}
        for section in schema["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        result = evaluate(config, answers)
        outputs = {
            "classification": result.classification,
            "domain_classifications": result.domain_classifications,
            "section_classifications": result.section_classifications,
            "indicators_by_domain": result.indicators_by_domain,
            "indicator_signals_by_domain": result.indicator_signals_by_domain,
            "cross_domain_flags": result.cross_domain_flags,
            "structural_considerations": result.structural_considerations,
            "output_language": "en",
        }
        pdf_bytes = generate_single_submission_pdf(
            config=config,
            schema=schema,
            outputs=outputs,
            branding={
                "organization_id": "org-1",
                "hospital_program_name": "Starlight Children's Hospital",
                "logo_path": None,
                "primary_color": "#0F4C81",
                "tagline": "Family-centered program",
                "footer_text": "Confidential hospital program document.",
            },
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    def test_single_submission_pdf_public_footer_fallback(self):
        config = default_base_config()
        schema = config["schema"]
        answers = {}
        for section in schema["sections"]:
            for field in section["fields"]:
                answers[field["id"]] = field["options"][0]["value"]
        result = evaluate(config, answers)
        outputs = {
            "classification": result.classification,
            "domain_classifications": result.domain_classifications,
            "section_classifications": result.section_classifications,
            "indicators_by_domain": result.indicators_by_domain,
            "indicator_signals_by_domain": result.indicator_signals_by_domain,
            "cross_domain_flags": result.cross_domain_flags,
            "structural_considerations": result.structural_considerations,
            "output_language": "en",
        }
        self.assertEqual(_DEFAULT_REPORT_FOOTER, DEFAULT_PUBLIC_FOOTER_TEXT)
        pdf_bytes = generate_single_submission_pdf(
            config=config,
            schema=schema,
            outputs=outputs,
            branding={"hospital_program_name": "SRI Program", "footer_text": ""},
            inspection_id="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
            config_version_id="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))
        # Streams are typically compressed; assert legacy credit is not embedded in raw bytes.
        self.assertNotIn(b"Powered by No Regret LLC", pdf_bytes)


class PresentationLabelMappingTests(TestCase):
    def test_domain_indicator_flag_pattern_and_language_labels_are_human_readable(self):
        config = default_base_config()
        schema = config["schema"]

        self.assertEqual(
            domain_label(
                "overnight_sleep_routines",
                config=config,
                schema=schema,
                lang="en",
            ),
            "Overnight Coverage & Sleep Routines",
        )
        self.assertEqual(
            indicator_label(
                "indicator:feeding_daytime_care:review_cadence",
                config=config,
                schema=schema,
                lang="en",
            ),
            "Feeding & Daytime Care Coordination - Review Cadence",
        )
        self.assertEqual(
            flag_label("multi_domain_structural_exposure", lang="en"),
            "Multiple domains show elevated structural complexity",
        )
        self.assertEqual(
            pattern_label("q03_occasional_variability", lang="en"),
            "Occasional Variability",
        )
        self.assertEqual(language_label("en", lang="en"), "English")

    def test_unmapped_values_fall_back_to_humanized_labels(self):
        config = default_base_config()
        schema = config["schema"]

        self.assertEqual(
            domain_label("unmapped_domain_name", config=config, schema=schema, lang="en"),
            "Unmapped Domain Name",
        )
        self.assertEqual(
            indicator_label(
                "custom_indicator_value",
                config=config,
                schema=schema,
                lang="en",
            ),
            "Custom Indicator Value",
        )
        self.assertEqual(flag_label("custom_cross_flag", lang="en"), "Custom Cross Flag")
        self.assertEqual(pattern_label("custom_pattern_value", lang="en"), "Custom Pattern Value")
        self.assertEqual(language_label("pt_br", lang="en"), "Pt Br")

    def test_aggregated_pdf_mapping_helpers_keep_admin_labels_readable(self):
        config = default_base_config()
        schema = config["schema"]

        self.assertEqual(
            tag_label(
                "indicator:feeding_daytime_care:review_cadence",
                config=config,
                schema=schema,
                lang="en",
            ),
            "Feeding & Daytime Care Coordination - Review Cadence",
        )

        pdf_bytes = generate_aggregated_pdf(
            config=config,
            schema=schema,
            counts={
                "by_classification": {"Cleared": 1, "Watch": 2, "Elevated": 3},
                "by_section": {},
                "tag_counts": {"indicator:feeding_daytime_care:review_cadence": 2},
                "top_patterns": [{"pattern": "q03_occasional_variability", "count": 1}],
                "cross_domain_flag_counts": {"multi_domain_structural_exposure": 3},
                "indicator_signal_totals_by_domain": {},
            },
            output_language="en",
        )
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))


class AdminWorkflowSafetyTests(TestCase):
    def test_inactive_question_is_not_required_and_not_returned(self):
        config = default_base_config()
        schema = config["schema"]
        first_field = schema["sections"][0]["fields"][0]
        first_field["required"] = True
        first_field.setdefault("meta", {})["active"] = False
        first_field["help_text"] = {
            "en": "Internal helper",
            "es": "Texto de ayuda",
        }
        field_id = first_field["id"]

        answers = {}
        for section in schema["sections"]:
            for field in section["fields"]:
                meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
                if meta.get("active") is False:
                    continue
                answers[field["id"]] = field["options"][0]["value"]

        validate_answers(config, answers)

        localized = localize_schema(
            schema=schema,
            config=config,
            lang="en",
            default_lang="en",
        )
        ids = []
        for section in localized["sections"]:
            for field in section["fields"]:
                ids.append(field["id"])
        self.assertNotIn(field_id, ids)
