from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .i18n import localize_schema, resolve_i18n_text


@dataclass(frozen=True)
class DomainReportData:
    domain_id: str
    domain_title: str
    classification: str
    confidence_marker: str
    confidence_counts: dict[str, int]
    triggered_indicators: list[str]
    structural_considerations: list[dict[str, Any]]


@dataclass(frozen=True)
class SingleSubmissionSriReportData:
    inspection_id: str
    inspection_standard: str
    inspection_standard_version: str
    completion_date: str
    overall_classification: str
    priority_review_order: list[str]
    domain_classification_overview: list[dict[str, str]]
    domains: list[DomainReportData]
    cross_domain_summary_flags: list[str]
    triggered_indicators: dict[str, list[str]]
    selected_structural_considerations: dict[str, list[dict[str, Any]]]
    confidence_markers: dict[str, dict[str, Any]]
    strengths_data: list[dict[str, str]]
    methodology_scope: dict[str, str]
    output_language: str


def _safe_str(v: Any) -> str:
    return "" if v is None else str(v)


def _resolve_report_text(value: Any, *, lang: str, default_lang: str) -> str:
    """
    Resolve report-facing copy without cross-language leakage.
    For non-default languages, only an explicit localized entry is accepted.
    """
    if isinstance(value, str):
        return value if lang == default_lang else ""
    if not isinstance(value, dict):
        return ""
    direct = value.get(lang)
    if isinstance(direct, str) and direct.strip():
        return direct
    if lang == default_lang:
        return resolve_i18n_text(value, lang=lang, default_lang=default_lang)
    return ""


def _classification_rank(label: str) -> int:
    return {"Cleared": 0, "Watch": 1, "Elevated": 2}.get(label, -1)


def _domain_order(schema: dict[str, Any]) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for section in schema.get("sections", []) or []:
        sid = section.get("id")
        if not isinstance(sid, str):
            continue
        title = _safe_str(section.get("title") or sid)
        rows.append((sid, title))
    return rows


def _domain_confidence(
    *,
    classification: str,
    signals: dict[str, dict[str, int]],
    output_language: str = "en",
) -> tuple[str, dict[str, int]]:
    moderate = 0
    high = 0
    for indicator in signals.values():
        moderate += int(indicator.get("moderate", 0) or 0)
        high += int(indicator.get("high", 0) or 0)

    if output_language == "es":
        if high > 0:
            marker = "Confianza Alta"
        elif moderate > 0:
            marker = "Confianza Moderada"
        else:
            marker = "Confianza Baja"
    else:
        if high > 0:
            marker = "High Confidence"
        elif moderate > 0:
            marker = "Moderate Confidence"
        else:
            marker = "Low Confidence"
    return marker, {"moderate": moderate, "high": high}


def _trim_considerations(
    *,
    domain_order: list[str],
    structural_considerations: dict[str, list[dict[str, Any]]],
    per_domain_cap: int = 2,
    total_cap: int = 8,
) -> dict[str, list[dict[str, Any]]]:
    selected_total = 0
    selected: dict[str, list[dict[str, Any]]] = {}
    for domain_id in domain_order:
        domain_items = structural_considerations.get(domain_id, [])
        if not isinstance(domain_items, list):
            continue
        ordered = sorted(
            [x for x in domain_items if isinstance(x, dict)],
            key=lambda x: int(x.get("question_number", 9999) or 9999),
        )
        kept: list[dict[str, Any]] = []
        for item in ordered:
            if len(kept) >= per_domain_cap or selected_total >= total_cap:
                break
            kept.append(item)
            selected_total += 1
        if kept:
            selected[domain_id] = kept
        if selected_total >= total_cap:
            break
    return selected


def assemble_single_submission_sri_report_data(
    *,
    inspection_id: str,
    config: dict[str, Any],
    schema: dict[str, Any],
    outputs: dict[str, Any],
    completion_dt: datetime | None = None,
    config_version_id: str | None = None,
) -> SingleSubmissionSriReportData:
    domain_classifications = outputs.get("domain_classifications")
    if not isinstance(domain_classifications, dict):
        domain_classifications = outputs.get("section_classifications", {})
    if not isinstance(domain_classifications, dict):
        domain_classifications = {}

    indicators_by_domain = outputs.get("indicators_by_domain")
    if not isinstance(indicators_by_domain, dict):
        indicators_by_domain = {}

    indicator_signals_by_domain = outputs.get("indicator_signals_by_domain")
    if not isinstance(indicator_signals_by_domain, dict):
        indicator_signals_by_domain = {}

    structural_considerations = outputs.get("structural_considerations")
    if not isinstance(structural_considerations, dict):
        structural_considerations = {}

    cross_flags = outputs.get("cross_domain_flags")
    if not isinstance(cross_flags, list):
        cross_flags = []
    cross_flags = sorted([x for x in cross_flags if isinstance(x, str)])

    completion_date = (completion_dt.isoformat() if completion_dt else "")
    inspection_standard = "SRI"
    if not bool(
        (
            config.get("evaluation", {})
            if isinstance(config.get("evaluation"), dict)
            else {}
        ).get("sri", {})
    ):
        inspection_standard = "Inspection"

    inspection_standard_version = _safe_str(
        config.get("version") or config_version_id or ""
    )
    overall_classification = _safe_str(outputs.get("classification") or "Cleared")

    output_cfg = config.get("output", {}) if isinstance(config.get("output"), dict) else {}
    default_lang = (
        output_cfg.get("default_language")
        if isinstance(output_cfg.get("default_language"), str)
        else "en"
    )
    output_language = _safe_str(outputs.get("output_language") or default_lang or "en")

    localized_schema = localize_schema(
        schema=schema,
        config=config,
        lang=output_language,
        default_lang=default_lang,
    )

    domain_rows = _domain_order(localized_schema)
    domain_ids_in_order = [sid for sid, _ in domain_rows]
    constrained_considerations = _trim_considerations(
        domain_order=domain_ids_in_order,
        structural_considerations=structural_considerations,
    )

    domains: list[DomainReportData] = []
    overview: list[dict[str, str]] = []
    confidence_markers: dict[str, dict[str, Any]] = {}

    for sid, title in domain_rows:
        cls = _safe_str(domain_classifications.get(sid) or overall_classification)
        triggered = indicators_by_domain.get(sid, [])
        if not isinstance(triggered, list):
            triggered = []
        triggered = sorted([x for x in triggered if isinstance(x, str)])
        signals = indicator_signals_by_domain.get(sid, {})
        if not isinstance(signals, dict):
            signals = {}
        marker, counts = _domain_confidence(
            classification=cls,
            signals=signals,
            output_language=output_language,
        )
        considerations = constrained_considerations.get(sid, [])

        domains.append(
            DomainReportData(
                domain_id=sid,
                domain_title=title,
                classification=cls,
                confidence_marker=marker,
                confidence_counts=counts,
                triggered_indicators=triggered,
                structural_considerations=considerations,
            )
        )
        overview.append({"domain_id": sid, "domain_title": title, "classification": cls})
        confidence_markers[sid] = {"marker": marker, "counts": counts}

    priority_review_order = [
        d.domain_id
        for d in sorted(
            domains,
            key=lambda x: (
                -_classification_rank(x.classification),
                [r[0] for r in domain_rows].index(x.domain_id),
            ),
        )
    ]

    strengths = outputs.get("strengths")
    strengths_data: list[dict[str, str]] = []
    if isinstance(strengths, list):
        for item in strengths:
            if isinstance(item, dict):
                strengths_data.append(
                    {
                        "title": _safe_str(item.get("title")),
                        "description": _safe_str(item.get("description")),
                    }
                )
            elif isinstance(item, str):
                strengths_data.append({"title": item, "description": ""})
    if not strengths_data:
        for d in domains:
            if d.classification == "Cleared":
                strengths_data.append(
                    {
                        "title": d.domain_title,
                        "description": resolve_i18n_text(
                            {
                                "en": "Current structure in this domain appears clearly organized and reviewable.",
                                "es": "La estructura actual de este dominio parece claramente organizada y revisable.",
                            },
                            lang=output_language,
                            default_lang=default_lang,
                        ),
                    }
                )
    if not strengths_data:
        strengths_data.append(
            {
                "title": resolve_i18n_text(
                    {"en": "System-level strength", "es": "Fortaleza a nivel de sistema"},
                    lang=output_language,
                    default_lang=default_lang,
                ),
                "description": resolve_i18n_text(
                    {
                        "en": "The submission provides sufficient structural detail to support focused institutional review.",
                        "es": "La respuesta proporciona detalle estructural suficiente para apoyar una revision institucional focalizada.",
                    },
                    lang=output_language,
                    default_lang=default_lang,
                ),
            }
        )

    report_cfg = output_cfg.get("report", {}) if isinstance(output_cfg.get("report"), dict) else {}
    methodology_scope = {
        "methodology": _safe_str(
            _resolve_report_text(
                report_cfg.get("methodology"),
                lang=output_language,
                default_lang=default_lang,
            )
            or resolve_i18n_text(
            {
                "en": "Configuration-driven SRI deterministic indicator evaluation.",
                "es": "Evaluacion deterministica de indicadores SRI guiada por configuracion.",
            },
            lang=output_language,
            default_lang=default_lang,
        )
        ),
        "scope": _safe_str(
            _resolve_report_text(
                report_cfg.get("scope"),
                lang=output_language,
                default_lang=default_lang,
            )
            or resolve_i18n_text(
            {
                "en": "Single recipient submission covering all configured SRI domains.",
                "es": "Una sola respuesta de destinatario que cubre todos los dominios SRI configurados.",
            },
            lang=output_language,
            default_lang=default_lang,
        )
        ),
    }

    return SingleSubmissionSriReportData(
        inspection_id=inspection_id,
        inspection_standard=inspection_standard,
        inspection_standard_version=inspection_standard_version,
        completion_date=completion_date,
        overall_classification=overall_classification,
        priority_review_order=priority_review_order,
        domain_classification_overview=overview,
        domains=domains,
        cross_domain_summary_flags=cross_flags,
        triggered_indicators={
            d.domain_id: list(d.triggered_indicators)
            for d in domains
        },
        selected_structural_considerations={
            d.domain_id: list(d.structural_considerations)
            for d in domains
            if d.structural_considerations
        },
        confidence_markers=confidence_markers,
        strengths_data=strengths_data,
        methodology_scope=methodology_scope,
        output_language=output_language,
    )

