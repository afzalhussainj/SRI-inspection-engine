"""
Deterministic identifiers for the seeded SRI baseline template (Milestone 1).

Used by the data migration, admin safety checks, and tests.
"""

from __future__ import annotations

import uuid

# Fixed UUIDs so migrations and documentation stay stable across environments.
SRI_BASELINE_INSTANCE_ID = uuid.UUID("f0000001-0000-4000-8000-000000000001")
SRI_BASELINE_CONFIG_VERSION_ID = uuid.UUID("f0000001-0000-4000-8000-000000000002")

SRI_BASELINE_INSTANCE_NAME = "SRI Baseline (template)"
