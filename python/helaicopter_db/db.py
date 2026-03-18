from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from helaicopter_api.server.config import Settings

from .settings import get_database_settings


def create_oltp_engine(settings: Settings | None = None) -> Engine:
    database_settings = get_database_settings(settings)
    return create_engine(
        database_settings.sqlite.sqlalchemy_url,
        future=True,
        connect_args={"check_same_thread": False},
    )


def create_olap_engine(settings: Settings | None = None) -> Engine:
    database_settings = get_database_settings(settings)
    return create_engine(
        database_settings.legacy_duckdb.sqlalchemy_url,
        future=True,
    )


def create_oltp_sessionmaker(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=create_oltp_engine(settings), autoflush=False, future=True)


def create_olap_sessionmaker(settings: Settings | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=create_olap_engine(settings), autoflush=False, future=True)
