from __future__ import annotations

from copy import deepcopy
from typing import Any


def resolve_i18n_text(value: Any, *, lang: str, default_lang: str = "en") -> str:
    """
    Resolve localized text from either:
      - plain string
      - dict like {"en": "...", "es": "..."}
    """
    if isinstance(value, str):
        return value
    if not isinstance(value, dict):
        return ""

    direct = value.get(lang)
    if isinstance(direct, str) and direct:
        return direct

    fallback = value.get(default_lang)
    if isinstance(fallback, str) and fallback:
        return fallback

    generic = value.get("default")
    if isinstance(generic, str) and generic:
        return generic

    # Deterministic final fallback.
    for key in sorted(value.keys()):
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate:
            return candidate
    return ""


def resolve_language(
    *,
    requested_lang: str | None,
    allowed_languages: list[str],
    default_language: str,
) -> str:
    if isinstance(requested_lang, str) and requested_lang and requested_lang in allowed_languages:
        return requested_lang
    return default_language


def localize_schema(
    *,
    schema: dict[str, Any],
    config: dict[str, Any],
    lang: str,
    default_lang: str,
) -> dict[str, Any]:
    """
    Returns a localized schema copy using config-driven questionnaire i18n blocks.
    The scoring logic remains language-neutral because ids/values are unchanged.
    """
    out = deepcopy(schema)
    output = config.get("output") if isinstance(config.get("output"), dict) else {}
    questionnaire = (
        output.get("questionnaire")
        if isinstance(output.get("questionnaire"), dict)
        else {}
    )

    sections_i18n = (
        questionnaire.get("sections")
        if isinstance(questionnaire.get("sections"), dict)
        else {}
    )
    fields_i18n = (
        questionnaire.get("fields")
        if isinstance(questionnaire.get("fields"), dict)
        else {}
    )
    help_texts_i18n = (
        questionnaire.get("help_texts")
        if isinstance(questionnaire.get("help_texts"), dict)
        else {}
    )
    option_values_i18n = (
        questionnaire.get("option_values")
        if isinstance(questionnaire.get("option_values"), dict)
        else {}
    )
    options_i18n = (
        questionnaire.get("options")
        if isinstance(questionnaire.get("options"), dict)
        else {}
    )

    title = schema.get("title")
    if title is not None:
        out["title"] = resolve_i18n_text(title, lang=lang, default_lang=default_lang) or str(title)

    for section in out.get("sections", []) or []:
        sid = section.get("id")
        if isinstance(sid, str):
            if sid in sections_i18n:
                section["title"] = resolve_i18n_text(
                    sections_i18n[sid],
                    lang=lang,
                    default_lang=default_lang,
                ) or section.get("title", sid)
            else:
                section["title"] = resolve_i18n_text(
                    section.get("title"),
                    lang=lang,
                    default_lang=default_lang,
                ) or section.get("title", sid)

        localized_fields: list[dict[str, Any]] = []
        for field in section.get("fields", []) or []:
            meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
            if meta.get("active") is False:
                continue
            fid = field.get("id")
            if isinstance(fid, str):
                if fid in fields_i18n:
                    field["label"] = resolve_i18n_text(
                        fields_i18n[fid],
                        lang=lang,
                        default_lang=default_lang,
                    ) or field.get("label", fid)
                else:
                    field["label"] = resolve_i18n_text(
                        field.get("label"),
                        lang=lang,
                        default_lang=default_lang,
                    ) or field.get("label", fid)
                if fid in help_texts_i18n:
                    resolved_help = resolve_i18n_text(
                        help_texts_i18n[fid],
                        lang=lang,
                        default_lang=default_lang,
                    )
                    if resolved_help:
                        field["help_text"] = resolved_help
                else:
                    existing_help = resolve_i18n_text(
                        field.get("help_text"),
                        lang=lang,
                        default_lang=default_lang,
                    )
                    if existing_help:
                        field["help_text"] = existing_help

            for option in field.get("options", []) or []:
                if not isinstance(option, dict):
                    continue
                ov = option.get("value")
                if isinstance(fid, str) and isinstance(ov, str):
                    per_field = options_i18n.get(fid) if isinstance(options_i18n.get(fid), dict) else {}
                    if isinstance(per_field.get(ov), (dict, str)):
                        option["label"] = resolve_i18n_text(
                            per_field.get(ov),
                            lang=lang,
                            default_lang=default_lang,
                        ) or option.get("label", ov)
                    elif isinstance(option_values_i18n.get(ov), (dict, str)):
                        option["label"] = resolve_i18n_text(
                            option_values_i18n.get(ov),
                            lang=lang,
                            default_lang=default_lang,
                        ) or option.get("label", ov)
                    else:
                        option["label"] = resolve_i18n_text(
                            option.get("label"),
                            lang=lang,
                            default_lang=default_lang,
                        ) or option.get("label", ov)
                else:
                    option["label"] = resolve_i18n_text(
                        option.get("label"),
                        lang=lang,
                        default_lang=default_lang,
                    ) or option.get("label", "")
            localized_fields.append(field)
        section["fields"] = localized_fields
    out["sections"] = [s for s in (out.get("sections", []) or []) if (s.get("fields") or [])]
    return out

