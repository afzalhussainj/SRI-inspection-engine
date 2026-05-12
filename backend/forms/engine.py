from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .i18n import resolve_i18n_text


class ValidationError(Exception):
    pass


def _resolve_schema(config: dict[str, Any]) -> dict[str, Any]:
    # Allow either {"schema": {...}} or schema-only JSON for MVP compatibility.
    if isinstance(config.get("schema"), dict):
        return config["schema"]
    return config


def _iter_fields(schema: dict[str, Any]) -> Iterable[dict[str, Any]]:
    for section in schema.get("sections", []) or []:
        for field in section.get("fields", []) or []:
            meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
            if meta.get("active") is False:
                continue
            yield field


def validate_answers(config: dict[str, Any], answers: dict[str, Any]) -> None:
    schema = _resolve_schema(config)
    errors: list[str] = []
    for field in _iter_fields(schema):
        fid = field.get("id")
        ftype = field.get("type")
        required = bool(field.get("required"))
        if not fid:
            continue

        if required and fid not in answers:
            errors.append(f"Missing required field: {fid}")
            continue

        if fid not in answers:
            continue

        val = answers.get(fid)
        if required and (val is None or val == ""):
            errors.append(f"Missing required field: {fid}")
            continue

        if ftype == "text":
            if val is None or val == "":
                continue
            if not isinstance(val, str):
                errors.append(f"Field {fid} must be text")
        elif ftype == "number":
            if val is None or val == "":
                continue
            if not isinstance(val, (int, float)) or isinstance(val, bool):
                errors.append(f"Field {fid} must be a number")
        elif ftype == "select":
            if val is None or val == "":
                continue
            if not isinstance(val, str):
                errors.append(f"Field {fid} must be a string")
                continue
            options = field.get("options") if isinstance(field.get("options"), list) else []
            allowed = []
            for o in options:
                if isinstance(o, dict) and isinstance(o.get("value"), str):
                    allowed.append(o["value"])
            if allowed and val not in set(allowed):
                errors.append(f"Field {fid} must be one of {sorted(set(allowed))}")
        else:
            errors.append(f"Unsupported field type for {fid}: {ftype}")

    if errors:
        # Stable ordering
        raise ValidationError("; ".join(sorted(errors)))


def _fields_in_condition(cond: Any) -> set[str]:
    if not isinstance(cond, dict):
        return set()
    if "field" in cond and isinstance(cond["field"], str):
        return {cond["field"]}
    if "and" in cond:
        out: set[str] = set()
        for c in cond.get("and", []) or []:
            out |= _fields_in_condition(c)
        return out
    if "or" in cond:
        out: set[str] = set()
        for c in cond.get("or", []) or []:
            out |= _fields_in_condition(c)
        return out
    if "not" in cond:
        return _fields_in_condition(cond.get("not"))
    return set()


def _eval_condition(cond: Any, answers: dict[str, Any]) -> bool:
    if cond is None:
        return False
    if isinstance(cond, bool):
        return cond
    if not isinstance(cond, dict):
        return False

    if "and" in cond:
        return all(_eval_condition(c, answers) for c in (cond.get("and", []) or []))
    if "or" in cond:
        return any(_eval_condition(c, answers) for c in (cond.get("or", []) or []))
    if "not" in cond:
        return not _eval_condition(cond.get("not"), answers)

    field = cond.get("field")
    op = cond.get("op")
    expected = cond.get("value")
    if not isinstance(field, str) or not isinstance(op, str):
        return False

    actual = answers.get(field)
    if op == "exists":
        return field in answers and actual not in (None, "")
    if op == "==":
        return actual == expected
    if op == "!=":
        return actual != expected

    # Numeric comparisons only when both are numbers (and not bool)
    if isinstance(actual, (int, float)) and not isinstance(actual, bool) and isinstance(expected, (int, float)):
        if op == ">":
            return actual > expected
        if op == ">=":
            return actual >= expected
        if op == "<":
            return actual < expected
        if op == "<=":
            return actual <= expected

    return False


def _classification_order(config: dict[str, Any]) -> list[str]:
    """
    Returns a deterministic severity order for classifications, fully driven by config.

    Supported (optional) config shape:
      config["evaluation"]["classification"]["order"] = ["Cleared", "Watch", "Elevated"]

    If not provided, we derive an order deterministically from:
      - default classification
      - then-values in rules in appearance order
    """
    evaluation = config.get("evaluation", {}) if isinstance(config.get("evaluation"), dict) else {}
    classification_cfg = evaluation.get("classification", {}) if isinstance(evaluation.get("classification"), dict) else {}

    order = classification_cfg.get("order")
    if isinstance(order, list):
        out: list[str] = []
        for x in order:
            if isinstance(x, str) and x and x not in out:
                out.append(x)
        if out:
            return out

    default_classification = classification_cfg.get("default", "Cleared")
    out: list[str] = [default_classification] if isinstance(default_classification, str) and default_classification else []

    rules = classification_cfg.get("rules", []) or []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        then = rule.get("then")
        if isinstance(then, str) and then and then not in out:
            out.append(then)

    return out or ["Cleared"]


def _classification_rank(order: list[str], name: str) -> int:
    try:
        return order.index(name)
    except ValueError:
        return 0


@dataclass(frozen=True)
class EvaluationResult:
    classification: str
    tags: list[str]
    patterns: list[str]
    section_classifications: dict[str, str]
    domain_classifications: dict[str, str]
    indicators_by_domain: dict[str, list[str]]
    indicator_signals_by_domain: dict[str, dict[str, dict[str, int]]]
    cross_domain_flags: list[str]
    structural_considerations: dict[str, list[dict[str, Any]]]


def evaluate(
    config: dict[str, Any],
    answers: dict[str, Any],
    *,
    content_language: str = "en",
    default_language: str = "en",
) -> EvaluationResult:
    schema = _resolve_schema(config)
    evaluation = config.get("evaluation", {}) if isinstance(config.get("evaluation"), dict) else {}

    classification_cfg = evaluation.get("classification", {}) if isinstance(evaluation.get("classification"), dict) else {}
    default_classification = classification_cfg.get("default", "Cleared")
    rules = classification_cfg.get("rules", []) or []

    # Field->section mapping (for section-level aggregation)
    field_to_section: dict[str, str] = {}
    for section in schema.get("sections", []) or []:
        sid = section.get("id")
        if not isinstance(sid, str):
            continue
        for field in section.get("fields", []) or []:
            meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
            if meta.get("active") is False:
                continue
            fid = field.get("id")
            if isinstance(fid, str):
                field_to_section[fid] = sid

    order = _classification_order(config)
    section_classifications: dict[str, str] = {
        sid: (default_classification if isinstance(default_classification, str) and default_classification else order[0])
        for sid in set(field_to_section.values())
    }

    chosen = default_classification
    patterns: list[str] = []

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        cond = rule.get("if")
        then = rule.get("then")
        if not isinstance(then, str):
            continue
        if _eval_condition(cond, answers):
            chosen = then
            rid = rule.get("id")
            if isinstance(rid, str):
                patterns.append(rid)
            # Promote section classification based on fields referenced in this matched rule
            for fid in _fields_in_condition(cond):
                sid = field_to_section.get(fid)
                if not sid:
                    continue
                cur = section_classifications.get(sid, "Cleared")
                if _classification_rank(order, then) > _classification_rank(order, cur):
                    section_classifications[sid] = then

    tags: list[str] = []
    for tr in evaluation.get("tags", []) or []:
        if not isinstance(tr, dict):
            continue
        cond = tr.get("if")
        add = tr.get("add", []) or []
        if _eval_condition(cond, answers):
            for t in add:
                if isinstance(t, str):
                    tags.append(t)

    # Optional SRI deterministic indicator model.
    sri = evaluation.get("sri", {}) if isinstance(evaluation.get("sri"), dict) else {}
    sri_enabled = bool(sri.get("enabled"))
    domain_classifications = dict(section_classifications)
    indicators_by_domain: dict[str, list[str]] = {}
    indicator_signals_by_domain: dict[str, dict[str, dict[str, int]]] = {}
    cross_domain_flags: list[str] = []
    structural_considerations: dict[str, list[dict[str, Any]]] = {}

    if sri_enabled:
        sri_rules = sri.get("indicator_rules", []) if isinstance(sri.get("indicator_rules"), list) else []
        thresholds = sri.get("thresholds", {}) if isinstance(sri.get("thresholds"), dict) else {}
        watch = thresholds.get("watch", {}) if isinstance(thresholds.get("watch"), dict) else {}
        elevated = thresholds.get("elevated", {}) if isinstance(thresholds.get("elevated"), dict) else {}
        cross = thresholds.get("cross_domain", {}) if isinstance(thresholds.get("cross_domain"), dict) else {}

        watch_min_moderate = watch.get("min_moderate", 2)
        watch_min_high_complexity = watch.get("min_high_complexity", 1)
        elevated_min_moderate = elevated.get("min_moderate", 3)
        elevated_min_high_complexity = elevated.get("min_high_complexity", 2)

        if not isinstance(watch_min_moderate, int):
            watch_min_moderate = 2
        if not isinstance(watch_min_high_complexity, int):
            watch_min_high_complexity = 1
        if not isinstance(elevated_min_moderate, int):
            elevated_min_moderate = 3
        if not isinstance(elevated_min_high_complexity, int):
            elevated_min_high_complexity = 2

        counts: dict[str, dict[str, dict[str, int]]] = {
            sid: {} for sid in section_classifications.keys()
        }
        matched_fields_by_domain: dict[str, set[str]] = {sid: set() for sid in section_classifications.keys()}
        patterns_sri: list[str] = []
        tags_sri: list[str] = []

        for rule in sri_rules:
            if not isinstance(rule, dict):
                continue
            domain = rule.get("domain")
            indicator = rule.get("indicator")
            signal = rule.get("signal")
            cond = rule.get("if")
            if not isinstance(domain, str) or not domain:
                continue
            if not isinstance(indicator, str) or not indicator:
                continue
            if signal not in {"moderate", "high"}:
                continue
            if not _eval_condition(cond, answers):
                continue

            if domain not in counts:
                counts[domain] = {}
            if indicator not in counts[domain]:
                counts[domain][indicator] = {"moderate": 0, "high": 0}
            counts[domain][indicator][signal] += 1
            matched_fields_by_domain.setdefault(domain, set()).update(_fields_in_condition(cond))

            rid = rule.get("id")
            if isinstance(rid, str) and rid:
                patterns_sri.append(rid)
            tags_sri.append(f"indicator:{domain}:{indicator}")

        for domain, indicator_counts in counts.items():
            moderate_total = 0
            high_complexity_total = 0
            for indicator, by_signal in indicator_counts.items():
                moderate_total += by_signal.get("moderate", 0)
                if indicator == "structural_complexity_exposure":
                    high_complexity_total += by_signal.get("high", 0)

            domain_cls = "Cleared"
            if moderate_total >= elevated_min_moderate or high_complexity_total >= elevated_min_high_complexity:
                domain_cls = "Elevated"
            elif moderate_total >= watch_min_moderate or high_complexity_total >= watch_min_high_complexity:
                domain_cls = "Watch"

            domain_classifications[domain] = domain_cls
            indicators_by_domain[domain] = sorted(
                [k for k, v in indicator_counts.items() if v.get("moderate", 0) or v.get("high", 0)]
            )
            indicator_signals_by_domain[domain] = {
                k: {"moderate": v.get("moderate", 0), "high": v.get("high", 0)}
                for k, v in sorted(indicator_counts.items(), key=lambda kv: kv[0])
            }

        # Overall classification is promoted from domain classifications.
        chosen = max(
            domain_classifications.values() or [default_classification],
            key=lambda x: _classification_rank(order, x),
        )

        elevated_domains = sum(1 for c in domain_classifications.values() if c == "Elevated")
        min_elevated_domains = cross.get("min_elevated_domains", 3)
        if not isinstance(min_elevated_domains, int):
            min_elevated_domains = 3
        if elevated_domains >= min_elevated_domains:
            flag = cross.get("flag", "multi_domain_structural_exposure")
            if isinstance(flag, str) and flag:
                cross_domain_flags.append(flag)
            pattern_id = cross.get("pattern_id", "cross_domain_multi_exposure")
            if isinstance(pattern_id, str) and pattern_id:
                patterns_sri.append(pattern_id)

        patterns.extend(patterns_sri)
        tags.extend(tags_sri)
        section_classifications = dict(domain_classifications)

        # Deterministic structural consideration selection.
        considerations_cfg = sri.get("considerations", {}) if isinstance(sri.get("considerations"), dict) else {}
        by_question = (
            considerations_cfg.get("by_question")
            if isinstance(considerations_cfg.get("by_question"), dict)
            else {}
        )
        max_per_domain = considerations_cfg.get("max_per_domain", 2)
        max_total = considerations_cfg.get("max_total", 8)
        if not isinstance(max_per_domain, int) or max_per_domain < 1:
            max_per_domain = 2
        if not isinstance(max_total, int) or max_total < 1:
            max_total = 8

        output_cfg = config.get("output") if isinstance(config.get("output"), dict) else {}
        considerations_i18n = (
            output_cfg.get("considerations")
            if isinstance(output_cfg.get("considerations"), dict)
            else {}
        )
        considerations_i18n_by_question = (
            considerations_i18n.get("by_question")
            if isinstance(considerations_i18n.get("by_question"), dict)
            else {}
        )

        def _resolve_text(v: Any, *, question_id: str, level: str) -> str:
            override_q = (
                considerations_i18n_by_question.get(question_id)
                if isinstance(considerations_i18n_by_question.get(question_id), dict)
                else {}
            )
            override_text = override_q.get(level)
            if override_text is not None:
                if isinstance(override_text, dict):
                    # Language-safe override resolution: only use override copy when
                    # requested/default language is explicitly present. This prevents
                    # cross-language fallback (e.g., Spanish-only override leaking into English output).
                    direct = override_text.get(content_language)
                    fallback = override_text.get(default_language)
                    resolved = ""
                    if isinstance(direct, str) and direct:
                        resolved = direct
                    elif isinstance(fallback, str) and fallback:
                        resolved = fallback
                else:
                    resolved = resolve_i18n_text(
                        override_text,
                        lang=content_language,
                        default_lang=default_language,
                    )
                if resolved:
                    return resolved
            return resolve_i18n_text(
                v,
                lang=content_language,
                default_lang=default_language,
            )

        selected_total = 0
        for section in schema.get("sections", []) or []:
            domain = section.get("id")
            if not isinstance(domain, str) or domain not in domain_classifications:
                continue
            domain_cls = domain_classifications[domain]
            if domain_cls not in {"Watch", "Elevated"}:
                continue
            triggered_fields = matched_fields_by_domain.get(domain, set())
            if not triggered_fields:
                continue

            domain_candidates: list[tuple[int, str, str]] = []
            for field in section.get("fields", []) or []:
                meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
                if meta.get("active") is False:
                    continue
                fid = field.get("id")
                if not isinstance(fid, str) or fid not in triggered_fields:
                    continue
                qnum = 10**6
                meta = field.get("meta") if isinstance(field.get("meta"), dict) else {}
                if isinstance(meta.get("sri_question_number"), int):
                    qnum = meta["sri_question_number"]
                qcfg = by_question.get(fid) if isinstance(by_question.get(fid), dict) else {}
                key = "elevated" if domain_cls == "Elevated" else "watch"
                text = _resolve_text(qcfg.get(key), question_id=fid, level=key)
                if not text and domain_cls == "Elevated":
                    text = _resolve_text(qcfg.get("watch"), question_id=fid, level="watch")
                    key = "watch"
                if not text:
                    continue
                domain_candidates.append((qnum, fid, text))

            domain_candidates.sort(key=lambda x: (x[0], x[1]))
            for qnum, fid, text in domain_candidates:
                if selected_total >= max_total:
                    break
                if len(structural_considerations.get(domain, [])) >= max_per_domain:
                    break
                structural_considerations.setdefault(domain, []).append(
                    {
                        "question_id": fid,
                        "question_number": qnum,
                        "classification_level": domain_cls,
                        "text": text,
                    }
                )
                selected_total += 1

    # Stable + unique
    tags = sorted(set(tags))
    patterns = sorted(set(patterns))
    cross_domain_flags = sorted(set(cross_domain_flags))

    return EvaluationResult(
        classification=chosen,
        tags=tags,
        patterns=patterns,
        section_classifications=section_classifications,
        domain_classifications=domain_classifications,
        indicators_by_domain=indicators_by_domain,
        indicator_signals_by_domain=indicator_signals_by_domain,
        cross_domain_flags=cross_domain_flags,
        structural_considerations=structural_considerations,
    )

