"""Migrations require the guarded operator connection; no standalone URL fallback."""

from alembic import context

connection = context.config.attributes.get("connection")
if connection is None:
    raise RuntimeError("Migration requires explicit guarded initialization connection")
context.configure(connection=connection, transactional_ddl=True)
with context.begin_transaction():
    context.run_migrations()
