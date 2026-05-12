# Repair output.* to match current default_base_config() (en + es) for baseline and pilot demo orgs.
# Published rows cannot be updated through Model.save() due to immutability checks; we use .update().

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


def repair_output_forwards(apps, schema_editor):
    from forms.models import default_base_config

    InspectionConfigVersion = apps.get_model("forms", "InspectionConfigVersion")
    InspectionInstance = apps.get_model("forms", "InspectionInstance")

    full = default_base_config()
    canonical_output = copy.deepcopy(full.get("output"))
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


def repair_output_backwards(apps, schema_editor):
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("forms", "0005_organizationbranding"),
    ]

    operations = [
        migrations.RunPython(repair_output_forwards, repair_output_backwards),
    ]
