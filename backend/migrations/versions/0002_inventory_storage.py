"""Add immutable inventory envelopes/documents and an explicitly selected index profile."""

import json
from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The guarded operator probes capability before beginning its write transaction.
    config = op.get_context().config
    if config is None:
        raise RuntimeError("INVENTORY_CAPABILITY_OBSERVATION_REQUIRED")
    fts5 = config.attributes.get("inventory_fts5")
    if type(fts5) is not bool:
        raise RuntimeError("INVENTORY_CAPABILITY_OBSERVATION_REQUIRED")
    profile = json.loads(
        (Path(__file__).resolve().parents[1] / "schema-0002.json").read_text(encoding="utf-8")
    )
    for _, _, sql in profile["common"]:
        op.execute(sql)
    mode = "fts5" if fts5 else "bounded_lexical"
    if fts5:
        # SQLite creates the five declared shadow tables itself.
        op.execute(profile["fts5"][0][2])
    op.get_bind().exec_driver_sql(
        "INSERT INTO inventory_storage_profile (id,mode) VALUES (1,?)", (mode,)
    )
    op.execute("UPDATE store_metadata SET schema_version='0002' WHERE id=1")


def downgrade() -> None:
    raise RuntimeError("Destructive downgrade unsupported; use the reviewed recovery procedure")
