# Refresh config["output"] from default_base_config() so questionnaire.option_values
# includes full en/es labels for every select option (see models._build_questionnaire_option_values).

from __future__ import annotations

import copy
import hashlib
import json
import uuid

from django.db import migrations


BASELINE_CV_ID = uuid.UUID("f0000001-0000-4000-8000-000000000002")
DEMO_ORGANIZATION_IDS = ("showcase-demo-org", "regional-transition-network")


def _config_hash(config: dict) -> str:
    payload = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def refresh_output_forwards(apps, schema_editor):
    from forms.models import default_base_config

    InspectionConfigVersion = apps.get_model("forms", "InspectionConfigVersion")
    InspectionInstance = apps.get_model("forms", "InspectionInstance")

    canonical_output = copy.deepcopy(default_base_config().get("output"))
    if not isinstance(canonical_output, dict):
        return

    def patch_version(pk) -> None:
        row = InspectionConfigVersion.objects.filter(pk=pk).first()
        if not row:
            return
        cfg = copy.deepcopy(row.config)
        if not isinstance(cfg, dict):
            return
        cfg["output"] = copy.deepcopy(canonical_output)
        new_hash = _config_hash(cfg)
        InspectionConfigVersion.objects.filter(pk=pk).update(config=cfg, config_sha256=new_hash)

    patch_version(BASELINE_CV_ID)

    for org_id in DEMO_ORGANIZATION_IDS:
        for inst in InspectionInstance.objects.filter(organization_id=org_id):
            for cv in InspectionConfigVersion.objects.filter(inspection_instance_id=inst.pk):
                patch_version(cv.pk)


def refresh_output_backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("forms", "0006_repair_bilingual_config_output"),
    ]

    operations = [
        migrations.RunPython(refresh_output_forwards, refresh_output_backwards),
    ]
