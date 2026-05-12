## SRI baseline template (Milestone 1)

### What gets created

On `migrate`, a deterministic **SRI baseline** row is seeded:

| Entity | Stable UUID | Notes |
|--------|-------------|--------|
| `InspectionInstance` | `f0000001-0000-4000-8000-000000000001` | `kind=template`, name **SRI Baseline (template)** |
| `InspectionConfigVersion` | `f0000001-0000-4000-8000-000000000002` | `status=published`, config = current `default_base_config()` (full SRI schema + rules) |

Identifiers live in `backend/forms/sri_baseline.py` for migrations, admin guards, and tests.

### Using it in admin

1. Open **Inspection instances** and find **SRI Baseline (template)** (or search by the UUID above).
2. The linked config version is already **published** — you can use **Create recipient link(s) for selected config versions** on that version, or create links from the instance inline as usual.
3. To run a **campaign**: use **Create campaign(s) from selected template(s)** with the baseline selected. Set `organization_id` on the new campaign if you need QuietRisk / aggregation behavior.
4. To change questions or rules: add a **new draft** config version under the same instance (or clone the template), edit JSON, **publish** the new version, then create **new** recipient links pinned to that published version. Existing submissions stay tied to the config version they used.

### Safety

- Published configs remain **immutable** (hash + model validation).
- The seeded baseline **instance** and **published config version** cannot be deleted from admin (prevents accidental removal of the reference template).
- Reverse migration removes the baseline only if no `RecipientLink` exists for that instance.

### Technical note

The seed migration uses the real Django models so `full_clean()`, publish validation, and `config_sha256` behave the same as records created by hand in admin.
