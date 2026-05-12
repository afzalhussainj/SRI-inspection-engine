from __future__ import annotations

from typing import Any

# Canonical consideration library sources:
# - English Watch
# - Spanish Watch
# - Spanish Elevated

_QUESTION_ID_BY_NUMBER: dict[int, str] = {
    1: "overnight_responders_count",
    2: "overnight_final_decision_authority",
    3: "overnight_routine_variability",
    4: "overnight_review_date_set",
    5: "daytime_primary_caregiver",
    6: "feeding_locations_consistency",
    7: "feeding_change_decision_process",
    8: "feeding_review_checkin",
    9: "transport_regular_vehicle_count",
    10: "transport_equipment_installer_clarity",
    11: "transport_configuration_change_frequency",
    12: "transport_configuration_authority",
    13: "home_single_level_caregiving",
    14: "home_supply_storage_distribution",
    15: "home_nighttime_room_movement_frequency",
    16: "home_setup_change_difficulty",
    17: "caregiver_responsibility_clarity",
    18: "caregiver_disagreement_final_authority",
    19: "routine_reassessment_timeline_set",
    20: "temporary_routine_change_expectation",
}

_EN_WATCH: dict[int, str] = {
    1: "Some households choose to designate a primary overnight responder so nighttime routines remain predictable when fatigue levels vary.",
    2: "Families sometimes clarify how overnight decisions are finalized so routine adjustments can be coordinated more smoothly when multiple caregivers participate.",
    3: "Some caregivers periodically review how sleep routines change under fatigue so expectations remain aligned across caregivers.",
    4: "Some households set informal check-in points to revisit overnight routines as infant sleep patterns evolve.",
    5: "Families sometimes review how daytime caregiving responsibilities shift during busy periods to maintain consistent routine coordination.",
    6: "Some households periodically simplify feeding locations when routines begin to rotate between several areas of the home.",
    7: "Families sometimes discuss how feeding routine changes are decided so caregivers remain aligned when adjustments occur.",
    8: "Some caregivers schedule occasional conversations about daytime feeding routines to keep expectations coordinated as schedules change.",
    9: "Families sometimes review transport routines when multiple vehicles are used so equipment placement and routines remain consistent.",
    10: "Some households choose to periodically confirm who oversees transport equipment setup so configuration responsibility remains clear.",
    11: "Families sometimes revisit equipment configuration plans when adjustments occur occasionally so routines remain predictable.",
    12: "Some caregivers clarify who typically reviews equipment concerns so decisions about configuration adjustments remain coordinated.",
    13: "Some households review how caregiving routines move between home levels so nighttime and daytime transitions remain manageable.",
    14: "Families sometimes consolidate essential caregiving supplies when multiple storage areas begin to develop.",
    15: "Some households review nighttime movement patterns between rooms to keep routines as simple as possible during overnight care.",
    16: "Families sometimes discuss how easily the caregiving environment could be adjusted if routines evolve over time.",
    17: "Some caregivers occasionally revisit responsibility divisions as schedules change so coordination remains clear.",
    18: "Families sometimes clarify how final decisions are reached when disagreements arise so routines remain consistent.",
    19: "Some households choose to set informal review points for caregiving routines as infant needs change over time.",
    20: "Families sometimes review how temporary routine changes are handled so adjustments remain coordinated among caregivers.",
}

_EN_ELEVATED: dict[int, str] = {
    1: "When several adults may respond overnight, some households simplify routines by identifying a consistent primary responder for nighttime wake events.",
    2: "When overnight decisions do not have a clearly identified final authority, some caregivers establish a simple escalation rule so routine changes remain consistent.",
    3: "When sleep routines are expected to vary frequently, some households periodically review the overnight approach so expectations remain coordinated.",
    4: "When no review point has been identified for overnight routines, some families set a future conversation date to revisit how the routine is working.",
    5: "When daytime caregiving responsibilities are not clearly defined, some households designate a primary coordinator to simplify daily routine decisions.",
    6: "When feeding locations rotate frequently, some caregivers consolidate feeding routines into fewer locations to reduce coordination complexity.",
    7: "When feeding routine decisions occur situationally, some households establish a simple decision structure so routine changes remain predictable.",
    8: "When no feeding routine review cadence exists, some families schedule periodic discussions to revisit how daytime care routines are functioning.",
    9: "When multiple vehicles transport the infant regularly, some households standardize equipment placement and routines across vehicles.",
    10: "When equipment installation responsibility is unclear, some caregivers designate one individual to periodically verify configuration consistency.",
    11: "When equipment configuration changes frequently, some households review how configuration decisions are coordinated among caregivers.",
    12: "When authority to modify equipment setup is unclear, some families designate a consistent review process for configuration concerns.",
    13: "When caregiving routines occur across multiple home levels, some households review nighttime and daytime movement patterns to simplify routines.",
    14: "When essential caregiving supplies are distributed across several locations, some caregivers reorganize storage so routines remain easier to manage.",
    15: "When frequent nighttime movement between rooms occurs, some households simplify room layouts to support more predictable routines.",
    16: "When environmental setup changes would require significant effort, some families review whether routine adjustments could reduce configuration friction.",
    17: "When caregiver responsibilities are frequently unclear, some households define ownership roles to support routine consistency.",
    18: "When disagreements do not have an escalation structure, some caregivers establish a final decision pathway to maintain routine alignment.",
    19: "When no reassessment timeline exists for caregiving routines, some families choose a future review point to revisit how routines are functioning.",
    20: "When routine adjustments are expected to occur frequently, some households define how temporary changes are coordinated among caregivers.",
}

_ES_WATCH: dict[int, str] = {
    1: "En algunos hogares se designa a un cuidador principal para responder durante la noche, lo que puede ayudar a mantener rutinas más predecibles cuando el cansancio varía entre los adultos.",
    2: "Algunas familias aclaran cómo se toman las decisiones finales durante la noche para que los cambios en las rutinas puedan coordinarse con mayor claridad entre cuidadores.",
    3: "Algunos cuidadores revisan ocasionalmente cómo cambian las rutinas de sueño cuando hay cansancio, para mantener las expectativas alineadas entre quienes cuidan al bebé.",
    4: "En algunos hogares se establecen puntos informales de revisión para conversar nuevamente sobre las rutinas nocturnas a medida que cambian los patrones de sueño del bebé.",
    5: "Algunas familias revisan cómo se distribuyen las responsabilidades de cuidado durante el día cuando los horarios cambian o se vuelven más ocupados.",
    6: "Algunos hogares revisan periódicamente los lugares donde se realizan las tomas cuando comienzan a utilizarse varias áreas de la casa.",
    7: "Algunas familias conversan sobre cómo se deciden los cambios en las rutinas de alimentación para mantener a los cuidadores coordinados cuando se realizan ajustes.",
    8: "Algunos cuidadores programan conversaciones ocasionales para revisar las rutinas de alimentación durante el día cuando las necesidades del bebé cambian.",
    9: "Cuando se utilizan varios vehículos para transportar al bebé, algunas familias revisan las rutinas de transporte para mantener consistencia en el uso del equipo.",
    10: "Algunos hogares revisan ocasionalmente quién supervisa la instalación o verificación del equipo de transporte para mantener claridad en la responsabilidad.",
    11: "Cuando la configuración del equipo cambia ocasionalmente, algunas familias revisan cómo se coordinan estos ajustes entre los cuidadores.",
    12: "Algunos cuidadores aclaran quién suele revisar las preocupaciones relacionadas con el equipo para mantener la coordinación cuando surgen cambios.",
    13: "En algunos hogares se revisa cómo se realizan las rutinas de cuidado entre distintos niveles de la casa para mantener las transiciones manejables.",
    14: "Algunas familias consolidan los suministros esenciales de cuidado cuando comienzan a almacenarse en varias áreas del hogar.",
    15: "Algunos hogares revisan los movimientos nocturnos entre habitaciones para mantener las rutinas lo más simples posible durante el cuidado nocturno.",
    16: "Algunas familias conversan sobre qué tan fácil sería modificar el entorno de cuidado si las rutinas cambian con el tiempo.",
    17: "Algunos cuidadores revisan ocasionalmente la distribución de responsabilidades cuando cambian los horarios o las necesidades del hogar.",
    18: "Algunas familias aclaran cómo se toman las decisiones finales cuando surgen desacuerdos para mantener consistencia en las rutinas.",
    19: "En algunos hogares se establecen puntos informales de revisión para volver a evaluar las rutinas de cuidado a medida que cambian las circunstancias.",
    20: "Algunas familias revisan cómo se coordinan los cambios temporales en las rutinas cuando se espera que ocurran ajustes ocasionales.",
}

_ES_ELEVATED: dict[int, str] = {
    1: "Cuando varias personas pueden responder durante la noche, algunos hogares simplifican la rutina designando a un cuidador principal para los despertares nocturnos.",
    2: "Cuando no existe una autoridad final claramente identificada para decisiones nocturnas, algunos cuidadores establecen una regla sencilla de decisión final para mantener consistencia en las rutinas.",
    3: "Cuando se espera que las rutinas de sueño cambien con frecuencia, algunas familias revisan periódicamente el enfoque nocturno para mantener las expectativas coordinadas.",
    4: "Cuando no se ha definido un momento de revisión para las rutinas nocturnas, algunas familias programan una conversación futura para evaluar cómo está funcionando la rutina.",
    5: "Cuando las responsabilidades de cuidado durante el día no están claramente definidas, algunos hogares designan a un coordinador principal para simplificar las decisiones diarias.",
    6: "Cuando las ubicaciones de alimentación cambian con frecuencia, algunos cuidadores consolidan las rutinas de alimentación en menos áreas del hogar.",
    7: "Cuando los cambios en las rutinas de alimentación se deciden de manera situacional, algunas familias establecen una estructura simple de decisión para mantener mayor previsibilidad.",
    8: "Cuando no existe una revisión programada de las rutinas de alimentación, algunas familias establecen conversaciones periódicas para revisar cómo están funcionando las rutinas diurnas.",
    9: "Cuando varios vehículos transportan al bebé regularmente, algunos hogares estandarizan la ubicación del equipo y las rutinas entre los vehículos.",
    10: "Cuando la responsabilidad de instalación o verificación del equipo no está clara, algunos cuidadores designan a una persona para revisar periódicamente la consistencia de la configuración.",
    11: "Cuando la configuración del equipo cambia con frecuencia, algunas familias revisan cómo se coordinan las decisiones de configuración entre los cuidadores.",
    12: "Cuando la autoridad para modificar la configuración del equipo no está clara, algunas familias establecen un proceso simple de revisión para atender estas situaciones.",
    13: "Cuando las rutinas de cuidado ocurren en varios niveles del hogar, algunos hogares revisan los movimientos nocturnos y diurnos para simplificar las transiciones.",
    14: "Cuando los suministros esenciales de cuidado están distribuidos en varias áreas, algunos cuidadores reorganizan el almacenamiento para facilitar la coordinación de las rutinas.",
    15: "Cuando se requiere movimiento frecuente entre habitaciones durante la noche, algunos hogares revisan la disposición de los espacios para mantener las rutinas más predecibles.",
    16: "Cuando modificar el entorno de cuidado requiere un esfuerzo significativo, algunas familias revisan si pequeños ajustes en la rutina podrían reducir esa complejidad.",
    17: "Cuando las responsabilidades de cuidado suelen ser poco claras, algunos hogares definen roles de coordinación para apoyar la consistencia de las rutinas.",
    18: "Cuando los desacuerdos no tienen una estructura de decisión final, algunos cuidadores establecen un proceso claro de resolución para mantener la coordinación.",
    19: "Cuando no existe un momento definido para revisar las rutinas de cuidado, algunas familias establecen un punto futuro para evaluar cómo están funcionando los sistemas del hogar.",
    20: "Cuando se espera que los cambios de rutina ocurran con frecuencia, algunos hogares definen cómo se coordinan estos ajustes entre los cuidadores.",
}


def build_canonical_considerations_by_question() -> dict[str, dict[str, Any]]:
    """
    Returns output.considerations.by_question mapping used by engine overrides.
    """
    out: dict[str, dict[str, Any]] = {}
    for qnum, qid in _QUESTION_ID_BY_NUMBER.items():
        out[qid] = {
            "watch": {
                "en": _EN_WATCH[qnum],
                "es": _ES_WATCH[qnum],
            },
            "elevated": {
                "en": _EN_ELEVATED[qnum],
                "es": _ES_ELEVATED[qnum],
            },
        }
    return out

