import json
from django.contrib import admin
from django import forms
from django.conf import settings
from django.utils.html import format_html
from django.urls import path
from django.http import Http404, FileResponse
from django.utils import timezone
from django.core.exceptions import ValidationError
from io import BytesIO

from .branding import resolve_branding_for_instance
from .engine import evaluate
from .models import (
    AggregatedReport,
    InspectionConfigVersion,
    InspectionInstance,
    OrganizationBranding,
    RecipientLink,
    Submission,
)
from .sri_baseline import SRI_BASELINE_CONFIG_VERSION_ID, SRI_BASELINE_INSTANCE_ID
from .pdf import build_parent_display_ids, generate_single_submission_pdf
from .report_data import assemble_single_submission_sri_report_data


class InspectionConfigVersionInline(admin.TabularInline):
    model = InspectionConfigVersion
    extra = 0
    fields = ("id", "status", "published_at", "created_at")
    readonly_fields = ("id", "published_at", "created_at")
    show_change_link = True


class RecipientLinkInline(admin.TabularInline):
    model = RecipientLink
    extra = 0
    fields = ("id", "status", "expires_at", "created_at", "public_url")
    # `id` is a non-editable UUIDField, so it must be readonly in admin forms.
    readonly_fields = ("id", "created_at", "public_url")
    show_change_link = True

    @admin.display(description="Public URL")
    def public_url(self, obj: RecipientLink) -> str:
        url = f"{settings.FRONTEND_BASE_URL}{obj.public_path}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)


@admin.register(InspectionInstance)
class InspectionInstanceAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "name", "organization_id", "created_at", "closes_at", "submission_threshold")
    search_fields = ("id", "organization_id", "name")
    list_filter = ("kind", "closes_at", "created_at")
    ordering = ("-created_at",)
    inlines = [InspectionConfigVersionInline, RecipientLinkInline]
    actions = ["clone_as_template", "clone_as_campaign", "generate_aggregated_pdf_now"]

    def _latest_config(self, instance: InspectionInstance) -> InspectionConfigVersion | None:
        return (
            instance.config_versions.order_by("-published_at", "-created_at").first()
        )

    def clone_as_template(self, request, queryset):
        created = 0
        for src in queryset:
            base_cfg = self._latest_config(src)
            clone = InspectionInstance.objects.create(
                kind=InspectionInstance.KIND_TEMPLATE,
                name=f"{src.name or 'Template'} (copy)",
                organization_id="",
                base_template=src if src.kind == InspectionInstance.KIND_TEMPLATE else None,
            )
            InspectionConfigVersion.objects.create(
                inspection_instance=clone,
                config=(base_cfg.config if base_cfg else {}),
            )
            created += 1
        self.message_user(request, f"Created {created} new template(s).")

    clone_as_template.short_description = "Clone selected as new template(s)"

    def clone_as_campaign(self, request, queryset):
        created = 0
        for src in queryset:
            base_cfg = self._latest_config(src)
            clone = InspectionInstance.objects.create(
                kind=InspectionInstance.KIND_CAMPAIGN,
                name=f"{src.name or 'Campaign'} (new)",
                organization_id="",
                base_template=src if src.kind == InspectionInstance.KIND_TEMPLATE else src.base_template,
                closes_at=None,
            )
            InspectionConfigVersion.objects.create(
                inspection_instance=clone,
                config=(base_cfg.config if base_cfg else {}),
            )
            created += 1
        self.message_user(request, f"Created {created} new campaign(s).")

    clone_as_campaign.short_description = "Create campaign(s) from selected template(s)"

    def generate_aggregated_pdf_now(self, request, queryset):
        from .aggregation import run_aggregation

        created = 0
        skipped = 0
        for inst in queryset:
            if inst.kind != InspectionInstance.KIND_CAMPAIGN:
                skipped += 1
                continue
            run_aggregation(inst)
            created += 1
        self.message_user(request, f"Updated aggregation counts for {created} campaign(s). Skipped {skipped}.")

    generate_aggregated_pdf_now.short_description = "Generate aggregated PDF now (campaigns only)"

    def has_delete_permission(self, request, obj=None) -> bool:
        if obj is not None and obj.pk == SRI_BASELINE_INSTANCE_ID:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(InspectionConfigVersion)
class InspectionConfigVersionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "inspection_instance",
        "status",
        "question_count",
        "active_question_count",
        "published_at",
        "created_at",
    )
    search_fields = ("id", "inspection_instance__id")
    list_filter = ("status", "published_at", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "published_at", "config_sha256", "operator_notes", "question_count", "active_question_count")
    actions = [
        "publish_selected",
        "create_recipient_links",
        "clone_as_new_draft",
        "validate_selected_configs",
    ]
    fieldsets = (
        (
            "Version Lifecycle",
            {
                "fields": (
                    "inspection_instance",
                    "status",
                    "published_at",
                    "created_at",
                    "config_sha256",
                )
            },
        ),
        (
            "Safe Operator Guidance",
            {
                "fields": ("operator_notes", "question_count", "active_question_count"),
                "description": (
                    "Edit only draft versions. Published versions are read-only and immutable."
                ),
            },
        ),
        (
            "Config JSON (Draft Editing Zone)",
            {
                "fields": ("config",),
                "description": (
                    "Question wording: schema.sections[].fields[].label and output.questionnaire.fields.<field_id>.<lang>. "
                    "Question help text: schema.sections[].fields[].help_text or output.questionnaire.help_texts.<field_id>.<lang>. "
                    "Active/inactive question workflow: set schema.sections[].fields[].meta.active=false (hidden + not required at runtime)."
                ),
            },
        ),
    )

    class ConfigVersionForm(forms.ModelForm):
        class Meta:
            model = InspectionConfigVersion
            fields = "__all__"
            widgets = {
                "config": forms.Textarea(attrs={"rows": 32, "style": "font-family:monospace;"}),
            }
            help_texts = {
                "config": (
                    "Draft only: edit question labels/help text, active flags, and evaluation config carefully. "
                    "Use Clone as new draft for safe edits."
                )
            }

    form = ConfigVersionForm

    @admin.display(description="Operator notes")
    def operator_notes(self, obj: InspectionConfigVersion | None) -> str:
        _ = obj
        return (
            "SAFE edits: wording/help text translations, question active flags, branding references. "
            "RISKY edits: rule thresholds, option values, removing question IDs referenced by evaluation rules."
        )

    @admin.display(description="Questions")
    def question_count(self, obj: InspectionConfigVersion) -> int:
        schema = obj.config.get("schema") if isinstance(obj.config, dict) and isinstance(obj.config.get("schema"), dict) else {}
        sections = schema.get("sections") if isinstance(schema.get("sections"), list) else []
        count = 0
        for s in sections:
            if isinstance(s, dict) and isinstance(s.get("fields"), list):
                count += len([f for f in s.get("fields", []) if isinstance(f, dict)])
        return count

    @admin.display(description="Active questions")
    def active_question_count(self, obj: InspectionConfigVersion) -> int:
        schema = obj.config.get("schema") if isinstance(obj.config, dict) and isinstance(obj.config.get("schema"), dict) else {}
        sections = schema.get("sections") if isinstance(schema.get("sections"), list) else []
        count = 0
        for s in sections:
            if not isinstance(s, dict) or not isinstance(s.get("fields"), list):
                continue
            for f in s.get("fields", []):
                if not isinstance(f, dict):
                    continue
                meta = f.get("meta") if isinstance(f.get("meta"), dict) else {}
                if meta.get("active") is False:
                    continue
                count += 1
        return count

    def publish_selected(self, request, queryset):
        updated = 0
        for cfg in queryset:
            if cfg.status != InspectionConfigVersion.STATUS_PUBLISHED:
                cfg.publish()
                cfg.save()
                updated += 1
        self.message_user(request, f"Published {updated} config version(s).")

    publish_selected.short_description = "Publish selected config versions"

    def create_recipient_links(self, request, queryset):
        created = 0
        skipped = 0
        last_path = None
        for cfg in queryset.select_related("inspection_instance"):
            if cfg.status != InspectionConfigVersion.STATUS_PUBLISHED:
                skipped += 1
                continue
            link = RecipientLink.objects.create(
                inspection_instance=cfg.inspection_instance,
                config_version=cfg,
                expires_at=cfg.inspection_instance.closes_at,
            )
            created += 1
            last_path = link.public_path

        msg = f"Created {created} recipient link(s)."
        if skipped:
            msg += f" Skipped {skipped} draft config(s) (publish first)."
        if last_path:
            msg += f" Example URL: {settings.FRONTEND_BASE_URL}{last_path}"
        self.message_user(request, msg)

    create_recipient_links.short_description = "Create recipient link(s) for selected config versions"

    def clone_as_new_draft(self, request, queryset):
        created = 0
        for cfg in queryset.select_related("inspection_instance"):
            InspectionConfigVersion.objects.create(
                inspection_instance=cfg.inspection_instance,
                config=json.loads(json.dumps(cfg.config)),
                status=InspectionConfigVersion.STATUS_DRAFT,
            )
            created += 1
        self.message_user(request, f"Created {created} draft clone(s).")

    clone_as_new_draft.short_description = "Clone selected version(s) as new draft"

    def validate_selected_configs(self, request, queryset):
        ok = 0
        failed = 0
        for cfg in queryset:
            try:
                cfg.full_clean()
                ok += 1
            except ValidationError:
                failed += 1
        self.message_user(request, f"Validation complete: {ok} valid, {failed} invalid.")

    validate_selected_configs.short_description = "Validate selected config versions"

    def get_readonly_fields(self, request, obj=None):
        ro = list(super().get_readonly_fields(request, obj))
        if obj and obj.status == InspectionConfigVersion.STATUS_PUBLISHED:
            # Enforce immutability in admin UI as well.
            ro.append("config")
            ro.append("inspection_instance")
            ro.append("status")
        return ro

    def has_delete_permission(self, request, obj=None) -> bool:
        if obj is not None and obj.pk == SRI_BASELINE_CONFIG_VERSION_ID:
            return False
        return super().has_delete_permission(request, obj)


class SubmissionInline(admin.StackedInline):
    model = Submission
    extra = 0
    fields = ("id", "config_version", "answers", "outputs", "created_at")
    readonly_fields = ("id", "config_version", "answers", "outputs", "created_at")
    can_delete = False


@admin.register(RecipientLink)
class RecipientLinkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "inspection_instance",
        "public_url",
        "status",
        "expires_at",
        "opened_at",
        "submitted_at",
        "created_at",
    )
    search_fields = ("id", "inspection_instance__id", "config_version__id")
    list_filter = ("status", "expires_at", "created_at")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "opened_at", "submitted_at", "public_url")
    inlines = [SubmissionInline]
    actions = ["create_test_submission_lowest_signal"]

    @admin.display(description="Public URL")
    def public_url(self, obj: RecipientLink) -> str:
        url = f"{settings.FRONTEND_BASE_URL}{obj.public_path}"
        return format_html('<a href="{}" target="_blank">{}</a>', url, url)

    def create_test_submission_lowest_signal(self, request, queryset):
        created = 0
        skipped = 0
        for link in queryset.select_related("config_version"):
            if link.status == RecipientLink.STATUS_SUBMITTED or hasattr(link, "submission"):
                skipped += 1
                continue
            cfg = link.config_version
            if cfg.status != InspectionConfigVersion.STATUS_PUBLISHED:
                skipped += 1
                continue
            config = cfg.config if isinstance(cfg.config, dict) else {}
            schema = config.get("schema") if isinstance(config.get("schema"), dict) else {}
            answers: dict[str, str] = {}
            for section in schema.get("sections", []) or []:
                if not isinstance(section, dict):
                    continue
                for field in section.get("fields", []) or []:
                    if not isinstance(field, dict):
                        continue
                    meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
                    if meta.get("active") is False:
                        continue
                    fid = field.get("id")
                    if not isinstance(fid, str) or not fid:
                        continue
                    if field.get("type") == "select":
                        options = field.get("options") if isinstance(field.get("options"), list) else []
                        first_opt = options[0] if options and isinstance(options[0], dict) else {}
                        first_val = first_opt.get("value")
                        if isinstance(first_val, str):
                            answers[fid] = first_val
            result = evaluate(config, answers)
            Submission.objects.create(
                recipient_link=link,
                config_version=cfg,
                answers=answers,
                outputs={
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
                },
            )
            link.status = RecipientLink.STATUS_SUBMITTED
            link.submitted_at = timezone.now()
            link.save(update_fields=["status", "submitted_at"])
            created += 1
        self.message_user(request, f"Created {created} test submission(s); skipped {skipped}.")

    create_test_submission_lowest_signal.short_description = "Create test submission(s) (lowest-signal answers)"


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "recipient_link", "config_version", "created_at", "pdf_download")
    search_fields = ("id", "recipient_link__id", "config_version__id")
    list_filter = ("created_at",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "pdf_download")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<uuid:object_id>/pdf/",
                self.admin_site.admin_view(self.download_pdf_view),
                name="forms_submission_pdf",
            )
        ]
        return custom + urls

    def download_pdf_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if not obj:
            raise Http404("Submission not found.")
        link = obj.recipient_link
        cfg = obj.config_version
        config = cfg.config if isinstance(cfg.config, dict) else {}
        schema = config.get("schema") if isinstance(config.get("schema"), dict) else config
        outputs = obj.outputs if isinstance(obj.outputs, dict) else {}
        report_data = assemble_single_submission_sri_report_data(
            inspection_id=str(link.inspection_instance_id),
            config=config,
            schema=schema,
            outputs=outputs,
            completion_dt=obj.created_at,
            config_version_id=str(cfg.id),
        )
        branding = resolve_branding_for_instance(link.inspection_instance)
        selected_lang = outputs.get("output_language") if isinstance(outputs.get("output_language"), str) else None
        pdf_bytes = generate_single_submission_pdf(
            config=config,
            schema=schema,
            outputs=outputs,
            output_language=selected_lang,
            report_data=report_data,
            inspection_id=str(link.inspection_instance_id),
            completion_dt=obj.created_at,
            config_version_id=str(cfg.id),
            branding=branding,
        )
        resp = FileResponse(BytesIO(pdf_bytes), content_type="application/pdf")
        display_id, _ = build_parent_display_ids(
            inspection_id=str(link.inspection_instance_id),
            report_reference=str(cfg.id),
            completion_date=obj.created_at.isoformat() if obj.created_at else "",
        )
        filename = f"{display_id}_StructuredWellbeingRiskSummary.pdf"
        resp["Content-Disposition"] = f'attachment; filename="{filename}"'
        return resp

    @admin.display(description="Submission PDF")
    def pdf_download(self, obj: Submission) -> str:
        if not obj:
            return "-"
        url = f"/admin/forms/submission/{obj.id}/pdf/"
        return format_html('<a href="{}" target="_blank">Download</a>', url)


@admin.register(AggregatedReport)
class AggregatedReportAdmin(admin.ModelAdmin):
    list_display = ("id", "inspection_instance", "generated_at","pdf_download")
    search_fields = ("id", "inspection_instance__id")
    readonly_fields = ("generated_at", "pdf_sha256", "pdf_download")

    def has_add_permission(self, request) -> bool:
        # Aggregated reports are generated by the system (admin action / admin process),
        # not manually created.
        return False

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<uuid:object_id>/pdf/",
                self.admin_site.admin_view(self.download_pdf_view),
                name="forms_aggregatedreport_pdf",
            )
        ]
        return custom + urls

    def download_pdf_view(self, request, object_id):
        obj = self.get_object(request, object_id)
        if not obj:
            raise Http404("Aggregated report not found.")

        # Generate on-demand (do not store to MEDIA).
        from .aggregation import aggregate_instance
        from .branding import resolve_branding_for_instance
        from .pdf import generate_aggregated_pdf

        instance = obj.inspection_instance

        cfg = (
            instance.config_versions.filter(status="published").order_by("-published_at", "-created_at").first()
            or instance.config_versions.order_by("-created_at").first()
        )
        config = cfg.config if cfg and isinstance(cfg.config, dict) else {}
        schema = config.get("schema") if isinstance(config.get("schema"), dict) else config

        counts = aggregate_instance(instance)

        output = config.get("output") if isinstance(config.get("output"), dict) else {}
        default_lang = output.get("default_language") if isinstance(output.get("default_language"), str) else None
        copy = output.get("copy") if isinstance(output.get("copy"), dict) else {}
        languages = output.get("languages") if isinstance(output.get("languages"), list) else list(copy.keys())
        languages = [x for x in languages if isinstance(x, str) and x]
        selected_lang = default_lang or (languages[0] if languages else "en")

        pdf_bytes = generate_aggregated_pdf(
            config=config,
            schema=schema,
            counts=counts,
            output_language=selected_lang,
            inspection_id=str(instance.id),
            config_version_id=str(cfg.id) if cfg else None,
            branding=resolve_branding_for_instance(instance),
        )

        resp = FileResponse(BytesIO(pdf_bytes), content_type="application/pdf")
        resp["Content-Disposition"] = f'attachment; filename="{instance.id}.pdf"'
        return resp

    @admin.display(description="Aggregated PDF")
    def pdf_download(self, obj: AggregatedReport) -> str:
        if not obj:
            return "-"
        url = f"/admin/forms/aggregatedreport/{obj.id}/pdf/"
        return format_html('<a href="{}" target="_blank">Download</a>', url)


@admin.register(OrganizationBranding)
class OrganizationBrandingAdmin(admin.ModelAdmin):
    list_display = (
        "organization_id",
        "hospital_program_name",
        "primary_color",
        "has_logo",
        "updated_at",
    )
    search_fields = ("organization_id", "hospital_program_name", "tagline")
    readonly_fields = ("created_at", "updated_at", "logo_preview")
    fieldsets = (
        (
            "Organization Linkage",
            {"fields": ("organization_id", "hospital_program_name")},
        ),
        (
            "Brand Presentation",
            {"fields": ("logo", "logo_preview", "primary_color", "tagline", "footer_text")},
        ),
        (
            "Audit",
            {"fields": ("created_at", "updated_at")},
        ),
    )

    @admin.display(boolean=True, description="Logo")
    def has_logo(self, obj: OrganizationBranding) -> bool:
        return bool(obj and obj.logo)

    @admin.display(description="Logo preview")
    def logo_preview(self, obj: OrganizationBranding) -> str:
        if not obj or not obj.logo:
            return "-"
        return format_html('<a href="{}" target="_blank">View logo file</a>', obj.logo.url)
