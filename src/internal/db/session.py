import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from src.internal.settings import settings
from src.internal.db.models import Base

logger = logging.getLogger(__name__)


def get_engine():
    if settings.postgres_url:
        try:
            engine = create_engine(settings.postgres_url, pool_pre_ping=True)
            with engine.connect() as conn:
                conn.execute(Base.metadata.tables["dim_geo"].select().limit(1))
            logger.info("Connected to PostgreSQL")
            return engine
        except Exception as e:
            logger.warning("PostgreSQL unavailable (%s), falling back to SQLite", e)

    local_path = settings.sqlite_local_path
    engine = create_engine(f"sqlite:///{local_path}")
    logger.info("Using local SQLite at %s", local_path)
    return engine


def init_db(engine=None):
    if engine is None:
        engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Database tables created / verified")
    return engine


def get_session(engine=None):
    if engine is None:
        engine = get_engine()
    return Session(engine)
