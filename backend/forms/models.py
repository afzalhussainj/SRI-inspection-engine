import hashlib
import json
import uuid

from django.core.files.base import ContentFile
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from .considerations_library import build_canonical_considerations_by_question

# Spanish labels for every select option *value* id used in the SRI schema (stable scoring values unchanged).
_SRI_OPTION_LABELS_ES: dict[str, str] = {
    "discussion_based_agreement": "Acuerdo basado en conversación",
    "easy": "Fácil",
    "frequently": "Con frecuencia",
    "informal_checkins": "Revisiones informales",
    "informal_plan": "Plan informal para volver a revisar",
    "informally_planned": "Planificado de forma informal",
    "moderate_effort": "Esfuerzo moderado",
    "mostly": "En su mayor parte",
    "multiple_individuals": "Varias personas",
    "multiple_levels": "No, varios niveles",
    "multiple_rotating_locations": "Varias ubicaciones rotativas",
    "named_decision_authority": "Autoridad nominal para decidir",
    "named_individual": "Persona nominal",
    "no_clear_authority": "Sin autoridad clara",
    "no_defined_escalation": "Sin regla definida de escalamiento",
    "no_defined_final_authority": "Sin autoridad final definida",
    "no_defined_review_point": "Sin punto de revisión definido",
    "no_plan": "Sin plan",
    "no_review_plan": "Sin plan de revisión identificado",
    "not_discussed": "No conversado",
    "not_sure": "No está seguro",
    "not_yet_determined": "Aún no determinado",
    "not_yet_installed": "Aún no instalado",
    "occasionally": "Ocasionalmente",
    "occasionally_unclear": "Ocasionalmente poco claro",
    "often_unclear": "A menudo poco claro",
    "one": "Uno",
    "one_adult_consistently": "Un adulto de manera consistente",
    "one_central_location": "Una ubicación central",
    "one_named_individual": "Una persona nominal",
    "rarely": "Rara vez",
    "scheduled": "Sí (programado)",
    "shared_authority": "Autoridad compartida",
    "shared_equally": "Compartido por igual",
    "shared_without_escalation": "Compartido sin regla de escalamiento",
    "shared_without_final_authority": "Decisión compartida sin autoridad final",
    "significant_effort": "Esfuerzo significativo",
    "single_primary_location": "Sí, una ubicación principal",
    "situational_whoever_present": "Situacional / quien esté presente",
    "sometimes": "A veces",
    "three_or_more": "Tres o más",
    "three_or_more_adults": "Tres o más adultos pueden responder",
    "three_or_more_areas": "Tres o más áreas",
    "two": "Dos",
    "two_adults_share_response": "Dos adultos comparten la respuesta",
    "two_areas": "Dos áreas",
    "two_common_locations": "Dos ubicaciones comunes",
    "unsure": "No está seguro",
    "varies_daily": "Varía cada día",
    "yes": "Sí",
    "yes_clearly_defined": "Sí, claramente definido",
}


def _build_questionnaire_option_values(schema: dict) -> dict[str, dict[str, str]]:
    """
    Full en/es labels per option value for localize_schema(); English matches schema option labels.
    """
    value_to_en: dict[str, str] = {}
    for section in schema.get("sections", []) or []:
        for field in section.get("fields", []) or []:
            for opt in field.get("options", []) or []:
                if not isinstance(opt, dict):
                    continue
                v = opt.get("value")
                if not isinstance(v, str) or not v:
                    continue
                if v not in value_to_en:
                    value_to_en[v] = opt.get("label", v) if isinstance(opt.get("label"), str) else v
    out: dict[str, dict[str, str]] = {}
    for value_id, en_label in sorted(value_to_en.items()):
        es = _SRI_OPTION_LABELS_ES.get(value_id)
        if es is None:
            raise ValueError(
                f"SRI_OPTION_LABELS_ES missing Spanish for option value {value_id!r}. "
                "Add a translation in models._SRI_OPTION_LABELS_ES."
            )
        out[value_id] = {"en": en_label, "es": es}
    return out


def default_base_config() -> dict:
    """
    Minimal base template config to start from.
    Admin can extend/minimize per recipient by editing the JSON in a draft config version,
    then publishing it.
    """
    schema = {
            "title": "Structured Wellbeing Risk Inspection",
            "sections": [
                {
                    "id": "overnight_sleep_routines",
                    "title": "Overnight Coverage & Sleep Routines",
                    "fields": [
                        {
                            "id": "overnight_responders_count",
                            "type": "select",
                            "label": "How many adults may respond overnight if the infant wakes?",
                            "required": True,
                            "options": [
                                {"value": "one_adult_consistently", "label": "One adult consistently"},
                                {"value": "two_adults_share_response", "label": "Two adults share response"},
                                {"value": "three_or_more_adults", "label": "Three or more adults may respond"},
                                {"value": "not_yet_determined", "label": "Not yet determined"},
                            ],
                            "meta": {"sri_question_number": 1},
                        },
                        {
                            "id": "overnight_final_decision_authority",
                            "type": "select",
                            "label": "Is one adult identified as the final decision-maker for overnight changes?",
                            "required": True,
                            "options": [
                                {"value": "yes", "label": "Yes"},
                                {
                                    "value": "shared_without_final_authority",
                                    "label": "Shared decision without final authority",
                                },
                                {"value": "no_defined_final_authority", "label": "No defined final decision authority"},
                            ],
                            "meta": {"sri_question_number": 2},
                        },
                        {
                            "id": "overnight_routine_variability",
                            "type": "select",
                            "label": "Are sleep routines expected to change depending on fatigue or circumstances?",
                            "required": True,
                            "options": [
                                {"value": "rarely", "label": "Rarely"},
                                {"value": "occasionally", "label": "Occasionally"},
                                {"value": "frequently", "label": "Frequently"},
                                {"value": "not_discussed", "label": "Not discussed"},
                            ],
                            "meta": {"sri_question_number": 3},
                        },
                        {
                            "id": "overnight_review_date_set",
                            "type": "select",
                            "label": "Has a review date been set to revisit overnight routines?",
                            "required": True,
                            "options": [
                                {"value": "scheduled", "label": "Yes (scheduled)"},
                                {"value": "informal_plan", "label": "Informal plan to revisit"},
                                {"value": "no_review_plan", "label": "No review plan identified"},
                            ],
                            "meta": {"sri_question_number": 4},
                        },
                    ],
                },
                {
                    "id": "feeding_daytime_care",
                    "title": "Feeding & Daytime Care Coordination",
                    "fields": [
                        {
                            "id": "daytime_primary_caregiver",
                            "type": "select",
                            "label": "Is there a primary daytime caregiver?",
                            "required": True,
                            "options": [
                                {"value": "yes_clearly_defined", "label": "Yes, clearly defined"},
                                {"value": "shared_equally", "label": "Shared equally"},
                                {"value": "varies_daily", "label": "Varies daily"},
                                {"value": "not_yet_determined", "label": "Not yet determined"},
                            ],
                            "meta": {"sri_question_number": 5},
                        },
                        {
                            "id": "feeding_locations_consistency",
                            "type": "select",
                            "label": "Are feeding locations consistent?",
                            "required": True,
                            "options": [
                                {"value": "single_primary_location", "label": "Yes, single primary location"},
                                {"value": "two_common_locations", "label": "Two common locations"},
                                {"value": "multiple_rotating_locations", "label": "Multiple rotating locations"},
                            ],
                            "meta": {"sri_question_number": 6},
                        },
                        {
                            "id": "feeding_change_decision_process",
                            "type": "select",
                            "label": "If feeding routines change, how are changes decided?",
                            "required": True,
                            "options": [
                                {"value": "named_decision_authority", "label": "Named decision authority"},
                                {"value": "discussion_based_agreement", "label": "Discussion-based agreement"},
                                {"value": "situational_whoever_present", "label": "Situational / whoever is present"},
                                {"value": "not_discussed", "label": "Not discussed"},
                            ],
                            "meta": {"sri_question_number": 7},
                        },
                        {
                            "id": "feeding_review_checkin",
                            "type": "select",
                            "label": "Is there a scheduled check-in to revisit feeding routines?",
                            "required": True,
                            "options": [
                                {"value": "yes", "label": "Yes"},
                                {"value": "informal_checkins", "label": "Informal check-ins"},
                                {"value": "no_defined_review_point", "label": "No defined review point"},
                            ],
                            "meta": {"sri_question_number": 8},
                        },
                    ],
                },
                {
                    "id": "transport_equipment_configuration",
                    "title": "Transport & Equipment Configuration",
                    "fields": [
                        {
                            "id": "transport_regular_vehicle_count",
                            "type": "select",
                            "label": "How many vehicles will regularly transport the infant?",
                            "required": True,
                            "options": [
                                {"value": "one", "label": "One"},
                                {"value": "two", "label": "Two"},
                                {"value": "three_or_more", "label": "Three or more"},
                            ],
                            "meta": {"sri_question_number": 9},
                        },
                        {
                            "id": "transport_equipment_installer_clarity",
                            "type": "select",
                            "label": "Who installed or verified equipment (e.g., car seat)?",
                            "required": True,
                            "options": [
                                {"value": "one_named_individual", "label": "One named individual"},
                                {"value": "multiple_individuals", "label": "Multiple individuals"},
                                {"value": "unsure", "label": "Unsure"},
                                {"value": "not_yet_installed", "label": "Not yet installed"},
                            ],
                            "meta": {"sri_question_number": 10},
                        },
                        {
                            "id": "transport_configuration_change_frequency",
                            "type": "select",
                            "label": "How often is equipment configuration expected to change?",
                            "required": True,
                            "options": [
                                {"value": "rarely", "label": "Rarely"},
                                {"value": "occasionally", "label": "Occasionally"},
                                {"value": "frequently", "label": "Frequently"},
                                {"value": "not_discussed", "label": "Not discussed"},
                            ],
                            "meta": {"sri_question_number": 11},
                        },
                        {
                            "id": "transport_configuration_authority",
                            "type": "select",
                            "label": "If configuration concerns arise, who has authority to modify it?",
                            "required": True,
                            "options": [
                                {"value": "named_individual", "label": "Named individual"},
                                {"value": "shared_authority", "label": "Shared authority"},
                                {"value": "no_clear_authority", "label": "No clear authority"},
                                {"value": "not_discussed", "label": "Not discussed"},
                            ],
                            "meta": {"sri_question_number": 12},
                        },
                    ],
                },
                {
                    "id": "home_layout_environmental_access",
                    "title": "Home Layout & Environmental Access",
                    "fields": [
                        {
                            "id": "home_single_level_caregiving",
                            "type": "select",
                            "label": "Is caregiving primarily conducted on one level of the home?",
                            "required": True,
                            "options": [
                                {"value": "yes", "label": "Yes"},
                                {"value": "multiple_levels", "label": "No, multiple levels"},
                                {"value": "not_yet_determined", "label": "Not yet determined"},
                            ],
                            "meta": {"sri_question_number": 13},
                        },
                        {
                            "id": "home_supply_storage_distribution",
                            "type": "select",
                            "label": "Are essential supplies stored in one location or multiple areas?",
                            "required": True,
                            "options": [
                                {"value": "one_central_location", "label": "One central location"},
                                {"value": "two_areas", "label": "Two areas"},
                                {"value": "three_or_more_areas", "label": "Three or more areas"},
                            ],
                            "meta": {"sri_question_number": 14},
                        },
                        {
                            "id": "home_nighttime_room_movement_frequency",
                            "type": "select",
                            "label": "During nighttime routines, is movement between rooms required?",
                            "required": True,
                            "options": [
                                {"value": "rarely", "label": "Rarely"},
                                {"value": "sometimes", "label": "Sometimes"},
                                {"value": "frequently", "label": "Frequently"},
                                {"value": "not_discussed", "label": "Not discussed"},
                            ],
                            "meta": {"sri_question_number": 15},
                        },
                        {
                            "id": "home_setup_change_difficulty",
                            "type": "select",
                            "label": "If environmental setup needs to change, how difficult would that be?",
                            "required": True,
                            "options": [
                                {"value": "easy", "label": "Easy"},
                                {"value": "moderate_effort", "label": "Moderate effort"},
                                {"value": "significant_effort", "label": "Significant effort"},
                                {"value": "not_sure", "label": "Not sure"},
                            ],
                            "meta": {"sri_question_number": 16},
                        },
                    ],
                },
                {
                    "id": "ownership_review_cadence",
                    "title": "Ownership & Review Cadence",
                    "fields": [
                        {
                            "id": "caregiver_responsibility_clarity",
                            "type": "select",
                            "label": "Are responsibilities clearly divided among caregivers?",
                            "required": True,
                            "options": [
                                {"value": "yes", "label": "Yes"},
                                {"value": "mostly", "label": "Mostly"},
                                {"value": "occasionally_unclear", "label": "Occasionally unclear"},
                                {"value": "often_unclear", "label": "Often unclear"},
                            ],
                            "meta": {"sri_question_number": 17},
                        },
                        {
                            "id": "caregiver_disagreement_final_authority",
                            "type": "select",
                            "label": "If disagreements arise, is there a final decision authority?",
                            "required": True,
                            "options": [
                                {"value": "yes", "label": "Yes"},
                                {"value": "shared_without_escalation", "label": "Shared without escalation rule"},
                                {"value": "no_defined_escalation", "label": "No defined escalation rule"},
                            ],
                            "meta": {"sri_question_number": 18},
                        },
                        {
                            "id": "routine_reassessment_timeline_set",
                            "type": "select",
                            "label": "Has a timeline been set to reassess routines as circumstances change?",
                            "required": True,
                            "options": [
                                {"value": "yes", "label": "Yes"},
                                {"value": "informally_planned", "label": "Informally planned"},
                                {"value": "no_plan", "label": "No plan"},
                            ],
                            "meta": {"sri_question_number": 19},
                        },
                        {
                            "id": "temporary_routine_change_expectation",
                            "type": "select",
                            "label": "Are temporary changes to routines expected to occur?",
                            "required": True,
                            "options": [
                                {"value": "rarely", "label": "Rarely"},
                                {"value": "occasionally", "label": "Occasionally"},
                                {"value": "frequently", "label": "Frequently"},
                                {"value": "not_discussed", "label": "Not discussed"},
                            ],
                            "meta": {"sri_question_number": 20},
                        },
                    ],
                },
            ],
        }
    return {
        "schema": schema,
        # Keep output/language shape stable for current API contracts.
        "output": {
            "default_language": "en",
            "languages": ["en", "es"],
            "copy": {
                "en": {
                    "intro": (
                        "This report summarizes structural household caregiving "
                        "coordination based on submitted responses."
                    ),
                    "sections": {},
                },
                "es": {
                    "intro": (
                        "Este informe resume la coordinación estructural del cuidado en el hogar "
                        "a partir de las respuestas enviadas."
                    ),
                    "sections": {},
                }
            },
            "questionnaire": {
                "sections": {
                    "overnight_sleep_routines": {
                        "en": "Overnight Coverage & Sleep Routines",
                        "es": "Cobertura nocturna y rutinas de sueño",
                    },
                    "feeding_daytime_care": {
                        "en": "Feeding & Daytime Care Coordination",
                        "es": "Alimentación y coordinación del cuidado diurno",
                    },
                    "transport_equipment_configuration": {
                        "en": "Transport & Equipment Configuration",
                        "es": "Transporte y configuración de equipos",
                    },
                    "home_layout_environmental_access": {
                        "en": "Home Layout & Environmental Access",
                        "es": "Distribución del hogar y acceso ambiental",
                    },
                    "ownership_review_cadence": {
                        "en": "Ownership & Review Cadence",
                        "es": "Responsabilidad y frecuencia de revisión",
                    },
                },
                "fields": {
                    "overnight_responders_count": {
                        "en": "How many adults may respond overnight if the infant wakes?",
                        "es": "¿Cuántas personas adultas pueden responder por la noche si el bebé se despierta?",
                    },
                    "overnight_final_decision_authority": {
                        "en": "Is one adult identified as the final decision-maker for overnight changes?",
                        "es": "¿Existe una persona adulta identificada como autoridad final para cambios en la rutina nocturna?",
                    },
                    "overnight_routine_variability": {
                        "en": "Are sleep routines expected to change depending on fatigue or circumstances?",
                        "es": "¿Se espera que las rutinas de sueño cambien según el cansancio o las circunstancias?",
                    },
                    "overnight_review_date_set": {
                        "en": "Has a review date been set to revisit overnight routines?",
                        "es": "¿Se estableció una fecha de revisión para retomar las rutinas nocturnas?",
                    },
                    "daytime_primary_caregiver": {
                        "en": "Is there a primary daytime caregiver?",
                        "es": "¿Existe una persona cuidadora principal durante el día?",
                    },
                    "feeding_locations_consistency": {
                        "en": "Are feeding locations consistent?",
                        "es": "¿Los lugares de alimentación son consistentes?",
                    },
                    "feeding_change_decision_process": {
                        "en": "If feeding routines change, how are changes decided?",
                        "es": "Si cambian las rutinas de alimentación, ¿cómo se deciden esos cambios?",
                    },
                    "feeding_review_checkin": {
                        "en": "Is there a scheduled check-in to revisit feeding routines?",
                        "es": "¿Hay una revisión programada para volver a evaluar las rutinas de alimentación?",
                    },
                    "transport_regular_vehicle_count": {
                        "en": "How many vehicles will regularly transport the infant?",
                        "es": "¿Cuántos vehículos transportarán regularmente al bebé?",
                    },
                    "transport_equipment_installer_clarity": {
                        "en": "Who installed or verified equipment (e.g., car seat)?",
                        "es": "¿Quién instaló o verificó el equipo de transporte del bebé (por ejemplo, la silla del coche)?",
                    },
                    "transport_configuration_change_frequency": {
                        "en": "How often is equipment configuration expected to change?",
                        "es": "¿Con qué frecuencia se espera que cambie la configuración del equipo?",
                    },
                    "transport_configuration_authority": {
                        "en": "If configuration concerns arise, who has authority to modify it?",
                        "es": "Si surgen dudas sobre la configuración, ¿quién tiene autoridad para modificarla?",
                    },
                    "home_single_level_caregiving": {
                        "en": "Is caregiving primarily conducted on one level of the home?",
                        "es": "¿El cuidado se realiza principalmente en un solo nivel del hogar?",
                    },
                    "home_supply_storage_distribution": {
                        "en": "Are essential supplies stored in one location or multiple areas?",
                        "es": "¿Los insumos esenciales del cuidado se guardan en un solo lugar o en varias áreas?",
                    },
                    "home_nighttime_room_movement_frequency": {
                        "en": "During nighttime routines, is movement between rooms required?",
                        "es": "Durante las rutinas nocturnas, ¿es necesario moverse entre habitaciones?",
                    },
                    "home_setup_change_difficulty": {
                        "en": "If environmental setup needs to change, how difficult would that be?",
                        "es": "Si se necesita cambiar la configuración del entorno, ¿qué tan difícil sería?",
                    },
                    "caregiver_responsibility_clarity": {
                        "en": "Are responsibilities clearly divided among caregivers?",
                        "es": "¿Las responsabilidades están claramente divididas entre las personas cuidadoras?",
                    },
                    "caregiver_disagreement_final_authority": {
                        "en": "If disagreements arise, is there a final decision authority?",
                        "es": "Si surgen desacuerdos, ¿existe una autoridad final para decidir?",
                    },
                    "routine_reassessment_timeline_set": {
                        "en": "Has a timeline been set to reassess routines as circumstances change?",
                        "es": "¿Se ha definido un cronograma para reevaluar rutinas cuando cambian las circunstancias?",
                    },
                    "temporary_routine_change_expectation": {
                        "en": "Are temporary changes to routines expected to occur?",
                        "es": "¿Se espera que ocurran cambios temporales en las rutinas?",
                    },
                },
                "option_values": _build_questionnaire_option_values(schema),
            },
            "report": {
                "methodology": {
                    "en": "Configuration-driven SRI deterministic indicator evaluation.",
                    "es": "Evaluación determinística de indicadores SRI guiada por configuración.",
                },
                "scope": {
                    "en": "Single recipient submission covering all configured SRI domains.",
                    "es": "Una sola respuesta de destinatario que cubre todos los dominios SRI configurados.",
                },
                "copy": {
                    "executive_overview": {
                        "en": "This report presents a structured summary of observed coordination patterns across configured domains. It is informational and non-directive, and it should be interpreted in context with local operational review.",
                        "es": "Este informe presenta un resumen estructurado de los patrones de coordinación observados en los dominios configurados. Su fin es informativo y no directivo, y debe interpretarse en contexto con la revisión operativa local.",
                    },
                    "cross_domain_summary": {
                        "en": "This section summarizes whether cross-domain escalation criteria were triggered in the configured model.",
                        "es": "Esta sección resume si se activaron criterios de escalamiento entre dominios en el modelo configurado.",
                    },
                    "structural_strengths_intro": {
                        "en": "Strengths identify areas with relatively stable and clearly defined coordination patterns in this submission.",
                        "es": "Las fortalezas identifican áreas con patrones de coordinación relativamente estables y claramente definidos en esta respuesta.",
                    },
                    "scope_limitations_notice": {
                        "en": "This report is informational and structural in scope. It does not provide medical advice, diagnostic conclusions, or prescriptive directives; it does not determine safety, compliance, or medical risk; and it does not replace clinical care. Outputs reflect self-reported information interpreted through deterministic rule logic. Healthcare providers retain full clinical judgment and responsibility for care decisions.",
                        "es": "Este informe es informativo y de alcance estructural. No proporciona asesoramiento medico, conclusiones diagnosticas ni directrices prescriptivas; no determina seguridad, cumplimiento ni riesgo medico; y no reemplaza la atencion clinica. Los resultados reflejan informacion auto reportada interpretada mediante logica deterministica de reglas. Los profesionales de salud mantienen el juicio clinico completo y la responsabilidad de las decisiones de cuidado.",
                    },
                },
            },
            # Canonical consideration copy by language.
            "considerations": {
                "by_question": build_canonical_considerations_by_question(),
            },
        },
        "evaluation": {
            "classification": {
                "default": "Cleared",
                "order": ["Cleared", "Watch", "Elevated"],
                "rules": [],
            },
            "tags": [],
            "sri": {
                "enabled": True,
                "indicator_rules": [
                    {
                        "id": "q01_two_adults_share_response",
                        "domain": "overnight_sleep_routines",
                        "indicator": "structural_complexity_exposure",
                        "signal": "moderate",
                        "if": {
                            "field": "overnight_responders_count",
                            "op": "==",
                            "value": "two_adults_share_response",
                        },
                    },
                    {
                        "id": "q01_three_or_more_adults",
                        "domain": "overnight_sleep_routines",
                        "indicator": "structural_complexity_exposure",
                        "signal": "high",
                        "if": {"field": "overnight_responders_count", "op": "==", "value": "three_or_more_adults"},
                    },
                    {
                        "id": "q01_not_yet_determined",
                        "domain": "overnight_sleep_routines",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {"field": "overnight_responders_count", "op": "==", "value": "not_yet_determined"},
                    },
                    {
                        "id": "q02_shared_without_final_authority",
                        "domain": "overnight_sleep_routines",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {
                            "field": "overnight_final_decision_authority",
                            "op": "==",
                            "value": "shared_without_final_authority",
                        },
                    },
                    {
                        "id": "q02_no_defined_final_authority",
                        "domain": "overnight_sleep_routines",
                        "indicator": "ownership_clarity",
                        "signal": "high",
                        "if": {
                            "field": "overnight_final_decision_authority",
                            "op": "==",
                            "value": "no_defined_final_authority",
                        },
                    },
                    {
                        "id": "q03_occasional_variability",
                        "domain": "overnight_sleep_routines",
                        "indicator": "drift_conditions",
                        "signal": "moderate",
                        "if": {"field": "overnight_routine_variability", "op": "==", "value": "occasionally"},
                    },
                    {
                        "id": "q03_frequent_variability",
                        "domain": "overnight_sleep_routines",
                        "indicator": "drift_conditions",
                        "signal": "high",
                        "if": {"field": "overnight_routine_variability", "op": "==", "value": "frequently"},
                    },
                    {
                        "id": "q03_not_discussed",
                        "domain": "overnight_sleep_routines",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "overnight_routine_variability", "op": "==", "value": "not_discussed"},
                    },
                    {
                        "id": "q04_informal_plan",
                        "domain": "overnight_sleep_routines",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "overnight_review_date_set", "op": "==", "value": "informal_plan"},
                    },
                    {
                        "id": "q04_no_review_plan",
                        "domain": "overnight_sleep_routines",
                        "indicator": "review_cadence",
                        "signal": "high",
                        "if": {"field": "overnight_review_date_set", "op": "==", "value": "no_review_plan"},
                    },
                    {
                        "id": "q05_shared_equally",
                        "domain": "feeding_daytime_care",
                        "indicator": "structural_complexity_exposure",
                        "signal": "moderate",
                        "if": {"field": "daytime_primary_caregiver", "op": "==", "value": "shared_equally"},
                    },
                    {
                        "id": "q05_varies_daily",
                        "domain": "feeding_daytime_care",
                        "indicator": "drift_conditions",
                        "signal": "high",
                        "if": {"field": "daytime_primary_caregiver", "op": "==", "value": "varies_daily"},
                    },
                    {
                        "id": "q05_not_yet_determined",
                        "domain": "feeding_daytime_care",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {"field": "daytime_primary_caregiver", "op": "==", "value": "not_yet_determined"},
                    },
                    {
                        "id": "q06_two_common_locations",
                        "domain": "feeding_daytime_care",
                        "indicator": "structural_complexity_exposure",
                        "signal": "moderate",
                        "if": {"field": "feeding_locations_consistency", "op": "==", "value": "two_common_locations"},
                    },
                    {
                        "id": "q06_multiple_rotating_locations",
                        "domain": "feeding_daytime_care",
                        "indicator": "structural_complexity_exposure",
                        "signal": "high",
                        "if": {
                            "field": "feeding_locations_consistency",
                            "op": "==",
                            "value": "multiple_rotating_locations",
                        },
                    },
                    {
                        "id": "q07_discussion_based_agreement",
                        "domain": "feeding_daytime_care",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {"field": "feeding_change_decision_process", "op": "==", "value": "discussion_based_agreement"},
                    },
                    {
                        "id": "q07_situational_whoever_present",
                        "domain": "feeding_daytime_care",
                        "indicator": "ownership_clarity",
                        "signal": "high",
                        "if": {
                            "field": "feeding_change_decision_process",
                            "op": "==",
                            "value": "situational_whoever_present",
                        },
                    },
                    {
                        "id": "q07_not_discussed",
                        "domain": "feeding_daytime_care",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "feeding_change_decision_process", "op": "==", "value": "not_discussed"},
                    },
                    {
                        "id": "q08_informal_checkins",
                        "domain": "feeding_daytime_care",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "feeding_review_checkin", "op": "==", "value": "informal_checkins"},
                    },
                    {
                        "id": "q08_no_defined_review_point",
                        "domain": "feeding_daytime_care",
                        "indicator": "review_cadence",
                        "signal": "high",
                        "if": {"field": "feeding_review_checkin", "op": "==", "value": "no_defined_review_point"},
                    },
                    {
                        "id": "q09_two_vehicles",
                        "domain": "transport_equipment_configuration",
                        "indicator": "structural_complexity_exposure",
                        "signal": "moderate",
                        "if": {"field": "transport_regular_vehicle_count", "op": "==", "value": "two"},
                    },
                    {
                        "id": "q09_three_or_more_vehicles",
                        "domain": "transport_equipment_configuration",
                        "indicator": "structural_complexity_exposure",
                        "signal": "high",
                        "if": {"field": "transport_regular_vehicle_count", "op": "==", "value": "three_or_more"},
                    },
                    {
                        "id": "q10_multiple_individuals",
                        "domain": "transport_equipment_configuration",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {
                            "field": "transport_equipment_installer_clarity",
                            "op": "==",
                            "value": "multiple_individuals",
                        },
                    },
                    {
                        "id": "q10_unsure",
                        "domain": "transport_equipment_configuration",
                        "indicator": "ownership_clarity",
                        "signal": "high",
                        "if": {"field": "transport_equipment_installer_clarity", "op": "==", "value": "unsure"},
                    },
                    {
                        "id": "q10_not_yet_installed",
                        "domain": "transport_equipment_configuration",
                        "indicator": "lock_in_reversibility_friction",
                        "signal": "moderate",
                        "if": {
                            "field": "transport_equipment_installer_clarity",
                            "op": "==",
                            "value": "not_yet_installed",
                        },
                    },
                    {
                        "id": "q11_occasional_changes",
                        "domain": "transport_equipment_configuration",
                        "indicator": "drift_conditions",
                        "signal": "moderate",
                        "if": {"field": "transport_configuration_change_frequency", "op": "==", "value": "occasionally"},
                    },
                    {
                        "id": "q11_frequent_changes",
                        "domain": "transport_equipment_configuration",
                        "indicator": "drift_conditions",
                        "signal": "high",
                        "if": {"field": "transport_configuration_change_frequency", "op": "==", "value": "frequently"},
                    },
                    {
                        "id": "q11_not_discussed",
                        "domain": "transport_equipment_configuration",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "transport_configuration_change_frequency", "op": "==", "value": "not_discussed"},
                    },
                    {
                        "id": "q12_shared_authority",
                        "domain": "transport_equipment_configuration",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {"field": "transport_configuration_authority", "op": "==", "value": "shared_authority"},
                    },
                    {
                        "id": "q12_no_clear_authority",
                        "domain": "transport_equipment_configuration",
                        "indicator": "ownership_clarity",
                        "signal": "high",
                        "if": {"field": "transport_configuration_authority", "op": "==", "value": "no_clear_authority"},
                    },
                    {
                        "id": "q12_not_discussed",
                        "domain": "transport_equipment_configuration",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "transport_configuration_authority", "op": "==", "value": "not_discussed"},
                    },
                    {
                        "id": "q13_multiple_levels",
                        "domain": "home_layout_environmental_access",
                        "indicator": "structural_complexity_exposure",
                        "signal": "high",
                        "if": {"field": "home_single_level_caregiving", "op": "==", "value": "multiple_levels"},
                    },
                    {
                        "id": "q13_not_yet_determined",
                        "domain": "home_layout_environmental_access",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "home_single_level_caregiving", "op": "==", "value": "not_yet_determined"},
                    },
                    {
                        "id": "q14_two_areas",
                        "domain": "home_layout_environmental_access",
                        "indicator": "structural_complexity_exposure",
                        "signal": "moderate",
                        "if": {"field": "home_supply_storage_distribution", "op": "==", "value": "two_areas"},
                    },
                    {
                        "id": "q14_three_or_more_areas",
                        "domain": "home_layout_environmental_access",
                        "indicator": "structural_complexity_exposure",
                        "signal": "high",
                        "if": {"field": "home_supply_storage_distribution", "op": "==", "value": "three_or_more_areas"},
                    },
                    {
                        "id": "q15_sometimes_movement",
                        "domain": "home_layout_environmental_access",
                        "indicator": "structural_complexity_exposure",
                        "signal": "moderate",
                        "if": {
                            "field": "home_nighttime_room_movement_frequency",
                            "op": "==",
                            "value": "sometimes",
                        },
                    },
                    {
                        "id": "q15_frequent_movement",
                        "domain": "home_layout_environmental_access",
                        "indicator": "structural_complexity_exposure",
                        "signal": "high",
                        "if": {
                            "field": "home_nighttime_room_movement_frequency",
                            "op": "==",
                            "value": "frequently",
                        },
                    },
                    {
                        "id": "q15_not_discussed",
                        "domain": "home_layout_environmental_access",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {
                            "field": "home_nighttime_room_movement_frequency",
                            "op": "==",
                            "value": "not_discussed",
                        },
                    },
                    {
                        "id": "q16_moderate_effort",
                        "domain": "home_layout_environmental_access",
                        "indicator": "lock_in_reversibility_friction",
                        "signal": "moderate",
                        "if": {"field": "home_setup_change_difficulty", "op": "==", "value": "moderate_effort"},
                    },
                    {
                        "id": "q16_significant_effort",
                        "domain": "home_layout_environmental_access",
                        "indicator": "lock_in_reversibility_friction",
                        "signal": "high",
                        "if": {"field": "home_setup_change_difficulty", "op": "==", "value": "significant_effort"},
                    },
                    {
                        "id": "q17_mostly",
                        "domain": "ownership_review_cadence",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {"field": "caregiver_responsibility_clarity", "op": "==", "value": "mostly"},
                    },
                    {
                        "id": "q17_occasionally_unclear",
                        "domain": "ownership_review_cadence",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {
                            "field": "caregiver_responsibility_clarity",
                            "op": "==",
                            "value": "occasionally_unclear",
                        },
                    },
                    {
                        "id": "q17_often_unclear",
                        "domain": "ownership_review_cadence",
                        "indicator": "ownership_clarity",
                        "signal": "high",
                        "if": {"field": "caregiver_responsibility_clarity", "op": "==", "value": "often_unclear"},
                    },
                    {
                        "id": "q18_shared_without_escalation",
                        "domain": "ownership_review_cadence",
                        "indicator": "ownership_clarity",
                        "signal": "moderate",
                        "if": {
                            "field": "caregiver_disagreement_final_authority",
                            "op": "==",
                            "value": "shared_without_escalation",
                        },
                    },
                    {
                        "id": "q18_no_defined_escalation",
                        "domain": "ownership_review_cadence",
                        "indicator": "ownership_clarity",
                        "signal": "high",
                        "if": {
                            "field": "caregiver_disagreement_final_authority",
                            "op": "==",
                            "value": "no_defined_escalation",
                        },
                    },
                    {
                        "id": "q19_informally_planned",
                        "domain": "ownership_review_cadence",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "routine_reassessment_timeline_set", "op": "==", "value": "informally_planned"},
                    },
                    {
                        "id": "q19_no_plan",
                        "domain": "ownership_review_cadence",
                        "indicator": "review_cadence",
                        "signal": "high",
                        "if": {"field": "routine_reassessment_timeline_set", "op": "==", "value": "no_plan"},
                    },
                    {
                        "id": "q20_occasionally",
                        "domain": "ownership_review_cadence",
                        "indicator": "drift_conditions",
                        "signal": "moderate",
                        "if": {"field": "temporary_routine_change_expectation", "op": "==", "value": "occasionally"},
                    },
                    {
                        "id": "q20_frequently",
                        "domain": "ownership_review_cadence",
                        "indicator": "drift_conditions",
                        "signal": "high",
                        "if": {"field": "temporary_routine_change_expectation", "op": "==", "value": "frequently"},
                    },
                    {
                        "id": "q20_not_discussed",
                        "domain": "ownership_review_cadence",
                        "indicator": "review_cadence",
                        "signal": "moderate",
                        "if": {"field": "temporary_routine_change_expectation", "op": "==", "value": "not_discussed"},
                    },
                ],
                "thresholds": {
                    "watch": {"min_moderate": 2, "min_high_complexity": 1},
                    "elevated": {"min_moderate": 3, "min_high_complexity": 2},
                    "cross_domain": {
                        "min_elevated_domains": 3,
                        "flag": "multi_domain_structural_exposure",
                        "pattern_id": "cross_domain_multi_exposure",
                    },
                },
                "considerations": {
                    "max_per_domain": 2,
                    "max_total": 8,
                    "by_question": {
                        "overnight_responders_count": {
                            "watch": "Some households find it useful to define a primary overnight response pattern.",
                            "elevated": "Multiple overnight responders can increase coordination load when routines change.",
                        },
                        "overnight_final_decision_authority": {
                            "watch": "Some caregivers document how final routine decisions are made when views differ.",
                            "elevated": "When final decision authority is unclear, overnight routines may vary across caregivers.",
                        },
                        "overnight_routine_variability": {
                            "watch": "Some families note common triggers that lead to overnight routine changes.",
                            "elevated": "Frequent overnight variability may increase day-to-day coordination demands.",
                        },
                        "overnight_review_date_set": {
                            "watch": "Informal routine review can be easier to sustain with a defined cadence.",
                            "elevated": "Without a review cadence, overnight routines may shift without shared alignment.",
                        },
                        "daytime_primary_caregiver": {
                            "watch": "Some households track daytime role ownership to reduce handoff ambiguity.",
                            "elevated": "Daily caregiver variation may increase coordination friction across routines.",
                        },
                        "feeding_locations_consistency": {
                            "watch": "Using more than one feeding location can add coordination steps.",
                            "elevated": "Rotating feeding locations may increase structural complexity across the day.",
                        },
                        "feeding_change_decision_process": {
                            "watch": "Discussion-based changes can be clearer with a documented escalation path.",
                            "elevated": "Situational feeding decisions can increase variability across caregivers.",
                        },
                        "feeding_review_checkin": {
                            "watch": "Informal check-ins are often more consistent when tied to a routine interval.",
                            "elevated": "Without a feeding review point, routine drift can accumulate over time.",
                        },
                        "transport_regular_vehicle_count": {
                            "watch": "Using multiple vehicles may benefit from a shared transport checklist.",
                            "elevated": "Higher vehicle count can increase equipment coordination complexity.",
                        },
                        "transport_equipment_installer_clarity": {
                            "watch": "Clarifying who verifies transport setup can reduce role ambiguity.",
                            "elevated": "Unclear transport setup ownership may increase configuration inconsistency.",
                        },
                        "transport_configuration_change_frequency": {
                            "watch": "Occasional configuration changes can be easier with explicit review triggers.",
                            "elevated": "Frequent configuration changes may increase drift across transport routines.",
                        },
                        "transport_configuration_authority": {
                            "watch": "Shared authority is often clearer with a documented escalation rule.",
                            "elevated": "No clear transport authority can increase decision friction during changes.",
                        },
                        "home_single_level_caregiving": {
                            "watch": "Environmental transitions can add routine coordination steps.",
                            "elevated": "Multiple caregiving levels may increase overnight and daytime movement load.",
                        },
                        "home_supply_storage_distribution": {
                            "watch": "Distributed supply storage can benefit from a shared organization pattern.",
                            "elevated": "Wide supply distribution may increase environmental coordination demands.",
                        },
                        "home_nighttime_room_movement_frequency": {
                            "watch": "Room-to-room movement can add predictable coordination friction.",
                            "elevated": "Frequent nighttime movement may increase structural workload.",
                        },
                        "home_setup_change_difficulty": {
                            "watch": "Moderate setup effort can limit how quickly routines are adjusted.",
                            "elevated": "High setup effort may reduce reversibility when routine updates are needed.",
                        },
                        "caregiver_responsibility_clarity": {
                            "watch": "Clarifying shared responsibilities can reduce routine handoff ambiguity.",
                            "elevated": "Frequent role ambiguity may increase day-to-day coordination load.",
                        },
                        "caregiver_disagreement_final_authority": {
                            "watch": "Some households define a simple escalation path for routine disagreements.",
                            "elevated": "No escalation rule can increase inconsistency across care decisions.",
                        },
                        "routine_reassessment_timeline_set": {
                            "watch": "Informal reassessment plans are often stronger with a fixed timeline.",
                            "elevated": "Without reassessment timing, routine drift may go unreviewed.",
                        },
                        "temporary_routine_change_expectation": {
                            "watch": "Expected temporary changes may be easier to manage with shared checkpoints.",
                            "elevated": "Frequent temporary changes can increase cumulative coordination complexity.",
                        },
                    },
                },
            },
        },
    }


class InspectionInstance(models.Model):
    """
    A unique inspection campaign/run.
    This is what the public URL uses as {inspection-id} (per your requirement).
    """

    KIND_TEMPLATE = "template"
    KIND_CAMPAIGN = "campaign"
    KIND_CHOICES = [
        (KIND_TEMPLATE, "Template"),
        (KIND_CAMPAIGN, "Campaign"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    kind = models.CharField(max_length=16, choices=KIND_CHOICES, default=KIND_CAMPAIGN)
    base_template = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="derived_instances",
        help_text="If this instance was cloned from a template, this points to the source template.",
    )
    organization_id = models.CharField(max_length=128, blank=True)
    name = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    closes_at = models.DateTimeField(null=True, blank=True)
    submission_threshold = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "inspection_instance"

    def __str__(self) -> str:
        name = (self.name or "Unnamed").strip()
        short = str(self.id)[:8]
        if self.kind == self.KIND_CAMPAIGN:
            org = (self.organization_id or "-").strip()
            return f"{name} (campaign, org={org}) [{short}]"
        return f"{name} (template) [{short}]"


class OrganizationBranding(models.Model):
    """
    Organization-level branding used by public form/report presentation layers.
    """

    organization_id = models.CharField(max_length=128, unique=True, db_index=True)
    hospital_program_name = models.CharField(max_length=255)
    logo = models.FileField(upload_to="branding/logos/", null=True, blank=True)
    primary_color = models.CharField(
        max_length=7,
        default="#1F2937",
        validators=[
            RegexValidator(
                regex=r"^#[0-9A-Fa-f]{6}$",
                message="primary_color must be a hex color in #RRGGBB format.",
            )
        ],
    )
    tagline = models.CharField(max_length=255, blank=True)
    footer_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "organization_branding"
        ordering = ("organization_id",)

    def __str__(self) -> str:
        return f"{self.organization_id} • {self.hospital_program_name}"


class InspectionConfigVersion(models.Model):
    """
    Immutable published config snapshot (stored as JSON) pinned to a recipient link.
    """

    STATUS_DRAFT = "draft"
    STATUS_PUBLISHED = "published"
    STATUS_CHOICES = [
        (STATUS_DRAFT, "Draft"),
        (STATUS_PUBLISHED, "Published"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection_instance = models.ForeignKey(
        InspectionInstance,
        on_delete=models.CASCADE,
        related_name="config_versions",
    )
    # Config is the source of truth (schema + evaluation rules). Stored as JSON.
    config = models.JSONField(default=default_base_config)
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=STATUS_CHOICES, default=STATUS_DRAFT)
    published_at = models.DateTimeField(null=True, blank=True)
    config_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "inspection_config_version"

    def __str__(self) -> str:
        short = str(self.id)[:8]
        return f"{self.inspection_instance} • {self.status} [{short}]"

    def _compute_config_sha256(self) -> str:
        # Stable JSON encoding to make hash deterministic.
        payload = json.dumps(self.config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def clean(self) -> None:
        if self.status == self.STATUS_PUBLISHED:
            # Minimal publish-time validation: schema must exist and be well-formed.
            if not isinstance(self.config, dict):
                raise ValidationError("Config must be a JSON object.")
            schema = self.config.get("schema")
            if not isinstance(schema, dict):
                raise ValidationError("Config must contain a 'schema' object before publishing.")
            if not isinstance(schema.get("title"), str) or not schema.get("title"):
                raise ValidationError("schema.title is required before publishing.")
            sections = schema.get("sections")
            if not isinstance(sections, list) or not sections:
                raise ValidationError("schema.sections must be a non-empty array before publishing.")
            for s in sections:
                if not isinstance(s, dict):
                    raise ValidationError("Each schema section must be an object.")
                if not isinstance(s.get("id"), str) or not s.get("id"):
                    raise ValidationError("Each section requires a non-empty 'id'.")
                if not isinstance(s.get("title"), str) or not s.get("title"):
                    raise ValidationError("Each section requires a non-empty 'title'.")
                fields = s.get("fields")
                if not isinstance(fields, list) or not fields:
                    raise ValidationError(f"Section '{s.get('id')}' must have a non-empty fields array.")
                for f in fields:
                    if not isinstance(f, dict):
                        raise ValidationError("Each field must be an object.")
                    if not isinstance(f.get("id"), str) or not f.get("id"):
                        raise ValidationError("Each field requires a non-empty 'id'.")
                    if f.get("type") not in {"text", "number", "select"}:
                        raise ValidationError(f"Field '{f.get('id')}' has unsupported type.")
                    if not isinstance(f.get("label"), str) or not f.get("label"):
                        raise ValidationError(f"Field '{f.get('id')}' requires a non-empty label.")
                    if not isinstance(f.get("required"), bool):
                        raise ValidationError(f"Field '{f.get('id')}' requires boolean 'required'.")
                    if f.get("type") == "select":
                        opts = f.get("options")
                        if not isinstance(opts, list) or not opts:
                            raise ValidationError(f"Field '{f.get('id')}' (select) requires a non-empty options array.")
                        values: set[str] = set()
                        for o in opts:
                            if not isinstance(o, dict):
                                raise ValidationError(f"Field '{f.get('id')}' options must be objects.")
                            v = o.get("value")
                            lab = o.get("label")
                            if not isinstance(v, str) or not v:
                                raise ValidationError(f"Field '{f.get('id')}' option requires non-empty 'value'.")
                            if not isinstance(lab, str) or not lab:
                                raise ValidationError(f"Field '{f.get('id')}' option requires non-empty 'label'.")
                            if v in values:
                                raise ValidationError(f"Field '{f.get('id')}' has duplicate option value '{v}'.")
                            values.add(v)

            current_hash = self._compute_config_sha256()
            if self.config_sha256 and self.config_sha256 != current_hash:
                raise ValidationError("Published config versions are immutable.")

    def publish(self) -> None:
        if self.status == self.STATUS_PUBLISHED:
            return
        self.status = self.STATUS_PUBLISHED
        self.config_sha256 = self._compute_config_sha256()
        self.published_at = timezone.now()

    def save(self, *args, **kwargs):
        # If status is manually set to published (e.g., via admin), normalize by
        # computing the hash + published_at automatically.
        if self.status == self.STATUS_PUBLISHED and not self.config_sha256:
            self.config_sha256 = self._compute_config_sha256()
        if self.status == self.STATUS_PUBLISHED and self.published_at is None:
            self.published_at = timezone.now()

        # Enforce clean() rules (immutability + FK constraints) consistently.
        self.full_clean()
        return super().save(*args, **kwargs)


class RecipientLink(models.Model):
    """
    Public recipient link token (UUID) for a campaign, pinned to a config version.
    No employee identity is stored here.
    """

    STATUS_CREATED = "created"
    STATUS_OPENED = "opened"
    STATUS_SUBMITTED = "submitted"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_CREATED, "Created"),
        (STATUS_OPENED, "Opened"),
        (STATUS_SUBMITTED, "Submitted"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection_instance = models.ForeignKey(
        InspectionInstance,
        on_delete=models.CASCADE,
        related_name="recipient_links",
    )
    config_version = models.ForeignKey(
        InspectionConfigVersion,
        on_delete=models.PROTECT,
        related_name="recipient_links",
    )
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_CREATED)
    created_at = models.DateTimeField(auto_now_add=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "recipient_link"
        constraints = [
            models.UniqueConstraint(
                fields=["inspection_instance", "id"],
                name="uniq_recipient_link_per_instance",
            )
        ]

    def __str__(self) -> str:
        short = str(self.id)[:8]
        return f"{self.inspection_instance} • link [{short}]"

    def clean(self) -> None:
        if self.config_version_id and self.config_version.inspection_instance_id != self.inspection_instance_id:
            raise ValidationError("RecipientLink config_version must belong to the same inspection_instance.")
        if self.config_version_id and self.config_version.status != InspectionConfigVersion.STATUS_PUBLISHED:
            raise ValidationError("Recipient links can only be created for published config versions.")

    @property
    def public_path(self) -> str:
        # Frontend expects /{inspection_instance_id}/{uuid}
        return f"/{self.inspection_instance_id}/{self.id}"

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class Submission(models.Model):
    """
    A submission for a recipient link.
    Answers are stored as JSON; deterministic outputs can also be stored as JSON.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient_link = models.OneToOneField(
        RecipientLink,
        on_delete=models.CASCADE,
        related_name="submission",
    )
    config_version = models.ForeignKey(
        InspectionConfigVersion,
        on_delete=models.PROTECT,
        related_name="submissions",
    )
    answers = models.JSONField()
    outputs = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to="pdfs/submissions/", null=True, blank=True)
    pdf_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "submission"

    def __str__(self) -> str:
        return f"{self.id}"

    def clean(self) -> None:
        if self.recipient_link_id and self.config_version_id:
            if self.recipient_link.config_version_id != self.config_version_id:
                raise ValidationError("Submission config_version must match recipient_link.config_version.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def attach_pdf(self, filename: str, pdf_bytes: bytes) -> None:
        self.pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        self.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)


class AggregatedReport(models.Model):
    """
    QuietRisk aggregated output for a campaign: one employer-level executive PDF.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection_instance = models.OneToOneField(
        InspectionInstance,
        on_delete=models.CASCADE,
        related_name="aggregated_report",
    )
    counts = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to="pdfs/aggregated/", null=True, blank=True)
    pdf_sha256 = models.CharField(max_length=64, blank=True)

    class Meta:
        db_table = "aggregated_report"

    def attach_pdf(self, filename: str, pdf_bytes: bytes) -> None:
        self.pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        self.pdf_file.save(filename, ContentFile(pdf_bytes), save=False)
