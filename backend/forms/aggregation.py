from __future__ import annotations

from collections import Counter
from typing import Any

from .models import AggregatedReport, InspectionInstance, Submission


def aggregate_instance(instance: InspectionInstance) -> dict[str, Any]:
    """
    QuietRisk MVP aggregation:
      - counts by section
      - counts by classification (Cleared/Watch/Elevated)
      - counts by indicator tags
      - top repeated risk patterns
    """
    submissions = (
        Submission.objects.select_related("recipient_link")
        .filter(recipient_link__inspection_instance=instance)
        .all()
    )

    by_classification = Counter()
    by_section: dict[str, Counter] = {}
    tag_counts = Counter()
    pattern_counts = Counter()
    cross_domain_flag_counts = Counter()
    indicator_counts_by_domain: dict[str, Counter] = {}
    indicator_signal_totals_by_domain: dict[str, dict[str, int]] = {}

    for sub in submissions:
        outputs = sub.outputs or {}
        overall = outputs.get("classification") or "Cleared"
        by_classification[overall] += 1

        sec_cls = outputs.get("section_classifications") or {}
        if isinstance(sec_cls, dict):
            for sid, cls in sec_cls.items():
                if sid not in by_section:
                    by_section[sid] = Counter()
                by_section[sid][cls or "Cleared"] += 1

        tags = outputs.get("tags") or []
        if isinstance(tags, list):
            for t in tags:
                if isinstance(t, str):
                    tag_counts[t] += 1

        patterns = outputs.get("patterns") or []
        if isinstance(patterns, list):
            for p in patterns:
                if isinstance(p, str):
                    pattern_counts[p] += 1

        cross_flags = outputs.get("cross_domain_flags") or []
        if isinstance(cross_flags, list):
            for flag in cross_flags:
                if isinstance(flag, str):
                    cross_domain_flag_counts[flag] += 1

        indicators_by_domain = outputs.get("indicators_by_domain") or {}
        if isinstance(indicators_by_domain, dict):
            for domain_id, indicators in indicators_by_domain.items():
                if not isinstance(domain_id, str) or not isinstance(indicators, list):
                    continue
                if domain_id not in indicator_counts_by_domain:
                    indicator_counts_by_domain[domain_id] = Counter()
                for indicator in indicators:
                    if isinstance(indicator, str):
                        indicator_counts_by_domain[domain_id][indicator] += 1

        indicator_signals = outputs.get("indicator_signals_by_domain") or {}
        if isinstance(indicator_signals, dict):
            for domain_id, by_indicator in indicator_signals.items():
                if not isinstance(domain_id, str) or not isinstance(by_indicator, dict):
                    continue
                bucket = indicator_signal_totals_by_domain.setdefault(
                    domain_id,
                    {"moderate": 0, "high": 0},
                )
                for _indicator, signal_counts in by_indicator.items():
                    if not isinstance(signal_counts, dict):
                        continue
                    bucket["moderate"] += int(signal_counts.get("moderate", 0) or 0)
                    bucket["high"] += int(signal_counts.get("high", 0) or 0)

    # Deterministic ordering: sort by (-count, key)
    top_patterns = sorted(pattern_counts.items(), key=lambda kv: (-kv[1], kv[0]))[:10]
    top_patterns = [{"pattern": k, "count": v} for k, v in top_patterns]

    indicator_counts_by_domain_sorted: dict[str, dict[str, int]] = {}
    for domain_id, counter in sorted(indicator_counts_by_domain.items(), key=lambda kv: kv[0]):
        indicator_counts_by_domain_sorted[domain_id] = dict(
            sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        )

    indicator_signal_totals_by_domain_sorted = {
        domain_id: {
            "moderate": int(values.get("moderate", 0) or 0),
            "high": int(values.get("high", 0) or 0),
        }
        for domain_id, values in sorted(indicator_signal_totals_by_domain.items(), key=lambda kv: kv[0])
    }

    return {
        "total_submissions": submissions.count(),
        "by_classification": {
            "Cleared": by_classification.get("Cleared", 0),
            "Watch": by_classification.get("Watch", 0),
            "Elevated": by_classification.get("Elevated", 0),
        },
        "by_section": {
            sid: {
                "Cleared": c.get("Cleared", 0),
                "Watch": c.get("Watch", 0),
                "Elevated": c.get("Elevated", 0),
            }
            for sid, c in sorted(by_section.items(), key=lambda kv: kv[0])
        },
        "tag_counts": dict(sorted(tag_counts.items(), key=lambda kv: (-kv[1], kv[0]))),
        "top_patterns": top_patterns,
        # SRI-compatible aggregate buckets (deterministic ordering).
        "cross_domain_flag_counts": dict(
            sorted(cross_domain_flag_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        ),
        "indicator_counts_by_domain": indicator_counts_by_domain_sorted,
        "indicator_signal_totals_by_domain": indicator_signal_totals_by_domain_sorted,
    }


def run_aggregation(instance: InspectionInstance) -> AggregatedReport:
    # Use the latest published config for schema ordering/titles.
    cfg = (
        instance.config_versions.filter(status="published").order_by("-published_at", "-created_at").first()
        or instance.config_versions.order_by("-created_at").first()
    )
    config = cfg.config if cfg and isinstance(cfg.config, dict) else {}

    counts = aggregate_instance(instance)

    report, _ = AggregatedReport.objects.get_or_create(inspection_instance=instance)
    report.counts = counts
    report.save()
    return report

