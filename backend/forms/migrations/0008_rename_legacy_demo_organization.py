# Rename legacy demo organization id and scrub "showcase" wording from branding / instances.

from __future__ import annotations

from django.db import migrations

OLD_DEMO_ORGANIZATION_ID = "showcase-demo-org"
NEW_DEMO_ORGANIZATION_ID = "regional-transition-network"
LEGACY_DEMO_INSTANCE_NAME = "Showcase — Parent & aggregate demo"
NEW_DEMO_INSTANCE_NAME = "Regional transitions — parent and aggregate pilot"


def forwards(apps, schema_editor):
    OrganizationBranding = apps.get_model("forms", "OrganizationBranding")
    InspectionInstance = apps.get_model("forms", "InspectionInstance")

    OrganizationBranding.objects.filter(organization_id=OLD_DEMO_ORGANIZATION_ID).update(
        organization_id=NEW_DEMO_ORGANIZATION_ID
    )
    InspectionInstance.objects.filter(organization_id=OLD_DEMO_ORGANIZATION_ID).update(
        organization_id=NEW_DEMO_ORGANIZATION_ID
    )

    for row in OrganizationBranding.objects.all().iterator():
        if "showcase" in (row.hospital_program_name or "").lower():
            OrganizationBranding.objects.filter(pk=row.pk).update(hospital_program_name="SRI Program")

    InspectionInstance.objects.filter(name=LEGACY_DEMO_INSTANCE_NAME).update(name=NEW_DEMO_INSTANCE_NAME)
    InspectionInstance.objects.filter(name__icontains="showcase").update(name=NEW_DEMO_INSTANCE_NAME)


def backwards(apps, schema_editor):
    OrganizationBranding = apps.get_model("forms", "OrganizationBranding")
    InspectionInstance = apps.get_model("forms", "InspectionInstance")

    OrganizationBranding.objects.filter(organization_id=NEW_DEMO_ORGANIZATION_ID).update(
        organization_id=OLD_DEMO_ORGANIZATION_ID
    )
    InspectionInstance.objects.filter(organization_id=NEW_DEMO_ORGANIZATION_ID).update(
        organization_id=OLD_DEMO_ORGANIZATION_ID
    )


class Migration(migrations.Migration):
    dependencies = [
        ("forms", "0007_refresh_canonical_output_questionnaire"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
