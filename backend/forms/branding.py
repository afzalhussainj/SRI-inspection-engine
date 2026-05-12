from __future__ import annotations

from typing import Any

from .models import InspectionInstance, OrganizationBranding

# Public-facing fallbacks when no org-specific branding applies (API + PDF alignment).
DEFAULT_PUBLIC_PROGRAM_NAME = "SRI Program"
DEFAULT_PUBLIC_FOOTER_TEXT = "Structured Risk Inspection Technology"


def resolve_branding_for_instance(instance: InspectionInstance) -> dict[str, Any]:
    """
    Resolve organization branding for a given inspection instance.
    Returns a stable fallback payload when no organization branding is configured.
    """
    org_id = (instance.organization_id or "").strip()
    default_name = (instance.name or "").strip() or DEFAULT_PUBLIC_PROGRAM_NAME
    fallback = {
        "organization_id": org_id,
        "hospital_program_name": default_name,
        "logo_url": None,
        "logo_path": None,
        "primary_color": "#1F2937",
        "tagline": "",
        "footer_text": DEFAULT_PUBLIC_FOOTER_TEXT,
    }
    if not org_id:
        return fallback

    branding = (
        OrganizationBranding.objects.filter(organization_id=org_id)
        .only(
            "organization_id",
            "hospital_program_name",
            "logo",
            "primary_color",
            "tagline",
            "footer_text",
        )
        .first()
    )
    if not branding:
        return fallback

    logo_url = branding.logo.url if branding.logo else None
    logo_path = branding.logo.path if branding.logo else None
    return {
        "organization_id": branding.organization_id,
        "hospital_program_name": branding.hospital_program_name or default_name,
        "logo_url": logo_url,
        "logo_path": logo_path,
        "primary_color": branding.primary_color or "#1F2937",
        "tagline": branding.tagline or "",
        "footer_text": branding.footer_text or "",
    }
