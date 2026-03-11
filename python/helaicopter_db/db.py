from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .settings import OLAP_ARTIFACT, OLTP_ARTIFACT


def create_oltp_engine() -> Engine:
    return create_engine(
        OLTP_ARTIFACT.sqlalchemy_url,
        future=True,
        connect_args={"check_same_thread": False},
    )


def create_olap_engine() -> Engine:
    return create_engine(
        OLAP_ARTIFACT.sqlalchemy_url,
        future=True,
    )


def create_oltp_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=create_oltp_engine(), autoflush=False, future=True)


def create_olap_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=create_olap_engine(), autoflush=False, future=True)
