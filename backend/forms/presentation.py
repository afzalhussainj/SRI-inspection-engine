from __future__ import annotations

import re
from typing import Any

from .i18n import localize_schema

_LANGUAGE_LABELS: dict[str, dict[str, str]] = {
    "en": {"en": "English", "es": "Spanish"},
    "es": {"en": "Ingles", "es": "Espanol"},
}

_INDICATOR_LABELS: dict[str, dict[str, str]] = {
    "drift_conditions": {
        "en": "Routine Variability",
        "es": "Variabilidad de rutinas",
    },
    "ownership_clarity": {
        "en": "Decision-Making Clarity",
        "es": "Claridad en la toma de decisiones",
    },
    "review_cadence": {
        "en": "Review Cadence",
        "es": "Frecuencia de revision",
    },
    "structural_complexity_exposure": {
        "en": "Structural Complexity",
        "es": "Complejidad estructural",
    },
    "lock_in_reversibility_friction": {
        "en": "Change Friction",
        "es": "Friccion ante cambios",
    },
}

_FLAG_LABELS: dict[str, dict[str, str]] = {
    "multi_domain_structural_exposure": {
        "en": "Multiple domains show elevated structural complexity",
        "es": "Multiples dominios muestran complejidad estructural elevada",
    },
}

_PATTERN_LABELS: dict[str, dict[str, str]] = {
    "cross_domain_multi_exposure": {
        "en": "Cross-domain structural exposure pattern",
        "es": "Patron de exposicion estructural entre dominios",
    },
}


def _safe_str(value: Any) -> str:
    return "" if value is None else str(value)


def _localized(mapping: dict[str, dict[str, str]], key: str, lang: str) -> str | None:
    options = mapping.get(key)
    if not options:
        return None
    return options.get(lang) or options.get("en")


def _humanize_identifier(value: str) -> str:
    parts = [part for part in re.split(r"[_:\-]+", _safe_str(value).strip()) if part]
    if not parts:
        return ""
    words: list[str] = []
    for part in parts:
        if part.isupper() and len(part) <= 4:
            words.append(part)
        else:
            words.append(part.capitalize())
    return " ".join(words)


def _question_pattern_label(value: str) -> str | None:
    """
    Human-readable pattern id for reports (no 'Question N' reader-facing prefix).
    """
    match = re.match(r"^q0*(\d+)[_:](.+)$", value)
    if not match:
        return None
    tail = _humanize_identifier(match.group(2))
    return tail or None


def domain_title_lookup(*, config: dict[str, Any], schema: dict[str, Any], lang: str) -> dict[str, str]:
    output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
    default_lang = (
        output_cfg.get("default_language")
        if isinstance(output_cfg.get("default_language"), str)
        else "en"
    )
    localized_schema = localize_schema(
        schema=schema,
        config=config,
        lang=lang,
        default_lang=default_lang,
    )
    lookup: dict[str, str] = {}
    for section in localized_schema.get("sections", []) or []:
        sid = section.get("id")
        if isinstance(sid, str):
            lookup[sid] = _safe_str(section.get("title") or sid)
    return lookup


def domain_label(
    domain_id: str,
    *,
    config: dict[str, Any],
    schema: dict[str, Any],
    lang: str,
) -> str:
    lookup = domain_title_lookup(config=config, schema=schema, lang=lang)
    return lookup.get(domain_id) or _humanize_identifier(domain_id) or _safe_str(domain_id)


def indicator_label(
    indicator: str,
    *,
    config: dict[str, Any],
    schema: dict[str, Any],
    lang: str,
    domain_id: str | None = None,
    include_domain: bool = False,
) -> str:
    raw = _safe_str(indicator).strip()
    if raw.startswith("indicator:"):
        parts = raw.split(":", 2)
        if len(parts) == 3:
            domain_id = parts[1]
            raw = parts[2]
            include_domain = True

    detail = _localized(_INDICATOR_LABELS, raw, lang) or _humanize_identifier(raw) or raw
    if include_domain and domain_id:
        return f"{domain_label(domain_id, config=config, schema=schema, lang=lang)} - {detail}"
    return detail


def flag_label(flag: str, *, lang: str) -> str:
    raw = _safe_str(flag).strip()
    return _localized(_FLAG_LABELS, raw, lang) or _humanize_identifier(raw) or raw


def pattern_label(pattern_id: str, *, lang: str) -> str:
    raw = _safe_str(pattern_id).strip()
    return (
        _localized(_PATTERN_LABELS, raw, lang)
        or _question_pattern_label(raw)
        or _humanize_identifier(raw)
        or raw
    )


def tag_label(
    tag: str,
    *,
    config: dict[str, Any],
    schema: dict[str, Any],
    lang: str,
) -> str:
    raw = _safe_str(tag).strip()
    if raw.startswith("indicator:"):
        return indicator_label(
            raw,
            config=config,
            schema=schema,
            lang=lang,
            include_domain=True,
        )
    if raw.startswith("flag:"):
        _, _, flag = raw.partition(":")
        return flag_label(flag, lang=lang)
    return _humanize_identifier(raw) or raw


def language_label(language_code: str, *, lang: str) -> str:
    raw = _safe_str(language_code).strip()
    return (
        _localized(_LANGUAGE_LABELS, raw, lang)
        or _localized(_LANGUAGE_LABELS, raw, "en")
        or _humanize_identifier(raw)
        or raw
    )
