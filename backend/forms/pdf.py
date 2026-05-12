from __future__ import annotations

import re
from io import BytesIO
from typing import Any
from datetime import datetime
import uuid as uuidlib

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import CondPageBreak, Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from xml.sax.saxutils import escape

from .presentation import (
    domain_label,
    flag_label,
    indicator_label,
    language_label,
    pattern_label,
    tag_label,
)
from .report_data import (
    SingleSubmissionSriReportData,
    assemble_single_submission_sri_report_data,
)
from .branding import DEFAULT_PUBLIC_FOOTER_TEXT
from .i18n import resolve_i18n_text

_PDF_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "report_title": "Structured Wellbeing Risk Summary",
        "report_subtitle": "Household Systems & Care Coordination Review",
        "inspection_id": "Inspection ID",
        "standard": "Standard",
        "version": "Version",
        "completion_date": "Completion date",
        "executive_overview": "Executive Overview",
        "overall_classification": "Overall Classification",
        "classification_label": "Classification Label",
        "cross_domain_flags": "Cross-domain flags",
        "priority_review_order": "Priority Review Order",
        "priority_none": "No priority order generated.",
        "domain_overview": "Domain Classification Overview",
        "confidence_note": "Confidence markers reflect indicator signal density/consistency and do not change the classification level.",
        "domain": "Domain",
        "classification": "Classification",
        "confidence_marker": "Confidence Marker",
        "domain_details": "Domain Detail Sections",
        "domain_details_intro": "The following sections summarize each domain's classification, confidence marker, indicator triggers, and selected structural considerations in a neutral reporting format.",
        "domain_id": "Domain ID",
        "confidence_counts": "Confidence Counts",
        "structural_indicators": "Structural Indicators",
        "no_structural_indicators": "No structural indicators were triggered for this domain.",
        "domain_interpretation": "Domain Interpretation",
        "selected_structural_considerations": "Selected Structural Considerations",
        "no_structural_considerations": "No structural considerations were selected for this domain.",
        "cross_domain_system_analysis": "Cross-Domain Observations",
        "triggered_indicator_groups": "Triggered indicator groups by domain",
        "structural_strengths": "Structural Strengths",
        "no_strengths": "No strengths were documented in this output snapshot.",
        "methodology_overview": "Methodology Overview",
        "scope_limitations": "Scope and Limitations",
        "output_language": "Output language",
        "institutional_resources": "Institutional Resources",
        "triggered_structural_notes": "Triggered Structural Notes",
        "program_reference": "Program reference",
        "report_reference": "Report reference",
        "generated": "Generated",
        "program": "Program",
        "none_documented": "None documented.",
        "additional_resources_for_program": "Additional Resources Provided by {program}",
    },
    "es": {
        "report_title": "Resumen de Riesgo de Bienestar Estructural",
        "report_subtitle": "Revision de Sistemas del Hogar y Coordinacion del Cuidado",
        "inspection_id": "ID de inspeccion",
        "standard": "Estandar",
        "version": "Version",
        "completion_date": "Fecha de finalizacion",
        "executive_overview": "Resumen ejecutivo",
        "overall_classification": "Clasificacion general",
        "classification_label": "Etiqueta de clasificacion",
        "cross_domain_flags": "Senales entre dominios",
        "priority_review_order": "Orden prioritario de revision",
        "priority_none": "No se genero un orden de prioridad.",
        "domain_overview": "Resumen de clasificacion por dominio",
        "confidence_note": "Los marcadores de confianza reflejan la densidad/consistencia de senales de indicadores y no cambian el nivel de clasificacion.",
        "domain": "Dominio",
        "classification": "Clasificacion",
        "confidence_marker": "Marcador de confianza",
        "domain_details": "Secciones de detalle por dominio",
        "domain_details_intro": "Las siguientes secciones resumen la clasificacion de cada dominio, su marcador de confianza, indicadores activados y consideraciones estructurales seleccionadas en un formato neutral.",
        "domain_id": "ID de dominio",
        "confidence_counts": "Conteos de confianza",
        "structural_indicators": "Indicadores estructurales",
        "no_structural_indicators": "No se activaron indicadores estructurales para este dominio.",
        "domain_interpretation": "Interpretacion del dominio",
        "selected_structural_considerations": "Consideraciones estructurales seleccionadas",
        "no_structural_considerations": "No se seleccionaron consideraciones estructurales para este dominio.",
        "cross_domain_system_analysis": "Analisis sistemico entre dominios",
        "triggered_indicator_groups": "Grupos de indicadores activados por dominio",
        "structural_strengths": "Fortalezas estructurales",
        "no_strengths": "No se documentaron fortalezas en este resultado.",
        "methodology_overview": "Descripcion metodologica",
        "scope_limitations": "Alcance y limitaciones",
        "output_language": "Idioma de salida",
        "institutional_resources": "Recursos institucionales",
        "triggered_structural_notes": "Notas estructurales activadas",
        "program_reference": "Referencia del programa",
        "report_reference": "Referencia del informe",
        "generated": "Generado",
        "program": "Programa",
        "none_documented": "Nada documentado.",
        "additional_resources_for_program": "Recursos adicionales proporcionados por {program}",
    },
}

_SRI_STANDARD_DISPLAY_NAME = "SRI Structural Systems Assessment Standard v1.0"
_DEFAULT_REPORT_FOOTER = DEFAULT_PUBLIC_FOOTER_TEXT


def _label(lang: str, key: str) -> str:
    return _PDF_LABELS.get(lang, _PDF_LABELS["en"]).get(key, _PDF_LABELS["en"].get(key, key))

def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    return str(v)

def _safe_int(v: Any) -> int:
    try:
        return int(v)
    except Exception:
        return 0


def _display_year(value: Any) -> int:
    raw = _safe_str(value).strip()
    if raw:
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).year
        except Exception:
            pass
    return 2000


def _display_sequence_from_uuid(value: str) -> int:
    raw = _safe_str(value).strip()
    try:
        return (uuidlib.UUID(raw).int % 1_000_000) + 1
    except Exception:
        compact = "".join(ch for ch in raw if ch.isalnum())
        if compact:
            return (sum(ord(ch) for ch in compact) % 1_000_000) + 1
    return 1


def build_parent_display_ids(
    *,
    inspection_id: str,
    report_reference: str,
    completion_date: str,
) -> tuple[str, str]:
    year = _display_year(completion_date)
    serial = _display_sequence_from_uuid(inspection_id)
    inspection_display = f"SWR-{year}-{serial:06d}"
    report_source = report_reference or inspection_id
    report_serial = _display_sequence_from_uuid(report_source)
    report_display = f"RPT-{year}-{report_serial:06d}"
    return inspection_display, report_display


def _safe_hex_color(value: str | None, fallback: str = "#1F2937") -> str:
    v = _safe_str(value).strip()
    if len(v) == 7 and v.startswith("#"):
        try:
            int(v[1:], 16)
            return v
        except Exception:
            return fallback
    return fallback


def _build_pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="PdfBody",
            parent=styles["Normal"],
            leading=14,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfCell",
            parent=styles["Normal"],
            leading=13,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfCellSmall",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfCellLabel",
            parent=styles["Normal"],
            leading=13,
            fontName="Helvetica-Bold",
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfCellLabelSmall",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            fontName="Helvetica-Bold",
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfBullet",
            parent=styles["Normal"],
            leading=13,
            leftIndent=18,
            firstLineIndent=0,
            bulletIndent=6,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfBulletSmall",
            parent=styles["Normal"],
            fontSize=9,
            leading=11,
            leftIndent=18,
            firstLineIndent=0,
            bulletIndent=6,
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfMeta",
            parent=styles["Normal"],
            leading=13,
            textColor=colors.HexColor("#374151"),
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfMuted",
            parent=styles["Normal"],
            leading=13,
            textColor=colors.HexColor("#4B5563"),
            spaceAfter=0,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfSectionHeading",
            parent=styles["Heading2"],
            spaceBefore=4,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfTitle",
            parent=styles["Title"],
            alignment=1,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfProgramTitle",
            parent=styles["Title"],
            alignment=1,
            textColor=colors.HexColor("#1F2937"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="PdfBadge",
            parent=styles["Normal"],
            fontSize=11,
            leading=13,
            fontName="Helvetica-Bold",
            alignment=1,
            textColor=colors.white,
            spaceAfter=0,
        )
    )
    return styles


def _para(text: Any, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(_safe_str(text)), style)


def _bullet_items(items: list[str]) -> list[str]:
    return [_safe_str(item).strip() for item in items if _safe_str(item).strip()]


def _bullet_paragraphs(items: list[str], *, styles, style_name: str = "PdfBullet") -> list[Paragraph]:
    rows: list[Paragraph] = []
    for item in _bullet_items(items):
        rows.append(Paragraph(escape(item), styles[style_name], bulletText="•"))
    return rows


def _render_considerations(items: list[dict[str, Any]], *, lang: str) -> list[str]:
    """
    Reader-facing consideration lines: use full consideration text only (no Question N labels).
    question_number is ignored for display; it remains in stored outputs for traceability.
    """
    if not items:
        return []
    rows: list[str] = []
    for item in items:
        text = _safe_str(item.get("text")).strip()
        if text:
            rows.append(text)
    return rows


def _display_flag_list(values: list[str], *, lang: str) -> str:
    items = [flag_label(x, lang=lang) for x in values if isinstance(x, str) and x]
    if not items:
        return _label(lang, "none_documented")
    return ", ".join(items)


def _display_indicator_bullets(
    values: list[str],
    *,
    config: dict[str, Any],
    schema: dict[str, Any],
    lang: str,
    domain_id: str | None = None,
    include_domain: bool = False,
    empty_text: str,
) -> str:
    items = [
        indicator_label(
            x,
            config=config,
            schema=schema,
            lang=lang,
            domain_id=domain_id,
            include_domain=include_domain,
        )
        for x in values
        if isinstance(x, str) and x
    ]
    if not items:
        return empty_text
    return items


def _table_cell(value: Any, *, styles, label: bool = False) -> Paragraph:
    style = styles["PdfCellLabel"] if label else styles["PdfCell"]
    return _para(value, style)


def _table_cell_small(value: Any, *, styles, label: bool = False) -> Paragraph:
    style = styles["PdfCellLabelSmall"] if label else styles["PdfCellSmall"]
    return _para(value, style)


def _table(
    rows: list[list[Any]],
    *,
    col_widths: list[int],
    repeat_header: bool,
    header_background: colors.Color,
    grid_color: colors.Color,
    zebra: bool = False,
) -> Table:
    table = Table(
        rows,
        hAlign="LEFT",
        colWidths=col_widths,
        repeatRows=1 if repeat_header else 0,
        splitByRow=1,
    )
    style = [
        ("GRID", (0, 0), (-1, -1), 0.5, grid_color),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if repeat_header:
        style.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), header_background),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
        if zebra and len(rows) > 1:
            style.append(
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")])
            )
    elif zebra:
        style.append(
            ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")])
        )
    table.setStyle(TableStyle(style))
    return table


def _meta_line(label: str, value: Any, *, styles) -> Paragraph:
    return Paragraph(
        f"<b>{escape(label)}:</b> {escape(_safe_str(value))}",
        styles["PdfMeta"],
    )


def _display_completion_date(value: Any) -> str:
    raw = _safe_str(value).strip()
    if not raw:
        return ""
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return raw


def _summary_metric_table(*, styles, by_class: dict[str, Any]) -> Table:
    rows = [[
        _table_cell("Cleared", styles=styles, label=True),
        _table_cell("Watch", styles=styles, label=True),
        _table_cell("Elevated", styles=styles, label=True),
    ], [
        _table_cell(_safe_str(by_class.get("Cleared", 0)), styles=styles),
        _table_cell(_safe_str(by_class.get("Watch", 0)), styles=styles),
        _table_cell(_safe_str(by_class.get("Elevated", 0)), styles=styles),
    ]]
    return _table(
        rows,
        col_widths=[170, 170, 170],
        repeat_header=True,
        header_background=colors.HexColor("#E5E7EB"),
        grid_color=colors.HexColor("#CBD5E1"),
        zebra=False,
    )


def _start_section(
    story: list[Any],
    title: str,
    *,
    styles,
    style_name: str = "PdfSectionHeading",
    min_space: int = 110,
    spacer_after: int = 8,
) -> None:
    story.append(CondPageBreak(min_space))
    story.append(Paragraph(title, styles[style_name]))
    if spacer_after:
        story.append(Spacer(1, spacer_after))


def _confidence_key(label: str) -> str:
    v = _safe_str(label).strip().lower()
    if "high" in v or "alta" in v:
        return "high"
    if "moderate" in v or "moderada" in v:
        return "moderate"
    return "low"


def _normalize_tier_key(classification: str) -> str:
    """Canonical tier keys used by interpretation tables (display / copy only)."""
    v = _safe_str(classification).strip().lower()
    if v == "elevated":
        return "Elevated"
    if v == "watch":
        return "Watch"
    return "Cleared"


def _title_case_classification_display(value: str) -> str:
    """Safe title-style label for unknown or custom classification strings."""
    s = _safe_str(value).strip()
    if not s:
        return ""
    chunks = [c for c in re.split(r"[\s_\-/]+", s) if c]
    if not chunks:
        return ""
    if len(chunks) > 1:
        return " ".join(chunk[:1].upper() + chunk[1:].lower() for chunk in chunks)
    word = chunks[0]
    if len(word) == 1:
        return word.upper()
    if word.isupper():
        return word[:1].upper() + word[1:].lower()
    return word[:1].upper() + word[1:].lower()


def format_classification_display(value: str, *, lang: str) -> str:
    """
    Display-layer label for PDF/report output. Engine outputs and aggregation keys stay unchanged;
    this only affects rendered text.
    """
    raw = _safe_str(value).strip().lower()
    mapping = {
        "cleared": {"en": "Cleared", "es": "Sin observaciones"},
        "watch": {"en": "Watch", "es": "Vigilancia"},
        "elevated": {"en": "Elevated", "es": "Elevado"},
    }
    for key, labels in mapping.items():
        if raw == key:
            return labels.get(lang, labels["en"])
    return _title_case_classification_display(value)


def _localized_classification(value: str, *, lang: str) -> str:
    return format_classification_display(value, lang=lang)


def _localized_confidence(value: str, *, lang: str) -> str:
    key = _confidence_key(value)
    mapping = {
        "high": {"en": "High Confidence", "es": "Confianza Alta"},
        "moderate": {"en": "Moderate Confidence", "es": "Confianza Moderada"},
        "low": {"en": "Low Confidence", "es": "Confianza Baja"},
    }
    return mapping.get(key, mapping["low"]).get(lang, mapping["low"]["en"])


# Domain narrative leads: rotate by domain order (variant_index) to reduce repetitive openings.
_SECTION_INTERPRETATION_LEADS: dict[str, dict[str, list[str]]] = {
    "Cleared": {
        "en": [
            "Reported responses indicate stable routine structure with defined ownership and limited complexity exposure.",
            "For this domain, responses suggest predictable routines with defined responsibilities and contained structural load.",
            "Structural signals here align with steady coordination patterns and limited complexity exposure.",
        ],
        "es": [
            "Las respuestas reportadas indican una estructura de rutinas estable, con propiedad definida y exposicion limitada a complejidad.",
            "En este dominio, las respuestas sugieren rutinas predecibles con responsabilidades claras y complejidad acotada.",
            "Las senales estructurales aqui se alinean con rutinas estables y demandas de coordinacion contenidas.",
        ],
    },
    "Watch": {
        "en": [
            "Reported responses indicate functioning routines with moderate complexity exposure. Defined ownership and review intervals may support structural stability.",
            "For this domain, responses suggest functioning routines with moderate structural exposure; clearer ownership and review timing may help sustain stability.",
            "Structural signals here point to active coordination needs with moderate exposure to routine complexity.",
        ],
        "es": [
            "Las respuestas reportadas indican rutinas funcionales con exposicion moderada a complejidad. La propiedad definida y los intervalos de revision pueden apoyar la estabilidad estructural.",
            "Para este dominio, las respuestas senalan rutinas funcionales con exposicion moderada a la complejidad estructural.",
            "Las respuestas apuntan a coordinacion activa con intervalos de revision que pueden favorecer la estabilidad operativa.",
        ],
    },
    "Elevated": {
        "en": [
            "Reported responses indicate multiple interacting structural factors that may increase coordination demands over time. Structured review and clarification may be beneficial.",
            "For this domain, responses reflect several interacting structural factors that may increase coordination load over time; structured review may be useful.",
            "Structural signals indicate elevated interdependence; clarifying roles and review cadence may support more predictable routines.",
        ],
        "es": [
            "Las respuestas reportadas indican multiples factores estructurales interdependientes que pueden aumentar las demandas de coordinacion con el tiempo. Una revision estructurada y la clarificacion pueden ser beneficiosas.",
            "En este dominio, las respuestas reflejan varios factores estructurales interdependientes que pueden incrementar la carga de coordinacion.",
            "Las senales indican mayor complejidad estructural; una revision estructurada y la clarificacion pueden ser utiles.",
        ],
    },
}

_INDICATOR_INTERPRETATION: dict[str, dict[str, dict[str, str]]] = {
    "structural_complexity_exposure": {
        "watch": {
            "en": "This configuration requires coordination across multiple decision points. When ownership and review cadence are not clearly defined, routine variation may increase over time.",
            "es": "Esta configuracion requiere coordinacion entre multiples puntos de decision. Cuando la propiedad y la frecuencia de revision no estan claramente definidas, la variacion de rutinas puede aumentar con el tiempo.",
        },
        "elevated": {
            "en": "This configuration includes several interacting decision points without clearly defined ownership or scheduled review. Under fatigue or routine variation, structural drift may occur.",
            "es": "Esta configuracion incluye varios puntos de decision interdependientes sin propiedad claramente definida ni revision programada. Bajo cansancio o variacion de rutinas, puede presentarse deriva estructural.",
        },
    },
    "drift_conditions": {
        "watch": {
            "en": "Informal or temporary adjustments may stabilize into default patterns if not periodically reviewed.",
            "es": "Los ajustes informales o temporales pueden estabilizarse como patrones por defecto si no se revisan periodicamente.",
        },
        "elevated": {
            "en": "Frequent situational adjustments combined with no scheduled reassessment may increase long-term structural inconsistency.",
            "es": "Los ajustes situacionales frecuentes combinados con ausencia de reevaluacion programada pueden aumentar la inconsistencia estructural a largo plazo.",
        },
    },
    "ownership_clarity": {
        "watch": {
            "en": "Shared responsibility without defined escalation may lead to minor routine variation.",
            "es": "La responsabilidad compartida sin una escalacion definida puede generar variaciones menores en las rutinas.",
        },
        "elevated": {
            "en": "Absence of defined final authority may increase decision ambiguity during high-demand periods.",
            "es": "La ausencia de una autoridad final definida puede aumentar la ambiguedad en la toma de decisiones durante periodos de alta demanda.",
        },
    },
    "lock_in_reversibility_friction": {
        "watch": {
            "en": "Configuration adjustments may require moderate coordination to implement.",
            "es": "Los ajustes de configuracion pueden requerir coordinacion moderada para implementarse.",
        },
        "elevated": {
            "en": "Structural configuration may be difficult to adjust once routines stabilize, potentially limiting flexibility.",
            "es": "La configuracion estructural puede ser dificil de ajustar una vez que las rutinas se estabilizan, lo que puede limitar la flexibilidad.",
        },
    },
    "review_cadence": {
        "watch": {
            "en": "Establishing a defined review interval may support routine clarity over time.",
            "es": "Establecer un intervalo definido de revision puede apoyar la claridad de las rutinas con el tiempo.",
        },
        "elevated": {
            "en": "Absence of structured review intervals across domains may increase cumulative complexity.",
            "es": "La ausencia de intervalos estructurados de revision entre dominios puede aumentar la complejidad acumulada.",
        },
    },
}

_INDICATOR_INTERPRETATION_PRIORITY = [
    "structural_complexity_exposure",
    "drift_conditions",
    "ownership_clarity",
    "lock_in_reversibility_friction",
    "review_cadence",
]


def _classification_level_key(classification: str) -> str:
    return "elevated" if _safe_str(classification).strip().lower() == "elevated" else "watch"


def _section_interpretation_text(
    classification: str, report_language: str, *, variant_index: int = 0
) -> str:
    cls = _normalize_tier_key(classification)
    lang = report_language if report_language in ("en", "es") else "en"
    bucket = _SECTION_INTERPRETATION_LEADS.get(cls) or _SECTION_INTERPRETATION_LEADS["Cleared"]
    variants = bucket.get(lang) or bucket.get("en") or []
    if not variants:
        return ""
    return _safe_str(variants[variant_index % len(variants)]).strip()


def _indicator_interpretation_text(
    *,
    classification: str,
    report_language: str,
    triggered_indicators: list[str],
) -> str:
    triggered_set = {x for x in triggered_indicators if isinstance(x, str)}
    selected_indicator = ""
    for indicator in _INDICATOR_INTERPRETATION_PRIORITY:
        if indicator in triggered_set:
            selected_indicator = indicator
            break
    if not selected_indicator:
        return ""
    level = _classification_level_key(classification)
    by_level = _INDICATOR_INTERPRETATION.get(selected_indicator, {})
    by_lang = by_level.get(level, {})
    return _safe_str(by_lang.get(report_language) or by_lang.get("en")).strip()


def _domain_interpretation_text(
    *,
    config: dict[str, Any],
    domain_id: str,
    report_language: str,
    classification: str,
    confidence_marker: str,
    triggered_indicators: list[str],
    indicator_count: int,
    consideration_count: int,
    domain_index: int = 0,
) -> str:
    output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
    report_cfg = output_cfg.get("report") if isinstance(output_cfg.get("report"), dict) else {}
    default_lang = output_cfg.get("default_language") if isinstance(output_cfg.get("default_language"), str) else "en"
    by_domain = (
        report_cfg.get("domain_interpretation")
        if isinstance(report_cfg.get("domain_interpretation"), dict)
        else {}
    )
    domain_cfg = by_domain.get(domain_id) if isinstance(by_domain.get(domain_id), dict) else {}
    configured = domain_cfg.get(_confidence_key(confidence_marker))
    resolved = resolve_i18n_text(configured, lang=report_language, default_lang=default_lang)
    if resolved:
        return resolved.strip()

    _ = confidence_marker
    _ = indicator_count
    _ = consideration_count
    section_text = _section_interpretation_text(
        classification, report_language, variant_index=domain_index
    )
    indicator_text = _indicator_interpretation_text(
        classification=classification,
        report_language=report_language,
        triggered_indicators=triggered_indicators,
    )
    if indicator_text:
        return f"{section_text} {indicator_text}".strip()
    return section_text


def _report_text(config: dict[str, Any], key: str, lang: str, fallback: str) -> str:
    output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
    report_cfg = output_cfg.get("report") if isinstance(output_cfg.get("report"), dict) else {}
    static_copy = report_cfg.get("copy") if isinstance(report_cfg.get("copy"), dict) else {}
    default_lang = output_cfg.get("default_language") if isinstance(output_cfg.get("default_language"), str) else "en"
    source_value = static_copy.get(key)
    if isinstance(source_value, str):
        resolved = source_value if lang == default_lang else ""
    elif isinstance(source_value, dict):
        direct = source_value.get(lang)
        if isinstance(direct, str) and direct.strip():
            resolved = direct
        elif lang == default_lang:
            resolved = resolve_i18n_text(source_value, lang=lang, default_lang=default_lang)
        else:
            resolved = ""
    else:
        resolved = ""
    if not resolved:
        resolved = fallback
    return resolved.strip()


def _report_cfg_text(config: dict[str, Any], key: str, lang: str) -> str:
    """
    Lightweight, safe accessor for optional report-facing text blocks.
    Supports either a plain string or i18n dict ({en:..., es:...}).
    """
    output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
    report_cfg = output_cfg.get("report") if isinstance(output_cfg.get("report"), dict) else {}
    default_lang = output_cfg.get("default_language") if isinstance(output_cfg.get("default_language"), str) else "en"
    value = report_cfg.get(key)
    if isinstance(value, str):
        resolved = value if lang == default_lang else ""
    elif isinstance(value, dict):
        direct = value.get(lang)
        if isinstance(direct, str) and direct.strip():
            resolved = direct
        elif lang == default_lang:
            resolved = resolve_i18n_text(value, lang=lang, default_lang=default_lang)
        else:
            resolved = ""
    else:
        resolved = ""
    return resolved.strip()


def _report_cfg_str(config: dict[str, Any], key: str) -> str:
    output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
    report_cfg = output_cfg.get("report") if isinstance(output_cfg.get("report"), dict) else {}
    return _safe_str(report_cfg.get(key)).strip()


def _report_cfg_bool(config: dict[str, Any], key: str, *, default: bool) -> bool:
    output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
    report_cfg = output_cfg.get("report") if isinstance(output_cfg.get("report"), dict) else {}
    raw = report_cfg.get(key)
    if isinstance(raw, bool):
        return raw
    return default


def _is_watch_or_elevated(value: str) -> bool:
    return _safe_str(value).strip().lower() in {"watch", "elevated"}


def _is_elevated(value: str) -> bool:
    return _safe_str(value).strip().lower() == "elevated"


def _classification_badge_color(classification: str) -> colors.Color:
    v = _safe_str(classification).strip().lower()
    if v == "elevated":
        return colors.HexColor("#9B4A48")  # muted red
    if v == "watch":
        return colors.HexColor("#8C6D1F")  # muted amber
    return colors.HexColor("#3F6B52")  # muted green


def _triggered_structural_notes(*, classification: str, lang: str, indicators: list[str]) -> list[str]:
    level = _classification_level_key(classification)
    notes: list[str] = []
    for indicator in _INDICATOR_INTERPRETATION_PRIORITY:
        if indicator not in indicators:
            continue
        indicator_text = _INDICATOR_INTERPRETATION.get(indicator, {}).get(level, {})
        resolved = _safe_str(indicator_text.get(lang) or indicator_text.get("en")).strip()
        if resolved:
            notes.append(resolved)
    return notes


def _overall_short_summary(*, classification: str, lang: str) -> str:
    v = _safe_str(classification).strip().lower()
    if lang == "es":
        if v == "elevated":
            return "Las respuestas reportadas reflejan multiples factores estructurales que requieren coordinacion activa entre dominios."
        if v == "watch":
            return "Las respuestas reportadas reflejan rutinas funcionales con exposicion moderada a complejidad en dominios seleccionados."
        return "Las respuestas reportadas reflejan una estructura de rutinas generalmente estable con exposicion limitada a complejidad."
    if v == "elevated":
        return "Reported responses reflect multiple interacting structural factors requiring active cross-domain coordination."
    if v == "watch":
        return "Reported responses reflect functioning routines with moderate complexity exposure in selected domains."
    return "Reported responses reflect generally stable routine structure with limited complexity exposure."


def _cross_domain_compounding_note(*, domains: list[Any], lang: str) -> str:
    shared_indicator_groups = {"ownership_clarity", "drift_conditions", "review_cadence"}
    shared_pattern_present = any(
        sum(
            1
            for d in domains
            if indicator in getattr(d, "triggered_indicators", [])
        )
        >= 2
        for indicator in shared_indicator_groups
    )
    if not shared_pattern_present:
        return ""
    if lang == "es":
        return (
            "Patrones estructurales similares aparecen en multiples dominios. "
            "Abordar la claridad de propiedad y la frecuencia de revision en un area "
            "puede apoyar una estabilidad sistemica mas amplia."
        )
    return (
        "Similar structural patterns appear across multiple domains. "
        "Addressing ownership clarity and review cadence in one area may support broader system stability."
    )


def _elevated_global_note(*, elevated_domain_count: int, lang: str) -> str:
    if elevated_domain_count < 3:
        return ""
    if lang == "es":
        return (
            "Multiples dominios demuestran complejidad estructural elevada basada en los datos reportados. "
            "Esto no predice resultados, pero sugiere beneficio de una revision estructurada."
        )
    return (
        "Multiple domains demonstrate elevated structural complexity based on reported inputs. "
        "This does not predict outcomes but suggests benefit from structured review."
    )


def _safeguard_statement(*, elevated_domain_count: int, lang: str) -> str:
    if elevated_domain_count < 1:
        return ""
    if lang == "es":
        return (
            "La clasificacion refleja la configuracion estructural basada unicamente en informacion auto reportada. "
            "No evalua el cumplimiento medico o de seguridad y no predice dano."
        )
    return (
        "Classification reflects structural configuration based solely on self-reported information. "
        "It does not evaluate medical or safety compliance and does not predict harm."
    )


def build_single_submission_pdf_outline(
    report_data: SingleSubmissionSriReportData,
) -> list[str]:
    """
    Returns ordered section headings for the SRI parent-facing report.
    This is intentionally testable without parsing binary PDF output.
    """
    _ = report_data
    return [
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
    ]


class _DeterministicCanvas(canvas.Canvas):
    """
    Best-effort deterministic PDF metadata so PDF bytes are stable across runs.
    (ReportLab otherwise may embed timestamps into document info.)
    """

    _FIXED_PDF_DATE = "D:20000101000000Z"

    def __init__(self, *args, **kwargs):
        self._footer_text = _safe_str(kwargs.pop("footer_text", ""))
        self._show_footer = bool(kwargs.pop("show_footer", False))
        super().__init__(*args, **kwargs)
        try:
            info = getattr(self, "_doc", None) and getattr(self._doc, "info", None)
            if info:
                # These attributes exist on ReportLab's PDFInfo on most versions.
                for k, v in {
                    "title": "Inspection Report",
                    "author": "Inspection Engine",
                    "creator": "Inspection Engine",
                    "producer": "Inspection Engine",
                    "creationDate": self._FIXED_PDF_DATE,
                    "modDate": self._FIXED_PDF_DATE,
                }.items():
                    try:
                        setattr(info, k, v)
                    except Exception:
                        pass
        except Exception:
            # Never fail PDF generation due to metadata hardening.
            pass

    def _draw_footer(self) -> None:
        if not self._show_footer or not self._footer_text:
            return
        self.saveState()
        try:
            self.setFont("Helvetica", 9)
            self.setFillColor(colors.HexColor("#6B7280"))
            self.drawCentredString(LETTER[0] / 2.0, 20, self._footer_text)
        finally:
            self.restoreState()

    def showPage(self):
        self._draw_footer()
        super().showPage()

    def save(self):
        super().save()


def _extract_output_copy(
    *, config: dict[str, Any], output_language: str | None
) -> tuple[str, str, dict[str, str]]:
    """
    Returns (selected_language, intro_text, section_copy_by_id).

    Supported config shape (optional):
      config["output"] = {
        "default_language": "en",
        "languages": ["en", "es"],
        "copy": {
          "en": {"intro": "...", "sections": {"profile": "..."}},
          "es": {"intro": "...", "sections": {"profile": "..."}},
        }
      }
    """
    output = config.get("output") if isinstance(config.get("output"), dict) else {}
    copy = output.get("copy") if isinstance(output.get("copy"), dict) else {}

    allowed = output.get("languages") if isinstance(output.get("languages"), list) else list(copy.keys())
    allowed = [x for x in allowed if isinstance(x, str) and x]

    default_lang = output.get("default_language") if isinstance(output.get("default_language"), str) else None
    selected = output_language if isinstance(output_language, str) and output_language else default_lang
    if not selected:
        selected = allowed[0] if allowed else "en"

    if allowed and selected not in allowed:
        # Caller should validate, but keep PDF generation defensive.
        selected = default_lang or allowed[0]

    lang_copy = copy.get(selected) if isinstance(copy.get(selected), dict) else {}
    intro = lang_copy.get("intro") if isinstance(lang_copy.get("intro"), str) else ""
    sections = lang_copy.get("sections") if isinstance(lang_copy.get("sections"), dict) else {}
    sections = {k: v for k, v in sections.items() if isinstance(k, str) and isinstance(v, str)}
    return selected, intro, sections


def generate_single_submission_pdf(
    *,
    config: dict[str, Any],
    schema: dict[str, Any],
    outputs: dict[str, Any],
    output_language: str | None = None,
    report_data: SingleSubmissionSriReportData | None = None,
    inspection_id: str = "",
    completion_dt: Any = None,
    config_version_id: str | None = None,
    branding: dict[str, Any] | None = None,
) -> bytes:
    """
    Fixed layout. Dynamic content limited to:
      - section name
      - classification
      - selected output language (copy provided by config)
    """
    brand = branding if isinstance(branding, dict) else {}
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        title="Inspection Report",
        author="Inspection Engine",
    )

    styles = _build_pdf_styles()
    story = []

    if report_data is None:
        report_data = assemble_single_submission_sri_report_data(
            inspection_id=inspection_id,
            config=config,
            schema=schema,
            outputs=outputs,
            completion_dt=completion_dt,
            config_version_id=config_version_id,
        )

    title = _safe_str(schema.get("title") or "Inspection Report")
    report_lang = _safe_str(report_data.output_language or "en")
    localized_report_title = _label(report_lang, "report_title")
    brand_name = _safe_str(brand.get("hospital_program_name") or localized_report_title)
    brand_tagline = _safe_str(brand.get("tagline")).strip()
    brand_footer = _safe_str(brand.get("footer_text")).strip()
    brand_color = _safe_hex_color(_safe_str(brand.get("primary_color") or "#1F2937"))
    brand_logo_path = _safe_str(brand.get("logo_path"))

    # Report header
    if brand_logo_path:
        try:
            logo = Image(brand_logo_path, width=120, height=40, kind="proportional")
            logo.hAlign = "CENTER"
            story.append(logo)
            story.append(Spacer(1, 6))
        except Exception:
            # Keep PDF generation robust even if the stored logo file is unavailable.
            pass
    story.append(Paragraph(f'<font color="{brand_color}"><b>{escape(brand_name)}</b></font>', styles["PdfProgramTitle"]))
    if brand_tagline:
        story.append(Paragraph(escape(brand_tagline), styles["PdfMuted"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(escape(_label(report_lang, "report_title")), styles["PdfTitle"]))
    subtitle = _report_cfg_text(config, "report_subtitle", report_lang) or _label(report_lang, "report_subtitle")
    if subtitle:
        story.append(Paragraph(escape(subtitle), styles["Heading3"]))
    if report_lang != "es":
        story.append(Paragraph(escape(title), styles["Heading2"]))
    story.append(Spacer(1, 12))

    # Report-facing identity + metadata (client-required fields)
    overall_raw = _safe_str(report_data.overall_classification or "Cleared")
    overall = _localized_classification(overall_raw, lang=report_lang)
    inspection_display_id, report_display_ref = build_parent_display_ids(
        inspection_id=_safe_str(report_data.inspection_id),
        report_reference=_safe_str(report_data.inspection_standard_version),
        completion_date=_safe_str(report_data.completion_date),
    )
    story.append(_meta_line(_label(report_lang, "standard"), _SRI_STANDARD_DISPLAY_NAME, styles=styles))
    if inspection_display_id:
        story.append(_meta_line(_label(report_lang, "inspection_id"), inspection_display_id, styles=styles))
    program_ref = _safe_str(outputs.get("program_reference_number")).strip() or _report_cfg_str(config, "program_reference_number")
    if program_ref:
        story.append(_meta_line(_label(report_lang, "program_reference"), program_ref, styles=styles))
    if report_data.completion_date:
        story.append(
            _meta_line(
                _label(report_lang, "completion_date"),
                _display_completion_date(report_data.completion_date),
                styles=styles,
            )
        )
    # Preserve a reproducibility reference to the configuration/version in effect at generation time.
    if report_data.inspection_standard_version:
        story.append(
            _meta_line(
                _label(report_lang, "report_reference"),
                report_display_ref,
                styles=styles,
            )
        )
    story.append(
        _meta_line(
            _label(report_lang, "output_language"),
            language_label(_safe_str(report_data.output_language or report_lang), lang=report_lang),
            styles=styles,
        )
    )
    story.append(Spacer(1, 10))

    # Executive overview (client first-page structure)
    _start_section(story, _label(report_lang, "executive_overview"), styles=styles, min_space=170, spacer_after=0)
    story.append(
        Paragraph(
            _report_text(
                config,
                "executive_overview",
                report_lang,
                "This report presents a structured summary of observed coordination patterns across configured domains. "
                "It is informational and non-directive, and it should be interpreted in context with local operational review."
                if report_lang != "es"
                else "Este informe presenta un resumen estructurado de los patrones de coordinacion observados en los dominios configurados. "
                "Su fin es informativo y no directivo, y debe interpretarse en contexto con la revision operativa local.",
            ),
            styles["PdfBody"],
        )
    )
    story.append(Spacer(1, 6))
    story.append(_para(_overall_short_summary(classification=overall_raw, lang=report_lang), styles["PdfBody"]))
    story.append(Spacer(1, 16))

    # Overall classification block (textual label, grayscale-friendly)
    overall_rows = [
        [
            _table_cell(_label(report_lang, "classification_label"), styles=styles, label=True),
            _table_cell(overall, styles=styles),
        ],
        [
            _table_cell(_label(report_lang, "cross_domain_flags"), styles=styles, label=True),
            _table_cell(_display_flag_list(report_data.cross_domain_summary_flags, lang=report_lang), styles=styles),
        ],
    ]
    overall_table = _table(
        overall_rows,
        col_widths=[170, 340],
        repeat_header=False,
        header_background=colors.HexColor("#F3F4F6"),
        grid_color=colors.HexColor("#9CA3AF"),
    )
    story.append(
        KeepTogether(
            [
                CondPageBreak(120),
                Paragraph(_label(report_lang, "overall_classification"), styles["PdfSectionHeading"]),
                Table(
                    [[Paragraph(escape(overall), styles["PdfBadge"])]],
                    colWidths=[150],
                    hAlign="LEFT",
                    style=TableStyle(
                        [
                            ("BACKGROUND", (0, 0), (0, 0), _classification_badge_color(overall_raw)),
                            ("LEFTPADDING", (0, 0), (0, 0), 8),
                            ("RIGHTPADDING", (0, 0), (0, 0), 8),
                            ("TOPPADDING", (0, 0), (0, 0), 4),
                            ("BOTTOMPADDING", (0, 0), (0, 0), 4),
                            ("BOX", (0, 0), (0, 0), 0.5, colors.HexColor("#6B7280")),
                        ]
                    ),
                ),
                Spacer(1, 8),
                overall_table,
            ]
        )
    )
    story.append(Spacer(1, 16))

    # Priority review order (client spec: max 3)
    _start_section(story, _label(report_lang, "priority_review_order"), styles=styles, min_space=95)
    eligible_review = []
    for domain_id in report_data.priority_review_order or []:
        domain_obj = next((d for d in report_data.domains if d.domain_id == domain_id), None)
        if domain_obj and _is_watch_or_elevated(domain_obj.classification):
            eligible_review.append(domain_id)
    review_order = eligible_review[:3]
    if review_order:
        review_items: list[Paragraph] = []
        for idx, domain_id in enumerate(review_order, start=1):
            domain_title = next(
                (
                    d.domain_title
                    for d in report_data.domains
                    if d.domain_id == domain_id
                ),
                domain_label(domain_id, config=config, schema=schema, lang=report_lang),
            )
            review_items.append(_para(f"{idx}. {_safe_str(domain_title)}", styles["PdfBody"]))
        story.append(KeepTogether(review_items))
    else:
        story.append(_para(_label(report_lang, "priority_none"), styles["PdfBody"]))
    story.append(Spacer(1, 10))

    # Domain classification overview (spec requires table presentation for Spanish parent output).
    story.append(Paragraph(_label(report_lang, "domain_overview"), styles["PdfSectionHeading"]))
    story.append(_para(_label(report_lang, "confidence_note"), styles["PdfBody"]))
    story.append(Spacer(1, 6))
    overview_rows = [[
        _table_cell(_label(report_lang, "domain"), styles=styles, label=True),
        _table_cell(_label(report_lang, "classification"), styles=styles, label=True),
        _table_cell(_label(report_lang, "confidence_marker"), styles=styles, label=True),
    ]]
    for d in report_data.domains:
        overview_rows.append([
            _table_cell(_safe_str(d.domain_title), styles=styles),
            _table_cell(_localized_classification(d.classification, lang=report_lang), styles=styles),
            _table_cell(_localized_confidence(d.confidence_marker, lang=report_lang), styles=styles),
        ])
    story.append(
        _table(
            overview_rows,
            col_widths=[270, 120, 120],
            repeat_header=True,
            header_background=colors.HexColor("#E5E7EB"),
            grid_color=colors.HexColor("#D1D5DB"),
            zebra=True,
        )
    )
    story.append(Spacer(1, 12))

    # Domain detail sections
    story.append(
        KeepTogether(
            [
                CondPageBreak(110),
                Paragraph(_label(report_lang, "domain_details"), styles["Heading1"]),
                Paragraph(
                    _label(report_lang, "domain_details_intro"),
                    styles["PdfBody"],
                ),
                Spacer(1, 12),
            ]
        )
    )
    for domain_index, domain in enumerate(report_data.domains):
        section_story: list[Any] = [Paragraph(_safe_str(domain.domain_title), styles["Heading2"])]
        consideration_lines = _render_considerations(domain.structural_considerations, lang=report_lang)
        summary_rows = [[
            _table_cell(_label(report_lang, "classification"), styles=styles, label=True),
            _table_cell(_localized_classification(domain.classification, lang=report_lang), styles=styles),
            _table_cell(_label(report_lang, "confidence_marker"), styles=styles, label=True),
            _table_cell(_localized_confidence(domain.confidence_marker, lang=report_lang), styles=styles),
        ]]
        summary_table = _table(
            summary_rows,
            col_widths=[95, 140, 110, 165],
            repeat_header=False,
            header_background=colors.white,
            grid_color=colors.HexColor("#D1D5DB"),
        )
        section_story.append(summary_table)
        section_story.append(Spacer(1, 8))
        section_story.append(
            Paragraph(
                f"<b>{escape(_label(report_lang, 'domain_interpretation'))}:</b> "
                f"{escape(_domain_interpretation_text(config=config, domain_id=domain.domain_id, report_language=report_lang, classification=domain.classification, confidence_marker=_localized_confidence(domain.confidence_marker, lang=report_lang), triggered_indicators=domain.triggered_indicators, indicator_count=len(domain.triggered_indicators), consideration_count=len(domain.structural_considerations), domain_index=domain_index))}",
                styles["PdfBody"],
            )
        )
        section_story.append(Spacer(1, 6))
        indicator_text = _display_indicator_bullets(
            domain.triggered_indicators,
            config=config,
            schema=schema,
            lang=report_lang,
            domain_id=domain.domain_id,
            empty_text=_label(report_lang, "no_structural_indicators"),
        )
        section_story.append(Paragraph(f"<b>{escape(_label(report_lang, 'structural_indicators'))}:</b>", styles["PdfBody"]))
        section_story.append(
            _para(_safe_str(indicator_text), styles["PdfBody"]) if isinstance(indicator_text, str) else Spacer(1, 0)
        )
        if isinstance(indicator_text, list):
            section_story.extend(_bullet_paragraphs(indicator_text, styles=styles))
        section_story.append(Spacer(1, 6))
        section_story.append(Paragraph(f"<b>{escape(_label(report_lang, 'selected_structural_considerations'))}:</b>", styles["PdfBody"]))
        if consideration_lines:
            section_story.extend(_bullet_paragraphs(consideration_lines, styles=styles))
        else:
            section_story.append(_para(_label(report_lang, "no_structural_considerations"), styles["PdfBody"]))
        triggered_notes = _triggered_structural_notes(
            classification=domain.classification,
            lang=report_lang,
            indicators=domain.triggered_indicators,
        )
        if triggered_notes:
            section_story.append(Spacer(1, 6))
            section_story.append(Paragraph(f"<b>{escape(_label(report_lang, 'triggered_structural_notes'))}:</b>", styles["PdfBody"]))
            section_story.extend(_bullet_paragraphs(triggered_notes, styles=styles))
        story.append(CondPageBreak(140))
        story.append(KeepTogether(section_story))
        story.append(Spacer(1, 14))

    # Cross-domain system analysis
    story.append(
        KeepTogether(
            [
                CondPageBreak(120),
                Paragraph(_label(report_lang, "cross_domain_system_analysis"), styles["Heading1"]),
                Paragraph(
                    _report_text(
                        config,
                        "cross_domain_summary",
                        report_lang,
                        "This section summarizes whether cross-domain escalation criteria were triggered in the configured model."
                        if report_lang != "es"
                        else "Esta seccion resume si se activaron criterios de escalamiento entre dominios en el modelo configurado.",
                    ),
                    styles["PdfBody"],
                ),
                Spacer(1, 8),
            ]
        )
    )
    story.append(
        Paragraph(
            f"<b>{escape(_label(report_lang, 'cross_domain_flags'))}:</b> "
            f"{escape(_display_flag_list(report_data.cross_domain_summary_flags, lang=report_lang))}",
            styles["PdfBody"],
        )
    )
    cross_domain_compounding = _cross_domain_compounding_note(domains=report_data.domains, lang=report_lang)
    if cross_domain_compounding:
        story.append(Spacer(1, 6))
        story.append(_para(cross_domain_compounding, styles["PdfBody"]))

    elevated_domain_count = sum(1 for d in report_data.domains if _is_elevated(d.classification))
    elevated_statement = _report_text(
        config,
        "cross_domain_elevated_statement",
        report_lang,
        _elevated_global_note(elevated_domain_count=elevated_domain_count, lang=report_lang),
    )
    if elevated_statement:
        story.append(Spacer(1, 6))
        story.append(_para(elevated_statement, styles["PdfBody"]))
    story.append(Spacer(1, 10))
    story.append(Paragraph(f"<b>{escape(_label(report_lang, 'triggered_indicator_groups'))}:</b>", styles["PdfBody"]))
    for domain in report_data.domains:
        indicator_items = [
            indicator_label(x, config=config, schema=schema, lang=report_lang, domain_id=domain.domain_id)
            for x in report_data.triggered_indicators.get(domain.domain_id, [])
            if isinstance(x, str) and x
        ]
        story.extend(
            _bullet_paragraphs(
                [f"{_safe_str(domain.domain_title)}: {', '.join(indicator_items) or _label(report_lang, 'none_documented')}"],
                styles=styles,
            )
        )
    # Structural strengths
    story.append(
        KeepTogether(
            [
                CondPageBreak(100),
                Paragraph(_label(report_lang, "structural_strengths"), styles["Heading1"]),
                Paragraph(
                    _report_text(
                        config,
                        "structural_strengths_intro",
                        report_lang,
                        "Strengths identify areas with relatively stable and clearly defined coordination patterns in this submission."
                        if report_lang != "es"
                        else "Las fortalezas identifican areas con patrones de coordinacion relativamente estables y claramente definidos en esta respuesta.",
                    ),
                    styles["PdfBody"],
                ),
                Spacer(1, 8),
            ]
        )
    )
    if report_data.strengths_data:
        for item in report_data.strengths_data:
            strength_text = f"{_safe_str(item.get('title'))}: {_safe_str(item.get('description'))}".strip(": ")
            story.extend(_bullet_paragraphs([strength_text], styles=styles))
    else:
        story.append(_para(_label(report_lang, "no_strengths"), styles["PdfBody"]))
    # Methodology overview
    _start_section(story, _label(report_lang, "methodology_overview"), styles=styles, style_name="Heading1", min_space=90, spacer_after=0)
    story.append(_para(_safe_str(report_data.methodology_scope.get("methodology")), styles["PdfBody"]))
    story.append(Spacer(1, 14))

    # Final scope and limitations
    _start_section(story, _label(report_lang, "scope_limitations"), styles=styles, style_name="Heading1", min_space=110, spacer_after=0)
    story.append(_para(_safe_str(report_data.methodology_scope.get("scope")), styles["PdfBody"]))
    story.append(Spacer(1, 8))
    story.append(
        Paragraph(
            _report_text(
                config,
                "scope_limitations_notice",
                report_lang,
                "This report is informational and structural in scope. It does not provide medical advice, diagnostic conclusions, or prescriptive directives; it does not determine safety, compliance, or medical risk; and it does not replace clinical care. Outputs reflect self-reported information interpreted through deterministic rule logic. Healthcare providers retain full clinical judgment and responsibility for care decisions."
                if report_lang != "es"
                else "Este informe es informativo y de alcance estructural. No proporciona asesoramiento medico, conclusiones diagnosticas ni directrices prescriptivas; no determina seguridad, cumplimiento ni riesgo medico; y no reemplaza la atencion clinica. Los resultados reflejan informacion auto reportada interpretada mediante logica deterministica de reglas. Los profesionales de salud mantienen el juicio clinico completo y la responsabilidad de las decisiones de cuidado.",
            ),
            styles["PdfBody"],
        )
    )
    safeguard_statement = _safeguard_statement(elevated_domain_count=elevated_domain_count, lang=report_lang)
    if safeguard_statement:
        story.append(Spacer(1, 6))
        story.append(_para(safeguard_statement, styles["PdfBody"]))
        story.append(Spacer(1, 8))

    # Institutional resources placeholder (client-requested)
    resources_heading = _label(report_lang, "additional_resources_for_program").format(program=brand_name)
    _start_section(story, resources_heading, styles=styles, style_name="Heading1", min_space=110, spacer_after=0)
    resources_text = _report_cfg_text(config, "institutional_resources_placeholder", report_lang)
    if not resources_text:
        resources_text = (
            "Los recursos institucionales pueden documentarse aqui (por ejemplo, contactos internos, protocolos locales o apoyos especificos del programa). "
            "Esta seccion es intencionalmente no directiva y puede ser completada por la institucion."
            if report_lang == "es"
            else "Institutional resources may be documented here (e.g., internal contacts, local protocols, or program-specific supports). "
            "This section is intentionally non-directive and may be completed by the institution."
        )
    story.append(_para(resources_text, styles["PdfBody"]))
    story.append(Spacer(1, 8))

    show_footer = _report_cfg_bool(config, "show_footer", default=True)
    footer_text = brand_footer or _DEFAULT_REPORT_FOOTER
    def _canvas_maker(*args, **kwargs):
        return _DeterministicCanvas(
            *args,
            footer_text=footer_text,
            show_footer=show_footer,
            **kwargs,
        )

    doc.build(story, canvasmaker=_canvas_maker)
    return buffer.getvalue()


def generate_aggregated_pdf(
    *,
    config: dict[str, Any],
    schema: dict[str, Any],
    counts: dict[str, Any],
    output_language: str | None = None,
    inspection_id: str | None = None,
    config_version_id: str | None = None,
    branding: dict[str, Any] | None = None,
) -> bytes:
    """
    Fixed layout. Dynamic content limited to:
      - section name
      - counts (aggregated)
      - classification (aggregated)
      - selected output language (copy provided by config)
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=LETTER,
        title="Aggregated Inspection Report",
        author="Inspection Engine",
    )

    styles = _build_pdf_styles()
    story = []

    title = _safe_str(schema.get("title") or "Aggregated Inspection Report")
    story.append(Paragraph("Operational Summary Report", styles["PdfTitle"]))
    story.append(Paragraph(escape(title), styles["Heading2"]))
    story.append(Spacer(1, 8))
    selected_lang, intro, section_copy = _extract_output_copy(config=config, output_language=output_language)

    brand = branding if isinstance(branding, dict) else {}
    program_name = _safe_str(brand.get("hospital_program_name")).strip()
    if program_name:
        story.append(_meta_line(_label(selected_lang, "program"), program_name, styles=styles))
    if inspection_id:
        story.append(_meta_line(_label(selected_lang, "inspection_id"), inspection_id, styles=styles))
    story.append(_meta_line(_label(selected_lang, "generated"), datetime.utcnow().strftime("%b %d, %Y"), styles=styles))
    story.append(_meta_line(_label(selected_lang, "standard"), _SRI_STANDARD_DISPLAY_NAME, styles=styles))
    if config_version_id:
        story.append(_meta_line(_label(selected_lang, "report_reference"), _safe_str(config_version_id), styles=styles))
        story.append(Spacer(1, 10))

    if intro:
        story.append(_para(_safe_str(intro), styles["PdfMuted"]))
        story.append(Spacer(1, 12))

    by_class = counts.get("by_classification", {}) or {}
    total_submissions = _safe_int(counts.get("total_submissions", 0))
    story.append(
        KeepTogether(
            [
                CondPageBreak(120),
                Paragraph("Summary counts", styles["PdfSectionHeading"]),
                _meta_line("Total submissions", total_submissions, styles=styles),
                Spacer(1, 8),
                _summary_metric_table(styles=styles, by_class=by_class),
            ]
        )
    )
    story.append(Spacer(1, 16))

    _start_section(story, "Counts by section", styles=styles, min_space=140)

    section_counts = counts.get("by_section", {}) or {}
    rows = [[
        _table_cell("Section", styles=styles, label=True),
        _table_cell("Cleared", styles=styles, label=True),
        _table_cell("Watch", styles=styles, label=True),
        _table_cell("Elevated", styles=styles, label=True),
    ]]
    for section in schema.get("sections", []) or []:
        sid = section.get("id")
        sname = section.get("title") or sid
        sc = section_counts.get(sid, {}) or {}
        rows.append(
            [
                _table_cell(_safe_str(sname), styles=styles),
                _table_cell(_safe_str(sc.get("Cleared", 0)), styles=styles),
                _table_cell(_safe_str(sc.get("Watch", 0)), styles=styles),
                _table_cell(_safe_str(sc.get("Elevated", 0)), styles=styles),
            ]
        )

    table = _table(
        rows,
        col_widths=[270, 80, 80, 80],
        repeat_header=True,
        header_background=colors.HexColor("#E9EDF5"),
        grid_color=colors.HexColor("#CBD5E1"),
        zebra=True,
    )
    story.append(table)
    story.append(Spacer(1, 16))

    # QuietRisk MVP: counts by indicator tags
    _start_section(story, "Counts by indicator tag", styles=styles, min_space=160)
    tag_counts = counts.get("tag_counts") if isinstance(counts.get("tag_counts"), dict) else {}
    tag_rows = [[_table_cell("Tag", styles=styles, label=True), _table_cell("Count", styles=styles, label=True)]]
    for tag, cnt in sorted(tag_counts.items(), key=lambda kv: (-_safe_int(kv[1]), str(kv[0]))):
        tag_rows.append(
            [
                _table_cell(tag_label(tag, config=config, schema=schema, lang=selected_lang), styles=styles),
                _table_cell(_safe_str(cnt), styles=styles),
            ]
        )
    tag_table = _table(
        tag_rows,
        col_widths=[400, 110],
        repeat_header=True,
        header_background=colors.HexColor("#E9EDF5"),
        grid_color=colors.HexColor("#CBD5E1"),
        zebra=True,
    )
    story.append(tag_table)
    story.append(Spacer(1, 16))

    # QuietRisk MVP: top repeated risk patterns
    _start_section(story, "Top repeated risk patterns", styles=styles, min_space=150)
    top_patterns = counts.get("top_patterns") if isinstance(counts.get("top_patterns"), list) else []
    pat_rows = [[_table_cell("Pattern", styles=styles, label=True), _table_cell("Count", styles=styles, label=True)]]
    for item in top_patterns:
        if isinstance(item, dict):
            pat_rows.append(
                [
                    _table_cell(pattern_label(_safe_str(item.get("pattern")), lang=selected_lang), styles=styles),
                    _table_cell(_safe_str(item.get("count", 0)), styles=styles),
                ]
            )
    pat_table = _table(
        pat_rows,
        col_widths=[400, 110],
        repeat_header=True,
        header_background=colors.HexColor("#E9EDF5"),
        grid_color=colors.HexColor("#CBD5E1"),
        zebra=True,
    )
    story.append(pat_table)
    story.append(Spacer(1, 16))

    # SRI-aligned summary without expanding scope into dashboards.
    _start_section(story, "Cross-domain summary flags", styles=styles, min_space=100)
    cross_flags = (
        counts.get("cross_domain_flag_counts")
        if isinstance(counts.get("cross_domain_flag_counts"), dict)
        else {}
    )
    cross_rows = [[_table_cell("Flag", styles=styles, label=True), _table_cell("Count", styles=styles, label=True)]]
    for flag, cnt in sorted(cross_flags.items(), key=lambda kv: (-_safe_int(kv[1]), str(kv[0]))):
        cross_rows.append([
            _table_cell(flag_label(flag, lang=selected_lang), styles=styles),
            _table_cell(_safe_str(cnt), styles=styles),
        ])
    cross_table = _table(
        cross_rows,
        col_widths=[400, 110],
        repeat_header=True,
        header_background=colors.HexColor("#E9EDF5"),
        grid_color=colors.HexColor("#CBD5E1"),
        zebra=True,
    )
    story.append(cross_table)
    story.append(Spacer(1, 16))

    _start_section(story, "Indicator signal totals by domain", styles=styles, min_space=130)
    signal_totals = (
        counts.get("indicator_signal_totals_by_domain")
        if isinstance(counts.get("indicator_signal_totals_by_domain"), dict)
        else {}
    )
    sig_rows = [[
        _table_cell("Domain", styles=styles, label=True),
        _table_cell("Moderate", styles=styles, label=True),
        _table_cell("High", styles=styles, label=True),
    ]]
    for section in schema.get("sections", []) or []:
        sid = section.get("id")
        if not isinstance(sid, str):
            continue
        title = _safe_str(section.get("title") or sid)
        vals = signal_totals.get(sid, {}) if isinstance(signal_totals.get(sid), dict) else {}
        sig_rows.append(
            [
                _table_cell(title, styles=styles),
                _table_cell(_safe_str(vals.get("moderate", 0)), styles=styles),
                _table_cell(_safe_str(vals.get("high", 0)), styles=styles),
            ]
        )
    sig_table = _table(
        sig_rows,
        col_widths=[300, 105, 105],
        repeat_header=True,
        header_background=colors.HexColor("#E9EDF5"),
        grid_color=colors.HexColor("#CBD5E1"),
        zebra=True,
    )
    # Keep the final output-language line with the last table to avoid an orphan last page.
    story.append(
        KeepTogether(
            [
                sig_table,
                Spacer(1, 6),
                Paragraph(
                    f"<b>Output language:</b> {escape(language_label(_safe_str(selected_lang), lang=selected_lang))}",
                    styles["PdfMeta"],
                ),
            ]
        )
    )
    for section in schema.get("sections", []) or []:
        sid = section.get("id")
        sname = section.get("title") or sid
        text = section_copy.get(str(sid)) if sid is not None else None
        if text:
            story.append(Spacer(1, 10))
            story.append(Paragraph(f"<b>{_safe_str(sname)}</b>", styles["Heading3"]))
            story.append(_para(_safe_str(text), styles["PdfBody"]))
            story.append(Spacer(1, 8))

    doc.build(story, canvasmaker=_DeterministicCanvas)
    return buffer.getvalue()

