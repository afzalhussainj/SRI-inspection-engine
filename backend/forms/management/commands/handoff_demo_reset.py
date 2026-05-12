"""
Reset local demo DB to a minimal branded pilot dataset and export sample PDFs
(EN/ES parent summaries and EN/ES aggregated operational reports).

Destructive: deletes all inspection data except the seeded SRI baseline template rows.

Usage:
  backend/.venv/bin/python manage.py handoff_demo_reset --execute
"""

from __future__ import annotations

import copy
import shutil
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from forms.aggregation import run_aggregation
from forms.branding import resolve_branding_for_instance
from forms.engine import evaluate, validate_answers
from forms.models import (
    AggregatedReport,
    InspectionConfigVersion,
    InspectionInstance,
    OrganizationBranding,
    RecipientLink,
    Submission,
    default_base_config,
)
from forms.pdf import generate_aggregated_pdf, generate_single_submission_pdf
from forms.report_data import assemble_single_submission_sri_report_data
from forms.sri_baseline import SRI_BASELINE_CONFIG_VERSION_ID, SRI_BASELINE_INSTANCE_ID


DEMO_ORG_ID = "regional-transition-network"
FIXTURE_LOGO = Path(__file__).resolve().parents[2] / "fixtures" / "demo_branding_logo.png"


def _outputs_from_result(result, output_language: str) -> dict:
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
        "output_language": output_language,
    }


def _baseline_answers(config: dict) -> dict[str, str]:
    answers: dict[str, str] = {}
    for section in config["schema"]["sections"]:
        for field in section["fields"]:
            meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
            if meta.get("active") is False:
                continue
            answers[field["id"]] = field["options"][0]["value"]
    return answers


class Command(BaseCommand):
    help = (
        "Remove non-baseline inspection rows, seed a minimal branded pilot campaign, "
        "and write English/Spanish parent PDFs plus English/Spanish aggregated PDFs to docs/artifacts/sample-reports/."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Perform destructive DB changes and write files (default is dry-run).",
        )

    def handle(self, *args, **options):
        if not options["execute"]:
            raise CommandError(
                "Dry-run only. Re-run with --execute to reset the database and export PDFs. "
                "This deletes all inspection instances except the SRI baseline template."
            )

        if not settings.DEBUG and not getattr(settings, "HANDOFF_DEMO_RESET_ALLOWED", False):
            raise CommandError(
                "Refusing to run with DEBUG=False unless settings.HANDOFF_DEMO_RESET_ALLOWED=True."
            )

        if not FIXTURE_LOGO.is_file():
            raise CommandError(f"Missing logo fixture at {FIXTURE_LOGO}")

        media_root = Path(settings.MEDIA_ROOT)
        for sub in ("branding/logos", "pdfs/submissions", "pdfs/aggregated"):
            p = media_root / sub
            if p.exists():
                shutil.rmtree(p, ignore_errors=True)

        self.stdout.write("Clearing non-baseline inspection data and branding…")
        AggregatedReport.objects.all().delete()
        OrganizationBranding.objects.all().delete()
        # RecipientLink PROTECTs config versions; remove links (and submissions) before instances.
        RecipientLink.objects.all().delete()
        InspectionConfigVersion.objects.filter(inspection_instance_id=SRI_BASELINE_INSTANCE_ID).exclude(
            pk=SRI_BASELINE_CONFIG_VERSION_ID
        ).delete()
        InspectionInstance.objects.exclude(pk=SRI_BASELINE_INSTANCE_ID).delete()

        baseline_cfg = InspectionConfigVersion.objects.get(pk=SRI_BASELINE_CONFIG_VERSION_ID)
        config_copy = copy.deepcopy(baseline_cfg.config)
        # Baseline rows in the DB may have been edited in admin (e.g. English-only output.copy).
        # For the pilot seed, always attach the canonical bilingual `output` block from code so the
        # public form exposes both EN/ES and questionnaire i18n matches the engine.
        canonical = default_base_config()
        if isinstance(canonical.get("output"), dict):
            config_copy["output"] = copy.deepcopy(canonical["output"])

        with FIXTURE_LOGO.open("rb") as lf:
            OrganizationBranding.objects.create(
                organization_id=DEMO_ORG_ID,
                hospital_program_name="SRI Program",
                logo=File(lf, name="demo_branding_logo.png"),
                primary_color="#0F4C81",
                tagline="Family-centered transition support",
                footer_text="Structured Risk Inspection Technology",
            )

        demo = InspectionInstance.objects.create(
            kind=InspectionInstance.KIND_CAMPAIGN,
            organization_id=DEMO_ORG_ID,
            name="Regional transitions — parent and aggregate pilot",
            base_template_id=SRI_BASELINE_INSTANCE_ID,
        )

        cv = InspectionConfigVersion.objects.create(
            inspection_instance=demo,
            config=config_copy,
        )
        cv.publish()
        cv.save()

        answers = _baseline_answers(cv.config)
        validate_answers(cv.config, answers)
        default_lang = (
            cv.config.get("output", {}).get("default_language")
            if isinstance(cv.config.get("output"), dict)
            else None
        )
        if not isinstance(default_lang, str) or not default_lang:
            default_lang = "en"

        result_en = evaluate(cv.config, answers, content_language="en", default_language=default_lang)
        result_es = evaluate(cv.config, answers, content_language="es", default_language=default_lang)

        link_en = RecipientLink.objects.create(inspection_instance=demo, config_version=cv)
        link_es = RecipientLink.objects.create(inspection_instance=demo, config_version=cv)

        Submission.objects.create(
            recipient_link=link_en,
            config_version=cv,
            answers=answers,
            outputs=_outputs_from_result(result_en, "en"),
        )
        link_en.status = RecipientLink.STATUS_SUBMITTED
        link_en.submitted_at = timezone.now()
        link_en.save()

        Submission.objects.create(
            recipient_link=link_es,
            config_version=cv,
            answers=answers,
            outputs=_outputs_from_result(result_es, "es"),
        )
        link_es.status = RecipientLink.STATUS_SUBMITTED
        link_es.submitted_at = timezone.now()
        link_es.save()

        run_aggregation(demo)

        branding = resolve_branding_for_instance(demo)
        sub_en = Submission.objects.get(recipient_link=link_en)
        sub_es = Submission.objects.get(recipient_link=link_es)

        sample_dir = Path(settings.BASE_DIR.parent) / "docs" / "artifacts" / "sample-reports"
        sample_dir.mkdir(parents=True, exist_ok=True)

        def write_parent_pdf(sub: Submission, path: Path, lang_label: str) -> None:
            cfg = sub.config_version
            config = cfg.config if isinstance(cfg.config, dict) else {}
            schema = config.get("schema") if isinstance(config.get("schema"), dict) else config
            outputs = sub.outputs if isinstance(sub.outputs, dict) else {}
            selected = outputs.get("output_language") if isinstance(outputs.get("output_language"), str) else None
            report_data = assemble_single_submission_sri_report_data(
                inspection_id=str(demo.id),
                config=config,
                schema=schema,
                outputs=outputs,
                completion_dt=sub.created_at,
                config_version_id=str(cfg.id),
            )
            pdf_bytes = generate_single_submission_pdf(
                config=config,
                schema=schema,
                outputs=outputs,
                output_language=selected,
                report_data=report_data,
                inspection_id=str(demo.id),
                completion_dt=sub.created_at,
                config_version_id=str(cfg.id),
                branding=branding,
            )
            path.write_bytes(pdf_bytes)
            self.stdout.write(self.style.SUCCESS(f"Wrote {lang_label}: {path}"))

        write_parent_pdf(sub_en, sample_dir / "sample-parent-report-en.pdf", "English parent PDF")
        write_parent_pdf(sub_es, sample_dir / "sample-parent-report-es.pdf", "Spanish parent PDF")

        from forms.aggregation import aggregate_instance

        counts = aggregate_instance(demo)
        agg_en = generate_aggregated_pdf(
            config=cv.config,
            schema=cv.config.get("schema") if isinstance(cv.config.get("schema"), dict) else cv.config,
            counts=counts,
            output_language="en",
            inspection_id=str(demo.id),
            config_version_id=str(cv.id),
            branding=branding,
        )
        (sample_dir / "sample-aggregated-report-en.pdf").write_bytes(agg_en)
        self.stdout.write(self.style.SUCCESS(f"Wrote aggregated (EN): {sample_dir / 'sample-aggregated-report-en.pdf'}"))
        agg_es = generate_aggregated_pdf(
            config=cv.config,
            schema=cv.config.get("schema") if isinstance(cv.config.get("schema"), dict) else cv.config,
            counts=counts,
            output_language="es",
            inspection_id=str(demo.id),
            config_version_id=str(cv.id),
            branding=branding,
        )
        (sample_dir / "sample-aggregated-report-es.pdf").write_bytes(agg_es)
        self.stdout.write(self.style.SUCCESS(f"Wrote aggregated (ES): {sample_dir / 'sample-aggregated-report-es.pdf'}"))

        self.stdout.write(self.style.SUCCESS("Demo reset complete."))
