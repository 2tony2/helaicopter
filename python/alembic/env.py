from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from alembic.ddl.impl import DefaultImpl
from sqlalchemy import engine_from_config, pool

from helaicopter_db.models import OlapBase, OltpBase
from helaicopter_db.settings import ensure_runtime_dirs, get_database_settings


class AlembicDuckDBImpl(DefaultImpl):
    __dialect__ = "duckdb"


config = context.config
database_settings = get_database_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

ensure_runtime_dirs()

target_name = context.get_x_argument(as_dictionary=True).get("target", "oltp")
target_metadata = OltpBase.metadata if target_name == "oltp" else OlapBase.metadata
target_url = (
    database_settings.sqlite.sqlalchemy_url
    if target_name == "oltp"
    else database_settings.legacy_duckdb.sqlalchemy_url
)
config.set_main_option("sqlalchemy.url", target_url)


def run_migrations_offline() -> None:
    context.configure(
        url=target_url,
        target_metadata=target_metadata,
        literal_binds=True,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
