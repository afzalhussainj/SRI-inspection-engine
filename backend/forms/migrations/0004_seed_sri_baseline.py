# Generated manually for Milestone 1 Phase 1.4 — deterministic SRI baseline seed.

from django.db import migrations


def seed_sri_baseline(apps, schema_editor):
    # Real models so publish validation, hashing, and full_clean run correctly.
    from forms import sri_baseline as baseline
    from forms.models import InspectionConfigVersion, InspectionInstance, default_base_config

    if InspectionInstance.objects.filter(pk=baseline.SRI_BASELINE_INSTANCE_ID).exists():
        return

    inst = InspectionInstance.objects.create(
        id=baseline.SRI_BASELINE_INSTANCE_ID,
        kind=InspectionInstance.KIND_TEMPLATE,
        name=baseline.SRI_BASELINE_INSTANCE_NAME,
        organization_id="",
    )
    cfg = InspectionConfigVersion(
        id=baseline.SRI_BASELINE_CONFIG_VERSION_ID,
        inspection_instance=inst,
        config=default_base_config(),
        status=InspectionConfigVersion.STATUS_PUBLISHED,
    )
    cfg.save()


def unseed_sri_baseline(apps, schema_editor):
    from forms import sri_baseline as baseline
    from forms.models import InspectionInstance, RecipientLink

    if RecipientLink.objects.filter(inspection_instance_id=baseline.SRI_BASELINE_INSTANCE_ID).exists():
        return
    InspectionInstance.objects.filter(pk=baseline.SRI_BASELINE_INSTANCE_ID).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("forms", "0003_inspectioninstance_base_template_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_sri_baseline, unseed_sri_baseline),
    ]
