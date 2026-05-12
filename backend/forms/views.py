from __future__ import annotations

from io import BytesIO
import uuid

from django.utils import timezone
from django.http import FileResponse
from rest_framework.decorators import api_view
from rest_framework.request import Request
from rest_framework.response import Response

from .branding import resolve_branding_for_instance
from .engine import ValidationError as EngineValidationError
from .engine import evaluate, validate_answers
from .i18n import localize_schema, resolve_language
from .models import RecipientLink, Submission
from .pdf import build_parent_display_ids, generate_single_submission_pdf
from .report_data import assemble_single_submission_sri_report_data

def _parse_uuid(value: str, field_name: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:
        return None


def _extract_output_languages(config: dict) -> tuple[list[str], str]:
    """
    Returns (allowed_languages, default_language).
    Language copy is optional. If not provided, defaults to ["en"] and "en".
    Merges explicit output.languages with languages that have copy blocks so configs
    that list only one code but include multiple copy locales still expose every option.
    """
    output = config.get("output") if isinstance(config.get("output"), dict) else {}
    copy = output.get("copy") if isinstance(output.get("copy"), dict) else {}
    explicit = output.get("languages") if isinstance(output.get("languages"), list) else []
    explicit = [x for x in explicit if isinstance(x, str) and x]
    from_copy = [x for x in copy.keys() if isinstance(x, str) and x]
    merged: list[str] = []
    seen: set[str] = set()
    for x in explicit + from_copy:
        if x not in seen:
            merged.append(x)
            seen.add(x)
    allowed = merged
    default_lang = output.get("default_language") if isinstance(output.get("default_language"), str) else None
    if not default_lang:
        default_lang = allowed[0] if allowed else "en"
    if not allowed:
        allowed = [default_lang]
    if default_lang not in allowed:
        allowed = [default_lang] + [x for x in allowed if x != default_lang]
    return allowed, default_lang


def _public_branding_payload(branding: dict) -> dict:
    payload = dict(branding)
    payload.pop("logo_path", None)
    return payload


@api_view(["GET"])
def health(_: Request) -> Response:
    return Response({"ok": True})


@api_view(["GET"])
def get_form_fields(request: Request, inspection_id, link_uuid) -> Response:
    inspection_uuid = _parse_uuid(inspection_id, "inspection_id")
    link_uuid_parsed = _parse_uuid(link_uuid, "link_uuid")
    if not inspection_uuid or not link_uuid_parsed:
        return Response(
            {"detail": "Invalid link. Expected UUIDs for inspection_id and link_uuid."},
            status=400,
        )

    link = (
        RecipientLink.objects.select_related("config_version", "inspection_instance")
        .filter(inspection_instance_id=inspection_uuid, id=link_uuid_parsed)
        .first()
    )
    if not link:
        return Response({"detail": "Link not found. Please check the URL you received."}, status=404)

    # Mark opened on first access
    if link.status == RecipientLink.STATUS_CREATED:
        link.status = RecipientLink.STATUS_OPENED
        link.opened_at = timezone.now()
        link.save()

    now = timezone.now()
    if link.expires_at and now > link.expires_at:
        if link.status != RecipientLink.STATUS_EXPIRED:
            link.status = RecipientLink.STATUS_EXPIRED
            link.save()
        return Response({"detail": "This link has expired."}, status=410)

    cfg = link.config_version
    if cfg.status != cfg.STATUS_PUBLISHED:
        return Response({"detail": "This inspection is not available yet."}, status=409)

    config = cfg.config if isinstance(cfg.config, dict) else {}
    schema = config.get("schema") if isinstance(config.get("schema"), dict) else config
    allowed_langs, default_lang = _extract_output_languages(config)
    selected_content_lang = resolve_language(
        requested_lang=request.query_params.get("lang"),
        allowed_languages=allowed_langs,
        default_language=default_lang,
    )
    localized_schema = localize_schema(
        schema=schema,
        config=config,
        lang=selected_content_lang,
        default_lang=default_lang,
    )

    already_submitted = link.status == RecipientLink.STATUS_SUBMITTED or hasattr(link, "submission")
    branding = _public_branding_payload(resolve_branding_for_instance(link.inspection_instance))
    logo_url = branding.get("logo_url")
    if isinstance(logo_url, str) and logo_url.startswith("/"):
        try:
            branding = {**branding, "logo_url": request.build_absolute_uri(logo_url)}
        except Exception:
            pass

    return Response(
        {
            "inspection_id": str(link.inspection_instance_id),
            "link_uuid": str(link.id),
            "config_version_id": str(cfg.id),
            "expires_at": link.expires_at.isoformat() if link.expires_at else None,
            "already_submitted": already_submitted,
            "schema": localized_schema,
            "output_languages": allowed_langs,
            "default_output_language": default_lang,
            "selected_content_language": selected_content_lang,
            "branding": branding,
        }
    )


@api_view(["POST"])
def submit_form(request: Request, inspection_id, link_uuid) -> Response:
    inspection_uuid = _parse_uuid(inspection_id, "inspection_id")
    link_uuid_parsed = _parse_uuid(link_uuid, "link_uuid")
    if not inspection_uuid or not link_uuid_parsed:
        return Response(
            {"detail": "Invalid link. Expected UUIDs for inspection_id and link_uuid."},
            status=400,
        )

    link = (
        RecipientLink.objects.select_related("config_version", "inspection_instance")
        .filter(inspection_instance_id=inspection_uuid, id=link_uuid_parsed)
        .first()
    )
    if not link:
        return Response({"detail": "Link not found. Please check the URL you received."}, status=404)

    now = timezone.now()
    if link.expires_at and now > link.expires_at:
        if link.status != RecipientLink.STATUS_EXPIRED:
            link.status = RecipientLink.STATUS_EXPIRED
            link.save()
        return Response({"detail": "This link has expired."}, status=410)

    if link.status == RecipientLink.STATUS_SUBMITTED or hasattr(link, "submission"):
        return Response({"detail": "This link was already submitted."}, status=409)

    cfg = link.config_version
    if cfg.status != cfg.STATUS_PUBLISHED:
        return Response({"detail": "This inspection is not available yet."}, status=409)

    answers = request.data.get("answers", {})
    if not isinstance(answers, dict):
        return Response({"detail": "Invalid answers payload. Expected an object."}, status=400)

    try:
        validate_answers(cfg.config, answers)
    except EngineValidationError as e:
        return Response({"detail": str(e)}, status=400)

    config = cfg.config if isinstance(cfg.config, dict) else {}
    allowed_langs, default_lang = _extract_output_languages(config)
    requested_lang = request.data.get("output_language")
    if requested_lang is None:
        selected_lang = default_lang
    elif isinstance(requested_lang, str) and requested_lang:
        if requested_lang not in allowed_langs:
            return Response(
                {"detail": f"Invalid output_language. Allowed: {allowed_langs}"},
                status=400,
            )
        selected_lang = requested_lang
    else:
        return Response({"detail": "Invalid output_language. Expected a string."}, status=400)

    result = evaluate(
        cfg.config,
        answers,
        content_language=selected_lang,
        default_language=default_lang,
    )

    submission = Submission.objects.create(
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
            "output_language": selected_lang,
        },
    )

    # PDFs are generated on-demand (runtime) and are not stored.

    link.status = RecipientLink.STATUS_SUBMITTED
    link.submitted_at = timezone.now()
    link.save()

    return Response(
        {
            "inspection_id": str(link.inspection_instance_id),
            "link_uuid": str(link.id),
            "status": "submitted",
        }
    )


@api_view(["GET"])
def get_submission_pdf(_: Request, inspection_id, link_uuid) -> Response:
    inspection_uuid = _parse_uuid(inspection_id, "inspection_id")
    link_uuid_parsed = _parse_uuid(link_uuid, "link_uuid")
    if not inspection_uuid or not link_uuid_parsed:
        return Response(
            {"detail": "Invalid link. Expected UUIDs for inspection_id and link_uuid."},
            status=400,
        )

    link = (
        RecipientLink.objects.select_related("config_version", "inspection_instance")
        .filter(inspection_instance_id=inspection_uuid, id=link_uuid_parsed)
        .first()
    )
    if not link:
        return Response({"detail": "Link not found. Please check the URL you received."}, status=404)

    if not hasattr(link, "submission"):
        return Response({"detail": "No submission found for this link yet."}, status=404)

    # QuietRisk: do not allow respondents to download PDFs.
    if link.inspection_instance.organization_id:
        return Response({"detail": "PDF download is not available for this inspection."}, status=403)

    sub = link.submission
    cfg = link.config_version
    config = cfg.config if isinstance(cfg.config, dict) else {}
    schema = config.get("schema") if isinstance(config.get("schema"), dict) else config

    outputs = sub.outputs if isinstance(sub.outputs, dict) else {}
    branding = resolve_branding_for_instance(link.inspection_instance)
    selected_lang = outputs.get("output_language") if isinstance(outputs.get("output_language"), str) else None
    report_data = assemble_single_submission_sri_report_data(
        inspection_id=str(link.inspection_instance_id),
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
        output_language=selected_lang,
        report_data=report_data,
        inspection_id=str(link.inspection_instance_id),
        completion_dt=sub.created_at,
        config_version_id=str(cfg.id),
        branding=branding,
    )

    resp = FileResponse(BytesIO(pdf_bytes), content_type="application/pdf")
    display_id, _ = build_parent_display_ids(
        inspection_id=str(link.inspection_instance_id),
        report_reference=str(cfg.id),
        completion_date=sub.created_at.isoformat() if sub.created_at else "",
    )
    filename = f"{display_id}_StructuredWellbeingRiskSummary.pdf"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp


